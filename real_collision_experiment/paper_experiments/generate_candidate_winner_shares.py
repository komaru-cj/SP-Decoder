#!/usr/bin/env python3
"""Measure which finite SP candidate source wins controlled collisions.

The experiment uses measured channel directions/reliability cones and random,
declared collision powers.  It never reads payload, SER, PRR, or CRC.  The
second candidate policy replaces the production three fixed checkpoints with
10,000 uniform interior checkpoints; all other candidate sources are held
fixed.  Chunked execution keeps the 30,000-scene experiment reproducible and
practical to resume.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluate_sp_dechirp_real_pos import SPPacketReliability, choose_lambda_sp
from generate_sp_v2_mechanism_figures import (
    COLORS,
    lower_envelope,
    measured_context,
    save_figure,
    unit_channel,
)


FINITE_ORDER = (
    "interval_endpoints",
    "analytic_flip_peak",
    "adaptive_midpoint",
    "constant_checkpoints_3",
)
DENSE_ORDER = (
    "interval_endpoints",
    "analytic_flip_peak",
    "adaptive_midpoint",
    "constant_checkpoints_10000",
)
CATEGORY_COLORS = {
    "interval_endpoints": "#8C969D",
    "analytic_flip_peak": "#F28E2B",
    "adaptive_midpoint": "#8064A2",
    "constant_checkpoints_3": "#2C7FB8",
    "constant_checkpoints_10000": "#2C7FB8",
}
CATEGORY_EXPORT_LABELS = {
    "interval_endpoints": "interval endpoints",
    "analytic_flip_peak": "pair-specific flip/peak points",
    "adaptive_midpoint": "adaptive midpoint",
    "constant_checkpoints_3": "three fixed uniform interior checkpoints",
    "constant_checkpoints_10000": "10,000 fixed uniform interior checkpoints",
}


def source_category(sources: list[str]) -> str:
    if any("flip" in source or "stat" in source for source in sources):
        return "analytic_flip_peak"
    if any("midpoint" in source for source in sources):
        return "adaptive_midpoint"
    if any("fixed_checkpoint" in source for source in sources):
        return "constant_checkpoints_3"
    return "interval_endpoints"


def scene_rng(seed: int, scene_index: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([seed, scene_index]))


def build_scene(
    context: dict,
    channels: list[np.ndarray],
    scene_index: int,
    seed: int,
) -> dict:
    rng = scene_rng(seed, scene_index)
    collision_number = int(rng.integers(2, 7))
    selected = rng.choice(len(channels), size=collision_number, replace=False)
    sir_db = rng.uniform(-8.0, 12.0, size=collision_number - 1)
    snr_db = float(rng.uniform(10.0, 30.0))
    noise = float(10.0 ** (-snr_db / 10.0))
    reliabilities: list[SPPacketReliability] = []
    for position, source in enumerate(selected):
        measured = context["reliabilities"][int(source)]
        power = (
            1.0
            if position == 0
            else float(10.0 ** (-sir_db[position - 1] / 10.0))
        )
        reliabilities.append(
            SPPacketReliability(
                theta_obs=measured.theta_obs,
                theta_drift=measured.theta_drift,
                theta_total=measured.theta_total,
                L=measured.L,
                power=power,
                noise_sigma2=noise,
                robust_hit_count=measured.robust_hit_count,
            )
        )
    selected_lambda, _, _, rows, search = choose_lambda_sp(
        0,
        reliabilities,
        [channels[int(source)] for source in selected],
        gamma=0.05,
        max_lambda=4.0,
    )
    finite_winner = next(
        item
        for item in search["candidate_points"]
        if abs(float(item["lambda"]) - float(selected_lambda)) < 1e-10
    )
    return {
        "scene_index": scene_index,
        "collision_number": collision_number,
        "source_indices": [int(source) for source in selected],
        "sir_db": [float(value) for value in sir_db],
        "snr_db": snr_db,
        "rows": rows,
        "search": search,
        "finite_category": source_category(finite_winner["sources"]),
        "finite_lambda": float(selected_lambda),
        "finite_objective": float(finite_winner["objective"]),
        "finite_sources": list(finite_winner["sources"]),
    }


def best_base_candidate(search: dict, rows: list[dict]) -> tuple[float, float, str]:
    """Return the best non-checkpoint candidate under dense-policy semantics."""

    values: dict[float, str] = {}
    for candidate in search["candidate_points"]:
        category = source_category(candidate["sources"])
        if category == "constant_checkpoints_3":
            continue
        value = float(candidate["lambda"])
        values.setdefault(value, category)
    lambdas = np.asarray(sorted(values), dtype=np.float64)
    objectives = lower_envelope(rows, lambdas)
    winner = int(np.argmax(objectives))
    value = float(lambdas[winner])
    return value, float(objectives[winner]), values[value]


def dense_winner_categories(scenes: list[dict], checkpoint_count: int) -> list[str]:
    """Evaluate the uniform-checkpoint policy in batches without approximation."""

    categories: list[str] = []
    batch_size = 1024
    for first in range(0, len(scenes), batch_size):
        group = scenes[first : first + batch_size]
        size = len(group)
        caps = np.asarray(
            [float(scene["search"]["lambda_cap"]) for scene in group],
            dtype=np.float64,
        )
        grid = (
            np.arange(1, checkpoint_count + 1, dtype=np.float64)[None, :]
            / float(checkpoint_count + 1)
            * caps[:, None]
        )
        objectives = np.full((size, checkpoint_count), np.inf, dtype=np.float64)
        max_pairs = max(len(scene["rows"]) for scene in group)
        for pair_slot in range(max_pairs):
            valid = np.asarray(
                [pair_slot < len(scene["rows"]) for scene in group],
                dtype=bool,
            )
            a = np.zeros(size, dtype=np.float64)
            b = np.zeros(size, dtype=np.float64)
            c0 = np.ones(size, dtype=np.float64)
            c2 = np.zeros(size, dtype=np.float64)
            for row_index, scene in enumerate(group):
                if pair_slot >= len(scene["rows"]):
                    continue
                row = scene["rows"][pair_slot]
                a[row_index] = float(row["A_under"])
                b[row_index] = float(row["B_under"])
                c0[row_index] = float(row["C0"])
                c2[row_index] = float(row["C2"])
            pair_objective = (a[:, None] + grid * b[:, None]) / np.sqrt(
                np.maximum(c0[:, None] + grid * grid * c2[:, None], 1e-30)
            )
            pair_objective[~valid, :] = np.inf
            objectives = np.minimum(objectives, pair_objective)
        grid_indices = np.argmax(objectives, axis=1)
        grid_values = grid[np.arange(size), grid_indices]
        grid_objectives = objectives[np.arange(size), grid_indices]
        for scene, grid_value, grid_objective in zip(
            group,
            grid_values,
            grid_objectives,
        ):
            base_value, base_objective, base_category = best_base_candidate(
                scene["search"], scene["rows"]
            )
            use_base = (
                base_objective > float(grid_objective) + 1e-12
                or (
                    abs(base_objective - float(grid_objective)) <= 1e-12
                    and base_value < float(grid_value)
                )
            )
            categories.append(
                base_category if use_base else "constant_checkpoints_10000"
            )
    return categories


def scene_example(scene: dict, context: dict, dense_category: str) -> dict:
    return {
        "scene_index": int(scene["scene_index"]),
        "collision_packet_count": int(scene["collision_number"]),
        "source_labels": [
            context["labels"][source] for source in scene["source_indices"]
        ],
        "sir_db_each": scene["sir_db"],
        "snr_db": float(scene["snr_db"]),
        "finite_winner_category": scene["finite_category"],
        "finite_winner_lambda": float(scene["finite_lambda"]),
        # `stat` is the historical internal identifier of a pair maximum; the
        # paper and all exported artifacts call it a peak point.
        "finite_winner_sources": [
            source.replace("_stat", "_peak") for source in scene["finite_sources"]
        ],
        "dense_policy_winner_category": dense_category,
    }


def run_chunk(args: argparse.Namespace) -> None:
    context = measured_context(args.clean)
    channels = [unit_channel(value) for value in context["channels"]]
    scenes = [
        build_scene(context, channels, scene_index, args.seed)
        for scene_index in range(args.scene_start, args.scene_start + args.scene_count)
    ]
    dense_categories = dense_winner_categories(scenes, args.dense_checkpoint_count)
    finite_counts = Counter(scene["finite_category"] for scene in scenes)
    dense_counts = Counter(dense_categories)
    examples: dict[str, dict] = {}
    for scene, dense_category in zip(scenes, dense_categories):
        examples.setdefault(
            f"finite:{scene['finite_category']}",
            scene_example(scene, context, dense_category),
        )
        examples.setdefault(
            f"dense:{dense_category}",
            scene_example(scene, context, dense_category),
        )
    payload = {
        "schema": "sp_candidate_winner_share_chunk_v1",
        "seed": args.seed,
        "scene_start": args.scene_start,
        "scene_count": args.scene_count,
        "dense_checkpoint_count": args.dense_checkpoint_count,
        "collision_definition": (
            "one target plus 1--5 competitors sampled without replacement from "
            "measured directions/reliability cones; declared per-interferer SIR "
            "uniform on [-8, 12] dB and SNR uniform on [10, 30] dB"
        ),
        "selection_guard": "no payload, SER, PRR, or CRC outcome is read",
        "finite_counts": {name: int(finite_counts[name]) for name in FINITE_ORDER},
        "dense_counts": {name: int(dense_counts[name]) for name in DENSE_ORDER},
        "examples": examples,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "finite_counts": payload["finite_counts"], "dense_counts": payload["dense_counts"]}, ensure_ascii=False))


def plot_share(
    out_dir: Path,
    stem: str,
    counts: dict[str, int],
    total: int,
    order: tuple[str, ...],
    labels: list[str],
    title: str,
    real_trace_metric: dict | None = None,
) -> None:
    shares = [100.0 * counts.get(name, 0) / max(total, 1) for name in order]
    fig, axis = plt.subplots(figsize=(6.6, 3.7))
    bars = axis.bar(
        np.arange(len(order)),
        shares,
        color=[CATEGORY_COLORS[name] for name in order],
        edgecolor="#263238",
        linewidth=0.55,
    )
    for bar, share in zip(bars, shares):
        axis.text(
            bar.get_x() + bar.get_width() / 2.0,
            share + 0.7,
            f"{share:.2f}%",
            ha="center",
            va="bottom",
            fontsize=8.7,
            fontweight="bold",
        )
    axis.set_xticks(np.arange(len(order)), labels)
    axis.set_ylabel("share of collision scenes (%)")
    axis.set_ylim(0.0, max(5.0, math.ceil((max(shares) + 5.0) / 5.0) * 5.0))
    axis.set_title(title, fontweight="bold")
    if real_trace_metric is not None:
        axis.text(
            0.985,
            0.955,
            (
                "10 real-IQ trace scenes\n"
                f"mean SER: {100.0 * float(real_trace_metric['mean_ser']):.2f}%\n"
                f"lambda selection: {float(real_trace_metric['mean_selection_ms']):.3f} ms/scene"
            ),
            transform=axis.transAxes,
            ha="right",
            va="top",
            color="#C62828",
            fontsize=8.6,
            fontweight="bold",
            bbox={"facecolor": "white", "edgecolor": "#C62828", "alpha": 0.92, "pad": 0.35},
        )
    axis.grid(axis="y", color="#D8DDE1", linewidth=0.65, alpha=0.75)
    axis.set_axisbelow(True)
    fig.tight_layout()
    save_figure(fig, out_dir, stem)


def aggregate_chunks(args: argparse.Namespace) -> None:
    paths = sorted(args.chunk_dir.glob("candidate_winner_chunk_*.json"))
    if not paths:
        raise FileNotFoundError(f"no chunks found in {args.chunk_dir}")
    chunks = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    starts = sorted(
        (int(chunk["scene_start"]), int(chunk["scene_count"])) for chunk in chunks
    )
    expected = 0
    for start, count in starts:
        if start != expected:
            raise RuntimeError(f"chunk coverage is not contiguous at scene {expected}")
        expected += count
    if expected != args.expected_scene_count:
        raise RuntimeError(
            f"expected {args.expected_scene_count} scenes, found {expected}"
        )
    finite_counts = Counter()
    dense_counts = Counter()
    examples: dict[str, dict] = {}
    for chunk in chunks:
        finite_counts.update(chunk["finite_counts"])
        dense_counts.update(chunk["dense_counts"])
        for key, value in chunk["examples"].items():
            displayed = dict(value)
            displayed["finite_winner_sources"] = [
                source.replace("_stat", "_peak")
                for source in displayed["finite_winner_sources"]
            ]
            examples.setdefault(key, displayed)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    total = expected
    real_trace_metrics = None
    if args.metrics_path is not None:
        real_trace_metrics = json.loads(args.metrics_path.read_text(encoding="utf-8"))
        if int(real_trace_metrics["scene_count"]) != 10:
            raise ValueError("figure annotation requires exactly 10 real-IQ scenes")
    plot_share(
        out_dir,
        "candidate_winner_share_three_checkpoints",
        dict(finite_counts),
        total,
        FINITE_ORDER,
        ["interval\nendpoints", "analytic\nflip/peak", "adaptive\nmidpoint", "3 constant\ncheckpoints"],
        f"Winner source with the production finite set ({total:,} controlled collisions)",
        None if real_trace_metrics is None else real_trace_metrics["finite_policy"],
    )
    plot_share(
        out_dir,
        "candidate_winner_share_10000_checkpoints",
        dict(dense_counts),
        total,
        DENSE_ORDER,
        ["interval\nendpoints", "analytic\nflip/peak", "adaptive\nmidpoint", "10,000 constant\ncheckpoints"],
        f"Winner source after replacing 3 by 10,000 checkpoints ({total:,} controlled collisions)",
        None if real_trace_metrics is None else real_trace_metrics["dense_checkpoint_policy"],
    )
    summary = {
        "schema": "sp_candidate_winner_share_v1",
        "scene_count": total,
        "seed": chunks[0]["seed"],
        "dense_checkpoint_count": chunks[0]["dense_checkpoint_count"],
        "collision_definition": chunks[0]["collision_definition"],
        "selection_guard": chunks[0]["selection_guard"],
        "finite_policy": {
            "candidate_sources": [
                "interval endpoints",
                "pair-specific flip/peak points",
                "adaptive midpoint",
                "three fixed uniform interior checkpoints",
            ],
            "winner_counts": {name: int(finite_counts[name]) for name in FINITE_ORDER},
            "winner_shares_percent": {
                name: 100.0 * finite_counts[name] / total for name in FINITE_ORDER
            },
        },
        "dense_checkpoint_policy": {
            "candidate_sources": [
                "interval endpoints",
                "pair-specific flip/peak points",
                "adaptive midpoint",
                "10,000 fixed uniform interior checkpoints",
            ],
            "winner_counts": {name: int(dense_counts[name]) for name in DENSE_ORDER},
            "winner_shares_percent": {
                name: 100.0 * dense_counts[name] / total for name in DENSE_ORDER
            },
        },
        "examples": examples,
    }
    if real_trace_metrics is not None:
        summary["real_trace_benchmark"] = real_trace_metrics
    (out_dir / "candidate_winner_share_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "candidate_winner_share.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "policy",
                "candidate_source",
                "winner_count",
                "winner_share_percent",
            ),
        )
        writer.writeheader()
        for policy, counts, order in (
            ("three_checkpoints", finite_counts, FINITE_ORDER),
            ("10000_checkpoints", dense_counts, DENSE_ORDER),
        ):
            for name in order:
                writer.writerow(
                    {
                        "policy": policy,
                        "candidate_source": CATEGORY_EXPORT_LABELS[name],
                        "winner_count": int(counts[name]),
                        "winner_share_percent": f"{100.0 * counts[name] / total:.8f}",
                    }
                )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        type=Path,
        default=Path("real_usrp_outputs/clean_pos_packets.npz"),
    )
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--scene-start", type=int, default=0)
    parser.add_argument("--scene-count", type=int, default=2500)
    parser.add_argument("--dense-checkpoint-count", type=int, default=10000)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument(
        "--chunk-dir",
        type=Path,
        default=Path("real_usrp_outputs/candidate_winner_share_chunks"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("real_usrp_outputs/sp_v2_paper_native_figures"),
    )
    parser.add_argument("--expected-scene-count", type=int, default=30000)
    parser.add_argument(
        "--metrics-path",
        type=Path,
        default=None,
        help="optional 10-real-IQ-scene SER/selection-latency annotation JSON",
    )
    args = parser.parse_args()
    if not args.aggregate and args.out is None:
        args.out = args.chunk_dir / f"candidate_winner_chunk_{args.scene_start:05d}.json"
    return args


def main() -> int:
    args = parse_args()
    if args.aggregate:
        aggregate_chunks(args)
    else:
        if args.scene_count <= 0:
            raise ValueError("scene count must be positive")
        run_chunk(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
