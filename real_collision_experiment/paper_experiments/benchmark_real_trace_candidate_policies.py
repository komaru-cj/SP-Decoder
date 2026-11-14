#!/usr/bin/env python3
"""Benchmark the two lambda candidate policies on measured-IQ collisions.

The 30,000-scene candidate-source statistic is deliberately geometric and
payload-free.  This companion script keeps that statistic untouched and
instead evaluates ten independently constructed, trace-driven two-packet
collisions.  Each collision is made by adding two measured dual-channel IQ
packets; clean target symbol bins are used only after selection to measure
SER.  Both policies therefore share the same real waveform, preamble channel
estimate, and payload decision input within each scene.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluate_sp_dechirp_real_pos import (  # noqa: E402
    SPPacketReliability,
    choose_lambda_sp,
)
from generate_sp_v2_mechanism_figures import (  # noqa: E402
    lower_envelope,
    measured_context,
    robust_preamble_channel_sp,
    synthesize_two_trace_packets,
    trace_collision_payload_lambda_sweep,
)


def dense_policy_lambda(search: dict, rows: list[dict], checkpoint_count: int) -> float:
    """Choose from endpoints/analytic/midpoint plus uniform interior points."""

    base_values: set[float] = set()
    for candidate in search["candidate_points"]:
        sources = list(candidate["sources"])
        # A geometric/analytic point can coincide exactly with a production
        # fixed checkpoint.  Keep it in the dense policy whenever it has an
        # additional source; only remove a purely three-checkpoint point.
        if all("fixed_checkpoint" in source for source in sources):
            continue
        base_values.add(float(candidate["lambda"]))
    base_lambdas = np.asarray(sorted(base_values), dtype=np.float64)
    base_objectives = lower_envelope(rows, base_lambdas)
    base_index = int(np.argmax(base_objectives))
    best_lambda = float(base_lambdas[base_index])
    best_objective = float(base_objectives[base_index])

    cap = float(search["lambda_cap"])
    checkpoints = (
        np.arange(1, checkpoint_count + 1, dtype=np.float64)
        * cap
        / float(checkpoint_count + 1)
    )
    checkpoint_objectives = lower_envelope(rows, checkpoints)
    checkpoint_index = int(np.argmax(checkpoint_objectives))
    checkpoint_lambda = float(checkpoints[checkpoint_index])
    checkpoint_objective = float(checkpoint_objectives[checkpoint_index])
    if (
        checkpoint_objective > best_objective + 1e-12
        or (
            abs(checkpoint_objective - best_objective) <= 1e-12
            and checkpoint_lambda < best_lambda
        )
    ):
        return checkpoint_lambda
    return best_lambda


def selection_benchmark(
    reliabilities: list[SPPacketReliability],
    channels: list[np.ndarray],
    *,
    repeats: int,
    checkpoint_count: int,
    gamma: float,
    lambda_max: float,
) -> tuple[float, float, float, float, list[dict], dict]:
    """Return policy lambdas and mean candidate-selection latency in ms."""

    finite_elapsed = 0.0
    dense_elapsed = 0.0
    finite_lambda = 0.0
    dense_lambda = 0.0
    rows: list[dict] = []
    search: dict = {}
    for _ in range(repeats):
        started = time.perf_counter_ns()
        finite_lambda, _, _, rows, search = choose_lambda_sp(
            0, reliabilities, channels, gamma=gamma, max_lambda=lambda_max
        )
        finite_elapsed += time.perf_counter_ns() - started

        started = time.perf_counter_ns()
        _, _, _, dense_rows, dense_search = choose_lambda_sp(
            0, reliabilities, channels, gamma=gamma, max_lambda=lambda_max
        )
        dense_lambda = dense_policy_lambda(
            dense_search, dense_rows, checkpoint_count
        )
        dense_elapsed += time.perf_counter_ns() - started
    return (
        float(finite_lambda),
        float(dense_lambda),
        finite_elapsed / float(repeats) / 1_000_000.0,
        dense_elapsed / float(repeats) / 1_000_000.0,
        rows,
        search,
    )


def rel_with_scene_power(
    rel: SPPacketReliability,
    channel: np.ndarray,
) -> SPPacketReliability:
    """Preserve real preamble uncertainty while retaining observed power."""

    return SPPacketReliability(
        theta_obs=float(rel.theta_obs),
        theta_drift=float(rel.theta_drift),
        theta_total=float(rel.theta_total),
        L=float(rel.L),
        power=max(float(np.vdot(channel, channel).real), 1e-30),
        # The original captures contain their measured receiver noise.  No
        # synthetic AWGN is injected, so do not introduce a new noise knob.
        noise_sigma2=1e-12,
        robust_hit_count=int(rel.robust_hit_count),
    )


def run_scene(
    context: dict,
    *,
    scene_index: int,
    target: int,
    interferer: int,
    sir_db: float,
    offset_symbols: float,
    timing_repeats: int,
    checkpoint_count: int,
    gamma: float,
    lambda_max: float,
) -> dict:
    cfg = context["cfg"]
    target_cfo = float(context["continuous_cfo_bins"][target])
    interferer_cfo = float(context["continuous_cfo_bins"][interferer])
    cfo_shift = target_cfo - interferer_cfo
    scene, target_start, interferer_start = synthesize_two_trace_packets(
        context["packets"][target],
        context["packets"][interferer],
        cfg,
        offset_symbols=offset_symbols,
        sir_db=sir_db,
        interferer_cfo_shift_bins=cfo_shift,
        full_frame=True,
    )
    target_h, target_rel = robust_preamble_channel_sp(
        scene, target_start, target_cfo, 0.0, cfg
    )
    interferer_h, interferer_rel = robust_preamble_channel_sp(
        scene, interferer_start, target_cfo, 0.0, cfg
    )
    finite_lambda, dense_lambda, finite_ms, dense_ms, _, _ = selection_benchmark(
        [
            rel_with_scene_power(target_rel, target_h),
            rel_with_scene_power(interferer_rel, interferer_h),
        ],
        [target_h, interferer_h],
        repeats=timing_repeats,
        checkpoint_count=checkpoint_count,
        gamma=gamma,
        lambda_max=lambda_max,
    )
    evaluated = np.asarray(sorted({finite_lambda, dense_lambda}), dtype=np.float64)
    outcome = trace_collision_payload_lambda_sweep(
        context,
        target=target,
        interferer=interferer,
        sir_db=sir_db,
        offset_symbols=offset_symbols,
        preamble_bin_separation=0.0,
        lambdas=evaluated,
        ser_threshold=0.20,
        target_h=target_h,
    )
    ser_by_lambda = {
        float(lam): float(ser)
        for lam, ser in zip(evaluated, outcome["ser_values"])
    }
    return {
        "scene_index": int(scene_index),
        "target_label": str(context["labels"][target]),
        "interferer_label": str(context["labels"][interferer]),
        "target_source_index": int(target),
        "interferer_source_index": int(interferer),
        "sir_db": float(sir_db),
        "offset_symbols": float(offset_symbols),
        "target_cfo_bins": target_cfo,
        "interferer_cfo_bins": interferer_cfo,
        "finite_lambda": finite_lambda,
        "dense_lambda": dense_lambda,
        "finite_ser": ser_by_lambda[finite_lambda],
        "dense_ser": ser_by_lambda[dense_lambda],
        "finite_selection_ms": finite_ms,
        "dense_selection_ms": dense_ms,
        "symbol_count": int(outcome["symbol_count"]),
        "target_reliability": asdict(target_rel),
        "interferer_reliability": asdict(interferer_rel),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        type=Path,
        default=Path("real_usrp_outputs/clean_pos_packets.npz"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("real_usrp_outputs/sp_v2_paper_native_figures"),
    )
    parser.add_argument("--scene-count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260816)
    parser.add_argument("--timing-repeats", type=int, default=500)
    parser.add_argument("--dense-checkpoint-count", type=int, default=10000)
    parser.add_argument("--sp-gamma", type=float, default=0.05)
    parser.add_argument("--sp-lambda-max", type=float, default=4.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.scene_count <= 0 or args.timing_repeats <= 0:
        raise ValueError("scene count and timing repeats must be positive")
    context = measured_context(args.clean)
    rng = np.random.default_rng(args.seed)
    rows: list[dict] = []
    for scene_index in range(args.scene_count):
        target, interferer = [
            int(value) for value in rng.choice(len(context["packets"]), 2, replace=False)
        ]
        rows.append(
            run_scene(
                context,
                scene_index=scene_index,
                target=target,
                interferer=interferer,
                sir_db=float(rng.uniform(-8.0, 12.0)),
                # Non-integer offset keeps the measured-IQ addition free of a
                # frame-boundary alignment artifact while maintaining overlap.
                offset_symbols=float(rng.uniform(1.15, 4.85)),
                timing_repeats=args.timing_repeats,
                checkpoint_count=args.dense_checkpoint_count,
                gamma=args.sp_gamma,
                lambda_max=args.sp_lambda_max,
            )
        )
    summary = {
        "schema": "sp_real_trace_candidate_policy_benchmark_v1",
        "scene_count": int(args.scene_count),
        "seed": int(args.seed),
        "timing_repeats_per_scene": int(args.timing_repeats),
        "dense_checkpoint_count": int(args.dense_checkpoint_count),
        "sp_gamma": float(args.sp_gamma),
        "sp_lambda_max": float(args.sp_lambda_max),
        "scene_definition": (
            "trace-driven two-packet collision: two measured dual-channel IQ "
            "packets are added in complex baseband at a declared SIR and a "
            "non-integer relative start; no synthetic AWGN is injected"
        ),
        "ser_definition": (
            "clean target symbol bins are evaluation-only and are read after "
            "lambda selection; each policy sees the same waveform and target "
            "preamble estimate in a scene"
        ),
        "timing_definition": (
            "mean candidate construction plus lower-envelope selection time; "
            "preamble channel estimation and payload decoding are shared "
            "between policies and excluded"
        ),
        "finite_policy": {
            "candidate_sources": [
                "interval endpoints",
                "pair-specific flip/peak points",
                "adaptive midpoint",
                "three fixed uniform interior checkpoints",
            ],
            "mean_ser": float(np.mean([row["finite_ser"] for row in rows])),
            "mean_selection_ms": float(
                np.mean([row["finite_selection_ms"] for row in rows])
            ),
        },
        "dense_checkpoint_policy": {
            "candidate_sources": [
                "interval endpoints",
                "pair-specific flip/peak points",
                "adaptive midpoint",
                "10,000 fixed uniform interior checkpoints",
            ],
            "mean_ser": float(np.mean([row["dense_ser"] for row in rows])),
            "mean_selection_ms": float(
                np.mean([row["dense_selection_ms"] for row in rows])
            ),
        },
        "scenes": rows,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "candidate_winner_real_trace_metrics.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with (args.out_dir / "candidate_winner_real_trace_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fieldnames = [
            "scene_index",
            "target_label",
            "interferer_label",
            "sir_db",
            "offset_symbols",
            "finite_lambda",
            "dense_lambda",
            "finite_ser",
            "dense_ser",
            "finite_selection_ms",
            "dense_selection_ms",
            "symbol_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({name: row[name] for name in fieldnames} for row in rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
