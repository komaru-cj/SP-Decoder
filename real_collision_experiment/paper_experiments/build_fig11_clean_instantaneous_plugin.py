#!/usr/bin/env python3
"""Build clean-packet instantaneous-collision Fig. 11 with a PCube -> SP cascade.

This is a trace-driven experiment: every synthesized packet retains the
dual-receiver spatial direction and CFO measured from a clean USRP capture,
while an explicit-header CRC-valid LoRa frame provides a known payload
identity.  Each scene uses one packet per measured position.  Starts are
distributed over a span shorter than one full frame, so that the final packet
starts before the first packet ends (and all packets are simultaneously live
at that instant).

The comparison is deliberately narrow:

* PCube: its native PDoA-clustered payload decoder;
* SP-Decoder: packet-level signed projection with its fixed global constants;
* PCube+SP: PCube passes only its PDoA-clustered FFT-bin set to SP, whose
  packet-level channel and lambda are otherwise unchanged.

No payload truth, CRC outcome, source identity, or scheduled start is used in
candidate detection, PDoA clustering, or bin selection.  These values are
used only after decoding to calculate packet reception ratio (PRR).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECEIVER_DIR = ROOT / "real_collision_experiment" / "node01_sp_receiver"
PAPER_DIR = ROOT / "real_collision_experiment" / "paper_experiments"
for path in (ROOT, RECEIVER_DIR, PAPER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from compare.real_packet_decoders import PaperComparisonContext  # noqa: E402
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda  # noqa: E402
from lora_mrc_sp_core import (  # noqa: E402
    compensate_symbol_window,
    instantaneous_chirp,
    lora_symbol_fft,
)
from lora_phy_decode import decode_payload_from_symbol_bins  # noqa: E402
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sp_node01_receiver import (  # noqa: E402
    decode_sp_stages,
)
from real_usrp_clean_packet_synth import load_extracted  # noqa: E402
from build_fig11_trace_runtime import (  # noqa: E402
    build_scene,
    build_trace_channel_known_phy_bank,
    maximum_preamble_overlap,
    prepare_receiver_inputs,
    resample_packet_bank,
    select_channel_packets,
    selected_position_keys,
)


METHODS = ("pcube", "sp", "pcube_sp")
METHOD_LABELS = {
    "pcube": "PCube",
    "sp": "SP-Decoder",
    "pcube_sp": "PCube+SP",
}
METHOD_COLORS = {
    "pcube": "#F4A261",
    "sp": "#159D8A",
    "pcube_sp": "#6C5CE7",
}
EPS = 1e-30
PCUBE_CLUSTER_RADIUS_RAD = 0.5


def parse_orders(value: str) -> tuple[int, ...]:
    orders = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not orders or any(order < 2 for order in orders):
        raise argparse.ArgumentTypeError("orders must be comma-separated integers >= 2")
    return orders


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def complex_pairs(values: list[list[float]]) -> np.ndarray:
    return np.asarray(
        [complex(float(real), float(imag)) for real, imag in values],
        dtype=np.complex128,
    )


def local_peaks(power: np.ndarray) -> np.ndarray:
    values = np.asarray(power, dtype=np.float64)
    floor = float(np.median(values)) + EPS
    mask = (
        (values >= np.roll(values, 1))
        & (values >= np.roll(values, -1))
        & (values >= 6.0 * floor)
        & (values >= 0.01 * float(np.max(values)))
    )
    peaks = np.flatnonzero(mask)
    if peaks.size == 0:
        return np.asarray([int(np.argmax(values))], dtype=np.int64)
    if peaks.size > 64:
        peaks = peaks[np.argsort(values[peaks])[-64:]]
    return peaks.astype(np.int64, copy=False)


def phase_distance(values: np.ndarray, reference: float) -> np.ndarray:
    return np.abs(np.angle(np.exp(1j * (np.asarray(values) - float(reference)))))


def payload_spectra(
    samples: np.ndarray,
    estimate: dict,
    cfg: RealCollisionLoRaConfig,
    symbol_index: int,
) -> np.ndarray:
    symbol_start = float(estimate["start_sample"]) + (
        float(cfg.payload_start_symbols) + int(symbol_index)
    ) * float(cfg.samples_per_symbol)
    cfo = float(
        estimate.get(
            "cfo_bins_sp",
            estimate.get("continuous_cfo_bins", estimate["cfo_bins"]),
        )
    )
    sto = float(estimate.get("sto_samples_sp", estimate.get("sto_samples", 0.0)))
    window = compensate_symbol_window(samples, symbol_start, cfo, cfg, sto_samples=sto)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    return np.vstack([lora_symbol_fft(row * downchirp, cfg) for row in window])


def pcube_sp_decode(
    *,
    physical: np.ndarray,
    white: np.ndarray,
    estimate: dict,
    configured_sp_estimate: dict,
    target_pdoa: float,
    cfg: RealCollisionLoRaConfig,
) -> dict:
    """Run SP only inside the PDoA cluster exposed by PCube.

    This function is the plug-in boundary.  PCube contributes a per-symbol
    allowed-bin set; SP retains its own pre-payload channel and packet-level
    lambda.  In particular, it does not use PCube's payload decision, CRC, or
    any source/truth metadata.
    """

    channel = complex_pairs(
        configured_sp_estimate.get("channel_sp", configured_sp_estimate["channel"])
    )
    norm = math.sqrt(float(np.vdot(channel, channel).real))
    if channel.size != 2 or norm <= EPS:
        raise ValueError("PCube+SP requires a nonzero two-Rx SP channel")
    target = channel / norm
    orthogonal = np.asarray(
        [-np.conj(target[1]), np.conj(target[0])], dtype=np.complex128
    )
    lam = float(configured_sp_estimate.get("lambda_sp", 0.0))
    bins: list[int] = []
    margins: list[float] = []
    cluster_sizes: list[int] = []
    fallback_count = 0
    for symbol_index in range(int(cfg.payload_symbol_count)):
        pcube_spectra = payload_spectra(physical, estimate, cfg, symbol_index)
        energy = np.sum(np.abs(pcube_spectra) ** 2, axis=0)
        candidates = local_peaks(energy)
        pair_phase = np.angle(
            pcube_spectra[0, candidates] * np.conj(pcube_spectra[1, candidates])
        )
        distances = phase_distance(pair_phase, target_pdoa)
        allowed = candidates[distances <= PCUBE_CLUSTER_RADIUS_RAD]
        if allowed.size == 0:
            allowed = np.asarray(
                [int(candidates[int(np.argmin(distances))])], dtype=np.int64
            )
            fallback_count += 1
        cluster_sizes.append(int(allowed.size))

        sp_spectra = payload_spectra(white, configured_sp_estimate, cfg, symbol_index)
        projected = np.conj(target) @ sp_spectra[:2]
        residual = np.conj(orthogonal) @ sp_spectra[:2]
        score = (np.abs(projected) ** 2 - lam * np.abs(residual) ** 2).real
        local = int(np.argmax(score[allowed]))
        chosen = int(allowed[local])
        bins.append(chosen)
        remaining = np.delete(score[allowed], local)
        margins.append(
            float(score[chosen] - np.max(remaining))
            if remaining.size
            else float(score[chosen])
        )
    phy = decode_payload_from_symbol_bins(bins, cfg)
    return {
        "method": "pcube_sp",
        "symbol_bins": [int(value) for value in bins],
        "mean_symbol_margin": float(np.mean(margins)) if margins else 0.0,
        "phy": {
            "payload_hex": phy.payload.hex(),
            "phy_crc_ok": bool(phy.phy_crc_ok),
            "corrected_codewords": int(phy.corrected_codewords),
            "uncorrected_codewords": int(phy.uncorrected_codewords),
            "status": phy.status,
        },
        "paper_diagnostics": {
            "cascade_interface": "PCube PDoA cluster bins -> SP fixed-lambda score",
            "pcube_target_pdoa_rad": float(target_pdoa),
            "pcube_cluster_radius_rad": PCUBE_CLUSTER_RADIUS_RAD,
            "mean_pcube_cluster_bin_count": float(np.mean(cluster_sizes)),
            "pcube_empty_cluster_fallback_count": int(fallback_count),
            "sp_lambda_source": "packet-level pre-payload configuration",
            "crc_or_truth_used_for_cluster_or_bin_selection": False,
        },
    }


def decode_scene(
    prepared: dict,
    cfg: RealCollisionLoRaConfig,
    *,
    sp_sync_max_trials: int,
) -> tuple[dict[str, list[dict]], dict[str, float]]:
    """Decode each common SP candidate by PCube, SP, and the cascade."""

    pcube_estimates = [dict(item) for item in prepared["estimates"]["pcube"]]
    for index, estimate in enumerate(pcube_estimates):
        estimate["_comparison_candidate_index"] = int(index)
    pcube_setup_started = time.perf_counter_ns()
    context = PaperComparisonContext(
        prepared["physical"], pcube_estimates, cfg, frontend_method="pcube"
    )
    pcube_setup_ms = (time.perf_counter_ns() - pcube_setup_started) / 1_000_000.0
    pcube_payload_started = time.perf_counter_ns()
    pcube_results = [context.decode_pcube(estimate) for estimate in pcube_estimates]
    pcube_elapsed_ms = pcube_setup_ms + (
        (time.perf_counter_ns() - pcube_payload_started) / 1_000_000.0
    )
    decoded_pcube = [
        {"estimate": estimate, "result": result}
        for estimate, result in zip(pcube_estimates, pcube_results)
    ]

    sp_config_started = time.perf_counter_ns()
    sp_estimates = attach_sp_reliability_and_lambda(
        prepared["white"],
        [dict(item) for item in prepared["estimates"]["sp_sync_refine"]],
        cfg,
        noise_sigma2=float(prepared["noise_sigma2_fft"]),
        gamma=0.05,
        max_lambda=4.0,
    )
    sp_config_ms = (time.perf_counter_ns() - sp_config_started) / 1_000_000.0
    sp_started = time.perf_counter_ns()
    sp_results: list[dict] = []
    for estimate in sp_estimates:
        stages = decode_sp_stages(
            prepared["white"], estimate, cfg, max_sync_trials=sp_sync_max_trials
        )
        sp_results.append(next(row for row in stages if row["method"] == "sp_sync_refine"))
    sp_elapsed_ms = (time.perf_counter_ns() - sp_started) / 1_000_000.0
    decoded_sp = [
        {"estimate": estimate, "result": result}
        for estimate, result in zip(sp_estimates, sp_results)
    ]

    if len(pcube_estimates) != len(sp_estimates):
        raise RuntimeError("shared PCube/SP candidate lists unexpectedly differ")
    cascade_started = time.perf_counter_ns()
    cascade_results: list[dict] = []
    for pcube_estimate, pcube_result, sp_estimate in zip(
        pcube_estimates, pcube_results, sp_estimates
    ):
        target_pdoa = float(pcube_result["paper_diagnostics"]["target_pdoa_rad"])
        cascade_results.append(
            pcube_sp_decode(
                physical=prepared["physical"],
                white=prepared["white"],
                estimate=pcube_estimate,
                configured_sp_estimate=sp_estimate,
                target_pdoa=target_pdoa,
                cfg=cfg,
            )
        )
    cascade_elapsed_ms = (time.perf_counter_ns() - cascade_started) / 1_000_000.0
    decoded_cascade = [
        {"estimate": estimate, "result": result}
        for estimate, result in zip(sp_estimates, cascade_results)
    ]
    return (
        {"pcube": decoded_pcube, "sp": decoded_sp, "pcube_sp": decoded_cascade},
        {
            "pcube": float(pcube_elapsed_ms),
            "sp": float(sp_config_ms + sp_elapsed_ms),
            # The cascade pays for only PCube's preamble PDoA-cluster setup,
            # rather than PCube's discarded payload decision, plus its SP pass.
            "pcube_sp": float(pcube_setup_ms + sp_config_ms + cascade_elapsed_ms),
        },
    )


def aligned_start(estimate: dict) -> float:
    return float(estimate["start_sample"]) + float(
        estimate.get("sto_samples_sp", estimate.get("sto_samples", 0.0))
    )


def match_truth_packets(
    truth_packets: list[dict], decoded: list[dict], cfg: RealCollisionLoRaConfig
) -> list[dict | None]:
    pairs: list[tuple[float, int, int]] = []
    for truth_index, truth in enumerate(truth_packets):
        for decoded_index, row in enumerate(decoded):
            error = abs(aligned_start(row["estimate"]) - float(truth["start_sample"]))
            if error <= 0.25 * float(cfg.samples_per_symbol):
                pairs.append((float(error), truth_index, decoded_index))
    matched: list[dict | None] = [None] * len(truth_packets)
    used_truth: set[int] = set()
    used_decoded: set[int] = set()
    for _, truth_index, decoded_index in sorted(pairs):
        if truth_index in used_truth or decoded_index in used_decoded:
            continue
        matched[truth_index] = decoded[decoded_index]
        used_truth.add(truth_index)
        used_decoded.add(decoded_index)
    return matched


def successful_packets(
    truth_packets: list[dict],
    decoded: list[dict],
    references: dict,
    cfg: RealCollisionLoRaConfig,
) -> tuple[int, int, list[dict]]:
    """Count CRC-closed, identity-correct packets after blind decoding."""

    rows: list[dict] = []
    matched = match_truth_packets(truth_packets, decoded, cfg)
    for truth, candidate in zip(truth_packets, matched):
        reference = references[int(truth["source_packet_index"])]
        expected_phy = decode_payload_from_symbol_bins(reference.symbol_bins, cfg)
        expected_payload_hex = expected_phy.payload.hex()
        if candidate is None:
            rows.append(
                {
                    "truth_packet_index": int(truth["packet_index"]),
                    "source_packet_index": int(truth["source_packet_index"]),
                    "status": "frontend_miss",
                    "success": False,
                }
            )
            continue
        result = candidate["result"]
        phy = result.get("phy", {})
        success = bool(phy.get("phy_crc_ok", False)) and (
            str(phy.get("payload_hex", "")) == expected_payload_hex
        )
        rows.append(
            {
                "truth_packet_index": int(truth["packet_index"]),
                "source_packet_index": int(truth["source_packet_index"]),
                "status": "crc_closed_identity_match" if success else "decode_or_identity_failure",
                "success": bool(success),
                "detected_start_sample": float(aligned_start(candidate["estimate"])),
            }
        )
    return int(sum(bool(row["success"]) for row in rows)), len(rows), rows


def bootstrap_mean(values: list[float], rng: np.random.Generator) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(array))
    if array.size < 2:
        return mean, mean, mean
    sampled = rng.choice(array, size=(20_000, array.size), replace=True)
    low, high = np.quantile(np.mean(sampled, axis=1), [0.025, 0.975])
    return mean, float(low), float(high)


def summarize(rows: list[dict], orders: tuple[int, ...], seed: int) -> list[dict]:
    summary: list[dict] = []
    rng = np.random.default_rng(seed ^ 0x5A5A)
    for order in orders:
        for method in METHODS:
            selected = [
                row
                for row in rows
                if int(row["collision_order"]) == int(order)
                and row["method"] == method
            ]
            successes = sum(int(row["successful_packet_count"]) for row in selected)
            expected = sum(int(row["expected_packet_count"]) for row in selected)
            prrs = [float(row["prr"]) for row in selected]
            times = [float(row["decode_time_per_candidate_ms"]) for row in selected]
            prr_mean, prr_low, prr_high = bootstrap_mean(prrs, rng)
            time_mean, time_low, time_high = bootstrap_mean(times, rng)
            summary.append(
                {
                    "collision_order": int(order),
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "scene_count": int(len(selected)),
                    "successful_packet_count": int(successes),
                    "expected_packet_count": int(expected),
                    "prr_pooled": float(successes / expected) if expected else float("nan"),
                    "prr_mean": prr_mean,
                    "prr_ci95_low": prr_low,
                    "prr_ci95_high": prr_high,
                    "decode_time_per_candidate_mean_ms": time_mean,
                    "decode_time_per_candidate_ci95_low_ms": time_low,
                    "decode_time_per_candidate_ci95_high_ms": time_high,
                }
            )
    return summary


def plot(summary: list[dict], orders: tuple[int, ...], out_prefix: Path, *, snr_db: float) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.0))
    x = np.arange(len(orders), dtype=np.float64)
    width = 0.23
    for method_index, method in enumerate(METHODS):
        values = {
            int(row["collision_order"]): row
            for row in summary
            if row["method"] == method
        }
        positions = x + (method_index - 1) * width
        times = np.asarray(
            [float(values[order]["decode_time_per_candidate_mean_ms"]) for order in orders]
        )
        time_low = np.asarray(
            [float(values[order]["decode_time_per_candidate_ci95_low_ms"]) for order in orders]
        )
        time_high = np.asarray(
            [float(values[order]["decode_time_per_candidate_ci95_high_ms"]) for order in orders]
        )
        axes[0].bar(
            positions,
            times,
            width,
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
            yerr=np.vstack([times - time_low, time_high - times]),
            capsize=2.0,
        )
        prr = np.asarray([float(values[order]["prr_mean"]) for order in orders])
        prr_low = np.asarray([float(values[order]["prr_ci95_low"]) for order in orders])
        prr_high = np.asarray([float(values[order]["prr_ci95_high"]) for order in orders])
        bars = axes[1].bar(
            positions,
            prr,
            width,
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
            yerr=np.vstack([prr - prr_low, prr_high - prr]),
            capsize=2.0,
        )
        for bar, value in zip(bars, prr):
            axes[1].text(
                bar.get_x() + bar.get_width() / 2.0,
                min(1.105, value + 0.025 + method_index * 0.025),
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    for axis in axes:
        axis.set_xticks(x, [str(order) for order in orders])
        axis.set_xlabel("Collision order (packets)")
        axis.grid(axis="y", color="#d9d9d9", linewidth=0.8)
        axis.set_axisbelow(True)
    axes[0].set_ylabel("Estimation + payload decoding (ms / candidate)")
    axes[0].set_title("(a) Decoder work")
    axes[1].set_ylabel("PRR")
    axes[1].set_ylim(0.0, 1.12)
    axes[1].set_title("(b) Packet reception ratio")
    handles, labels = axes[1].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=3,
        frameon=True,
    )
    figure.suptitle(
        f"Trace-driven dense instantaneous collisions (per-packet SNR = {snr_db:g} dB)",
        fontweight="bold",
        y=0.995,
    )
    figure.subplots_adjust(left=0.10, right=0.98, bottom=0.17, top=0.78, wspace=0.10)
    for suffix in (".png", ".pdf"):
        figure.savefig(out_prefix.with_suffix(suffix), dpi=240)
    plt.close(figure)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean-packets",
        type=Path,
        default=ROOT / "real_usrp_outputs/clean_pos_packets.npz",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "real_usrp_outputs/fig11_clean_instantaneous_plugin",
    )
    parser.add_argument("--orders", type=parse_orders, default=(2, 4, 6, 8, 10))
    parser.add_argument("--scenes-per-order", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--payload-seed", type=int, default=20260811)
    parser.add_argument("--scene-snr-db", type=float, default=20.0)
    parser.add_argument("--evaluation-rate-hz", type=float, default=500_000.0)
    parser.add_argument("--adjacent-start-spacing-symbols", type=float, default=4.5)
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--cfo-min", type=float, default=-32.0)
    parser.add_argument("--cfo-max", type=float, default=32.0)
    parser.add_argument("--sp-scan-phase-count", type=int, default=8)
    parser.add_argument("--sp-sync-max-trials", type=int, default=32)
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="redraw the existing summary without recomputing collision scenes",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.scenes_per_order < 1:
        raise SystemExit("--scenes-per-order must be positive")
    if args.sp_scan_phase_count < 1:
        raise SystemExit("--sp-scan-phase-count must be positive")
    if args.adjacent_start_spacing_symbols <= 0.0:
        raise SystemExit("--adjacent-start-spacing-symbols must be positive")
    args.clean_packets = args.clean_packets.resolve()
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.plot_only:
        summary_path = args.out_dir / "fig11_clean_instantaneous_summary.csv"
        with summary_path.open("r", encoding="utf-8", newline="") as stream:
            summary = list(csv.DictReader(stream))
        plot(
            summary,
            args.orders,
            args.out_dir / "fig11_clean_instantaneous_time_prr",
            snr_db=float(args.scene_snr_db),
        )
        print(f"FIG11_CLEAN_INSTANT_PLOT_ONLY out={args.out_dir}")
        return 0

    measured_packets, metadata = load_extracted(args.clean_packets)
    packet_meta = list(metadata["packets"])
    source_cfg = metadata.get("config", {})
    cfg = RealCollisionLoRaConfig(
        sf=int(source_cfg.get("sf", 10)),
        bw_hz=float(source_cfg.get("bw_hz", 125_000.0)),
        sample_rate_hz=float(args.evaluation_rate_hz),
        cr=1,
        preamble_len=8,
        sync_word=0x34,
        # 25-byte explicit-header/CRC payload yields the clean corpus's exact
        # 50.25-symbol frame duration at SF10/BW125/CR4/5.
        payload_len=25,
        crc_on=True,
        implicit_header=False,
        ldro=False,
    )
    source_rate_hz = float(source_cfg.get("sample_rate_hz", 1_000_000.0))
    converted = resample_packet_bank(measured_packets, source_rate_hz, cfg.sample_rate_hz)
    packets, references = build_trace_channel_known_phy_bank(
        converted, packet_meta, cfg, payload_seed=args.payload_seed
    )
    positions = {
        Path(str(item.get("source_file", f"source_{index}"))).name
        for index, item in enumerate(packet_meta)
    }
    if max(args.orders) > len(positions):
        raise SystemExit(
            f"requested {max(args.orders)} distinct positions, but corpus has only {len(positions)}"
        )
    # A full frame is 50.25 symbols under this fixed explicit-header PHY.
    maximum_start_span = float(args.adjacent_start_spacing_symbols) * (max(args.orders) - 1)
    if maximum_start_span >= float(cfg.frame_symbols):
        raise SystemExit(
            "the latest packet would not start before the earliest packet ends; "
            "decrease --adjacent-start-spacing-symbols"
        )

    rng = np.random.default_rng(args.seed)
    rows: list[dict] = []
    packet_rows: list[dict] = []
    scene_audit: list[dict] = []
    for order in args.orders:
        for scene_index in range(1, args.scenes_per_order + 1):
            selected = select_channel_packets(packet_meta, int(order), rng)
            position_keys = selected_position_keys(packet_meta, selected)
            if len(set(position_keys)) != int(order):
                raise RuntimeError("scene re-used a position despite enough distinct positions")
            # ``build_scene`` represents start positions within +/-max_offset.
            # Its construction therefore needs half of the full first-to-last
            # span here; using the 4.5-symbol adjacent spacing directly would
            # silently collapse every order >= 4 into a roughly 9-symbol span.
            scene_max_offset_symbols = (
                0.5
                * float(args.adjacent_start_spacing_symbols)
                * max(0, int(order) - 1)
                + 0.125
            )
            scene, truth_packets, offsets, _ = build_scene(
                packets,
                packet_meta,
                cfg,
                selected,
                rng,
                min_offset_symbols=0.2,
                max_offset_symbols=scene_max_offset_symbols,
                min_fractional_chirp_offset=0.2,
                stagger_high_order_preambles=True,
                uniform_stagger_spacing_symbols=float(args.adjacent_start_spacing_symbols),
            )
            starts = [float(packet["start_sample"]) for packet in truth_packets]
            start_span_symbols = (max(starts) - min(starts)) / float(cfg.samples_per_symbol)
            if not start_span_symbols < float(cfg.frame_symbols):
                raise RuntimeError("instantaneous-all-packet overlap invariant failed")
            noise_rng = np.random.default_rng(
                int(args.seed) ^ (int(order) << 20) ^ (int(scene_index) * 0x45D9F3B)
            )
            noise_power = 10.0 ** (-float(args.scene_snr_db) / 10.0)
            noise = (
                noise_rng.normal(size=scene.shape) + 1j * noise_rng.normal(size=scene.shape)
            ) * math.sqrt(noise_power / 2.0)
            scene = (scene + noise.astype(np.complex64)).astype(np.complex64)
            prepared = prepare_receiver_inputs(
                scene,
                cfg,
                max_candidates=max(3 * int(order), int(order) + 8),
                candidates_per_window=max(2 * int(order), 16),
                threshold=float(args.threshold),
                cfo_min=float(args.cfo_min),
                cfo_max=float(args.cfo_max),
                sp_scan_phase_count=int(args.sp_scan_phase_count),
            )
            decoded_by_method, elapsed_ms = decode_scene(
                prepared, cfg, sp_sync_max_trials=int(args.sp_sync_max_trials)
            )
            max_preamble_overlap = maximum_preamble_overlap(offsets, float(cfg.preamble_len))
            scene_audit.append(
                {
                    "collision_order": int(order),
                    "scene_index": int(scene_index),
                    "source_indices": [int(value) for value in selected],
                    "source_position_keys": position_keys,
                    "distinct_source_position_count": int(len(set(position_keys))),
                    "offset_symbols": [float(value) for value in offsets],
                    "start_span_symbols": float(start_span_symbols),
                    "frame_symbols": float(cfg.frame_symbols),
                    "latest_starts_before_first_ends": True,
                    "maximum_simultaneous_full_frames": int(order),
                    "maximum_simultaneous_preambles": int(max_preamble_overlap),
                }
            )
            for method in METHODS:
                successes, expected, per_packet = successful_packets(
                    truth_packets, decoded_by_method[method], references, cfg
                )
                decoded_count = len(decoded_by_method[method])
                rows.append(
                    {
                        "collision_order": int(order),
                        "scene_index": int(scene_index),
                        "method": method,
                        "method_label": METHOD_LABELS[method],
                        "expected_packet_count": int(expected),
                        "successful_packet_count": int(successes),
                        "prr": float(successes / expected),
                        "decoder_candidate_count": int(decoded_count),
                        "decode_time_total_ms": float(elapsed_ms[method]),
                        "decode_time_per_candidate_ms": float(
                            elapsed_ms[method] / max(1, decoded_count)
                        ),
                        "distinct_source_position_count": int(len(set(position_keys))),
                        "start_span_symbols": float(start_span_symbols),
                        "maximum_simultaneous_full_frames": int(order),
                        "maximum_simultaneous_preambles": int(max_preamble_overlap),
                    }
                )
                for packet in per_packet:
                    packet_rows.append(
                        {
                            **packet,
                            "collision_order": int(order),
                            "scene_index": int(scene_index),
                            "method": method,
                            "method_label": METHOD_LABELS[method],
                        }
                    )
            print(
                f"FIG11_CLEAN_INSTANT order={order} scene={scene_index}/{args.scenes_per_order}",
                flush=True,
            )

    summary = summarize(rows, args.orders, args.seed)
    write_csv(args.out_dir / "fig11_clean_instantaneous_raw.csv", rows)
    write_csv(args.out_dir / "fig11_clean_instantaneous_packet_audit.csv", packet_rows)
    write_csv(args.out_dir / "fig11_clean_instantaneous_summary.csv", summary)
    plot(
        summary,
        args.orders,
        args.out_dir / "fig11_clean_instantaneous_time_prr",
        snr_db=float(args.scene_snr_db),
    )
    audit = {
        "schema": "fig11_clean_packet_instantaneous_collision_v1",
        "source_clean_packet_corpus": str(args.clean_packets),
        "source_sha256": sha256_file(args.clean_packets),
        "measured_clean_packet_count": int(len(measured_packets)),
        "distinct_measured_position_count": int(len(positions)),
        "trace_driven_known_phy": True,
        "source_packet_role": "measured dual-Rx direction and CFO",
        "constructed_phy_role": "explicit-header CRC-valid LoRa payload identity",
        "global_sp_constants": {"gamma": 0.05, "lambda_max": 4.0},
        "pcube_sp_interface": (
            "PCube PDoA-clustered payload FFT-bin set is the only PCube output "
            "passed to SP; SP keeps its original packet-level channel and lambda"
        ),
        "prr_definition": (
            "unique start-matched packet whose decoded PHY CRC closes and whose "
            "payload equals the evaluation-only transmitted payload, divided by "
            "the number of constructed packets"
        ),
        "orders": list(args.orders),
        "scenes_per_order": int(args.scenes_per_order),
        "per_packet_snr_db": float(args.scene_snr_db),
        "evaluation_phy": {
            "sf": int(cfg.sf),
            "bandwidth_hz": float(cfg.bw_hz),
            "sample_rate_hz": float(cfg.sample_rate_hz),
            "frame_symbols": float(cfg.frame_symbols),
            "payload_bytes": int(cfg.payload_len),
            "crc_on": bool(cfg.crc_on),
        },
        "instantaneous_collision_rule": (
            "all packet starts are placed approximately 4.5 symbols apart with "
            "sub-symbol jitter; start span is strictly shorter than one complete "
            "frame, therefore all N packets overlap when the latest starts"
        ),
        "scenes": scene_audit,
        "summary": summary,
    }
    (args.out_dir / "fig11_clean_instantaneous_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"FIG11_CLEAN_INSTANT_DONE scenes={len(scene_audit)} out={args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
