#!/usr/bin/env python3
"""Compare SER only when the dense policy selects a fixed checkpoint.

This is the payload counterpart of ``generate_candidate_winner_shares.py``.
It uses its exact payload-free controlled-scene definition: one target plus
one to five competitors, sampled from measured channel directions/reliability
cones at declared per-interferer SIR and SNR.  A scene enters the reported
cohort only if the policy with 10,000 uniform interior checkpoints selects one
of those checkpoints over all non-checkpoint candidates.  The corresponding
measured-IQ payload traces are then mixed and evaluated for:

* MRC (lambda = 0),
* the candidate set without fixed checkpoints,
* the production set with three fixed checkpoints, and
* the same set with 10,000 fixed checkpoints.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generate_candidate_winner_shares import build_scene  # noqa: E402
from generate_sp_preliminary_figures import packet_power, projected_spectra  # noqa: E402
from generate_sp_v2_mechanism_figures import (  # noqa: E402
    lower_envelope,
    measured_context,
    unit_channel,
)
from lora_mrc_sp_core import fractional_read_2d  # noqa: E402


POLICIES = (
    ("mrc", "MRC\n($\\lambda=0$)", "#7A858E"),
    ("no_constant", "no constant\ncheckpoints", "#7754A6"),
    ("three_constant", "3 constant\ncheckpoints", "#2878B5"),
    ("dense_constant", "10,000 constant\ncheckpoints", "#DE7B22"),
)
PLOT_POLICIES = tuple(policy for policy in POLICIES if policy[0] != "no_constant")


def best_nonconstant_candidate(search: dict, pair_rows: list[dict]) -> tuple[float, float, list[str]]:
    """Choose from endpoints, analytic points, and midpoint only.

    A point with both a fixed-checkpoint tag and a structural tag remains: it
    is still available without the fixed grid.  This matches the dense-policy
    treatment in the existing candidate-winner experiment.
    """

    candidates = [
        item
        for item in search["candidate_points"]
        if not all("fixed_checkpoint" in source for source in item["sources"])
    ]
    if not candidates:
        return 0.0, 0.0, ["boundary_low"]
    values = np.asarray(sorted({float(item["lambda"]) for item in candidates}), dtype=np.float64)
    objective = lower_envelope(pair_rows, values)
    index = int(np.argmax(objective))  # sorted values make ties choose lower lambda.
    winner = float(values[index])
    source = next(item["sources"] for item in candidates if abs(float(item["lambda"]) - winner) <= 1e-12)
    return winner, float(objective[index]), list(source)


def dense_checkpoint_choice(search: dict, pair_rows: list[dict], checkpoint_count: int) -> dict:
    """Apply the 10,000-checkpoint rule without looking at payload SER."""

    base_lambda, base_objective, base_sources = best_nonconstant_candidate(search, pair_rows)
    cap = float(search["lambda_cap"])
    checkpoints = (
        np.arange(1, checkpoint_count + 1, dtype=np.float64)
        * cap
        / float(checkpoint_count + 1)
    )
    objectives = lower_envelope(pair_rows, checkpoints)
    checkpoint_index = int(np.argmax(objectives))
    checkpoint_lambda = float(checkpoints[checkpoint_index])
    checkpoint_objective = float(objectives[checkpoint_index])
    checkpoint_wins = (
        checkpoint_objective > base_objective + 1e-12
        or (
            abs(checkpoint_objective - base_objective) <= 1e-12
            and checkpoint_lambda < base_lambda
        )
    )
    return {
        "lambda": checkpoint_lambda if checkpoint_wins else base_lambda,
        "objective": checkpoint_objective if checkpoint_wins else base_objective,
        "is_constant_checkpoint": bool(checkpoint_wins),
        "checkpoint_lambda": checkpoint_lambda,
        "checkpoint_objective": checkpoint_objective,
        "base_lambda": base_lambda,
        "base_objective": base_objective,
        "base_sources": base_sources,
    }


def controlled_payload_evaluation(
    context: dict,
    scene: dict,
    dense: dict,
    *,
    seed: int,
) -> dict:
    """Evaluate the exact candidate-winner controlled scene on measured IQ.

    Lambda selection is intentionally the same payload-free geometry used by
    the two candidate-winner share figures.  After selection, clean measured
    traces are mixed one target-aligned payload window at a time.  Every
    interferer keeps its declared SIR, gets a deterministic fractional start,
    and is shifted by its measured relative CFO before the target projection.
    """

    cfg = context["cfg"]
    source_indices = [int(value) for value in scene["source_indices"]]
    target = source_indices[0]
    interferers = source_indices[1:]
    sir_db = [float(value) for value in scene["sir_db"]]
    target_h = np.asarray(context["channels"][target], dtype=np.complex128)
    target_cfo = float(context["continuous_cfo_bins"][target])
    random = np.random.default_rng(np.random.SeedSequence([seed, int(scene["scene_index"]), 991]))
    offsets = random.uniform(1.15, 4.85, size=len(interferers))
    lambdas = np.asarray(
        sorted({0.0, float(scene["finite_lambda"]), float(dense["base_lambda"]), float(dense["lambda"])}),
        dtype=np.float64,
    )
    errors = np.zeros(lambdas.size, dtype=np.int64)
    packets = context["packets"]
    truth_bins = context["refs"][target].symbol_bins
    target_power = packet_power(packets[target])
    snr_db = float(scene["snr_db"])
    noise_power = target_power / (10.0 ** (snr_db / 10.0))
    for symbol_index, truth_bin in enumerate(truth_bins):
        begin = (cfg.payload_start_symbols + symbol_index) * cfg.samples_per_symbol
        mixed = fractional_read_2d(packets[target], begin, cfg.samples_per_symbol).astype(np.complex64)
        for source, declared_sir, offset in zip(interferers, sir_db, offsets):
            interferer_begin = float(begin) - float(offset) * cfg.samples_per_symbol
            window = fractional_read_2d(packets[source], interferer_begin, cfg.samples_per_symbol)
            scale = math.sqrt(
                target_power
                / max(packet_power(packets[source]), 1e-30)
                / (10.0 ** (declared_sir / 10.0))
            )
            cfo_shift = target_cfo - float(context["continuous_cfo_bins"][source])
            samples = interferer_begin + np.arange(cfg.samples_per_symbol, dtype=np.float64)
            rotation = np.exp(1j * 2.0 * math.pi * cfo_shift * samples / cfg.samples_per_symbol).astype(np.complex64)
            mixed += scale * window * rotation[None, :]
        noise = (
            random.standard_normal(mixed.shape) + 1j * random.standard_normal(mixed.shape)
        ) * math.sqrt(noise_power / 2.0)
        mixed = (mixed + noise.astype(np.complex64)).astype(np.complex64)
        support_spectrum, contradiction_spectrum = projected_spectra(mixed, cfg, target_cfo, target_h)
        support = np.abs(support_spectrum) ** 2
        contradiction = np.abs(contradiction_spectrum) ** 2
        decisions = np.argmax(support[None, :] - lambdas[:, None] * contradiction[None, :], axis=1)
        errors += decisions != (int(truth_bin) % cfg.m)
    ser_by_lambda = {float(lam): float(error / max(len(truth_bins), 1)) for lam, error in zip(lambdas, errors)}
    return {
        "proposal_index": int(scene["scene_index"]),
        "target_label": str(context["labels"][target]),
        "interferer_label": " + ".join(str(context["labels"][source]) for source in interferers),
        "sir_db": float(np.mean(sir_db)),
        "offset_symbols": float(np.mean(offsets)),
        "target_cfo_bins": target_cfo,
        "interferer_cfo_bins": float(np.mean([context["continuous_cfo_bins"][source] for source in interferers])),
        "mrc_lambda": 0.0,
        "no_constant_lambda": float(dense["base_lambda"]),
        "three_constant_lambda": float(scene["finite_lambda"]),
        "dense_constant_lambda": float(dense["lambda"]),
        "dense_checkpoint_lambda": float(dense["checkpoint_lambda"]),
        "mrc_ser": ser_by_lambda[0.0],
        "no_constant_ser": ser_by_lambda[float(dense["base_lambda"])],
        "three_constant_ser": ser_by_lambda[float(scene["finite_lambda"])],
        "dense_constant_ser": ser_by_lambda[float(dense["lambda"])],
        "symbol_count": int(len(truth_bins)),
        "collision_packet_count": int(len(source_indices)),
        "declared_sir_db_each": sir_db,
        "declared_snr_db": snr_db,
        "interferer_offsets_symbols": [float(value) for value in offsets],
    }


def bootstrap_interval(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    if values.size <= 1:
        return float(values.mean()), float(values.mean())
    samples = rng.choice(values, size=(10_000, values.size), replace=True).mean(axis=1)
    return float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def plot_ser(rows: list[dict], out_dir: Path) -> dict:
    policy_keys = [policy[0] for policy in PLOT_POLICIES]
    values = np.asarray([[float(row[f"{key}_ser"]) for key in policy_keys] for row in rows], dtype=float)
    means = values.mean(axis=0)
    rng = np.random.default_rng(20260820)
    intervals = np.asarray([bootstrap_interval(values[:, index], rng) for index in range(values.shape[1])])
    errors = np.vstack((means - intervals[:, 0], intervals[:, 1] - means))

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.labelsize": 12})
    fig, axis = plt.subplots(figsize=(8.0, 6.0))
    positions = np.arange(len(PLOT_POLICIES))
    bars = axis.bar(
        positions,
        100.0 * means,
        yerr=100.0 * errors,
        capsize=3,
        color=[policy[2] for policy in PLOT_POLICIES],
        edgecolor="#18232F",
        linewidth=0.8,
        zorder=4,
    )
    for bar, mean in zip(bars, means):
        axis.text(bar.get_x() + bar.get_width() / 2.0, 100.0 * mean + 0.75, f"{100.0 * mean:.1f}%", ha="center", va="bottom", fontsize=9, weight="bold")
    axis.set_xticks(positions, [policy[1] for policy in PLOT_POLICIES])
    axis.set_ylabel("full-payload SER (%)")
    axis.set_ylim(0.0, max(5.0, 100.0 * float(np.max(intervals[:, 1])) + 6.0))
    axis.set_axisbelow(True)
    axis.grid(axis="y", color="#AEB6BF", linestyle="--", linewidth=0.7, alpha=0.75)
    for spine in axis.spines.values():
        spine.set_visible(True)
        spine.set_color("#000000")
        spine.set_linewidth(1.0)
    axis.tick_params(axis="both", direction="in", colors="#000000")
    fig.subplots_adjust(left=0.15, right=0.97, bottom=0.19, top=0.96)
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        fig.savefig(out_dir / f"candidate_checkpoint_selected_ser_comparison.{suffix}", dpi=200, facecolor="white")
    plt.close(fig)
    return {
        key: {
            "mean_ser": float(means[index]),
            "bootstrap_95_percent_interval": [float(intervals[index, 0]), float(intervals[index, 1])],
        }
        for index, key in enumerate(policy_keys)
    }


def write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = [
        "proposal_index", "target_label", "interferer_label", "sir_db", "offset_symbols",
        "target_cfo_bins", "interferer_cfo_bins", "mrc_lambda", "no_constant_lambda",
        "three_constant_lambda", "dense_constant_lambda", "dense_checkpoint_lambda",
        "mrc_ser", "no_constant_ser", "three_constant_ser", "dense_constant_ser", "symbol_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({name: row[name] for name in fieldnames} for row in rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", type=Path, default=Path("real_usrp_outputs/clean_pos_packets.npz"))
    parser.add_argument("--out-dir", type=Path, default=Path("real_usrp_outputs/sp_v2_paper_native_figures"))
    parser.add_argument("--accepted-scene-count", type=int, default=24)
    parser.add_argument("--max-proposals", type=int, default=600)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--dense-checkpoint-count", type=int, default=10_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.accepted_scene_count <= 0 or args.max_proposals < args.accepted_scene_count:
        raise ValueError("accepted-scene-count must be positive and no greater than max-proposals")
    context = measured_context(args.clean)
    channels = [unit_channel(value) for value in context["channels"]]
    accepted: list[dict] = []
    for proposal_index in range(args.max_proposals):
        scene = build_scene(
            context,
            channels,
            proposal_index,
            args.seed,
        )
        dense = dense_checkpoint_choice(
            scene["search"], scene["rows"], args.dense_checkpoint_count
        )
        if not dense["is_constant_checkpoint"]:
            continue
        accepted.append(controlled_payload_evaluation(context, scene, dense, seed=args.seed))
        gc.collect()
        if len(accepted) >= args.accepted_scene_count:
            break
    if len(accepted) < args.accepted_scene_count:
        raise RuntimeError(
            f"only found {len(accepted)} dense-checkpoint winners in {args.max_proposals} proposals; "
            "increase --max-proposals"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "candidate_checkpoint_selected_ser.csv"
    write_csv(accepted, csv_path)
    metrics = plot_ser(accepted, args.out_dir)
    summary = {
        "schema": "sp_dense_checkpoint_selected_ser_v1",
        "accepted_scene_count": len(accepted),
        "proposals_examined": int(accepted[-1]["proposal_index"] + 1),
        "dense_checkpoint_count": int(args.dense_checkpoint_count),
        "seed": int(args.seed),
        "selection_cohort": (
            "retain only payload-free controlled collisions where the 10,000-uniform-checkpoint policy "
            "selects a fixed interior checkpoint rather than a non-checkpoint candidate"
        ),
        "selection_guard": "payload SER is evaluated only after every lambda policy has been selected",
        "scene_definition": (
            "one target plus one to five competitors are selected from measured channel cones at declared SIR/SNR; "
            "their measured dual-channel IQ payloads are then mixed at deterministic fractional starts and relative CFOs"
        ),
        "policies": {
            "mrc": "lambda = 0",
            "no_constant": "endpoints, analytic flip/peak points, and adaptive midpoint only",
            "three_constant": "the production candidate set plus three uniform fixed checkpoints",
            "dense_constant": "the same base set plus 10,000 uniform fixed checkpoints",
        },
        "metrics": metrics,
        "rows": accepted,
    }
    (args.out_dir / "candidate_checkpoint_selected_ser_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"accepted_scene_count": len(accepted), "proposals_examined": summary["proposals_examined"], "metrics": metrics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
