"""Read and validate dual-channel B210 sc16 captures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class CaptureData:
    samples: np.ndarray
    metadata: dict
    warnings: list[str]


def read_sc16(
    path: Path,
    *,
    channel_count: int = 2,
    start_sample_per_channel: int = 0,
    max_samples_per_channel: int | None = None,
) -> np.ndarray:
    start_sample_per_channel = max(0, int(start_sample_per_channel))
    count = (
        -1
        if max_samples_per_channel is None
        else max(0, int(max_samples_per_channel)) * channel_count * 2
    )
    raw = np.fromfile(
        path,
        dtype="<i2",
        count=count,
        offset=start_sample_per_channel * channel_count * 2 * np.dtype("<i2").itemsize,
    )
    item_count = channel_count * 2
    if raw.size % item_count != 0:
        raise ValueError(f"{path} length is not divisible by {item_count} int16 values")
    framed = raw.reshape(-1, channel_count, 2)
    iq = framed[:, :, 0].astype(np.float32) + 1j * framed[:, :, 1].astype(np.float32)
    return (iq / 32768.0).T.astype(np.complex64)


def load_capture(
    path: Path,
    metadata_path: Path | None = None,
    *,
    start_time_s: float = 0.0,
    max_duration_s: float | None = None,
) -> CaptureData:
    metadata_path = metadata_path or path.with_suffix(path.suffix + ".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    channel_count = int(metadata.get("channel_count", 2))
    actual = metadata.get("actual", {}) if isinstance(metadata, dict) else {}
    requested = metadata.get("requested", {}) if isinstance(metadata, dict) else {}
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 750_000.0)))
    start_sample = round(max(0.0, float(start_time_s)) * rate)
    max_samples = None
    if max_duration_s is not None:
        max_samples = round(max(0.0, float(max_duration_s)) * rate)
    samples = read_sc16(
        path,
        channel_count=channel_count,
        start_sample_per_channel=start_sample,
        max_samples_per_channel=max_samples,
    )
    warnings: list[str] = []
    if samples.shape[0] != 2:
        warnings.append(f"expected 2 RX channels, got {samples.shape[0]}")
    expected = metadata.get("samples_per_channel")
    if (
        float(start_time_s) == 0.0
        and max_duration_s is None
        and expected is not None
        and int(expected) != samples.shape[1]
    ):
        warnings.append(f"samples_per_channel metadata={expected} actual={samples.shape[1]}")
    if float(start_time_s) != 0.0 or max_duration_s is not None:
        metadata = dict(metadata)
        metadata["analysis_slice"] = {
            "kind": "time_range",
            "start_time_s": float(start_time_s),
            "requested_duration_s": (
                None if max_duration_s is None else float(max_duration_s)
            ),
            "samples_per_channel": int(samples.shape[1]),
        }
    if int(metadata.get("overflow_count", 0)) != 0:
        warnings.append(f"overflow_count={metadata.get('overflow_count')}")
    if int(metadata.get("timeout_count", 0)) != 0:
        warnings.append(f"timeout_count={metadata.get('timeout_count')}")
    clipping = metadata.get("clipping_count", [0, 0])
    if any(int(x) != 0 for x in clipping):
        warnings.append(f"clipping_count={clipping}")
    return CaptureData(samples=samples, metadata=metadata, warnings=warnings)


def dc_remove_and_whiten(samples: np.ndarray, *, noise_samples: int) -> tuple[np.ndarray, np.ndarray, float, dict]:
    x = np.asarray(samples, dtype=np.complex128)
    n0 = max(128, min(int(noise_samples), x.shape[1]))
    noise = x[:, :n0]
    dc = np.mean(noise, axis=1, keepdims=True)
    centered = x - dc
    noise_centered = centered[:, :n0]
    cov = (noise_centered @ noise_centered.conj().T) / max(1, noise_centered.shape[1])
    cov += np.eye(cov.shape[0], dtype=np.complex128) * max(float(np.trace(cov).real), 1e-18) * 1e-6
    vals, vecs = np.linalg.eigh(cov)
    floor = max(float(np.max(vals).real), 1e-18) * 1e-6
    vals = np.maximum(vals.real, floor)
    whitener = (vecs @ np.diag(1.0 / np.sqrt(vals)) @ vecs.conj().T).astype(np.complex128)
    white = (whitener @ centered).astype(np.complex64)
    whitened_noise = whitener @ noise_centered
    sigma2_fft = float(np.mean(np.abs(whitened_noise) ** 2))
    diag = {
        "dc": [[float(np.real(v)), float(np.imag(v))] for v in dc[:, 0]],
        "noise_covariance": [
            [[float(np.real(v)), float(np.imag(v))] for v in row]
            for row in cov
        ],
        "whitener": [
            [[float(np.real(v)), float(np.imag(v))] for v in row]
            for row in whitener
        ],
        "noise_sigma2_time": sigma2_fft,
    }
    return white, whitener, sigma2_fft, diag


def adc_clipping_statistics(samples: np.ndarray, *, chunk_samples: int = 1_000_000) -> dict:
    """Count full-scale and near-full-scale complex samples per RX channel."""

    x = np.asarray(samples)
    clipped = np.zeros(x.shape[0], dtype=np.int64)
    near_clipped = np.zeros(x.shape[0], dtype=np.int64)
    peak = np.zeros(x.shape[0], dtype=np.float64)
    full_scale = 32760.0 / 32768.0
    near_full_scale = 30000.0 / 32768.0
    for begin in range(0, x.shape[1], max(1, int(chunk_samples))):
        block = x[:, begin : begin + max(1, int(chunk_samples))]
        real_abs = np.abs(block.real)
        imag_abs = np.abs(block.imag)
        clipped += np.count_nonzero((real_abs >= full_scale) | (imag_abs >= full_scale), axis=1)
        near_clipped += np.count_nonzero(
            (real_abs >= near_full_scale) | (imag_abs >= near_full_scale), axis=1
        )
        peak = np.maximum(peak, np.maximum(np.max(real_abs, axis=1), np.max(imag_abs, axis=1)))
    return {
        "peak_fraction_full_scale": [float(v) for v in peak],
        "near_full_scale_count": [int(v) for v in near_clipped],
        "clipped_count": [int(v) for v in clipped],
        "clipped_fraction": [float(v) / max(1, x.shape[1]) for v in clipped],
    }
