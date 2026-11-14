#!/usr/bin/env python3
"""End-to-end AWGN sweep: add noise, rerun frontend detection, decode methods.

Unlike ``evaluate_awgn_prr_sweep.py``, this script does not reuse certified
fine-sync targets. For every noise point it creates a noisy sc16 capture and
reruns ``sp_node01_receiver.py`` end to end. It reports detector recall and
decoded-packet-rate diagnostics only: it intentionally emits no PRR, because
an end-to-end frontend rerun does not preserve the shared Fig.9/10 D set.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RECEIVER = ROOT / "real_collision_experiment" / "node01_sp_receiver" / "sp_node01_receiver.py"
METHODS = ("sp_sync_refine", "sp_repair", "mrc", "mrc_cic", "pcube", "maloragw")
METHOD_LABELS = {
    "sp_sync_refine": "sp+sync-refine",
    "sp_repair": "sp+repair",
    "mrc": "mrc",
    "mrc_cic": "mrc_cic",
    "pcube": "pcube",
    "maloragw": "maloragw",
}


def _complex_matrix(values: list[list[list[float]]]) -> np.ndarray:
    return np.asarray(
        [[complex(float(value[0]), float(value[1])) for value in row] for row in values],
        dtype=np.complex128,
    )


def _serializable_complex_matrix(matrix: np.ndarray) -> list[list[list[float]]]:
    return [
        [[float(np.real(value)), float(np.imag(value))] for value in row]
        for row in np.asarray(matrix)
    ]


def _resolve(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _db_tag(value: float) -> str:
    text = f"{value:+.1f}".replace("+", "p").replace("-", "m").replace(".", "p")
    return text + "db"


def _noise_basis(covariance: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(np.asarray(covariance, dtype=np.complex128))
    floor = max(float(np.max(values).real), 1e-18) * 1e-9
    return vectors @ np.diag(np.sqrt(np.maximum(values.real, floor)))


def _count_clipping(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    real_abs = np.abs(samples.real)
    imag_abs = np.abs(samples.imag)
    clipped = np.count_nonzero((real_abs >= 1.0) | (imag_abs >= 1.0), axis=1)
    near = np.count_nonzero((real_abs >= 30000.0 / 32768.0) | (imag_abs >= 30000.0 / 32768.0), axis=1)
    peak = np.maximum(np.max(real_abs, axis=1), np.max(imag_abs, axis=1))
    return clipped.astype(np.int64), near.astype(np.int64), peak.astype(np.float64)


def write_noisy_sc16(
    *,
    source_iq: Path,
    source_metadata: Path,
    out_iq: Path,
    out_metadata: Path,
    covariance: np.ndarray,
    noise_rise_db: float,
    seed: int,
    chunk_samples: int,
) -> dict:
    metadata = json.loads(source_metadata.read_text(encoding="utf-8")) if source_metadata.exists() else {}
    channel_count = int(metadata.get("channel_count", 2))
    item_count = channel_count * 2
    total_multiplier = 10.0 ** (float(noise_rise_db) / 10.0)
    added_multiplier = max(0.0, total_multiplier - 1.0)
    basis = _noise_basis(covariance)
    if basis.shape != (channel_count, channel_count):
        raise ValueError(
            f"noise covariance shape {basis.shape} does not match channel_count={channel_count}"
        )
    rng = np.random.default_rng(int(seed))
    clipped_total = np.zeros(channel_count, dtype=np.int64)
    near_total = np.zeros(channel_count, dtype=np.int64)
    peak_total = np.zeros(channel_count, dtype=np.float64)
    sample_count = 0

    out_iq.parent.mkdir(parents=True, exist_ok=True)
    with source_iq.open("rb") as input_file, out_iq.open("wb") as output_file:
        while True:
            raw = np.fromfile(
                input_file,
                dtype="<i2",
                count=max(1, int(chunk_samples)) * item_count,
            )
            if raw.size == 0:
                break
            if raw.size % item_count != 0:
                raise ValueError(f"{source_iq} has a partial trailing sc16 frame")
            frames = raw.reshape(-1, channel_count, 2)
            samples = (
                frames[:, :, 0].astype(np.float32)
                + 1j * frames[:, :, 1].astype(np.float32)
            ).T.astype(np.complex64) / np.float32(32768.0)
            if added_multiplier > 0.0:
                standard = (
                    rng.standard_normal((channel_count, samples.shape[1]))
                    + 1j * rng.standard_normal((channel_count, samples.shape[1]))
                ) / math.sqrt(2.0)
                samples = samples + (
                    math.sqrt(added_multiplier) * (basis @ standard)
                ).astype(np.complex64)
            clipped, near, peak = _count_clipping(samples)
            clipped_total += clipped
            near_total += near
            peak_total = np.maximum(peak_total, peak)
            quantized = np.empty((samples.shape[1], channel_count, 2), dtype="<i2")
            quantized[:, :, 0] = np.rint(
                np.clip(samples.real.T * 32768.0, -32768.0, 32767.0)
            ).astype("<i2")
            quantized[:, :, 1] = np.rint(
                np.clip(samples.imag.T * 32768.0, -32768.0, 32767.0)
            ).astype("<i2")
            quantized.tofile(output_file)
            sample_count += int(samples.shape[1])

    noisy_metadata = dict(metadata)
    noisy_metadata["samples_per_channel"] = int(sample_count)
    noisy_metadata["channel_count"] = int(channel_count)
    noisy_metadata["clipping_count"] = [int(value) for value in clipped_total]
    noisy_metadata["near_full_scale_count"] = [int(value) for value in near_total]
    noisy_metadata["awgn"] = {
        "definition": (
            "Additional complex Gaussian noise is white over time and has the "
            "measured two-channel receiver-noise covariance."
        ),
        "source_iq": str(source_iq),
        "source_metadata": str(source_metadata),
        "noise_floor_rise_db": float(noise_rise_db),
        "total_noise_variance_multiplier": float(total_multiplier),
        "added_noise_variance_multiplier": float(added_multiplier),
        "seed": int(seed),
        "noise_covariance": _serializable_complex_matrix(covariance),
        "peak_fraction_full_scale_after_noise": [float(value) for value in peak_total],
    }
    out_metadata.write_text(
        json.dumps(noisy_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "samples_per_channel": int(sample_count),
        "clipping_count": [int(value) for value in clipped_total],
        "near_full_scale_count": [int(value) for value in near_total],
        "peak_fraction_full_scale": [float(value) for value in peak_total],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--noise-rise-db",
        type=float,
        nargs="+",
        default=[0.0, 30.0, 35.0, 40.0, 45.0, 50.0],
        help="Total receiver-noise-floor increase relative to the measured capture noise.",
    )
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--chunk-samples", type=int, default=1_000_000)
    parser.add_argument(
        "--keep-noisy-iq",
        action="store_true",
        help="Keep generated noisy sc16 files next to the output report.",
    )
    parser.add_argument(
        "--quiet-receiver",
        action="store_true",
        help="Pass --quiet to sp_node01_receiver.py.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Override receiver frontend threshold; default copies source report.",
    )
    parser.add_argument(
        "--energy-min-ratio",
        type=float,
        default=None,
        help="Override receiver energy prefilter ratio; default copies source report.",
    )
    parser.add_argument(
        "--energy-top-windows",
        type=int,
        default=None,
        help="Override receiver max energy windows; default copies source report.",
    )
    parser.add_argument(
        "--disable-energy-prefilter",
        action="store_true",
        help="Force the receiver to scan the full capture.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Override receiver max candidates; default copies source report.",
    )
    parser.add_argument(
        "--frontend-candidates-per-window",
        type=int,
        default=None,
        help="Override receiver candidates per energy window; default copies source report.",
    )
    return parser


def _append_option(command: list[str], name: str, value) -> None:
    if value is not None:
        command.extend([name, str(value)])


def _receiver_command(
    *,
    source_report: dict,
    iq: Path,
    metadata: Path,
    manifest: Path | None,
    out: Path,
    args: argparse.Namespace,
) -> list[str]:
    frontend = source_report.get("frontend", {}) if isinstance(source_report, dict) else {}
    decoder = source_report.get("decoder", {}) if isinstance(source_report, dict) else {}
    command = [
        sys.executable,
        str(RECEIVER),
        "--iq",
        str(iq),
        "--metadata",
        str(metadata),
        "--out",
        str(out),
    ]
    if manifest is not None:
        command.extend(["--manifest", str(manifest)])
    run_id = source_report.get("run_id")
    if run_id is not None:
        command.extend(["--run-id", f"0x{int(run_id):08X}"])
    for node_id in source_report.get("active_nodes", []):
        command.extend(["--active-node", str(int(node_id))])

    threshold = args.threshold if args.threshold is not None else frontend.get("threshold")
    energy_min_ratio = (
        args.energy_min_ratio
        if args.energy_min_ratio is not None
        else (frontend.get("energy_prefilter", {}) or {}).get("min_ratio")
    )
    max_candidates = (
        args.max_candidates if args.max_candidates is not None else frontend.get("max_candidates")
    )
    candidates_per_window = (
        args.frontend_candidates_per_window
        if args.frontend_candidates_per_window is not None
        else frontend.get("frontend_candidates_per_window")
    )
    _append_option(command, "--threshold", threshold)
    _append_option(command, "--step", frontend.get("step"))
    _append_option(command, "--max-candidates", max_candidates)
    _append_option(command, "--frontend-candidates-per-window", candidates_per_window)
    _append_option(command, "--min-sync-score", frontend.get("min_sync_score"))
    _append_option(command, "--min-coherent-metric", frontend.get("min_coherent_metric"))
    _append_option(command, "--min-sfd-score", frontend.get("min_sfd_score"))
    _append_option(command, "--min-refined-sync-score", frontend.get("min_refined_sync_score"))
    _append_option(command, "--cfo-min", frontend.get("cfo_min"))
    _append_option(command, "--cfo-max", frontend.get("cfo_max"))
    energy_top_windows = (
        args.energy_top_windows
        if args.energy_top_windows is not None
        else (frontend.get("energy_prefilter", {}) or {}).get("top_windows")
    )
    _append_option(command, "--energy-top-windows", energy_top_windows)
    _append_option(command, "--energy-window-seconds", (frontend.get("energy_prefilter", {}) or {}).get("window_seconds"))
    _append_option(command, "--energy-min-ratio", energy_min_ratio)
    _append_option(command, "--sp-sync-max-trials", decoder.get("sp_sync_max_trials"))

    if bool(frontend.get("local_projection_tracks", False)):
        command.append("--local-projection-tracks")
    spatial = frontend.get("spatial_residual_tracks")
    if spatial is True:
        command.append("--spatial-residual-tracks")
    elif spatial is False:
        command.append("--no-spatial-residual-tracks")
    if bool(frontend.get("fast_grid_refine", False)):
        command.append("--fast-grid-refine")
    if bool(frontend.get("full_refine", False)):
        command.append("--full-refine")
    if not bool(frontend.get("detector_phase_retry", True)):
        command.append("--disable-detector-phase-retry")
    if args.disable_energy_prefilter:
        command.append("--disable-energy-prefilter")
    if args.quiet_receiver:
        command.append("--quiet")
    return command


def _method_summary(report: dict, method: str) -> dict:
    by_method = report.get("detection_and_decode", {}).get("by_method", {})
    row = by_method.get(method, {}) if isinstance(by_method, dict) else {}
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    return {
        "decoded_success_count": row.get(
            "decoded_success_count",
            summary.get(f"{fallback_prefix}_decoded_success_count"),
        ),
        "decoded_success_tps": row.get(
            "decoded_success_tps",
            summary.get(f"{fallback_prefix}_tps_business_s"),
        ),
    }


def _median_detected_snr_db(report: dict) -> float | None:
    cfg = report.get("config", {})
    frontend = report.get("frontend", {})
    m = 2 ** int(cfg.get("sf", 10))
    noise_sigma2_fft = float(frontend.get("noise_sigma2_fft", 0.0))
    values = []
    if noise_sigma2_fft <= 0.0:
        return None
    for row in report.get("candidates", []):
        power = row.get("power_sp", row.get("power"))
        if power is None:
            continue
        values.append(10.0 * math.log10((float(power) + 1e-30) / (m * noise_sigma2_fft + 1e-30)))
    return float(np.median(values)) if values else None


def _sweep_summary(noise_rise_db: float, child_report_path: Path, report: dict, noise_diag: dict) -> dict:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    detection = report.get("detection_and_decode", {})
    return {
        "noise_floor_rise_db": float(noise_rise_db),
        "child_report": str(child_report_path),
        "expected_packet_count": detection.get("expected_packet_count", summary.get("expected_packet_count")),
        "raw_detected_rf_burst_count": detection.get("raw_detected_rf_burst_count", summary.get("raw_detected_rf_burst_count")),
        "complete_detected_packet_count": detection.get(
            "complete_detected_packet_count",
            summary.get("complete_detected_packet_count"),
        ),
        "complete_candidate_hypothesis_count": detection.get(
            "complete_candidate_hypothesis_count",
            summary.get("complete_candidate_hypothesis_count"),
        ),
        "packet_detection_rate": detection.get("packet_detection_rate", summary.get("packet_detection_rate")),
        "median_detected_preamble_snr_db": _median_detected_snr_db(report),
        "clipping_count_after_noise": noise_diag.get("clipping_count"),
        "near_full_scale_count_after_noise": noise_diag.get("near_full_scale_count"),
        "by_method": {
            METHOD_LABELS[method]: _method_summary(report, method)
            for method in METHODS
        },
    }


def main() -> int:
    args = build_parser().parse_args()
    source_report = json.loads(args.source_report.read_text(encoding="utf-8"))
    source_iq = _resolve(source_report.get("input", {}).get("iq"))
    source_metadata = _resolve(source_report.get("input", {}).get("metadata"))
    manifest = _resolve(source_report.get("input", {}).get("manifest"))
    if source_iq is None or source_metadata is None:
        raise ValueError("source report must contain input.iq and input.metadata")
    if not source_iq.exists():
        raise FileNotFoundError(source_iq)
    if not source_metadata.exists():
        raise FileNotFoundError(source_metadata)
    if manifest is not None and not manifest.exists():
        raise FileNotFoundError(manifest)
    covariance = _complex_matrix(source_report["calibration"]["noise_covariance"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    child_dir = args.out.parent / (args.out.stem + "_children")
    child_dir.mkdir(parents=True, exist_ok=True)
    kept_iq_dir = args.out.parent / (args.out.stem + "_noisy_iq")
    if args.keep_noisy_iq:
        kept_iq_dir.mkdir(parents=True, exist_ok=True)

    sweep = []
    with tempfile.TemporaryDirectory(prefix="awgn_frontend_") as tmpdir_text:
        tmpdir = Path(tmpdir_text)
        for index, noise_rise_db in enumerate(args.noise_rise_db):
            tag = _db_tag(float(noise_rise_db))
            child_report_path = child_dir / f"{args.out.stem}_{tag}.json"
            if abs(float(noise_rise_db)) < 1e-12:
                noisy_iq = source_iq
                noisy_metadata = source_metadata
                noise_diag = {
                    "samples_per_channel": None,
                    "clipping_count": None,
                    "near_full_scale_count": None,
                    "peak_fraction_full_scale": None,
                }
            else:
                noisy_dir = kept_iq_dir if args.keep_noisy_iq else tmpdir
                noisy_iq = noisy_dir / f"{args.out.stem}_{tag}.sc16"
                noisy_metadata = noisy_iq.with_suffix(noisy_iq.suffix + ".json")
                print(
                    f"[awgn] writing noisy capture {tag}: rise={float(noise_rise_db):.1f} dB",
                    flush=True,
                )
                noise_diag = write_noisy_sc16(
                    source_iq=source_iq,
                    source_metadata=source_metadata,
                    out_iq=noisy_iq,
                    out_metadata=noisy_metadata,
                    covariance=covariance,
                    noise_rise_db=float(noise_rise_db),
                    seed=int(args.seed) + index,
                    chunk_samples=int(args.chunk_samples),
                )
            command = _receiver_command(
                source_report=source_report,
                iq=noisy_iq,
                metadata=noisy_metadata,
                manifest=manifest,
                out=child_report_path,
                args=args,
            )
            print(f"[awgn] decoding {tag}: report={child_report_path}", flush=True)
            subprocess.run(command, cwd=str(ROOT), check=True)
            child_report = json.loads(child_report_path.read_text(encoding="utf-8"))
            row = _sweep_summary(float(noise_rise_db), child_report_path, child_report, noise_diag)
            sweep.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if not args.keep_noisy_iq and noisy_iq != source_iq:
                noisy_iq.unlink(missing_ok=True)
                noisy_metadata.unlink(missing_ok=True)

    output = {
        "schema": "real_iq_awgn_frontend_decode_sweep_v1",
        "definition": (
            "End-to-end low-SNR test on real IQ: each noise point reruns RF-energy "
            "prefilter, SP frontend packet detection/sync, and all comparison decoders. "
            "It does not report PRR because this rerun does not retain the certified "
            "shared fine-sync D set required by Fig.9/10. Missed detections are "
            "reflected in packet_detection_rate and decoded TPS."
        ),
        "prr_not_reported_reason": (
            "End-to-end frontend AWGN reruns do not use a fixed shared "
            "anonymous fine-sync physical candidate set; use evaluate_awgn_prr_sweep.py for "
            "formal Fig.9/10-aligned PRR."
        ),
        "source_report": str(args.source_report),
        "source_iq": str(source_iq),
        "source_metadata": str(source_metadata),
        "manifest": str(manifest) if manifest is not None else None,
        "random_seed": int(args.seed),
        "receiver": str(RECEIVER),
        "receiver_overrides": {
            "threshold": args.threshold,
            "energy_min_ratio": args.energy_min_ratio,
            "energy_top_windows": args.energy_top_windows,
            "disable_energy_prefilter": bool(args.disable_energy_prefilter),
            "max_candidates": args.max_candidates,
            "frontend_candidates_per_window": args.frontend_candidates_per_window,
        },
        "kept_noisy_iq_dir": str(kept_iq_dir) if args.keep_noisy_iq else None,
        "child_report_dir": str(child_dir),
        "sweep": sweep,
    }
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
