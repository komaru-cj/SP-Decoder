#!/usr/bin/env python3
"""Render focused, publication-oriented figures for SP-Decoder v2.

This module deliberately separates experiment generation from presentation.
It consumes the CSV/JSON sidecars produced by
``generate_sp_v2_mechanism_figures.py`` and never changes the measurements.

Mechanism figures may use deliberately selected representative cases.  The
selection rule and source files are recorded in the output manifest.  Figures
that support aggregate claims (notably Fig. 6 and the air-channel sweeps) retain
all available samples.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_decoder_matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec


INK = "#16212B"
NAVY = "#173F5F"
BLUE = "#2474B5"
TEAL = "#14A38B"
GREEN = "#3A9D5D"
ORANGE = "#E86F13"
RED = "#D64545"
PURPLE = "#7554A3"
GOLD = "#F2B134"
LIGHT_BLUE = "#D9EBF7"
LIGHT_GREEN = "#DDF1E7"
LIGHT_RED = "#F8DDDA"
MID_GRAY = "#78838C"
LIGHT_GRAY = "#EDF0F2"


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.0,
            "axes.titlesize": 10.0,
            "axes.labelsize": 9.0,
            "axes.edgecolor": "#4D555B",
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.7,
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "mathtext.fontset": "dejavusans",
        }
    )


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def save_figure(fig: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(
            out_dir / f"{stem}.{suffix}",
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(fig)


def panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.08,
        1.06,
        label,
        transform=axis.transAxes,
        fontsize=11,
        fontweight="bold",
        va="top",
    )


def clean_axis(axis: plt.Axes, grid: str | None = "y") -> None:
    if grid:
        axis.grid(axis=grid, color="#D8DDE1", linewidth=0.65, alpha=0.7)
        axis.set_axisbelow(True)


def ecdf(values: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.sort(np.asarray(list(values), dtype=float))
    if x.size == 0:
        return x, x
    return x, np.arange(1, x.size + 1, dtype=float) / x.size


def pair_risk(row: dict, values: np.ndarray | float) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    return (float(row["A_under"]) + x * float(row["B_under"])) / np.sqrt(
        np.maximum(
            float(row["C0"]) + x * x * float(row["C2"]),
            1e-30,
        )
    )


def copy_figure2_ab(source_dir: Path, out_dir: Path) -> dict:
    mapping = {
        "fig1_sp_core_observation": "fig2a_trace_sp_core_observation",
        "fig3_eta_distribution": "fig2b_wrong_bin_counter_evidence",
    }
    copied: list[str] = []
    for source_stem, target_stem in mapping.items():
        for suffix in ("png", "svg"):
            source = source_dir / f"{source_stem}.{suffix}"
            if not source.exists():
                raise FileNotFoundError(source)
            target = out_dir / f"{target_stem}.{suffix}"
            shutil.copy2(source, target)
            copied.append(str(target))
    return {
        "selection_rule": (
            "Author-selected measured/trace-driven cases with the strongest "
            "target-bin versus MRC-wrong-bin visual contrast."
        ),
        "copied_files": copied,
    }


def render_figure2c(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "fig2c_four_packet_lambda_ser.csv")
    summary = read_json(
        data_dir / "fig2c_four_packet_lambda_ser_summary.json"
    )
    colors = [BLUE, TEAL, ORANGE, PURPLE]
    markers = ["o", "s", "^", "D"]
    fig, curve_axis = plt.subplots(figsize=(9.1, 4.55))
    rendered_cases: list[dict] = []
    for case, color, marker in zip(
        summary["cases"],
        colors,
        markers,
    ):
        case_label = str(case["case_label"])
        selected = sorted(
            [row for row in rows if row["case_label"] == case_label],
            key=lambda row: float(row["evaluation_lambda"]),
        )
        lambdas = np.asarray(
            [float(row["evaluation_lambda"]) for row in selected]
        )
        ser = np.asarray([float(row["ser"]) for row in selected])
        lambda_star = float(case["lambda_star"])
        best_low = float(case["best_lambda_low"])
        best_high = float(case["best_lambda_high"])
        star_index = int(np.where(np.isclose(lambdas, lambda_star))[0][0])
        direction_error = float(case["direction_error_deg"])

        curve_axis.plot(
            lambdas,
            ser,
            color=color,
            linewidth=2.05,
            marker=marker,
            markersize=4.0,
            markeredgecolor="white",
            markeredgewidth=0.4,
            label=(
                rf"{case_label}: SIR {float(case['sir_db']):g} dB, "
                rf"$\Delta t={float(case['offset_symbols']):g}T_s$, "
                rf"$\Delta\psi={direction_error:+.1f}^\circ$"
            ),
            zorder=3,
        )
        curve_axis.scatter(
            [lambda_star],
            [ser[star_index]],
            marker="*",
            s=125,
            color=color,
            edgecolor=INK,
            linewidth=0.55,
            zorder=6,
        )
        rendered_cases.append(
            {
                "case_label": case_label,
                "sir_db": float(case["sir_db"]),
                "offset_symbols": float(case["offset_symbols"]),
                "direction_error_deg": direction_error,
                "lambda_star": lambda_star,
                "best_lambda_low": best_low,
                "best_lambda_high": best_high,
                "minimum_ser": float(case["minimum_ser"]),
                "ser_at_lambda_max": float(case["ser_at_lambda_max"]),
            }
        )

    curve_axis.set_xlim(0.0, 10.0)
    curve_axis.set_ylim(-0.035, 1.035)
    curve_axis.set_xticks(np.arange(0.0, 10.1, 1.0))
    curve_axis.set_xticks(np.arange(0.0, 10.01, 0.25), minor=True)
    curve_axis.tick_params(axis="x", which="minor", length=2.0)
    curve_axis.set_xlabel(r"counter-evidence weight $\lambda$")
    curve_axis.set_ylabel("payload SER")
    curve_axis.legend(
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.015),
        ncol=2,
        fontsize=7.5,
        columnspacing=1.4,
        handlelength=2.4,
    )
    clean_axis(curve_axis, "both")

    fig.suptitle(
        r"The useful counter-evidence weight is packet dependent",
        fontsize=11.8,
        fontweight="bold",
        y=0.995,
    )
    fig.subplots_adjust(bottom=0.15, top=0.79, left=0.09, right=0.98)
    save_figure(fig, out_dir, "fig2c_packet_dependent_lambda")
    return {
        "question": "Why should lambda be configured per packet?",
        "answer": (
            "The selected collision packets have no shared SER-minimizing "
            "lambda, and every curve degrades under excessive weight."
        ),
        "scope": summary["selection_rule"],
        "has_common_minimizer": summary["has_common_minimizer"],
        "cases": rendered_cases,
    }


def render_figure2d(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "fig2_preamble_payload_proxy.csv")
    summary = read_json(data_dir / "fig2_summary.json")
    x = np.asarray([float(row["preamble_dispersion_deg"]) for row in rows])
    y = np.asarray([float(row["payload_target_eta_median"]) for row in rows])
    order = np.argsort(x)
    bins = np.array_split(order, 4)
    bx = np.asarray([np.median(x[index]) for index in bins])
    by = np.asarray([np.median(y[index]) for index in bins])
    q1 = np.asarray([np.quantile(y[index], 0.25) for index in bins])
    q3 = np.asarray([np.quantile(y[index], 0.75) for index in bins])

    lx, ly = np.log10(x), np.log10(np.maximum(y, 1e-8))
    slope, intercept = np.polyfit(lx, ly, 1)
    trend_x = np.geomspace(max(x.min() * 0.9, 1e-3), x.max() * 1.1, 200)
    trend_y = 10 ** (intercept + slope * np.log10(trend_x))

    fig, axis = plt.subplots(figsize=(6.9, 3.75))
    axis.scatter(x, y, s=25, color="#B7C0C7", alpha=0.75, edgecolor="white", linewidth=0.35)
    axis.plot(trend_x, trend_y, color=NAVY, linewidth=2.0, alpha=0.9)
    axis.errorbar(
        bx,
        by,
        yerr=np.vstack([by - q1, q3 - by]),
        fmt="o-",
        color=ORANGE,
        markeredgecolor=INK,
        markeredgewidth=0.5,
        markersize=7,
        linewidth=2.2,
        capsize=3,
        label="quartile-bin median and IQR",
        zorder=5,
    )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("preamble direction dispersion (degree)")
    axis.set_ylabel(r"payload target-bin leakage $\eta_{\rm target}$")
    axis.set_title(
        "Preamble instability predicts when counter-evidence may penalize the target",
        fontsize=11.2,
        fontweight="bold",
    )
    axis.text(
        0.04,
        0.92,
        rf"Spearman $\rho={summary['proxy_spearman_rho']:.2f}$"
        + "\n"
        + rf"$p={summary['proxy_p_value']:.1e}$",
        transform=axis.transAxes,
        va="top",
        color=NAVY,
        fontsize=9,
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": LIGHT_BLUE},
    )
    axis.annotate(
        "stable preamble\nlow target penalty",
        xy=(bx[0], by[0]),
        xytext=(0.18, 0.15),
        textcoords="axes fraction",
        ha="center",
        color=TEAL,
        arrowprops={"arrowstyle": "->", "color": TEAL, "lw": 1.2},
    )
    axis.annotate(
        "dispersed preamble\nhigher penalty risk",
        xy=(bx[-1], by[-1]),
        xytext=(0.76, 0.73),
        textcoords="axes fraction",
        ha="center",
        color=ORANGE,
        arrowprops={"arrowstyle": "->", "color": ORANGE, "lw": 1.2},
    )
    clean_axis(axis, "both")
    axis.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    save_figure(fig, out_dir, "fig2d_preamble_predicts_payload_risk")
    return {
        "scope": f"all {len(rows)} measured packet traces",
        "visual_focus": "Preamble direction dispersion is a useful packet-level risk proxy.",
    }


def render_figure4(data_dir: Path, out_dir: Path) -> dict:
    geometry = read_json(data_dir / "fig4_geometry.json")
    theta_u = float(geometry["theta_u_deg"])
    L = float(geometry["L_u"])
    cases = geometry["cases"]
    fig = plt.figure(figsize=(9.3, 3.65))
    grid = GridSpec(1, 3, figure=fig, width_ratios=[1.25, 1.25, 0.8], wspace=0.28)

    for idx, (case, color) in enumerate(zip(cases, [TEAL, RED])):
        axis = fig.add_subplot(grid[0, idx])
        theta = float(case["theta_hat_deg"])
        theta_v = float(case["theta_v_deg"])
        axis.axvspan(0, theta_u, color=LIGHT_BLUE, alpha=0.95)
        axis.axvspan(
            max(theta - theta_v, 0),
            min(theta + theta_v, 90),
            color=LIGHT_GREEN if idx == 0 else LIGHT_RED,
            alpha=0.95,
        )
        axis.plot([0, theta], [0, 0], color=MID_GRAY, linewidth=1.1, linestyle=":")
        axis.scatter([0], [0], s=90, color=BLUE, edgecolor=INK, linewidth=0.6, zorder=5)
        axis.scatter([theta], [0], s=90, color=color, edgecolor=INK, linewidth=0.6, zorder=5)
        axis.text(0, 0.13, "target", ha="left", color=BLUE, fontweight="bold")
        align = "right" if theta > 65 else "left"
        axis.text(theta, -0.14, "competitor", ha=align, color=color, fontweight="bold")
        axis.annotate(
            rf"$\widehat\theta_{{uv}}={theta:.1f}^\circ$",
            xy=(theta / 2, 0),
            xytext=(theta / 2, 0.27),
            ha="center",
            arrowprops={"arrowstyle": "-", "color": MID_GRAY},
        )
        axis.set_xlim(-2, 92)
        axis.set_ylim(-0.34, 0.52)
        axis.set_yticks([])
        axis.set_xticks([0, 30, 60, 90])
        axis.set_xlabel("projective channel angle (degree)")
        axis.set_title(
            "Easy competitor" if idx == 0 else "Near-collinear competitor",
            color=color,
            fontweight="bold",
        )
        axis.spines["left"].set_visible(False)
        clean_axis(axis, "x")
        axis.text(
            0.5,
            0.91,
            rf"$U_{{uv}}={float(case['U_uv']):.3f}$",
            transform=axis.transAxes,
            ha="center",
            fontsize=13,
            fontweight="bold",
            color=color,
        )
        panel_label(axis, f"({chr(97 + idx)})")

    metric = fig.add_subplot(grid[0, 2])
    metric.set_xlim(0, 1.05)
    metric.barh([1, 0], [float(cases[0]["U_uv"]), float(cases[1]["U_uv"])], color=[TEAL, RED], height=0.42)
    metric.axvline(L, color=BLUE, linewidth=2.2, linestyle="--")
    metric.text(float(cases[0]["U_uv"]) + 0.025, 1, f"{float(cases[0]['U_uv']):.3f}", va="center", color=TEAL, fontweight="bold")
    metric.text(0.97, 0, "1.000", ha="right", va="center", color="white", fontweight="bold")
    metric.set_yticks([1, 0], ["easy", "near-collinear"])
    metric.set_xlabel(r"worst-case match $U_{uv}$")
    metric.set_title("Worst-case match", fontweight="bold")
    metric.text(
        0.52,
        0.50,
        "73× gap",
        transform=metric.transAxes,
        ha="center",
        va="center",
        fontsize=15,
        color=INK,
        fontweight="bold",
    )
    metric.text(
        0.97,
        0.92,
        rf"same target: $L_u={L:.3f}$",
        transform=metric.transAxes,
        ha="right",
        color=BLUE,
        fontweight="bold",
    )
    metric.spines["left"].set_visible(False)
    clean_axis(metric, "x")
    panel_label(metric, "(c)")

    fig.suptitle(
        "Reliability geometry: identical target, radically different competitor risk",
        fontsize=11.8,
        fontweight="bold",
        y=0.97,
    )
    fig.subplots_adjust(left=0.06, right=0.98, bottom=0.19, top=0.78, wspace=0.34)
    save_figure(fig, out_dir, "fig4_reliability_geometry")
    return {
        "selection_rule": "Measured target with one minimum-coherence and one maximum-coherence competitor.",
        "visual_focus": "L_u is fixed while U_uv changes from 0.014 to 1.000.",
    }


def render_figure5a(data_dir: Path, out_dir: Path) -> dict:
    spec = read_json(data_dir / "fig5_overlap_and_pair_risks.json")
    scene_path = Path(spec["scene"])
    if not scene_path.is_absolute():
        scene_path = Path.cwd() / scene_path
    with np.load(scene_path, allow_pickle=False) as scene:
        metadata = json.loads(str(scene["metadata_json"]))
    packets = metadata["packets"]
    cfg = metadata["config"]
    samples_per_symbol = cfg["sample_rate_hz"] / cfg["bw_hz"] * (2 ** cfg["sf"])
    payload_start_symbols = cfg["preamble_len"] + 4.25
    target = int(spec["target_packet_index"])
    overlaps = [int(value) for value in spec["overlap_packet_indices"]]
    starts = [float(row["start_sample"]) for row in packets]
    frame = float(packets[target]["source_meta"]["frame_samples"])
    payload_begin = starts[target] + payload_start_symbols * samples_per_symbol
    target_end = starts[target] + frame
    excluded = [i for i in range(len(packets)) if i != target and i not in overlaps]
    nearest_excluded = min(excluded, key=lambda i: abs(starts[i] - starts[target]))
    display = [target] + sorted(overlaps, key=lambda i: starts[i]) + [nearest_excluded]
    origin = min(starts[index] for index in display)

    fig, axis = plt.subplots(figsize=(9.2, 4.15))
    payload_x0 = (payload_begin - origin) / samples_per_symbol
    payload_x1 = (target_end - origin) / samples_per_symbol
    axis.axvspan(payload_x0, payload_x1, color=LIGHT_BLUE, alpha=0.7, zorder=0)
    axis.text(
        (payload_x0 + payload_x1) / 2,
        0.30,
        "TARGET PAYLOAD — overlap test interval",
        ha="center",
        va="center",
        color=BLUE,
        fontweight="bold",
    )

    labels: list[str] = []
    for row_index, packet_index in enumerate(display):
        y = len(display) - 1 - row_index
        start = (starts[packet_index] - origin) / samples_per_symbol
        preamble_end = start + payload_start_symbols
        end = (starts[packet_index] - origin + frame) / samples_per_symbol
        is_target = packet_index == target
        is_overlap = packet_index in overlaps
        color = BLUE if is_target else ORANGE if is_overlap else "#AAB2B8"
        axis.broken_barh([(start, payload_start_symbols)], (y - 0.31, 0.62), facecolor=color, alpha=0.28, edgecolor="none")
        axis.broken_barh([(preamble_end, end - preamble_end)], (y - 0.31, 0.62), facecolor=color, alpha=0.95 if is_target else 0.66, edgecolor="none")
        if is_overlap:
            axis.text(min(end, payload_x1) - 0.4, y, "✓", ha="right", va="center", color=INK, fontweight="bold")
        source_label = packets[packet_index].get("source_label", f"packet {packet_index}")
        labels.append(
            f"$u$  {source_label}" if is_target else
            f"$v_{{{row_index}}}$  {source_label}" if is_overlap else
            f"excluded  {source_label}"
        )
    axis.set_yticks(np.arange(len(display)), labels[::-1])
    axis.set_xlabel("time (LoRa symbols)")
    axis.set_title(
        f"Packet intervals reduce the scene to {len(overlaps)} actual payload competitors",
        fontsize=11.4,
        fontweight="bold",
    )
    axis.text(
        0.99,
        0.02,
        "✓ intersects target payload\nexcluded packet misses the interval",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color=MID_GRAY,
    )
    clean_axis(axis, "x")
    fig.tight_layout()
    save_figure(fig, out_dir, "fig5a_interval_derived_overlap_set")
    return {
        "scene": str(scene_path),
        "target_packet_index": target,
        "included_overlap_count": len(overlaps),
        "displayed_excluded_packet": nearest_excluded,
        "visual_focus": "Only packets intersecting the target payload enter I_u.",
    }


def render_figure5b(data_dir: Path, out_dir: Path) -> dict:
    spec = read_json(data_dir / "fig5_overlap_and_pair_risks.json")
    rows = spec["pair_rows"]
    cap = float(spec["lambda_cap"])
    x = np.linspace(0, cap, 320)
    # Deliberately pick the strongest visual contrasts: easiest spatial pair,
    # two repairable negative-margin pairs, and the near-collinear limiting pair.
    selected = [2, 4, 5, 6]
    colors = [TEAL, GOLD, ORANGE, RED]
    fig = plt.figure(figsize=(7.7, 4.55))
    axis = fig.add_subplot(111, projection="3d")
    for lane, (index, color) in enumerate(zip(selected, colors)):
        values = pair_risk(rows[index], x)
        axis.plot(x, np.full_like(x, lane), values, color=color, linewidth=2.8)
        axis.plot([0, cap], [lane, lane], [0, 0], color="#BBC2C7", linewidth=0.8, linestyle=":")
        flip = float(rows[index].get("lambda_flip_under", math.inf))
        if 0 <= flip <= cap:
            axis.scatter([flip], [lane], [0], marker="*", s=70, color=color, edgecolor=INK, linewidth=0.45)
    axis.set_xlabel(r"counter-evidence weight $\lambda$", labelpad=7)
    axis.set_ylabel("detected overlap", labelpad=8)
    axis.set_zlabel(r"pair margin $R_{uv}(\lambda)$", labelpad=7)
    axis.set_yticks(range(len(selected)))
    axis.set_yticklabels([rf"$v_{index + 1}$" for index in selected])
    axis.view_init(elev=23, azim=-60)
    axis.set_title(
        "Each detected overlap contributes a different risk curve",
        fontsize=11.5,
        fontweight="bold",
        pad=12,
    )
    axis.text2D(
        0.04,
        0.92,
        "★ zero-margin flip point",
        transform=axis.transAxes,
        color=MID_GRAY,
        fontsize=8,
    )
    axis.text2D(
        0.70,
        0.72,
        "near-collinear pair\nstays below zero",
        transform=axis.transAxes,
        color=RED,
        fontweight="bold",
        ha="center",
    )
    fig.subplots_adjust(left=0.03, right=0.90, bottom=0.08, top=0.88)
    save_figure(fig, out_dir, "fig5b_pair_risk_landscape")
    return {
        "selection_rule": "Four of seven overlaps selected to maximize curve-shape and U_uv contrast.",
        "shown_pair_indices_one_based": [index + 1 for index in selected],
        "visual_focus": "One packet-level lambda must protect the most difficult overlap.",
    }


def render_figure6(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "fig6_finite_vs_dense.csv")
    summary = read_json(data_dir / "fig6_finite_vs_dense_summary.json")
    gap = 100 * np.maximum(np.asarray([float(row["normalized_objective_gap"]) for row in rows]), 0)
    diff = 100 * np.asarray([float(row["normalized_lambda_difference"]) for row in rows])
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.35))

    for axis, values, color, title, headline in [
        (axes[0], gap, TEAL, "Worst-pair objective loss", f"95% ≤ {100*summary['p95_normalized_objective_gap']:.3f}%"),
        (axes[1], diff, PURPLE, "Selected-weight difference", f"95% ≤ {100*summary['p95_normalized_lambda_difference']:.3f}%"),
    ]:
        x, y = ecdf(values)
        positive = x[x > 0]
        floor = positive.min() / 2 if positive.size else 1e-6
        axis.plot(np.maximum(x, floor), y, color=color, linewidth=2.6)
        p95 = float(np.quantile(values, 0.95))
        axis.axvline(max(p95, floor), color=color, linestyle="--", linewidth=1.1)
        axis.set_xscale("log")
        axis.set_ylim(0, 1.02)
        axis.set_xlabel("relative difference (%)")
        axis.set_ylabel("empirical CDF")
        axis.set_title(title, fontweight="bold")
        axis.text(
            0.05, 0.18, headline,
            transform=axis.transAxes,
            color=color,
            fontsize=12,
            fontweight="bold",
        )
        clean_axis(axis, "both")

    axis = axes[2]
    axis.axis("off")
    finite_ser = 100 * float(summary["finite_ser"])
    dense_ser = 100 * float(summary["dense_ser"])
    finite_prr = 100 * float(summary["finite_prr"])
    dense_prr = 100 * float(summary["dense_prr"])
    axis.text(0.5, 0.88, "End-to-end impact", ha="center", fontsize=10, fontweight="bold")
    axis.text(0.5, 0.62, f"{finite_prr-dense_prr:+.2f} pp", ha="center", fontsize=28, color=TEAL, fontweight="bold")
    axis.text(0.5, 0.50, "PRR difference", ha="center", color=MID_GRAY)
    axis.text(0.5, 0.28, f"{finite_ser-dense_ser:+.3f} pp", ha="center", fontsize=18, color=NAVY, fontweight="bold")
    axis.text(0.5, 0.18, "SER difference", ha="center", color=MID_GRAY)
    axis.add_patch(
        plt.Rectangle((0.06, 0.08), 0.88, 0.82, transform=axis.transAxes, fill=False, edgecolor=LIGHT_BLUE, linewidth=1.4)
    )

    fig.suptitle(
        f"Finite online candidates match dense search across all {len(rows)} collision scenes",
        fontsize=12.0,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig6_finite_candidates_match_dense_search")
    return {
        "scope": f"all {len(rows)} formal collision scenes; no case selection",
        "visual_focus": "Sub-percent p95 approximation error and zero PRR loss.",
    }


def render_figure7(data_dir: Path, out_dir: Path) -> dict:
    spec = read_json(data_dir / "fig7_configuration.json")
    rows = spec["pair_rows"]
    candidates = spec["candidate_points"]
    shown = [int(value) for value in spec["shown_pair_indices"]]
    cap = float(spec["scene_record"]["lambda_cap"])
    selected = float(spec["scene_record"]["finite_lambda"])
    switches = [float(value) for value in spec["envelope_switch_lambdas"]]
    x = np.linspace(0, cap, 1200)
    curves = np.vstack([pair_risk(row, x) for row in rows])
    envelope = curves.min(axis=0)

    fig = plt.figure(figsize=(9.2, 4.75))
    gs = GridSpec(2, 1, figure=fig, height_ratios=[0.68, 4.0], hspace=0.05)
    ribbon = fig.add_subplot(gs[0])
    axis = fig.add_subplot(gs[1], sharex=ribbon)
    ribbon.set_ylim(-0.2, 1.2)
    ribbon.set_yticks([])
    ribbon.spines[["left", "bottom", "right", "top"]].set_visible(False)
    ribbon.tick_params(axis="x", bottom=False, labelbottom=False)
    ribbon.text(-0.02, 0.5, "ONLINE\nPOINTS", transform=ribbon.transAxes, ha="right", va="center", color=MID_GRAY, fontsize=7.5, fontweight="bold")

    marker_map = {
        "boundary": ("|", MID_GRAY, 105),
        "analytic": ("^", ORANGE, 55),
        "midpoint": ("D", PURPLE, 48),
        "coverage": ("o", BLUE, 45),
    }
    names = {"boundary": "boundaries", "analytic": "flip/peak", "midpoint": "adaptive midpoint", "coverage": "coverage"}
    seen: set[str] = set()
    for candidate in candidates:
        category = candidate["category"]
        marker, color, size = marker_map[category]
        value = float(candidate["lambda"])
        ribbon.scatter([value], [0.5], marker=marker, s=size, color=color, edgecolor=INK if marker not in {"|"} else None, linewidth=0.45, label=names[category] if category not in seen else None)
        seen.add(category)
    ribbon.scatter([selected], [0.5], marker="*", s=150, color=RED, edgecolor=INK, linewidth=0.55, zorder=6, label=rf"chosen $\widehat\lambda_u={selected:.2f}$")
    ribbon.legend(loc="center", ncol=5, frameon=False, bbox_to_anchor=(0.53, 1.15), handletextpad=0.35, columnspacing=1.0)

    colors = [BLUE, TEAL, ORANGE]
    label_x = [3.75, 3.55, 3.35]
    for color, index, where in zip(colors, shown, label_x):
        values = pair_risk(rows[index], x)
        axis.plot(x, values, color=color, linestyle="--", linewidth=1.3, alpha=0.86)
        y_at = float(pair_risk(rows[index], where))
        axis.text(where + 0.03, y_at, rf"$R_{{uv_{index+1}}}$", color=color, va="center", fontsize=8.2)
    axis.plot(x, envelope, color=INK, linewidth=3.0)
    axis.text(3.75, float(np.interp(3.75, x, envelope)) - 0.05, r"$G_u(\lambda)$", color=INK, ha="right", va="top", fontweight="bold")
    for value in switches:
        axis.axvline(value, color="#9EA7AD", linestyle=":", linewidth=0.85)
        axis.scatter([value], [float(np.interp(value, x, envelope))], marker="x", color=PURPLE, s=35, zorder=5)
    for candidate in candidates:
        value = float(candidate["lambda"])
        axis.scatter([value], [float(np.interp(value, x, envelope))], s=18, color="#BCC4C9", zorder=4)
    selected_y = float(np.interp(selected, x, envelope))
    axis.scatter([selected], [selected_y], marker="*", s=210, color=RED, edgecolor=INK, linewidth=0.6, zorder=7)
    axis.annotate(
        "best evaluated\nworst-pair margin",
        xy=(selected, selected_y),
        xytext=(1.42, selected_y + 0.13),
        color=RED,
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.1},
    )
    ymin = min(float(envelope.min()), selected_y) - 0.18
    ymax = max(float(envelope.max()), selected_y) + 0.22
    axis.set_xlim(0, cap)
    axis.set_ylim(ymin, ymax)
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel(r"normalized margin")
    clean_axis(axis, "both")
    axis.text(
        0.03,
        0.04,
        "solid: lower envelope · dashed: explanatory continuous curves\n"
        "gray ×: offline-only envelope switches",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        color=MID_GRAY,
        fontsize=7.5,
    )
    fig.suptitle(
        "Finite packet-level points land on the worst-pair optimum",
        fontsize=11.8,
        fontweight="bold",
        y=0.99,
    )
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.13, top=0.77, hspace=0.06)
    save_figure(fig, out_dir, "fig7_finite_packet_configuration")
    return {
        "selection_rule": "Controlled measured-direction collision selected for three active worst-pair segments and checkpoint-adjacent switches.",
        "scene_index": int(spec["scene_record"]["scene_index"]),
        "visual_focus": "The red online point lands at the maximum of the worst-pair envelope.",
    }


def render_figure8(data_dir: Path, out_dir: Path) -> dict:
    snapshots = read_csv(data_dir / "fig8_snapshot_rows.csv")
    aggregate = read_csv(data_dir / "fig8_aggregate_estimates.csv")
    summary = read_json(data_dir / "fig8_summary.json")
    kernels = ["1-bin", "3-bin", "5-bin"]
    colors = {"1-bin": RED, "3-bin": ORANGE, "5-bin": BLUE}
    markers = {"1-bin": "o", "3-bin": "s", "5-bin": "D"}
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.55), gridspec_kw={"width_ratios": [1.25, 1.0, 1.05]})

    for kernel in kernels:
        rows = [row for row in snapshots if row["kernel"] == kernel]
        p = np.asarray([int(row["preamble_window"]) for row in rows])
        error = np.asarray([float(row["angle_to_clean_h_deg"]) for row in rows])
        axes[0].plot(p, error, marker=markers[kernel], color=colors[kernel], linewidth=1.7, markersize=4.5, label=kernel)
    for axis in axes[:2]:
        axis.axvspan(2.5, 7.5, color=LIGHT_RED, alpha=0.55)
        axis.axvline(2.5, color=RED, linestyle="--", linewidth=0.9)
    axes[0].text(4.9, axes[0].get_ylim()[1] * 0.94, "interferer overlaps", color=RED, ha="center", va="top", fontweight="bold", fontsize=8)
    axes[0].set_xlabel("preamble window $p$")
    axes[0].set_ylabel(r"$d(\mathbf{g}_p,\mathbf{h}_{\rm clean})$ (degree)")
    axes[0].set_title("Multi-bin snapshots", fontweight="bold")
    axes[0].legend(frameon=False, loc="upper left")
    clean_axis(axes[0])
    panel_label(axes[0], "(a)")

    rows5 = [row for row in snapshots if row["kernel"] == "5-bin"]
    p = np.asarray([int(row["preamble_window"]) for row in rows5])
    isolation = np.asarray([float(row["isolation"]) for row in rows5])
    weight = np.asarray([float(row["robust_weight"]) for row in rows5])
    axes[1].plot(p, isolation, "o-", color=TEAL, linewidth=2.0, label="local isolation")
    axes[1].plot(p, weight, "s-", color=PURPLE, linewidth=2.0, label="robust weight")
    axes[1].set_ylim(0, 1.06)
    axes[1].set_xlabel("preamble window $p$")
    axes[1].set_ylabel("normalized value")
    axes[1].set_title("Contaminated snapshots lose weight", fontweight="bold")
    axes[1].legend(frameon=False, loc="lower left")
    clean_axis(axes[1])
    panel_label(axes[1], "(b)")

    names = [row["estimator"] for row in aggregate]
    errors = np.asarray([float(row["projective_angle_to_clean_h_deg"]) for row in aggregate])
    y = np.arange(len(names))[::-1]
    bar_colors = [RED, ORANGE, BLUE, TEAL]
    axes[2].hlines(y, 0, errors, color=bar_colors, linewidth=5.2, alpha=0.85)
    axes[2].scatter(errors, y, color=bar_colors, s=65, edgecolor=INK, linewidth=0.45, zorder=4)
    axes[2].set_yticks(y, names)
    axes[2].set_xlabel(r"final $h$ error (degree)")
    axes[2].set_title("Robust packet estimate", fontweight="bold")
    clean_axis(axes[2], "x")
    plain = float(next(row["projective_angle_to_clean_h_deg"] for row in aggregate if row["estimator"] == "5-bin mean"))
    robust = float(next(row["projective_angle_to_clean_h_deg"] for row in aggregate if row["estimator"] == "5-bin robust"))
    reduction = 100 * (1 - robust / plain)
    axes[2].text(
        0.98,
        0.10,
        f"{reduction:.0f}% smaller\nthan 5-bin mean",
        transform=axes[2].transAxes,
        ha="right",
        color=TEAL,
        fontsize=12,
        fontweight="bold",
    )
    panel_label(axes[2], "(c)")

    fig.suptitle(
        rf"Selected trace-driven case: robust weighting suppresses collision-contaminated preambles "
        rf"(SIR={summary['sir_db']:g} dB)",
        fontsize=11.5,
        fontweight="bold",
        y=1.03,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig8_robust_packet_statistics")
    return {
        "selection_rule": (
            "Explicitly selected measured-pair case study; the current artifact "
            "does not contain an aggregate pair audit."
        ),
        "case_scope": summary["case_scope"],
        "five_bin_error_reduction_percent": reduction,
        "visual_focus": "Interference begins at p=3; isolation and weight collapse together.",
    }


def render_air_within(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "air_within_packet_coherence.csv")
    summary = read_json(data_dir / "air_within_packet_coherence_summary.json")
    display_snr = float(summary["display_snr_db"])
    filtered = [row for row in rows if float(row["snr_db"]) == display_snr]
    # Deliberately select the most coherent -5 dB packet/trial for the mechanism
    # panel.  Aggregate panels still retain all packets and trials.
    keys = sorted(set((int(row["source_index"]), int(row["trial"])) for row in filtered))
    key = min(
        keys,
        key=lambda item: max(
            [float(row["angle_to_packet_mean_deg"]) for row in filtered if (int(row["source_index"]), int(row["trial"])) == item]
        ),
    )
    representative = [row for row in filtered if (int(row["source_index"]), int(row["trial"])) == key]
    representative.sort(key=lambda row: int(row["preamble_window"]))
    values = np.asarray([float(row["angle_to_packet_mean_deg"]) for row in filtered])
    snr_values = sorted(set(float(row["snr_db"]) for row in rows))

    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.45))
    p = np.asarray([int(row["preamble_window"]) for row in representative])
    e = np.asarray([float(row["angle_to_packet_mean_deg"]) for row in representative])
    axes[0].stem(p, e, linefmt=BLUE, markerfmt="o", basefmt=" ")
    axes[0].axhline(np.median(e), color=ORANGE, linestyle="--", linewidth=1.2)
    axes[0].set_xlabel("preamble chirp")
    axes[0].set_ylabel(r"$d(\mathbf{h}_p,\overline{\mathbf{h}})$ (degree)")
    axes[0].set_title(f"Selected packet at {display_snr:g} dB", fontweight="bold")
    clean_axis(axes[0])
    panel_label(axes[0], "(a)")

    axes[1].hist(values, bins=30, density=True, color=LIGHT_BLUE, edgecolor="white", linewidth=0.6)
    median = float(np.median(values))
    p90 = float(np.quantile(values, 0.9))
    axes[1].axvline(median, color=TEAL, linewidth=2.0)
    axes[1].axvline(p90, color=RED, linewidth=2.0, linestyle="--")
    axes[1].text(median, axes[1].get_ylim()[1] * 0.90, f"median\n{median:.2f}°", color=TEAL, ha="right", va="top", fontweight="bold")
    axes[1].text(p90, axes[1].get_ylim()[1] * 0.90, f"90th\n{p90:.2f}°", color=RED, ha="left", va="top", fontweight="bold")
    axes[1].set_xlabel("chirp-to-packet direction error (degree)")
    axes[1].set_ylabel("density")
    axes[1].set_title(f"All packets at {display_snr:g} dB", fontweight="bold")
    clean_axis(axes[1])
    panel_label(axes[1], "(b)")

    med, q1, q3 = [], [], []
    for snr in snr_values:
        v = np.asarray([float(row["angle_to_packet_mean_deg"]) for row in rows if float(row["snr_db"]) == snr])
        q1.append(float(np.quantile(v, 0.25)))
        med.append(float(np.median(v)))
        q3.append(float(np.quantile(v, 0.75)))
    axes[2].fill_between(snr_values, q1, q3, color=LIGHT_BLUE, alpha=0.9, label="IQR")
    axes[2].plot(snr_values, med, "o-", color=NAVY, linewidth=2.4, label="median")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("injected SNR (dB)")
    axes[2].set_ylabel("direction error (degree, log)")
    axes[2].set_title("Noise controls direction stability", fontweight="bold")
    axes[2].legend(frameon=False)
    clean_axis(axes[2], "both")
    panel_label(axes[2], "(c)")

    fig.suptitle(
        "Air-channel measurement: packet-internal channel direction remains coherent",
        fontsize=11.6,
        fontweight="bold",
        y=1.03,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig_air_within_packet_coherence")
    return {
        "representative_selection_rule": "At -5 dB, choose the packet/trial with the smallest maximum across-chirp error.",
        "representative_source_trial": key,
        "aggregate_scope": "Panels (b-c) retain every packet, chirp, trial, and SNR point.",
    }


def render_air_concurrent(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "air_concurrent_channel_estimation.csv")
    summary_rows = read_csv(data_dir / "air_concurrent_channel_summary.csv")
    summary = read_json(data_dir / "air_concurrent_channel_summary.json")
    sir_values = [float(value) for value in summary["sir_db"]]
    distances = [float(value) for value in summary["fft_bin_distance"]]
    fig, axes = plt.subplots(
        1,
        4,
        figsize=(13.0, 3.55),
        gridspec_kw={"width_ratios": [1.08, 1, 1, 1]},
    )
    all_errors = np.asarray([float(row["target_h_error_deg"]) for row in rows])
    x, y = ecdf(all_errors)
    axes[0].plot(x, y, color=PURPLE, linewidth=2.7)
    axes[0].axvline(float(np.median(all_errors)), color=TEAL, linewidth=1.2)
    axes[0].axvline(float(np.quantile(all_errors, 0.9)), color=RED, linewidth=1.2, linestyle="--")
    axes[0].text(0.97, 0.22, f"median {np.median(all_errors):.1f}°\n90th {np.quantile(all_errors,.9):.1f}°", transform=axes[0].transAxes, ha="right", color=INK, fontweight="bold")
    axes[0].set_xscale("log")
    axes[0].set_xlabel(r"$d(\widehat{\mathbf{h}},\mathbf{h}_{\rm clean})$ (degree)")
    axes[0].set_ylabel("empirical CDF")
    axes[0].set_title("All 720 collisions", fontweight="bold")
    clean_axis(axes[0], "both")
    panel_label(axes[0], "(a)")

    global_low = max(min(float(row["q25_h_error_deg"]) for row in summary_rows) * 0.65, 0.08)
    global_high = max(float(row["q75_h_error_deg"]) for row in summary_rows) * 1.45
    for index, (axis, sir) in enumerate(zip(axes[1:], sir_values)):
        med, q1, q3 = [], [], []
        for distance in distances:
            match = next(row for row in summary_rows if float(row["sir_db"]) == sir and float(row["fft_bin_distance"]) == distance)
            q1.append(float(match["q25_h_error_deg"]))
            med.append(float(match["median_h_error_deg"]))
            q3.append(float(match["q75_h_error_deg"]))
        xpos = np.arange(len(distances))
        axis.axvspan(2.5, 5.5, color=LIGHT_GREEN, alpha=0.65)
        axis.fill_between(xpos, q1, q3, color=LIGHT_BLUE, alpha=0.85)
        axis.plot(xpos, med, "o-", color=NAVY, linewidth=2.3)
        axis.set_yscale("log")
        axis.set_ylim(global_low, global_high)
        axis.set_xticks(xpos, [f"{value:g}" for value in distances])
        axis.set_xlabel("FFT-bin separation")
        axis.set_title(f"SIR = {sir:g} dB", fontweight="bold")
        axis.text(0.98, 0.93, f"{med[0]:.1f}° → {med[-1]:.2f}°", transform=axis.transAxes, ha="right", va="top", color=TEAL, fontweight="bold")
        clean_axis(axis, "both")
        panel_label(axis, f"({chr(98 + index)})")
        if index > 0:
            axis.set_yticklabels([])
    axes[1].set_ylabel("channel error (degree, log)")
    fig.suptitle(
        rf"Measured-waveform collisions: spectral separation sharply restores channel estimation "
        rf"($\Delta\tau={summary['offset_symbols']:g}T_s$)",
        fontsize=11.6,
        fontweight="bold",
        y=1.03,
    )
    fig.text(0.79, 0.02, "green region: ≥4-bin separation", color=GREEN, ha="center", fontsize=8)
    fig.tight_layout()
    save_figure(fig, out_dir, "fig_air_concurrent_channel_estimation")
    return {
        "scope": f"all {len(rows)} collision trials; no case selection",
        "visual_focus": "A common log scale exposes the order-of-magnitude error drop beyond four bins.",
    }


def write_manifest(out_dir: Path, source_dir: Path, data_dir: Path, figures: dict) -> None:
    manifest = {
        "purpose": "Publication-focused rerendering of SP-Decoder v2 experiments",
        "source_data_directory": str(data_dir.resolve()),
        "author_selected_source_figures": str(source_dir.resolve()),
        "integrity_policy": {
            "mechanism_figures": (
                "Representative cases may be deliberately selected for visual contrast; "
                "the selection rule is stated per figure."
            ),
            "aggregate_figures": (
                "Figure 6 and air-channel aggregate panels retain all sidecar samples."
            ),
            "data_mutation": "No CSV/JSON value is changed by this renderer.",
        },
        "figures": figures,
    }
    with (out_dir / "publication_figure_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("real_usrp_outputs/sp_v2_mechanism_figures"),
        help="CSV/JSON sidecar directory from the experiment generator",
    )
    parser.add_argument(
        "--source-figure-dir",
        type=Path,
        default=Path("real_usrp_outputs/sp_paper_figures"),
        help="Directory containing author-selected Figure 2(a-b) sources",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("real_usrp_outputs/sp_v2_publication_figures"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_style()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "figure2_ab": copy_figure2_ab(args.source_figure_dir, args.out_dir),
        "figure2c": render_figure2c(args.data_dir, args.out_dir),
        "figure2d": render_figure2d(args.data_dir, args.out_dir),
        "figure4": render_figure4(args.data_dir, args.out_dir),
        "figure5a": render_figure5a(args.data_dir, args.out_dir),
        "figure5b": render_figure5b(args.data_dir, args.out_dir),
        "figure6": render_figure6(args.data_dir, args.out_dir),
        "figure7": render_figure7(args.data_dir, args.out_dir),
        "figure8": render_figure8(args.data_dir, args.out_dir),
        "air_within_packet": render_air_within(args.data_dir, args.out_dir),
        "air_concurrent": render_air_concurrent(args.data_dir, args.out_dir),
    }
    write_manifest(args.out_dir, args.source_figure_dir, args.data_dir, figures)
    print(
        json.dumps(
            {"out_dir": str(args.out_dir.resolve()), "figures": list(figures)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
