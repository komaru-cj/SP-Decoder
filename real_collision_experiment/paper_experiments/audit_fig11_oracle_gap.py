#!/usr/bin/env python3
"""Decompose Fig. 11 SER into detection, synchronization, and channel-geometry gaps."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECEIVER_DIR = ROOT / "real_collision_experiment" / "node01_sp_receiver"
for path in (ROOT, RECEIVER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_fig11_trace_runtime as fig11  # noqa: E402
from evaluate_sp_dechirp_real_pos import (  # noqa: E402
    attach_sp_reliability_and_lambda,
    sp_dechirp_decode_bins,
)
from lora_mrc_sp_core import (  # noqa: E402
    decode_packet_branch,
    fixed_mrc_branch_parameters,
)
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import (  # noqa: E402
    dc_remove_and_whiten,
)
from real_usrp_clean_packet_synth import load_extracted  # noqa: E402


LAMBDA_GRID = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)


def complex_channel(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(float(r), float(i)) for r, i in values])


def rho(a: np.ndarray, b: np.ndarray) -> float:
    denom = math.sqrt(
        float(np.vdot(a, a).real) * float(np.vdot(b, b).real)
    )
    return float(abs(np.vdot(a, b)) / max(denom, 1e-30))


def angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.degrees(np.arccos(np.clip(rho(a, b), 0.0, 1.0))))


def symbol_ser(values: list[int], truth: list[int]) -> float:
    return fig11.strict_ser([int(v) for v in values], truth)


def mrc_ser(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    truth_bins: list[int],
    *,
    start: float,
    cfo: float,
    sto: float,
    channel: np.ndarray,
) -> float:
    decoded = decode_packet_branch(
        samples,
        0,
        float(start),
        float(cfo),
        fixed_mrc_branch_parameters(channel),
        cfg,
        sto_samples=float(sto),
    )
    return symbol_ser([row.symbol_bin for row in decoded.decisions], truth_bins)


def match_estimates(
    truth_packets: list[dict], estimates: list[dict], cfg: RealCollisionLoRaConfig
) -> list[int | None]:
    pairs: list[tuple[float, int, int]] = []
    tolerance = 0.25 * float(cfg.samples_per_symbol)
    for truth_index, truth in enumerate(truth_packets):
        for estimate_index, estimate in enumerate(estimates):
            error = abs(
                fig11.aligned_start(estimate) - float(truth["start_sample"])
            )
            if error <= tolerance:
                pairs.append((error, truth_index, estimate_index))
    out: list[int | None] = [None] * len(truth_packets)
    used_truth: set[int] = set()
    used_estimates: set[int] = set()
    for _, truth_index, estimate_index in sorted(pairs):
        if truth_index in used_truth or estimate_index in used_estimates:
            continue
        out[truth_index] = estimate_index
        used_truth.add(truth_index)
        used_estimates.add(estimate_index)
    return out


def aggregate(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for order in sorted({int(row["collision_order"]) for row in rows}):
        local = [row for row in rows if int(row["collision_order"]) == order]
        detected = [row for row in local if bool(row["detected"])]

        def mean(key: str, source: list[dict]) -> float | None:
            values = [float(row[key]) for row in source if row.get(key) is not None]
            return float(np.mean(values)) if values else None

        output.append(
            {
                "collision_order": order,
                "packet_count": len(local),
                "detection_rate": len(detected) / max(1, len(local)),
                "frontend_miss_ser_floor": 1.0 - len(detected) / max(1, len(local)),
                "native_mrc_ser_with_misses": mean("native_mrc_ser", local),
                "native_mrc_conditional_ser": mean("native_mrc_ser", detected),
                "native_sp_core_ser_with_misses": mean("native_sp_core_ser", local),
                "native_sp_core_conditional_ser": mean("native_sp_core_ser", detected),
                "native_sync_oracle_h_conditional_ser": mean(
                    "native_sync_oracle_h_ser", detected
                ),
                "oracle_sync_native_h_conditional_ser": mean(
                    "oracle_sync_native_h_ser", detected
                ),
                "full_oracle_mrc_ser": mean("full_oracle_mrc_ser", local),
                "full_oracle_sp_best_lambda_ser": mean(
                    "full_oracle_sp_best_lambda_ser", local
                ),
                "median_channel_angle_error_deg": (
                    float(np.median([row["channel_angle_error_deg"] for row in detected]))
                    if detected
                    else None
                ),
                "median_abs_start_error_samples": (
                    float(np.median([abs(row["start_error_samples"]) for row in detected]))
                    if detected
                    else None
                ),
                "median_abs_coupled_cfo_residual_bins": (
                    float(
                        np.median(
                            [abs(row["coupled_cfo_residual_bins"]) for row in detected]
                        )
                    )
                    if detected
                    else None
                ),
                "median_target_max_rho": float(
                    np.median([row["target_max_rho"] for row in local])
                ),
                "fraction_target_max_rho_ge_0_9": float(
                    np.mean([row["target_max_rho"] >= 0.9 for row in local])
                ),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean-packets",
        type=Path,
        default=ROOT / "real_usrp_outputs" / "clean_pos_packets.npz",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "real_usrp_outputs" / "fig11_oracle_audit",
    )
    parser.add_argument("--collision-orders", type=fig11.parse_orders, default=(2, 4, 6, 8))
    parser.add_argument("--scenes-per-order", type=int, default=4)
    parser.add_argument("--evaluation-rate-hz", type=float, default=500_000.0)
    parser.add_argument("--min-offset-symbols", type=float, default=5.0)
    parser.add_argument("--max-offset-symbols", type=float, default=15.0)
    parser.add_argument("--min-fractional-chirp-offset", type=float, default=0.2)
    parser.add_argument("--sp-scan-phase-count", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--cfo-min", type=float, default=-32.0)
    parser.add_argument("--cfo-max", type=float, default=32.0)
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260801)
    args = parser.parse_args()

    packets, metadata = load_extracted(args.clean_packets.resolve())
    source_cfg = metadata["config"]
    cfg = RealCollisionLoRaConfig(
        sf=int(source_cfg.get("sf", 10)),
        bw_hz=float(source_cfg.get("bw_hz", 125_000.0)),
        sample_rate_hz=float(args.evaluation_rate_hz),
        cr=int(source_cfg.get("cr", 1)),
        preamble_len=int(source_cfg.get("preamble_len", 8)),
        sync_word=int(source_cfg.get("sync_word", 0x12)),
        payload_len=int(source_cfg.get("payload_len", 32)),
        crc_on=bool(source_cfg.get("crc_on", True)),
        implicit_header=bool(source_cfg.get("implicit_header", True)),
        ldro=bool(source_cfg.get("ldro", False)),
    )
    packets = fig11.resample_packet_bank(
        packets, float(source_cfg["sample_rate_hz"]), cfg.sample_rate_hz
    )
    packet_meta = list(metadata["packets"])
    references = fig11.build_in_memory_references(packets, packet_meta, cfg)
    rng = np.random.default_rng(int(args.seed))
    rows: list[dict] = []

    for order in args.collision_orders:
        for scene_index in range(1, args.scenes_per_order + 1):
            selected = rng.choice(len(packets), size=order, replace=False)
            scene, truth_packets, _, _ = fig11.build_scene(
                packets,
                packet_meta,
                cfg,
                selected,
                rng,
                min_offset_symbols=args.min_offset_symbols,
                max_offset_symbols=args.max_offset_symbols,
                min_fractional_chirp_offset=args.min_fractional_chirp_offset,
            )
            white, whitener, sigma2_time, _ = dc_remove_and_whiten(
                scene,
                noise_samples=max(
                    128, int(round(0.75 * cfg.samples_per_symbol))
                ),
            )
            estimates = fig11.current_sp_frontend(
                white,
                cfg,
                max_candidates=max(args.max_candidates, 3 * order),
                threshold=args.threshold,
                cfo_min=args.cfo_min,
                cfo_max=args.cfo_max,
                scan_phase_count=args.sp_scan_phase_count,
            )
            configured = attach_sp_reliability_and_lambda(
                white,
                [dict(item) for item in estimates],
                cfg,
                noise_sigma2=max(float(cfg.m) * float(sigma2_time), 1e-12),
                gamma=0.05,
                max_lambda=4.0,
            )
            matches = match_estimates(truth_packets, estimates, cfg)

            oracle_channels: list[np.ndarray] = []
            for source_index in selected:
                h = complex_channel(references[int(source_index)].channel)
                scale = 1.0 / max(
                    math.sqrt(float(np.mean(np.abs(packets[int(source_index)]) ** 2))),
                    1e-12,
                )
                oracle_channels.append(whitener @ (h * scale))

            for target_index, (truth, oracle_h) in enumerate(
                zip(truth_packets, oracle_channels)
            ):
                source_index = int(truth["source_packet_index"])
                reference = references[source_index]
                truth_bins = [int(value) for value in reference.symbol_bins]
                max_rho = max(
                    (
                        rho(oracle_h, oracle_channels[other])
                        for other in range(order)
                        if other != target_index
                    ),
                    default=0.0,
                )
                oracle_mrc = mrc_ser(
                    white,
                    cfg,
                    truth_bins,
                    start=float(truth["start_sample"]),
                    cfo=float(reference.cfo_bins),
                    sto=0.0,
                    channel=oracle_h,
                )
                oracle_sp_values = []
                for lam in LAMBDA_GRID:
                    decoded = sp_dechirp_decode_bins(
                        white,
                        float(truth["start_sample"]),
                        float(reference.cfo_bins),
                        0.0,
                        oracle_h,
                        cfg,
                        truth_bins,
                        lam=float(lam),
                    )
                    oracle_sp_values.append(
                        (symbol_ser(decoded.bins, truth_bins), float(lam))
                    )
                oracle_sp_ser, oracle_best_lambda = min(oracle_sp_values)

                estimate_index = matches[target_index]
                row = {
                    "collision_order": int(order),
                    "scene_index": int(scene_index),
                    "truth_packet_index": int(target_index),
                    "source_packet_index": source_index,
                    "detected": estimate_index is not None,
                    "target_max_rho": float(max_rho),
                    "full_oracle_mrc_ser": float(oracle_mrc),
                    "full_oracle_sp_best_lambda_ser": float(oracle_sp_ser),
                    "full_oracle_sp_best_lambda": float(oracle_best_lambda),
                    "native_mrc_ser": 1.0,
                    "native_sp_core_ser": 1.0,
                    "native_sync_oracle_h_ser": None,
                    "oracle_sync_native_h_ser": None,
                    "start_error_samples": None,
                    "cfo_error_bins": None,
                    "coupled_cfo_residual_bins": None,
                    "channel_angle_error_deg": None,
                }
                if estimate_index is not None:
                    estimate = estimates[int(estimate_index)]
                    configured_estimate = configured[int(estimate_index)]
                    aligned = fig11.aligned_start(estimate)
                    cfo = float(
                        estimate.get(
                            "continuous_cfo_bins", estimate["cfo_bins"]
                        )
                    )
                    sto = float(estimate.get("sto_samples", 0.0))
                    estimated_h = complex_channel(estimate["channel"])
                    native_mrc = mrc_ser(
                        white,
                        cfg,
                        truth_bins,
                        start=float(estimate["start_sample"]),
                        cfo=cfo,
                        sto=sto,
                        channel=estimated_h,
                    )
                    oracle_h_native_sync = mrc_ser(
                        white,
                        cfg,
                        truth_bins,
                        start=float(estimate["start_sample"]),
                        cfo=cfo,
                        sto=sto,
                        channel=oracle_h,
                    )
                    oracle_sync_native_h = mrc_ser(
                        white,
                        cfg,
                        truth_bins,
                        start=float(truth["start_sample"]),
                        cfo=float(reference.cfo_bins),
                        sto=0.0,
                        channel=estimated_h,
                    )
                    h_sp = complex_channel(
                        configured_estimate.get(
                            "channel_sp", configured_estimate["channel"]
                        )
                    )
                    sp_core = sp_dechirp_decode_bins(
                        white,
                        float(configured_estimate["start_sample"]),
                        float(configured_estimate["cfo_bins_sp"]),
                        float(configured_estimate.get("sto_samples_sp", 0.0)),
                        h_sp,
                        cfg,
                        truth_bins,
                        lam=float(configured_estimate["lambda_sp"]),
                    )
                    start_error = aligned - float(truth["start_sample"])
                    cfo_error = cfo - float(reference.cfo_bins)
                    row.update(
                        {
                            "native_mrc_ser": float(native_mrc),
                            "native_sp_core_ser": float(
                                symbol_ser(sp_core.bins, truth_bins)
                            ),
                            "native_sync_oracle_h_ser": float(
                                oracle_h_native_sync
                            ),
                            "oracle_sync_native_h_ser": float(
                                oracle_sync_native_h
                            ),
                            "start_error_samples": float(start_error),
                            "cfo_error_bins": float(cfo_error),
                            "coupled_cfo_residual_bins": float(
                                cfo_error - start_error / float(cfg.osr)
                            ),
                            "channel_angle_error_deg": float(
                                angle_deg(estimated_h, oracle_h)
                            ),
                        }
                    )
                rows.append(row)

            # Fig. 11 shuffles decoder order after constructing every scene;
            # replay it so the RNG state, and hence subsequent scenes, is exact.
            method_order = list(fig11.METHODS)
            rng.shuffle(method_order)
            print(
                f"FIG11_ORACLE_AUDIT order={order} scene={scene_index}/{args.scenes_per_order}",
                flush=True,
            )

    summary = aggregate(rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "fig11_oracle_gap_packets.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (args.out_dir / "fig11_oracle_gap_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    (args.out_dir / "fig11_oracle_gap_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"FIG11_ORACLE_AUDIT_DONE out={args.out_dir.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
