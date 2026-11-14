#!/usr/bin/env python3
"""Controlled signal/collision/noise simulations for the SP paper.

The decision suite uses the exact real-trace records behind motivation Fig. 2
for M2, bootstraps multi-packet collisions from the same measured dual-channel
waveforms for M3, and uses the real 20-byte explicit-header LoRa PHY plus
complex Gaussian FFT noise for the D1 lambda study.

The sync experiment synthesizes full oversampled LoRa waveforms and injects a
known coarse start/CFO error before calling the production SP-core and bounded
sync-refine decoder stages.  It is deliberately one controlled scenario, not
an end-to-end detector benchmark.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_matplotlib")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RECEIVER_DIR = ROOT / "real_collision_experiment" / "node01_sp_receiver"
if str(RECEIVER_DIR) not in sys.path:
    sys.path.insert(0, str(RECEIVER_DIR))

from evaluate_sp_dechirp_real_pos import (  # noqa: E402
    SPPacketReliability,
    choose_lambda_sp,
)
from generate_sp_preliminary_figures import (  # noqa: E402
    coherence2,
    complex_pairs_to_array,
    packet_power,
    projected_spectra,
)
from lora_mrc_sp_core import (  # noqa: E402
    LoRaConfig as TraceLoRaConfig,
    add_fractional_waveform,
    fractional_read_2d,
)
from real_usrp_clean_packet_synth import load_extracted  # noqa: E402
from real_collision_experiment.node01_sp_receiver.lora_phy_decode import (  # noqa: E402
    decode_payload_from_symbol_bins,
)
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sp_node01_receiver import (  # noqa: E402
    decode_sp_stages,
)
from sp_detection_frontend import build_references  # noqa: E402
from usrp_b210_lora_tx import (  # noqa: E402
    gray_demap,
    hamming_encode,
    instantaneous_chirp,
    interleave,
    payload_nibbles,
)


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials <= 0:
        return float("nan"), float("nan")
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item.strip()]


def parse_ints(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def encode_explicit_payload(payload: bytes, cfg: RealCollisionLoRaConfig) -> list[int]:
    """Return formal-profile payload symbol bins that close standard PHY CRC."""

    if len(payload) != cfg.payload_len:
        raise ValueError(f"payload must contain {cfg.payload_len} bytes")
    # Fixed explicit header for length=20, CR4/5 and PHY CRC on.  These are the
    # same nibbles checked by the production decoder.
    nibbles = [1, 4, 3, 1, 7] + payload_nibbles(payload, cfg)
    codewords = [
        hamming_encode(nibble, 4 if index < cfg.sf - 2 else cfg.cr)
        for index, nibble in enumerate(nibbles)
    ]
    values = interleave(codewords, cfg)
    bins = [int(gray_demap(value, cfg)) for value in values]
    if len(bins) != cfg.payload_symbol_count:
        raise AssertionError(
            f"encoder produced {len(bins)} symbols, expected {cfg.payload_symbol_count}"
        )
    self_check = decode_payload_from_symbol_bins(bins, cfg)
    if not self_check.phy_crc_ok or self_check.payload != payload:
        raise AssertionError("formal PHY encoder/decoder self-check failed")
    return bins


def build_explicit_frame(
    payload: bytes, cfg: RealCollisionLoRaConfig
) -> tuple[np.ndarray, list[int]]:
    bins = encode_explicit_payload(payload, cfg)
    up0 = instantaneous_chirp(0, cfg, up=True)
    down0 = instantaneous_chirp(0, cfg, up=False)
    parts: list[np.ndarray] = [up0] * cfg.preamble_len
    parts.append(
        instantaneous_chirp(((cfg.sync_word & 0xF0) >> 4) << 3, cfg, up=True)
    )
    parts.append(instantaneous_chirp((cfg.sync_word & 0x0F) << 3, cfg, up=True))
    parts.extend([down0, down0, down0[: cfg.samples_per_symbol // 4]])
    parts.extend(instantaneous_chirp(symbol, cfg, up=True) for symbol in bins)
    return np.concatenate(parts).astype(np.complex64), bins


def spatial_channel(rho: float, phase: float) -> np.ndarray:
    rho = float(np.clip(rho, 0.0, 1.0))
    return np.asarray(
        [
            math.sqrt(rho) + 0.0j,
            math.sqrt(max(0.0, 1.0 - rho)) * np.exp(1j * phase),
        ],
        dtype=np.complex128,
    )


def orthogonal_basis(channel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(channel, dtype=np.complex128)
    a /= math.sqrt(float(np.vdot(a, a).real))
    b = np.asarray([-np.conj(a[1]), np.conj(a[0])], dtype=np.complex128)
    return a, b


def lambda_for_condition(
    channels: list[np.ndarray],
    powers: list[float],
    *,
    noise_variance: float,
    theta_deg: float,
    gamma: float,
    lambda_max: float,
) -> tuple[float, dict]:
    theta = math.radians(theta_deg)
    reliabilities = [
        SPPacketReliability(
            theta_obs=theta,
            theta_drift=0.0,
            theta_total=theta,
            L=float(math.cos(theta) ** 2),
            power=float(power),
            noise_sigma2=float(noise_variance),
            robust_hit_count=8,
        )
        for power in powers
    ]
    lam, u_max, certified, pair_rows, search = choose_lambda_sp(
        0,
        reliabilities,
        channels,
        gamma=gamma,
        max_lambda=lambda_max,
    )
    return float(lam), {
        "u_max": float(u_max),
        "certified": bool(certified),
        "pair_rows": pair_rows,
        "search": search,
        "L_u": reliabilities[0].L,
    }


def simulate_packet_decisions(
    cfg: RealCollisionLoRaConfig,
    rng: np.random.Generator,
    *,
    rho: float,
    sir_db: float,
    interferer_count: int,
    snr_db: float,
    theta_deg: float,
    gamma: float,
    lambda_max: float,
    lambdas: list[float] | None = None,
    calculate_adaptive: bool = True,
    asynchronous: bool = True,
) -> tuple[dict[float, dict], float, dict]:
    """Simulate one formal-PHY packet and evaluate arbitrary signed weights.

    ``sir_db`` is the received target-to-*each-interferer* power ratio.  The
    returned symbol error count is measured before FEC over every explicit
    header/payload symbol bin; packet success still requires PHY CRC and exact
    payload equality and is retained for audit only.
    """

    payload = rng.integers(0, 256, size=cfg.payload_len, dtype=np.uint8).tobytes()
    target_bins = encode_explicit_payload(payload, cfg)
    interferer_bins = []
    for _ in range(interferer_count):
        bins = encode_explicit_payload(
            rng.integers(0, 256, size=cfg.payload_len, dtype=np.uint8).tobytes(),
            cfg,
        )
        # The real Poisson experiments are asynchronous. A nonzero cyclic
        # symbol shift prevents every user's deterministic explicit header
        # from being unrealistically aligned with the target header.
        shift = int(rng.integers(1, cfg.payload_symbol_count)) if asynchronous else 0
        interferer_bins.append(list(np.roll(np.asarray(bins), shift)))
    target_channel = np.asarray([1.0 + 0.0j, 0.0 + 0.0j])
    channels = [target_channel] + [
        spatial_channel(rho, 2.0 * math.pi * (index + 0.37) / max(1, interferer_count))
        for index in range(interferer_count)
    ]
    interferer_power = 10.0 ** (-sir_db / 10.0)
    powers = [1.0] + [interferer_power] * interferer_count
    noise_variance = 10.0 ** (-snr_db / 10.0)
    if calculate_adaptive:
        adaptive_lambda, diagnostics = lambda_for_condition(
            channels,
            powers,
            noise_variance=noise_variance,
            theta_deg=theta_deg,
            gamma=gamma,
            lambda_max=lambda_max,
        )
    else:
        adaptive_lambda, diagnostics = float("nan"), {}
    a, b = orthogonal_basis(target_channel)
    evaluated_lambdas = list(lambdas if lambdas is not None else [0.0])
    if calculate_adaptive:
        evaluated_lambdas.append(adaptive_lambda)
    evaluated_lambdas = sorted({float(value) for value in evaluated_lambdas})
    lambda_bins = {lam: [] for lam in evaluated_lambdas}

    for symbol_index, target_bin in enumerate(target_bins):
        noise_scale = math.sqrt(noise_variance / 2.0)
        p_spec = (
            rng.normal(size=cfg.m) + 1j * rng.normal(size=cfg.m)
        ) * noise_scale
        q_spec = (
            rng.normal(size=cfg.m) + 1j * rng.normal(size=cfg.m)
        ) * noise_scale
        all_bins = [target_bin] + [
            bins[symbol_index] for bins in interferer_bins
        ]
        for channel, power, symbol_bin in zip(channels, powers, all_bins):
            symbol_phase = np.exp(1j * rng.uniform(-math.pi, math.pi))
            amplitude = math.sqrt(power) * symbol_phase
            p_spec[int(symbol_bin)] += amplitude * np.vdot(a, channel)
            q_spec[int(symbol_bin)] += amplitude * np.vdot(b, channel)
        p_power = np.abs(p_spec) ** 2
        q_power = np.abs(q_spec) ** 2
        for lam in evaluated_lambdas:
            lambda_bins[lam].append(int(np.argmax(p_power - lam * q_power)))

    outcomes: dict[float, dict] = {}
    truth = np.asarray(target_bins, dtype=np.int64)
    for lam, bins in lambda_bins.items():
        decoded = decode_payload_from_symbol_bins(bins, cfg)
        errors = int(np.count_nonzero(np.asarray(bins, dtype=np.int64) != truth))
        outcomes[lam] = {
            "symbol_error_count": errors,
            "symbol_count": len(target_bins),
            "packet_success": bool(decoded.phy_crc_ok and decoded.payload == payload),
        }
    return outcomes, adaptive_lambda, diagnostics


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_m2_rows_from_trace_records(
    records_path: Path,
    *,
    sir_values: list[float],
    rho_edges: list[float],
) -> list[dict]:
    """Pool the exact real-trace symbol records used by preliminary Fig. 2."""

    records = json.loads(records_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for sir in sir_values:
        for rho_bin in range(len(rho_edges) - 1):
            lo = rho_edges[rho_bin]
            hi = rho_edges[rho_bin + 1]
            selected = [
                row
                for row in records
                if abs(float(row["sir_db"]) - sir) < 1e-9
                and lo <= float(row["rho"]) < hi
            ]
            if not selected:
                raise RuntimeError(
                    f"no M2 trace records for SIR={sir:g}, rho=[{lo:g},{hi:g})"
                )
            errors = sum(int(bool(row["mrc_error"])) for row in selected)
            rows.append(
                {
                    "family": "m2_trace_rho_sir",
                    "rho_bin": rho_bin,
                    "rho_low": lo,
                    "rho_high": hi,
                    "sir_db": sir,
                    "method": "mrc",
                    "symbol_error_count": errors,
                    "symbol_count": len(selected),
                    "ser": errors / len(selected),
                    "source": str(records_path),
                }
            )
    return rows


def m3_local_peaks(
    power: np.ndarray,
    *,
    ratio: float = 6.0,
    max_fraction: float = 0.01,
    limit: int = 64,
) -> np.ndarray:
    values = np.asarray(power, dtype=np.float64)
    if values.size == 0:
        return np.asarray([], dtype=np.int64)
    floor = float(np.median(values)) + 1e-30
    mask = (
        (values >= np.roll(values, 1))
        & (values >= np.roll(values, -1))
        & (values >= ratio * floor)
        & (values >= max_fraction * float(np.max(values)))
    )
    peaks = np.flatnonzero(mask)
    if peaks.size == 0:
        return np.asarray([int(np.argmax(values))], dtype=np.int64)
    if peaks.size > limit:
        peaks = peaks[np.argsort(values[peaks])[-int(limit) :]]
    return peaks.astype(np.int64, copy=False)


def reconstruct_physical_spectra(
    p_spec: np.ndarray,
    q_spec: np.ndarray,
    channel: np.ndarray,
) -> np.ndarray:
    h, b = orthogonal_basis(channel)
    return np.vstack([h[0] * p_spec + b[0] * q_spec, h[1] * p_spec + b[1] * q_spec])


def channel_pdoa(channel: np.ndarray) -> float:
    h = np.asarray(channel, dtype=np.complex128)
    if h.size < 2:
        return 0.0
    return float(np.angle(h[0] * np.conj(h[1])))


def choose_trace_lambda(
    channels: list[np.ndarray],
    *,
    noise_variance: float,
    theta_deg: float,
    gamma: float,
    lambda_max: float,
) -> float:
    theta = math.radians(theta_deg)
    reliabilities = []
    for channel in channels:
        power = max(float(np.vdot(channel, channel).real), 1e-30)
        reliabilities.append(
            SPPacketReliability(
                theta_obs=theta,
                theta_drift=0.0,
                theta_total=theta,
                L=float(math.cos(theta) ** 2),
                power=power,
                noise_sigma2=max(float(noise_variance), 1e-12),
                robust_hit_count=8,
            )
        )
    lam, _, _, _, _ = choose_lambda_sp(
        0,
        reliabilities,
        channels,
        gamma=gamma,
        max_lambda=lambda_max,
    )
    return float(lam)


def decide_m3_symbol(
    *,
    method: str,
    p_spec: np.ndarray,
    q_spec: np.ndarray,
    target_channel: np.ndarray,
    channels: list[np.ndarray],
    noise_variance: float,
    theta_deg: float,
    gamma: float,
    lambda_max: float,
) -> tuple[int, float]:
    p_power = np.abs(p_spec) ** 2
    q_power = np.abs(q_spec) ** 2
    if method == "mrc":
        return int(np.argmax(p_power)), 0.0
    if method == "sp":
        lam = choose_trace_lambda(
            channels,
            noise_variance=noise_variance,
            theta_deg=theta_deg,
            gamma=gamma,
            lambda_max=lambda_max,
        )
        return int(np.argmax(p_power - lam * q_power)), lam

    spectra = reconstruct_physical_spectra(p_spec, q_spec, target_channel)
    energy = np.sum(np.abs(spectra) ** 2, axis=0)
    candidates = m3_local_peaks(energy, ratio=6.0, limit=64)
    if method == "pcube":
        z_pair = spectra[0] * np.conj(spectra[1])
        target_pdoa = channel_pdoa(target_channel)
        phase_distance = np.abs(
            np.angle(np.exp(1j * (np.angle(z_pair[candidates]) - target_pdoa)))
        )
        order = np.lexsort((-energy[candidates], phase_distance))
        return int(candidates[int(order[0])]), 0.0

    if method == "maloragw":
        antenna_count = int(spectra.shape[0])
        strongest = sorted(
            range(len(channels)),
            key=lambda index: float(np.vdot(channels[index], channels[index]).real),
            reverse=True,
        )[: min(len(channels), antenna_count)]
        if strongest:
            channel_matrix = np.column_stack([channels[index] for index in strongest])
            projected = np.linalg.pinv(channel_matrix) @ spectra
        else:
            projected = spectra
        projected_candidates = [
            m3_local_peaks(np.abs(projected[row]) ** 2, ratio=6.0, limit=32)
            for row in range(projected.shape[0])
        ]
        candidates = np.unique(np.concatenate(projected_candidates + [candidates]))
        reference = (
            target_channel[0]
            if abs(target_channel[0]) > 1e-30
            else 1.0 + 0.0j
        )
        target_ratio = target_channel / reference
        denominator = np.where(
            np.abs(spectra[0, candidates]) > 1e-30,
            spectra[0, candidates],
            1.0,
        )
        ratios = spectra[:, candidates] / denominator[None, :]
        ratio_distance = np.linalg.norm(ratios - target_ratio[:, None], axis=0) / (
            1.0 + np.linalg.norm(target_ratio)
        )
        projected_energy = np.sum(np.abs(projected[:, candidates]) ** 2, axis=0)
        order = np.lexsort((-projected_energy, ratio_distance))
        return int(candidates[int(order[0])]), 0.0

    raise ValueError(f"unknown M3 method: {method}")


def simulate_trace_method_points(
    packets: np.ndarray,
    refs: dict[int, object],
    cfg: TraceLoRaConfig,
    rng: np.random.Generator,
    *,
    collision_number: int,
    snr_db: float,
    median_sir_db: float,
    sir_jitter_db: float,
    offsets: list[float],
    symbol_trials: int,
    theta_deg: float,
    gamma: float,
    lambda_max: float,
) -> list[dict]:
    """Bootstrap one M3 point and evaluate all methods on identical symbols."""

    if collision_number < 2 or collision_number > len(packets):
        raise ValueError(
            f"collision_number must be in [2,{len(packets)}], got {collision_number}"
        )
    packet_powers = np.asarray(
        [packet_power(packet) for packet in packets],
        dtype=np.float64,
    )
    methods = ("mrc", "sp", "pcube", "maloragw")
    errors = {method: 0 for method in methods}
    lambda_values: list[float] = []
    rho_observations: list[float] = []
    actual_sirs: list[float] = []
    packet_indices = np.arange(len(packets))
    for _ in range(symbol_trials):
        target_idx = int(rng.integers(0, len(packets)))
        interferer_pool = packet_indices[packet_indices != target_idx]
        interferer_ids = [
            int(value)
            for value in rng.choice(
                interferer_pool,
                size=collision_number - 1,
                replace=False,
            )
        ]
        ref_u = refs[target_idx]
        symbol_index = int(rng.integers(0, len(ref_u.symbol_bins)))
        truth = int(ref_u.symbol_bins[symbol_index])
        t0 = int(
            round(
                (cfg.payload_start_symbols + symbol_index)
                * cfg.samples_per_symbol
            )
        )
        target_window = np.asarray(
            packets[
                target_idx,
                :,
                t0 : t0 + cfg.samples_per_symbol,
            ],
            dtype=np.complex64,
        )
        window = np.array(target_window, copy=True)
        h_u = complex_pairs_to_array(ref_u.channel)
        active_channels = [h_u]
        for interferer_idx in interferer_ids:
            actual_sir = float(
                median_sir_db + rng.normal(scale=max(0.0, sir_jitter_db))
            )
            offset = float(offsets[int(rng.integers(0, len(offsets)))])
            scale = math.sqrt(
                packet_powers[target_idx]
                / max(packet_powers[interferer_idx], 1e-30)
                / (10.0 ** (actual_sir / 10.0))
            )
            rel = float(t0) - offset * cfg.samples_per_symbol
            window += scale * fractional_read_2d(
                packets[interferer_idx],
                rel,
                cfg.samples_per_symbol,
            )
            h_v = complex_pairs_to_array(refs[interferer_idx].channel) * scale
            active_channels.append(h_v)
            rho_observations.append(coherence2(h_u, h_v))
            actual_sirs.append(actual_sir)

        target_power = float(np.mean(np.abs(target_window) ** 2))
        noise_power = target_power / (10.0 ** (snr_db / 10.0))
        noise = (
            rng.normal(size=window.shape) + 1j * rng.normal(size=window.shape)
        ) * math.sqrt(noise_power / 2.0)
        window = (window + noise.astype(np.complex64)).astype(np.complex64)
        p_spec, q_spec = projected_spectra(
            window,
            cfg,
            float(ref_u.cfo_bins),
            h_u,
        )
        for method in methods:
            chosen, lam = decide_m3_symbol(
                method=method,
                p_spec=p_spec,
                q_spec=q_spec,
                target_channel=h_u,
                channels=active_channels,
                noise_variance=cfg.m * noise_power,
                theta_deg=theta_deg,
                gamma=gamma,
                lambda_max=lambda_max,
            )
            errors[method] += int(chosen != truth)
            if method == "sp":
                lambda_values.append(lam)
    rows: list[dict] = []
    method_labels = {
        "mrc": "MRC",
        "sp": "SP",
        "pcube": "PCube",
        "maloragw": "MaLoRaGW",
    }
    for method in methods:
        rows.append(
            {
                "family": "m3_trace_collision_snr",
                "collision_number": collision_number,
                "snr_db": snr_db,
                "median_sir_db": median_sir_db,
                "sir_jitter_db": sir_jitter_db,
                "symbol_error_count": errors[method],
                "symbol_count": symbol_trials,
                "ser": errors[method] / symbol_trials,
                "observed_rho_mean": float(np.mean(rho_observations)),
                "observed_rho_p10": float(np.quantile(rho_observations, 0.10)),
                "observed_rho_p90": float(np.quantile(rho_observations, 0.90)),
                "observed_sir_mean_db": float(np.mean(actual_sirs)),
                "method": method,
                "method_label": method_labels[method],
                "mean_lambda": (
                    float(np.mean(lambda_values)) if method == "sp" and lambda_values else ""
                ),
            }
        )
    return rows


def ser_heatmap(
    axis: plt.Axes,
    rows: list[dict],
    *,
    x_key: str,
    x_values: list[float],
    y_key: str,
    y_values: list[float],
    value_key: str,
    title: str,
    x_label: str,
    y_label: str,
    colorbar_label: str = "MRC SER",
    annotate: bool = True,
) -> None:
    matrix = np.full((len(y_values), len(x_values)), np.nan)
    lookup = {(float(row[x_key]), float(row[y_key])): float(row[value_key]) for row in rows}
    for yi, y in enumerate(y_values):
        for xi, x in enumerate(x_values):
            matrix[yi, xi] = lookup.get((float(x), float(y)), np.nan)
    image = axis.imshow(
        matrix,
        origin="lower",
        aspect="auto",
        vmin=0.0,
        vmax=1.0,
        cmap="magma",
    )
    axis.set_xticks(range(len(x_values)), [f"{value:g}" for value in x_values])
    axis.set_yticks(range(len(y_values)), [f"{value:g}" for value in y_values])
    axis.set_xlabel(x_label)
    axis.set_ylabel(y_label)
    axis.set_title(title)
    if annotate:
        for yi in range(len(y_values)):
            for xi in range(len(x_values)):
                if np.isfinite(matrix[yi, xi]):
                    axis.text(
                        xi,
                        yi,
                        f"{matrix[yi, xi]:.2f}",
                        ha="center",
                        va="center",
                        color="white",
                        fontsize=8,
                    )
    plt.colorbar(image, ax=axis, label=colorbar_label)


def decision_command(args: argparse.Namespace) -> int:
    cfg = RealCollisionLoRaConfig()
    rng = np.random.default_rng(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    m2_sir_values = sorted(parse_floats(args.m2_sir_db))
    m2_rho_edges = parse_floats(args.m2_rho_edges)
    if len(m2_rho_edges) < 2 or any(
        right <= left for left, right in zip(m2_rho_edges, m2_rho_edges[1:])
    ):
        raise SystemExit("--m2-rho-edges must be strictly increasing")
    collision_numbers = sorted(parse_ints(args.collision_number))
    snr_values = sorted(parse_floats(args.snr_db))
    d1_oracle_rhos = sorted(parse_floats(args.d1_oracle_rho))
    lambda_sweep = sorted({float(value) for value in parse_floats(args.lambda_sweep)})
    if not lambda_sweep or lambda_sweep[0] < 0.0:
        raise SystemExit("--lambda-sweep must contain non-negative values")
    rows = build_m2_rows_from_trace_records(
        args.m2_records,
        sir_values=m2_sir_values,
        rho_edges=m2_rho_edges,
    )

    trace_cfg = TraceLoRaConfig()
    trace_packets, _ = load_extracted(args.clean_packets)
    trace_refs = build_references(
        args.clean_packets,
        list(range(len(trace_packets))),
        trace_cfg,
    )
    m3_offsets = parse_floats(args.m3_offset_symbols)
    if not m3_offsets:
        raise SystemExit("--m3-offset-symbols must not be empty")
    for collision_number in collision_numbers:
        for snr in snr_values:
            rows.extend(
                simulate_trace_method_points(
                    trace_packets,
                    trace_refs,
                    trace_cfg,
                    rng,
                    collision_number=collision_number,
                    snr_db=snr,
                    median_sir_db=args.m3_median_sir_db,
                    sir_jitter_db=args.m3_sir_jitter_db,
                    offsets=m3_offsets,
                    symbol_trials=args.m3_symbol_trials,
                    theta_deg=args.theta_deg,
                    gamma=args.sp_gamma,
                    lambda_max=args.sp_lambda_max,
                )
            )

    def run_mrc_point(
        *,
        family: str,
        rho: float,
        sir: float,
        collision_number: int,
        snr: float,
        asynchronous: bool = True,
    ) -> None:
        symbol_errors = 0
        symbol_count = 0
        packet_successes = 0
        for _ in range(args.trials):
            outcomes, _, _ = simulate_packet_decisions(
                cfg,
                rng,
                rho=rho,
                sir_db=sir,
                interferer_count=collision_number - 1,
                snr_db=snr,
                theta_deg=args.theta_deg,
                gamma=args.sp_gamma,
                lambda_max=args.sp_lambda_max,
                lambdas=[0.0],
                calculate_adaptive=False,
                asynchronous=asynchronous,
            )
            result = outcomes[0.0]
            symbol_errors += int(result["symbol_error_count"])
            symbol_count += int(result["symbol_count"])
            packet_successes += int(result["packet_success"])
        ci_low, ci_high = wilson_interval(packet_successes, args.trials)
        rows.append(
            {
                "family": family,
                "rho": rho,
                "sir_db": sir,
                "collision_number": collision_number,
                "snr_db": snr,
                "alignment": "asynchronous" if asynchronous else "fully_aligned",
                "method": "mrc",
                "method_label": "MRC",
                "trial_count": args.trials,
                "symbol_error_count": symbol_errors,
                "symbol_count": symbol_count,
                "ser": symbol_errors / max(1, symbol_count),
                "success_count": packet_successes,
                "prr": packet_successes / args.trials,
                "prr_ci_low": ci_low,
                "prr_ci_high": ci_high,
            }
        )

    if args.include_m4:
        for asynchronous in (True, False):
            run_mrc_point(
                family="m4_alignment_boundary",
                rho=args.alignment_rho,
                sir=args.alignment_sir_db,
                collision_number=2,
                snr=args.alignment_snr_db,
                asynchronous=asynchronous,
            )

    write_csv(args.out_dir / "decision_records.csv", rows)

    # M2 deliberately ends at the MRC failure phenomenon.  No SP variable is
    # present before the paper introduces the signed-spectrum mechanism.
    m2_rows = [row for row in rows if row["family"] == "m2_trace_rho_sir"]
    m2_rho_bins = list(range(len(m2_rho_edges) - 1))
    fig, axis = plt.subplots(figsize=(7.2, 3.8))
    ser_heatmap(
        axis,
        m2_rows,
        x_key="rho_bin",
        x_values=[float(value) for value in m2_rho_bins],
        y_key="sir_db",
        y_values=m2_sir_values,
        value_key="ser",
        title="MRC symbol error rate under oracle synchronization and channel",
        x_label=r"channel coherence $\rho$",
        y_label="SIR (dB)",
    )
    axis.set_xticks(
        m2_rho_bins,
        [
            f"{m2_rho_edges[index]:.1f}-{m2_rho_edges[index + 1]:.1f}"
            for index in m2_rho_bins
        ],
    )
    fig.tight_layout()
    fig.savefig(args.out_dir / "m2_mrc_ser_rho_sir.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)

    m3_rows = [
        row for row in rows if row["family"] == "m3_trace_collision_snr"
    ]
    m3_methods = [
        ("mrc", "MRC"),
        ("sp", "SP"),
        ("pcube", "PCube"),
        ("maloragw", "MaLoRaGW"),
    ]
    for method, label in m3_methods:
        fig, axis = plt.subplots(figsize=(7.2, 3.8))
        ser_heatmap(
            axis,
            [row for row in m3_rows if row["method"] == method],
            x_key="snr_db",
            x_values=snr_values,
            y_key="collision_number",
            y_values=[float(value) for value in collision_numbers],
            value_key="ser",
            title=f"{label} symbol errors with multiple concurrent packets",
            x_label="target waveform SNR before dechirp (dB)",
            y_label="concurrent packet number (including target)",
            colorbar_label="SER",
        )
        fig.suptitle(
            (
                f"Measured channel/waveform bootstrap; per-interferer median "
                f"SIR={args.m3_median_sir_db:g} dB"
            ),
            fontsize=10,
        )
        fig.tight_layout()
        fig.savefig(
            args.out_dir / f"m3_{method}_ser_collision_snr.pdf",
            dpi=200,
            bbox_inches="tight",
        )
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.2))
    for axis, (method, label) in zip(axes.flat, m3_methods):
        ser_heatmap(
            axis,
            [row for row in m3_rows if row["method"] == method],
            x_key="snr_db",
            x_values=snr_values,
            y_key="collision_number",
            y_values=[float(value) for value in collision_numbers],
            value_key="ser",
            title=label,
            x_label="target waveform SNR before dechirp (dB)",
            y_label="concurrent packet number",
            colorbar_label="SER",
            annotate=False,
        )
    fig.suptitle(
        (
            f"M3: same trace-driven collision symbols, median SIR="
            f"{args.m3_median_sir_db:g} dB"
        ),
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(args.out_dir / "m3_methods_ser_collision_snr.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # D1(a): the receiver's risk objective, its finite checkpoints, and the
    # explicitly excluded extreme-lambda region.
    d1_collision_number = args.d1_collision_number
    example_channels = [
        np.asarray([1.0 + 0.0j, 0.0 + 0.0j]),
    ] + [
        spatial_channel(
            args.d1_example_rho,
            2.0 * math.pi * (index + 0.37) / max(1, d1_collision_number - 1),
        )
        for index in range(d1_collision_number - 1)
    ]
    example_power = 10.0 ** (-args.d1_example_sir_db / 10.0)
    example_noise = 10.0 ** (-args.d1_example_snr_db / 10.0)
    selected_lambda, diagnostics = lambda_for_condition(
        example_channels,
        [1.0] + [example_power] * (d1_collision_number - 1),
        noise_variance=example_noise,
        theta_deg=args.theta_deg,
        gamma=args.sp_gamma,
        lambda_max=args.sp_lambda_max,
    )
    pair_rows = diagnostics["pair_rows"]
    cap = float(diagnostics["search"]["lambda_cap"])
    candidates = diagnostics["search"]["candidate_points"]

    # D1(b): empirical fixed-lambda SER.  Values 100 and 1000 are stress
    # controls, not production candidates.
    d1_curve_rows: list[dict] = []
    d1_case_rhos = parse_floats(args.d1_case_rho)
    d1_case_sirs = parse_floats(args.d1_case_sir_db)
    if len(d1_case_rhos) != len(d1_case_sirs) or not d1_case_rhos:
        raise SystemExit(
            "--d1-case-rho and --d1-case-sir-db must contain the same "
            "nonzero number of comma-separated values"
        )
    d1_cases = list(zip(d1_case_rhos, d1_case_sirs))
    for rho, sir in d1_cases:
        totals: dict[float, list[int]] = defaultdict(lambda: [0, 0])
        selected_values: list[float] = []
        for _ in range(args.d1_trials):
            outcomes, adaptive_lambda, _ = simulate_packet_decisions(
                cfg,
                rng,
                rho=rho,
                sir_db=sir,
                interferer_count=d1_collision_number - 1,
                snr_db=args.d1_snr_db,
                theta_deg=args.theta_deg,
                gamma=args.sp_gamma,
                lambda_max=args.sp_lambda_max,
                lambdas=lambda_sweep,
            )
            selected_values.append(adaptive_lambda)
            for lam, result in outcomes.items():
                totals[lam][0] += int(result["symbol_error_count"])
                totals[lam][1] += int(result["symbol_count"])
        mean_selected = float(np.mean(selected_values))
        for lam in sorted(totals):
            d1_curve_rows.append(
                {
                    "record_type": "lambda_curve",
                    "rho": rho,
                    "sir_db": sir,
                    "collision_number": d1_collision_number,
                    "snr_db": args.d1_snr_db,
                    "lambda": lam,
                    "symbol_error_count": totals[lam][0],
                    "symbol_count": totals[lam][1],
                    "ser": totals[lam][0] / max(1, totals[lam][1]),
                    "risk_selected_lambda": mean_selected,
                    "trial_count": args.d1_trials,
                }
            )

    # D1(c): compare the truth-free risk choice with an oracle chosen only for
    # offline evaluation from the lambda sweep's minimum empirical SER.
    d1_oracle_rows: list[dict] = []
    d1_oracle_sirs = sorted(parse_floats(args.d1_oracle_sir_db))
    for rho in d1_oracle_rhos:
        for sir in d1_oracle_sirs:
            totals: dict[float, list[int]] = defaultdict(lambda: [0, 0])
            selected_values: list[float] = []
            for _ in range(args.d1_oracle_trials):
                outcomes, adaptive_lambda, _ = simulate_packet_decisions(
                    cfg,
                    rng,
                    rho=rho,
                    sir_db=sir,
                    interferer_count=d1_collision_number - 1,
                    snr_db=args.d1_snr_db,
                    theta_deg=args.theta_deg,
                    gamma=args.sp_gamma,
                    lambda_max=args.sp_lambda_max,
                    lambdas=lambda_sweep,
                )
                selected_values.append(adaptive_lambda)
                for lam, result in outcomes.items():
                    totals[lam][0] += int(result["symbol_error_count"])
                    totals[lam][1] += int(result["symbol_count"])
            fixed_lambdas = [
                lam
                for lam in totals
                if lam in lambda_sweep and lam <= args.sp_lambda_max + 1e-12
            ]
            oracle_lambda = min(
                fixed_lambdas,
                key=lambda lam: (totals[lam][0] / max(1, totals[lam][1]), lam),
            )
            risk_lambda = float(np.mean(selected_values))
            risk_key = min(totals, key=lambda lam: abs(lam - risk_lambda))
            oracle_ser = totals[oracle_lambda][0] / max(1, totals[oracle_lambda][1])
            risk_ser = totals[risk_key][0] / max(1, totals[risk_key][1])
            d1_oracle_rows.append(
                {
                    "record_type": "oracle_comparison",
                    "rho": rho,
                    "sir_db": sir,
                    "collision_number": d1_collision_number,
                    "snr_db": args.d1_snr_db,
                    "oracle_lambda": oracle_lambda,
                    "oracle_ser": oracle_ser,
                    "risk_selected_lambda": risk_lambda,
                    "risk_selected_ser": risk_ser,
                    "excess_ser": risk_ser - oracle_ser,
                    "oracle_scope": (
                        f"fixed lambda sweep restricted to [0,{args.sp_lambda_max:g}]"
                    ),
                    "trial_count": args.d1_oracle_trials,
                }
            )

    write_csv(args.out_dir / "d1_lambda_records.csv", d1_curve_rows + d1_oracle_rows)
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 4.1))
    axis = axes[0]
    allowed_lambda = np.linspace(0.0, max(cap, 1e-9), 400)
    allowed_objective = [
        min(
            (row["A_under"] + lam * row["B_under"])
            / math.sqrt(max(row["C0"] + lam * lam * row["C2"], 1e-30))
            for row in pair_rows
        )
        for lam in allowed_lambda
    ]
    axis.plot(
        allowed_lambda,
        allowed_objective,
        color="#2166ac",
        label="guaranteed minimum margin",
    )
    axis.axvspan(
        0.0,
        cap,
        color="#67a9cf",
        alpha=0.16,
        label="uncertainty-safe range",
    )
    axis.scatter(
        [row["lambda"] for row in candidates],
        [row["objective"] for row in candidates],
        color="#fdae61",
        edgecolor="black",
        linewidth=0.35,
        s=34,
        label=r"$\lambda$ values actually tested",
        zorder=3,
    )
    selected_objective = min(
        (row["A_under"] + selected_lambda * row["B_under"])
        / math.sqrt(max(row["C0"] + selected_lambda**2 * row["C2"], 1e-30))
        for row in pair_rows
    )
    axis.scatter(
        [selected_lambda],
        [selected_objective],
        marker="*",
        s=130,
        color="#d73027",
        edgecolor="black",
        linewidth=0.5,
        label=rf"chosen $\lambda_u={selected_lambda:.2g}$",
        zorder=4,
    )
    axis.axhline(0.0, color="0.35", linestyle=":", linewidth=1.0)
    axis.text(
        0.02 * max(cap, 1.0),
        0.04,
        "positive: target beats every modeled interferer",
        fontsize=6.8,
        color="0.25",
        va="bottom",
    )
    axis.set_xlim(0.0, max(cap, 1e-9))
    axis.set_xlabel(r"$\lambda$")
    axis.set_ylabel("guaranteed minimum decision margin")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=7, loc="best")
    axis.set_title(r"(a) One packet: choose $\lambda_u$ inside the safe range")

    axis = axes[1]
    fixed_curve_rows = [
        row
        for row in d1_curve_rows
        if any(abs(float(row["lambda"]) - lam) < 1e-12 for lam in lambda_sweep)
    ]
    case_indices = list(range(len(d1_cases)))
    case_rows: list[dict] = []
    for case_index, (rho, sir) in enumerate(d1_cases):
        for row in fixed_curve_rows:
            if (
                abs(float(row["rho"]) - rho) < 1e-12
                and abs(float(row["sir_db"]) - sir) < 1e-12
            ):
                case_rows.append(dict(row) | {"case_index": case_index})
    ser_heatmap(
        axis,
        case_rows,
        x_key="lambda",
        x_values=lambda_sweep,
        y_key="case_index",
        y_values=[float(value) for value in case_indices],
        value_key="ser",
        title=r"(b) Fixed $\lambda$ is condition-dependent",
        x_label=r"fixed subtraction weight $\lambda$",
        y_label=r"channel condition $(\rho,\mathrm{SIR})$",
        colorbar_label="SER",
        annotate=False,
    )
    axis.set_yticks(
        case_indices,
        [rf"$({rho:g},{sir:g}\,\mathrm{{dB}})$" for rho, sir in d1_cases],
    )
    axis.tick_params(axis="x", rotation=45, labelsize=7)
    allowed_indices = [
        index
        for index, lam in enumerate(lambda_sweep)
        if lam <= args.sp_lambda_max + 1e-12
    ]
    if allowed_indices and max(allowed_indices) < len(lambda_sweep) - 1:
        boundary_x = max(allowed_indices) + 0.5
        axis.axvline(
            boundary_x,
            color="white",
            linestyle="--",
            linewidth=1.1,
        )
        axis.text(
            boundary_x - 0.12,
            len(d1_cases) - 0.52,
            rf"receiver searches only $\lambda\leq{args.sp_lambda_max:g}$",
            color="white",
            fontsize=6.8,
            ha="right",
            va="top",
        )
    for case_index, (rho, sir) in enumerate(d1_cases):
        selected_row = next(
            row
            for row in d1_curve_rows
            if abs(float(row["rho"]) - rho) < 1e-12
            and abs(float(row["sir_db"]) - sir) < 1e-12
        )
        selected_lambda = float(selected_row["risk_selected_lambda"])
        selected_x = float(
            np.interp(
                selected_lambda,
                np.asarray(lambda_sweep),
                np.arange(len(lambda_sweep)),
            )
        )
        axis.scatter(
            [selected_x],
            [case_index],
            marker="*",
            s=62,
            facecolor="#00e5ff",
            edgecolor="black",
            linewidth=0.55,
            zorder=5,
        )
    axis.scatter(
        [],
        [],
        marker="*",
        s=62,
        facecolor="#00e5ff",
        edgecolor="black",
        label=r"risk-selected $\lambda_u$",
    )
    axis.legend(loc="upper left", fontsize=7, framealpha=0.85)

    axis = axes[2]
    oracle_ser_values = np.asarray(
        [row["oracle_ser"] for row in d1_oracle_rows],
        dtype=np.float64,
    )
    risk_ser_values = np.asarray(
        [row["risk_selected_ser"] for row in d1_oracle_rows],
        dtype=np.float64,
    )
    scatter = axis.scatter(
        oracle_ser_values,
        risk_ser_values,
        c=[row["rho"] for row in d1_oracle_rows],
        s=55,
        cmap="viridis",
        vmin=min(d1_oracle_rhos),
        vmax=max(d1_oracle_rhos),
        alpha=0.85,
        edgecolor="black",
        linewidth=0.35,
    )
    performance_max = max(
        0.05,
        float(np.max(oracle_ser_values)),
        float(np.max(risk_ser_values)),
    )
    axis.plot(
        [0.0, performance_max],
        [0.0, performance_max],
        color="0.35",
        linestyle="--",
        linewidth=1.0,
        label="same SER",
    )
    axis.set_xlim(-0.01, min(1.0, performance_max * 1.08))
    axis.set_ylim(-0.01, min(1.0, performance_max * 1.08))
    axis.set_xlabel("hindsight-best SER within the same safe range")
    axis.set_ylabel(r"SER using risk-selected $\lambda_u$")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=7, loc="lower right")
    excess = risk_ser_values - oracle_ser_values
    axis.text(
        0.04,
        0.96,
        (
            f"median excess SER={np.median(excess):.3f}\n"
            f"90th percentile={np.quantile(excess, 0.90):.3f}"
        ),
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=7,
        bbox={"facecolor": "white", "alpha": 0.78, "edgecolor": "0.75"},
    )
    axis.set_title("(c) Performance, not weight equality")
    fig.colorbar(scatter, ax=axis, label=r"channel coherence $\rho$")
    fig.suptitle(
        "D1: why the signed subtraction weight is condition-dependent",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(args.out_dir / "d1_lambda_selection.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)

    (args.out_dir / "d1_lambda_diagnostics.json").write_text(
        json.dumps(
            {
                "schema": "sp_lambda_selection_v2",
                "example": {
                    "rho": args.d1_example_rho,
                    "sir_db": args.d1_example_sir_db,
                    "snr_db": args.d1_example_snr_db,
                    "collision_number": d1_collision_number,
                },
                "lambda_sweep": lambda_sweep,
                "selected_lambda": selected_lambda,
                "diagnostics": diagnostics,
                "note": (
                    "lambda values above sp_lambda_max are shown only to expose "
                    "over-subtraction; the receiver excludes them using its "
                    "channel/noise uncertainty bound"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if args.include_m4:
        alignment_rows = [
            row for row in rows if row["family"] == "m4_alignment_boundary"
        ]
        fig, axis = plt.subplots(figsize=(5.8, 3.7))
        selected = {row["alignment"]: row for row in alignment_rows}
        labels = ["asynchronous", "fully_aligned"]
        axis.bar(
            labels,
            [float(selected[label]["ser"]) for label in labels],
            color=["#2c7bb6", "#d7191c"],
        )
        axis.set_ylabel("MRC SER")
        axis.set_ylim(0.0, 1.02)
        axis.grid(axis="y", alpha=0.25)
        axis.set_title("Optional M4: fully aligned identical-header boundary")
        fig.tight_layout()
        fig.savefig(args.out_dir / "m4_alignment_boundary.pdf", dpi=200, bbox_inches="tight")
        plt.close(fig)

    (args.out_dir / "decision_config.json").write_text(
        json.dumps(
            {
                "schema": "sp_mechanism_decision_sim_v3",
                "config": asdict(cfg),
                "arguments": vars(args) | {"out_dir": str(args.out_dir)},
                "m2_definition": (
                    "exact pooled real-trace symbol observations from the records "
                    "that generated preliminary Fig. 2"
                ),
                "m3_definition": (
                    "measured clean dual-channel waveforms bootstrapped into "
                    "multi-packet collisions with random target/interferer identity, "
                    "symbol, offset, received-power jitter, and target-referenced AWGN; "
                    "MRC, SP, PCube, and MaLoRaGW are evaluated on the same symbol samples"
                ),
                "d1_definition": (
                    "formal explicit-header PHY collision/noise simulation; SER is "
                    "measured over symbol bins before FEC, while PHY closure remains "
                    "available inside the simulator"
                ),
                "sir_definition": (
                    "10*log10(target received power / each interferer's received power)"
                ),
                "collision_number_definition": (
                    "total concurrently present packets, including the target"
                ),
                "alignment_definition": (
                    "asynchronous uses a nonzero random payload-symbol shift; fully_aligned "
                    "aligns identical explicit headers and is an optional failure boundary"
                ),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out_dir.resolve()}")
    return 0


def add_cfo(waveform: np.ndarray, cfo_bins: float, cfg: RealCollisionLoRaConfig) -> np.ndarray:
    phase = np.exp(
        1j
        * 2.0
        * math.pi
        * float(cfo_bins)
        * np.arange(waveform.size)
        / cfg.samples_per_symbol
    )
    return (waveform * phase).astype(np.complex64)


def synthesize_sync_scene(
    cfg: RealCollisionLoRaConfig,
    rng: np.random.Generator,
    *,
    rho: float,
    power_gap_db: float,
    snr_db: float,
    offset_symbols: float,
    target_cfo_bins: float,
    interferer_cfo_bins: float,
) -> tuple[np.ndarray, bytes, float, np.ndarray, float, dict]:
    target_payload = rng.integers(0, 256, size=cfg.payload_len, dtype=np.uint8).tobytes()
    interferer_payload = rng.integers(0, 256, size=cfg.payload_len, dtype=np.uint8).tobytes()
    target_frame, _ = build_explicit_frame(target_payload, cfg)
    interferer_frame, _ = build_explicit_frame(interferer_payload, cfg)
    target_frame = add_cfo(target_frame, target_cfo_bins, cfg)
    interferer_frame = add_cfo(interferer_frame, interferer_cfo_bins, cfg)
    target_start = 2.0 * cfg.samples_per_symbol
    interferer_start = target_start + offset_symbols * cfg.samples_per_symbol
    total = int(
        math.ceil(max(target_start + target_frame.size, interferer_start + interferer_frame.size))
        + 2 * cfg.samples_per_symbol
    )
    samples = np.zeros((2, total), dtype=np.complex64)
    target_channel = np.asarray([1.0 + 0.0j, 0.0 + 0.0j])
    interferer_channel = spatial_channel(rho, 1.1)
    interferer_amplitude = math.sqrt(10.0 ** (power_gap_db / 10.0))
    for channel_index in range(2):
        add_fractional_waveform(
            samples[channel_index],
            target_frame,
            target_start,
            target_channel[channel_index],
        )
        add_fractional_waveform(
            samples[channel_index],
            interferer_frame,
            interferer_start,
            interferer_amplitude * interferer_channel[channel_index],
        )
    noise_variance = 10.0 ** (-snr_db / 10.0)
    noise = (
        rng.normal(size=samples.shape) + 1j * rng.normal(size=samples.shape)
    ) * math.sqrt(noise_variance / 2.0)
    samples = (samples + noise.astype(np.complex64)).astype(np.complex64)
    adaptive_lambda, diagnostics = lambda_for_condition(
        [target_channel, interferer_channel],
        [1.0, 10.0 ** (power_gap_db / 10.0)],
        noise_variance=noise_variance * cfg.m,
        theta_deg=3.0,
        gamma=0.05,
        lambda_max=4.0,
    )
    return (
        samples,
        target_payload,
        target_start,
        target_channel,
        adaptive_lambda,
        diagnostics,
    )


def sync_command(args: argparse.Namespace) -> int:
    cfg = RealCollisionLoRaConfig()
    rng = np.random.default_rng(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    start_errors = parse_floats(args.start_error_samples)
    rows: list[dict] = []
    for start_error in start_errors:
        counts = {"sp_core": 0, "sp_sync_refine": 0}
        trials_used: list[int] = []
        for _ in range(args.trials):
            (
                samples,
                payload,
                true_start,
                target_channel,
                adaptive_lambda,
                diagnostics,
            ) = synthesize_sync_scene(
                cfg,
                rng,
                rho=args.rho,
                power_gap_db=args.power_gap_db,
                snr_db=args.snr_db,
                offset_symbols=args.interferer_offset_symbols,
                target_cfo_bins=args.target_cfo_bins,
                interferer_cfo_bins=args.interferer_cfo_bins,
            )
            estimate = {
                "start_sample": true_start + start_error,
                "cfo_bins": args.target_cfo_bins + args.cfo_error_bins,
                "continuous_cfo_bins": args.target_cfo_bins + args.cfo_error_bins,
                "cfo_bins_sp": args.target_cfo_bins + args.cfo_error_bins,
                "sto_samples": 0.0,
                "sto_samples_sp": 0.0,
                "channel": [
                    [float(value.real), float(value.imag)] for value in target_channel
                ],
                "channel_sp": [
                    [float(value.real), float(value.imag)] for value in target_channel
                ],
                "lambda_sp": adaptive_lambda,
                "lambda_cap_sp": diagnostics["search"]["lambda_cap"],
                "lambda_candidate_points_sp": diagnostics["search"]["candidate_points"],
                "sync_confidence": 2000.0,
            }
            stages = decode_sp_stages(
                samples,
                estimate,
                cfg,
                max_sync_trials=args.max_sync_trials,
            )
            for method in ("sp_core", "sp_sync_refine"):
                stage = next(row for row in stages if row["method"] == method)
                decoded_payload = bytes.fromhex(stage["phy"]["payload_hex"])
                ok = bool(stage["phy"]["phy_crc_ok"] and decoded_payload == payload)
                counts[method] += int(ok)
                if method == "sp_sync_refine":
                    trials_used.append(int(stage["synchronization_trials"]))
        for method in ("sp_core", "sp_sync_refine"):
            ci_low, ci_high = wilson_interval(counts[method], args.trials)
            rows.append(
                {
                    "injected_start_error_samples": start_error,
                    "injected_cfo_error_bins": args.cfo_error_bins,
                    "method": method,
                    "trial_count": args.trials,
                    "success_count": counts[method],
                    "prr": counts[method] / args.trials,
                    "prr_ci_low": ci_low,
                    "prr_ci_high": ci_high,
                    "mean_sync_trials": (
                        float(np.mean(trials_used)) if method == "sp_sync_refine" else 1.0
                    ),
                }
            )
    write_csv(args.out_dir / "sync_refine_records.csv", rows)
    (args.out_dir / "sync_refine_config.json").write_text(
        json.dumps(
            {
                "schema": "sp_bounded_sync_refine_sim_v1",
                "config": asdict(cfg),
                "arguments": vars(args) | {"out_dir": str(args.out_dir)},
                "definition": (
                    "known errors are intentionally added to the true packet start/CFO "
                    "before production SP-core and bounded sync-refine are invoked"
                ),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    fig, axis = plt.subplots(figsize=(6.4, 4.0))
    for method, label in (
        ("sp_core", "SP-core"),
        ("sp_sync_refine", "SP+sync-refine"),
    ):
        selected = sorted(
            (row for row in rows if row["method"] == method),
            key=lambda row: row["injected_start_error_samples"],
        )
        axis.plot(
            [row["injected_start_error_samples"] for row in selected],
            [row["prr"] for row in selected],
            marker="o",
            label=label,
        )
    axis.set_xlabel("Injected coarse start error (samples)")
    axis.set_ylabel("PHY-CRC PRR")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.legend()
    axis.set_title(
        f"Known CFO error={args.cfo_error_bins:g} bins; bounded to {args.max_sync_trials} trials"
    )
    fig.tight_layout()
    fig.savefig(args.out_dir / "sync_refine_prr.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {args.out_dir.resolve()}")
    return 0


def read_csv_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                row["source_csv"] = str(path)
                rows.append(row)
    return rows


def aggregate_command(args: argparse.Namespace) -> int:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    raw_decision = read_csv_rows(args.decision_csv)
    decision_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    decision_keys = (
        "family",
        "rho",
        "rho_bin",
        "rho_low",
        "rho_high",
        "sir_db",
        "collision_number",
        "snr_db",
        "median_sir_db",
        "alignment",
        "method",
        "method_label",
    )
    for row in raw_decision:
        decision_groups[tuple(row.get(key, "") for key in decision_keys)].append(row)
    decision_rows: list[dict] = []
    for key, group in sorted(decision_groups.items()):
        trials = sum(int(row.get("trial_count") or 0) for row in group)
        successes = sum(int(row.get("success_count") or 0) for row in group)
        symbol_errors = sum(
            int(row.get("symbol_error_count") or 0) for row in group
        )
        symbol_count = sum(int(row.get("symbol_count") or 0) for row in group)
        output = dict(zip(decision_keys, key))
        output.update(
            {
                "trial_count": trials,
                "symbol_error_count": symbol_errors,
                "symbol_count": symbol_count,
                "ser": symbol_errors / max(1, symbol_count),
                "success_count": successes,
                "prr": successes / trials if trials else "",
                "prr_ci_low": wilson_interval(successes, trials)[0] if trials else "",
                "prr_ci_high": wilson_interval(successes, trials)[1] if trials else "",
                "seed_file_count": len(group),
            }
        )
        decision_rows.append(output)
    write_csv(args.out_dir / "decision_aggregate.csv", decision_rows)

    m2_rows = [
        row for row in decision_rows if row["family"] == "m2_trace_rho_sir"
    ]
    rho_bins = sorted({float(row["rho_bin"]) for row in m2_rows})
    sir_values = sorted({float(row["sir_db"]) for row in m2_rows})
    if m2_rows:
        fig, axis = plt.subplots(figsize=(7.2, 3.8))
        ser_heatmap(
            axis,
            m2_rows,
            x_key="rho_bin",
            x_values=rho_bins,
            y_key="sir_db",
            y_values=sir_values,
            value_key="ser",
            title="MRC symbol error rate under oracle synchronization and channel",
            x_label=r"channel coherence $\rho$",
            y_label="SIR (dB)",
        )
        axis.set_xticks(
            range(len(rho_bins)),
            [
                (
                    f"{float(next(row for row in m2_rows if float(row['rho_bin']) == value)['rho_low']):.1f}-"
                    f"{float(next(row for row in m2_rows if float(row['rho_bin']) == value)['rho_high']):.1f}"
                )
                for value in rho_bins
            ],
        )
        fig.tight_layout()
        fig.savefig(
            args.out_dir / "m2_mrc_ser_rho_sir_aggregate.pdf",
            dpi=200,
            bbox_inches="tight",
        )
        plt.close(fig)

    m3_rows = [
        row
        for row in decision_rows
        if row["family"] == "m3_trace_collision_snr"
    ]
    collision_numbers = sorted(
        {float(row["collision_number"]) for row in m3_rows}
    )
    snr_values = sorted({float(row["snr_db"]) for row in m3_rows})
    if m3_rows:
        m3_methods = [
            ("mrc", "MRC"),
            ("sp", "SP"),
            ("pcube", "PCube"),
            ("maloragw", "MaLoRaGW"),
        ]
        for method, label in m3_methods:
            selected_rows = [row for row in m3_rows if row["method"] == method]
            if not selected_rows:
                continue
            fig, axis = plt.subplots(figsize=(7.2, 3.8))
            ser_heatmap(
                axis,
                selected_rows,
                x_key="snr_db",
                x_values=snr_values,
                y_key="collision_number",
                y_values=collision_numbers,
                value_key="ser",
                title=f"{label} symbol errors with multiple concurrent packets",
                x_label="target waveform SNR before dechirp (dB)",
                y_label="concurrent packet number (including target)",
                colorbar_label="SER",
            )
            fig.tight_layout()
            fig.savefig(
                args.out_dir / f"m3_{method}_ser_collision_snr_aggregate.pdf",
                dpi=200,
                bbox_inches="tight",
            )
            plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.2))
        for axis, (method, label) in zip(axes.flat, m3_methods):
            ser_heatmap(
                axis,
                [row for row in m3_rows if row["method"] == method],
                x_key="snr_db",
                x_values=snr_values,
                y_key="collision_number",
                y_values=collision_numbers,
                value_key="ser",
                title=label,
                x_label="target waveform SNR before dechirp (dB)",
                y_label="concurrent packet number",
                colorbar_label="SER",
                annotate=False,
            )
        fig.suptitle("M3 aggregate: same trace-driven collision symbols", fontsize=11)
        fig.tight_layout()
        fig.savefig(
            args.out_dir / "m3_methods_ser_collision_snr_aggregate.pdf",
            dpi=200,
            bbox_inches="tight",
        )
        plt.close(fig)

    alignment_rows = [
        row for row in decision_rows if row["family"] == "m4_alignment_boundary"
    ]
    if alignment_rows:
        fig, axis = plt.subplots(figsize=(5.8, 3.7))
        selected = {row["alignment"]: row for row in alignment_rows}
        labels = ["asynchronous", "fully_aligned"]
        axis.bar(
            labels,
            [float(selected[label]["ser"]) for label in labels],
            color=["#2c7bb6", "#d7191c"],
        )
        axis.set_ylabel("MRC SER")
        axis.set_ylim(0.0, 1.02)
        axis.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(
            args.out_dir / "m4_alignment_boundary_aggregate.pdf",
            dpi=200,
            bbox_inches="tight",
        )
        plt.close(fig)

    if args.sync_csv:
        raw_sync = read_csv_rows(args.sync_csv)
        sync_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in raw_sync:
            sync_groups[
                (
                    row["injected_start_error_samples"],
                    row["injected_cfo_error_bins"],
                    row["method"],
                )
            ].append(row)
        sync_rows: list[dict] = []
        for (start, cfo, method), group in sorted(sync_groups.items()):
            trials = sum(int(row["trial_count"]) for row in group)
            successes = sum(int(row["success_count"]) for row in group)
            sync_rows.append(
                {
                    "injected_start_error_samples": float(start),
                    "injected_cfo_error_bins": float(cfo),
                    "method": method,
                    "trial_count": trials,
                    "success_count": successes,
                    "prr": successes / max(1, trials),
                    "prr_ci_low": wilson_interval(successes, trials)[0],
                    "prr_ci_high": wilson_interval(successes, trials)[1],
                    "seed_file_count": len(group),
                    "mean_sync_trials": float(
                        np.average(
                            [float(row["mean_sync_trials"]) for row in group],
                            weights=[int(row["trial_count"]) for row in group],
                        )
                    ),
                }
            )
        write_csv(args.out_dir / "sync_refine_aggregate.csv", sync_rows)
        fig, axis = plt.subplots(figsize=(6.4, 4.0))
        for method, label in (
            ("sp_core", "SP-core"),
            ("sp_sync_refine", "SP+sync-refine"),
        ):
            selected = sorted(
                (row for row in sync_rows if row["method"] == method),
                key=lambda row: row["injected_start_error_samples"],
            )
            axis.plot(
                [row["injected_start_error_samples"] for row in selected],
                [row["prr"] for row in selected],
                marker="o",
                label=label,
            )
        axis.set_xlabel("Injected coarse start error (samples)")
        axis.set_ylabel("PHY-CRC PRR")
        axis.set_ylim(-0.02, 1.02)
        axis.grid(alpha=0.25)
        axis.legend()
        fig.tight_layout()
        fig.savefig(args.out_dir / "sync_refine_prr_aggregate.pdf", dpi=200, bbox_inches="tight")
        plt.close(fig)
    print(f"wrote {args.out_dir.resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    decision = commands.add_parser(
        "decision", help="rho/SIR/concurrent-packet/SNR decision simulation"
    )
    decision.add_argument("--out-dir", type=Path, required=True)
    decision.add_argument("--trials", type=int, default=100)
    decision.add_argument("--seed", type=int, default=20260731)
    decision.add_argument(
        "--m2-records",
        type=Path,
        default=Path(
            "real_usrp_outputs/sp_paper_figures/preliminary_records.json"
        ),
    )
    decision.add_argument("--m2-sir-db", default="-5,-4,-3,-2,-1,0")
    decision.add_argument("--m2-rho-edges", default="0,0.2,0.6,0.8,1.0001")
    decision.add_argument(
        "--clean-packets",
        type=Path,
        default=Path("real_usrp_outputs/clean_pos_packets.npz"),
    )
    decision.add_argument("--collision-number", default="2,4,6,8,15")
    decision.add_argument(
        "--snr-db",
        default="-30,-27.5,-25,-22.5,-20,-17.5,-15",
    )
    decision.add_argument("--m3-median-sir-db", type=float, default=0.0)
    decision.add_argument("--m3-sir-jitter-db", type=float, default=1.5)
    decision.add_argument("--m3-offset-symbols", default="0,0.1,0.25,0.5,0.9")
    decision.add_argument("--m3-symbol-trials", type=int, default=1000)
    decision.add_argument("--theta-deg", type=float, default=5.0)
    decision.add_argument("--sp-gamma", type=float, default=0.05)
    decision.add_argument("--sp-lambda-max", type=float, default=4.0)
    decision.add_argument(
        "--lambda-sweep",
        default="0,0.01,0.03,0.1,0.25,0.5,1,2,4,10,30,100,300,1000",
    )
    decision.add_argument(
        "--d1-case-rho",
        default="0,0.2,0.2,0.4,0.4,0.6,0.6,0.8,0.8",
    )
    decision.add_argument(
        "--d1-case-sir-db",
        default="10,10,3,3,0,0,-3,-3,-10",
    )
    decision.add_argument(
        "--d1-oracle-rho",
        default="0,0.2,0.4,0.6,0.8,0.95",
    )
    decision.add_argument(
        "--d1-oracle-sir-db",
        default="-20,-10,0,3,6,10,20",
    )
    decision.add_argument("--d1-snr-db", type=float, default=25.0)
    decision.add_argument("--d1-collision-number", type=int, default=4)
    decision.add_argument("--d1-trials", type=int, default=100)
    decision.add_argument("--d1-oracle-trials", type=int, default=30)
    decision.add_argument("--d1-example-rho", type=float, default=0.4)
    decision.add_argument("--d1-example-sir-db", type=float, default=-10.0)
    decision.add_argument("--d1-example-snr-db", type=float, default=5.0)
    decision.add_argument(
        "--include-m4",
        action="store_true",
        help="also generate the optional fully-aligned failure-boundary figure",
    )
    decision.add_argument("--alignment-rho", type=float, default=0.3)
    decision.add_argument("--alignment-sir-db", type=float, default=-10.0)
    decision.add_argument("--alignment-snr-db", type=float, default=25.0)
    decision.set_defaults(func=decision_command)

    sync = commands.add_parser(
        "sync", help="known-error SP-core versus bounded sync-refine simulation"
    )
    sync.add_argument("--out-dir", type=Path, required=True)
    sync.add_argument("--trials", type=int, default=20)
    sync.add_argument("--seed", type=int, default=20260801)
    sync.add_argument("--start-error-samples", default="0,1,2,3")
    sync.add_argument("--cfo-error-bins", type=float, default=0.6)
    sync.add_argument("--rho", type=float, default=0.3)
    sync.add_argument("--power-gap-db", type=float, default=10.0)
    sync.add_argument("--snr-db", type=float, default=10.0)
    sync.add_argument("--interferer-offset-symbols", type=float, default=0.35)
    sync.add_argument("--target-cfo-bins", type=float, default=0.27)
    sync.add_argument("--interferer-cfo-bins", type=float, default=-0.35)
    sync.add_argument("--max-sync-trials", type=int, default=32)
    sync.set_defaults(func=sync_command)

    aggregate = commands.add_parser(
        "aggregate", help="pool multiple decision/sync simulation seed CSV files"
    )
    aggregate.add_argument("--decision-csv", type=Path, nargs="+", required=True)
    aggregate.add_argument("--sync-csv", type=Path, nargs="*", default=[])
    aggregate.add_argument("--out-dir", type=Path, required=True)
    aggregate.set_defaults(func=aggregate_command, trials=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.trials <= 0:
        raise SystemExit("--trials must be positive")
    if args.command == "decision":
        if (
            args.m3_symbol_trials <= 0
            or args.d1_trials <= 0
            or args.d1_oracle_trials <= 0
        ):
            raise SystemExit(
                "--m3-symbol-trials, --d1-trials and "
                "--d1-oracle-trials must be positive"
            )
        if args.d1_collision_number < 2:
            raise SystemExit("--d1-collision-number must be at least 2")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
