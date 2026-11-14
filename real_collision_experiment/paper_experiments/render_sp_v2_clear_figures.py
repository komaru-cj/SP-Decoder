#!/usr/bin/env python3
"""Render the human-readable, academically conservative SP-Decoder figures.

The script consumes the validated sidecars from
``generate_sp_v2_mechanism_figures.py``.  It deliberately uses a small visual
vocabulary: two-dimensional comparisons, direct labels, common axes, and one
question per figure.  No experiment value is modified.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_decoder_matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm, TwoSlopeNorm
from matplotlib.patches import Arc, FancyArrowPatch, Rectangle, Wedge

from render_sp_v2_publication_figures import (
    BLUE,
    GREEN,
    INK,
    LIGHT_BLUE,
    LIGHT_GRAY,
    LIGHT_GREEN,
    LIGHT_RED,
    MID_GRAY,
    NAVY,
    ORANGE,
    PURPLE,
    RED,
    TEAL,
    clean_axis,
    configure_style,
    copy_figure2_ab,
    ecdf,
    pair_risk,
    panel_label,
    read_csv,
    read_json,
    render_air_within,
    render_figure2c as render_packet_lambda_figure,
    render_figure5a,
    save_figure,
)


def render_figure2c(data_dir: Path, out_dir: Path) -> dict:
    return render_packet_lambda_figure(data_dir, out_dir)


def render_figure2d(data_dir: Path, out_dir: Path) -> dict:
    all_rows = read_csv(
        data_dir / "fig2d_collision_direction_lambda_ser.csv"
    )
    summary = read_json(
        data_dir / "fig2d_collision_direction_ser_summary.json"
    )
    rows = all_rows
    x = np.asarray(
        [float(row["direction_error_deg"]) for row in rows]
    )
    ser = np.asarray([float(row["ser"]) for row in rows])
    evaluated_lambda = np.asarray(
        [float(row["evaluation_lambda"]) for row in rows]
    )
    plotted_x = x

    fig, axis = plt.subplots(figsize=(7.25, 4.05))
    points = axis.scatter(
        plotted_x,
        ser,
        c=evaluated_lambda,
        cmap="viridis",
        vmin=0.0,
        vmax=4.0,
        marker="o",
        s=19,
        edgecolor="none",
        alpha=0.30,
        label=r"all nine $\lambda$ evaluations",
        zorder=2,
    )
    axis.axhspan(0.0, 0.2, color="#DDF2E9", alpha=0.55, zorder=0)
    axis.axhline(0.2, color=TEAL, linestyle=":", linewidth=1.15)
    axis.text(
        12.15,
        0.215,
        r"$\geq80\%$ symbol success",
        color=TEAL,
        ha="right",
        va="bottom",
        fontsize=7.7,
        fontweight="bold",
    )
    axis.axvline(0.0, color=MID_GRAY, linestyle=":", linewidth=1.0)
    axis.set_xlim(-12.6, 12.6)
    axis.set_ylim(-0.035, 1.03)
    axis.set_xticks(np.arange(-10, 11, 2))
    axis.set_xlabel(
        r"collision-biased preamble direction error $\Delta\psi$ (degree)"
    )
    axis.set_ylabel("payload SER")
    axis.set_title(
        r"A usable $\lambda$ often survives sizable preamble-direction error",
        fontweight="bold",
    )
    colorbar = fig.colorbar(points, ax=axis, pad=0.015)
    colorbar.set_label(r"evaluated counter-evidence weight $\lambda$")
    colorbar.set_ticks(np.arange(0.0, 4.01, 0.5))
    axis.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.17),
        fontsize=7.2,
        ncol=1,
    )
    clean_axis(axis, "both")
    fig.tight_layout(rect=(0.0, 0.10, 1.0, 1.0))
    save_figure(fig, out_dir, "fig2d_preamble_predicts_payload_risk")
    return {
        "question": (
            "Does a safe lambda still exist under collision-biased "
            "preamble direction errors?"
        ),
        "answer": (
            "Across the 0--4 grid, many collisions retain a low-SER operating "
            "point even around ten degrees of direction error."
        ),
        "scope": (
            f"All {summary['rendered_scene_count']} collisions and all "
            f"{summary['rendered_lambda_evaluation_count']} lambda "
            "evaluations are shown without a highlighted best-case subset."
        ),
        "edge_best_median_ser": summary["edge_best_median_ser"],
        "edge_success_fraction": (
            summary[
                "edge_has_lambda_with_symbol_success_at_least_80_percent_fraction"
            ]
        ),
    }


def draw_direction_geometry(
    axis: plt.Axes,
    theta_u: float,
    theta_v: float,
    theta_hat: float,
    competitor_color: str,
    title: str,
) -> None:
    axis.add_patch(Wedge((0, 0), 1.0, -theta_u, theta_u, facecolor=LIGHT_BLUE, edgecolor="none", alpha=0.95))
    axis.add_patch(
        Wedge(
            (0, 0),
            0.92,
            theta_hat - theta_v,
            theta_hat + theta_v,
            facecolor=LIGHT_GREEN if competitor_color == TEAL else LIGHT_RED,
            edgecolor="none",
            alpha=0.95,
        )
    )
    target = np.array([1.0, 0.0])
    angle = math.radians(theta_hat)
    competitor = np.array([math.cos(angle), math.sin(angle)])
    axis.add_patch(FancyArrowPatch((0, 0), target, arrowstyle="-|>", mutation_scale=16, linewidth=2.5, color=BLUE))
    axis.add_patch(FancyArrowPatch((0, 0), competitor, arrowstyle="-|>", mutation_scale=16, linewidth=2.5, color=competitor_color))
    if theta_hat > 3:
        axis.add_patch(Arc((0, 0), 0.72, 0.72, theta1=0, theta2=theta_hat, color=MID_GRAY, linewidth=1.2))
        mid = math.radians(theta_hat / 2)
        axis.text(0.43 * math.cos(mid), 0.43 * math.sin(mid), rf"${theta_hat:.1f}^\circ$", ha="center", va="center")
    else:
        axis.text(0.42, 0.09, rf"${theta_hat:.1f}^\circ$", color=RED, fontweight="bold")
    axis.text(1.02, -0.02, "target", color=BLUE, fontweight="bold", va="center")
    axis.text(0.96 * competitor[0], 0.96 * competitor[1] + 0.06, "competitor", color=competitor_color, fontweight="bold", ha="center")
    arc = np.linspace(0, np.pi / 2, 100)
    axis.plot(np.cos(arc), np.sin(arc), color="#CDD3D8", linewidth=0.8)
    axis.axhline(0, color="#D8DDE1", linewidth=0.7)
    axis.axvline(0, color="#D8DDE1", linewidth=0.7)
    axis.set_xlim(-0.08, 1.15)
    axis.set_ylim(-0.10, 1.10)
    axis.set_aspect("equal")
    axis.set_xticks([])
    axis.set_yticks([])
    axis.spines[["left", "bottom", "right", "top"]].set_visible(False)
    axis.set_title(title, color=competitor_color, fontweight="bold")


def render_figure4(data_dir: Path, out_dir: Path) -> dict:
    geometry = read_json(data_dir / "fig4_geometry.json")
    theta_u = float(geometry["theta_u_deg"])
    L = float(geometry["L_u"])
    easy, near = geometry["cases"]
    fig, axes = plt.subplots(1, 3, figsize=(8.9, 3.25), gridspec_kw={"width_ratios": [1, 1, 0.9]})
    draw_direction_geometry(
        axes[0],
        theta_u,
        float(easy["theta_v_deg"]),
        float(easy["theta_hat_deg"]),
        TEAL,
        "Easy competitor",
    )
    draw_direction_geometry(
        axes[1],
        theta_u,
        float(near["theta_v_deg"]),
        float(near["theta_hat_deg"]),
        RED,
        "Near-collinear competitor",
    )
    panel_label(axes[0], "(a)")
    panel_label(axes[1], "(b)")

    axis = axes[2]
    u = [float(easy["U_uv"]), float(near["U_uv"])]
    ypos = [1, 0]
    axis.barh(ypos, u, height=0.42, color=[TEAL, RED])
    axis.axvline(L, color=BLUE, linestyle="--", linewidth=2.0, label=rf"target lower bound $L_u={L:.3f}$")
    axis.text(u[0] + 0.03, 1, f"{u[0]:.3f}", va="center", color=TEAL, fontweight="bold")
    axis.text(0.97, 0, f"{u[1]:.3f}", ha="right", va="center", color="white", fontweight="bold")
    axis.set_yticks(ypos, ["easy", "near-collinear"])
    axis.set_xlim(0, 1.05)
    axis.set_xlabel(r"competitor upper bound $U_{uv}$")
    axis.set_title("Retained-energy bounds", fontweight="bold")
    axis.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.20))
    clean_axis(axis, "x")
    panel_label(axis, "(c)")
    fig.suptitle(
        "Figure 4: the same target can face very different spatial ambiguity",
        fontsize=11.5,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig4_reliability_geometry")
    return {
        "question": "Why is one lambda not equally safe for every target-interferer pair?",
        "answer": "With the same L_u, U_uv changes from 0.014 to 1.000 as the channels become collinear.",
        "selection": "One measured target with its easiest and most collinear measured competitors.",
    }


def render_figure5b(data_dir: Path, out_dir: Path) -> dict:
    spec = read_json(data_dir / "fig5_overlap_and_pair_risks.json")
    rows = spec["pair_rows"]
    cap = float(spec["lambda_cap"])
    lambdas = np.linspace(0, cap, 401)
    values = np.vstack([pair_risk(row, lambdas) for row in rows])
    limit = max(abs(float(values.min())), abs(float(values.max())))
    limit = min(max(limit, 10.0), 22.0)

    fig, axis = plt.subplots(figsize=(7.2, 3.65))
    image = axis.imshow(
        values,
        aspect="auto",
        origin="upper",
        extent=[0, cap, len(rows) - 0.5, -0.5],
        cmap="RdBu",
        norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
        interpolation="nearest",
    )
    for index, row in enumerate(rows):
        flip = float(row.get("lambda_flip_under", math.inf))
        if 0 <= flip <= cap:
            axis.scatter([flip], [index], marker="*", s=65, color="#FFD166", edgecolor=INK, linewidth=0.5, zorder=5)
    axis.set_yticks(np.arange(len(rows)), [rf"$v_{index + 1}$" for index in range(len(rows))])
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel("overlapping competitor")
    axis.set_title("Each overlap imposes a different safe weight range", fontweight="bold")
    colorbar = fig.colorbar(image, ax=axis, pad=0.025)
    colorbar.set_label(r"pair margin $R_{uv}(\lambda)$")
    axis.text(
        0.985,
        0.035,
        "blue: positive margin\nred: negative margin\n★: zero-margin flip",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.6,
        color=MID_GRAY,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#D8DDE1", "alpha": 0.92},
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig5b_pair_risk_heatmap")
    return {
        "question": "How do all detected overlaps constrain lambda?",
        "answer": "Every row has a different safe region; the near-collinear row remains negative.",
        "scope": f"All {len(rows)} overlaps in the selected timeline scene.",
    }


def render_figure6(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "fig6_finite_vs_dense.csv")
    summary = read_json(data_dir / "fig6_finite_vs_dense_summary.json")
    gap = np.maximum(np.asarray([float(row["normalized_objective_gap"]) for row in rows]), 0)
    finite_lambda = np.asarray([float(row["finite_lambda"]) for row in rows])
    dense_lambda = np.asarray([float(row["dense_lambda"]) for row in rows])

    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.25))
    axis = axes[0]
    x, y = ecdf(100 * gap)
    positive = x[x > 0]
    floor = positive.min() / 2 if positive.size else 1e-7
    axis.plot(np.maximum(x, floor), y, color=TEAL, linewidth=2.5)
    p95 = 100 * float(summary["p95_normalized_objective_gap"])
    exact = 100 * float(np.mean(gap <= 1e-12))
    axis.axvline(p95, color=ORANGE, linestyle="--", linewidth=1.3)
    axis.set_xscale("log")
    axis.set_xlabel("relative objective loss (%)")
    axis.set_ylabel("empirical CDF")
    axis.set_title("Objective approximation", fontweight="bold")
    axis.text(0.05, 0.24, f"{exact:.0f}% exact\n95th ≤ {p95:.3f}%", transform=axis.transAxes, color=TEAL, fontweight="bold")
    clean_axis(axis, "both")
    panel_label(axis, "(a)")

    axis = axes[1]
    axis.scatter(dense_lambda, finite_lambda, s=18, color=PURPLE, alpha=0.55, edgecolor="none")
    axis.plot([0, 4], [0, 4], color=INK, linestyle="--", linewidth=1.3, label="exact agreement")
    axis.set_xlim(-0.08, 4.08)
    axis.set_ylim(-0.08, 4.08)
    axis.set_aspect("equal")
    axis.set_xlabel(r"dense-search $\lambda$")
    axis.set_ylabel(r"finite-candidate $\widehat\lambda$")
    axis.set_title("Selected weight", fontweight="bold")
    axis.legend(frameon=False, loc="lower right")
    axis.text(
        0.04,
        0.94,
        "off-diagonal cases retain\nthe same symbol-error count",
        transform=axis.transAxes,
        va="top",
        fontsize=7.5,
        color=MID_GRAY,
    )
    clean_axis(axis, "both")
    panel_label(axis, "(b)")

    axis = axes[2]
    metrics = ["SER", "PRR"]
    finite = np.asarray([100 * float(summary["finite_ser"]), 100 * float(summary["finite_prr"])])
    dense = np.asarray([100 * float(summary["dense_ser"]), 100 * float(summary["dense_prr"])])
    ypos = np.asarray([1, 0])
    for yrow, fvalue, dvalue in zip(ypos, finite, dense):
        axis.plot([fvalue, dvalue], [yrow, yrow], color="#B8C0C6", linewidth=2.0)
        axis.scatter([dvalue], [yrow], color=MID_GRAY, marker="s", s=48, label="dense" if yrow == 1 else None)
        axis.scatter([fvalue], [yrow], color=BLUE, marker="o", s=55, label="finite" if yrow == 1 else None)
        axis.text(max(fvalue, dvalue) + 1.4, yrow, f"Δ {fvalue-dvalue:+.3f} pp", va="center", fontsize=8, fontweight="bold")
    axis.set_yticks(ypos, metrics)
    axis.set_xlim(0, 70)
    axis.set_xlabel("rate (%)")
    axis.set_title("End-to-end decoding", fontweight="bold")
    axis.legend(frameon=False)
    clean_axis(axis, "x")
    panel_label(axis, "(c)")
    fig.suptitle(
        f"Figure 6: finite candidates reproduce dense search over all {len(rows)} scenes",
        fontsize=11.5,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig6_finite_vs_dense")
    return {
        "question": "Does the constant-size candidate set approximate dense search?",
        "answer": "Weights lie near the equality line and PRR is unchanged.",
        "scope": f"All {len(rows)} formal collision scenes.",
    }


def candidate_category(candidate: dict) -> str:
    return str(candidate["category"])


def render_figure7(data_dir: Path, out_dir: Path) -> dict:
    spec = read_json(data_dir / "fig7_configuration.json")
    rows = spec["pair_rows"]
    candidates = spec["candidate_points"]
    shown = [int(value) for value in spec["shown_pair_indices"]]
    cap = float(spec["scene_record"]["lambda_cap"])
    selected = float(spec["scene_record"]["finite_lambda"])
    switches = [float(value) for value in spec["envelope_switch_lambdas"]]
    x = np.linspace(0, cap, 1000)
    curves = np.vstack([pair_risk(row, x) for row in rows])
    envelope = curves.min(axis=0)

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.65), gridspec_kw={"width_ratios": [1.65, 0.9]})
    axis = axes[0]
    for index in shown:
        axis.plot(x, curves[index], color="#AEB6BC", linewidth=1.1, linestyle="--")
    axis.plot(x, envelope, color=INK, linewidth=3.0, label=r"$G_u(\lambda)=\min_v R_{uv}(\lambda)$")
    for switch in switches:
        axis.axvline(switch, color="#BEC5CA", linestyle=":", linewidth=0.9)
    for candidate in candidates:
        value = float(candidate["lambda"])
        objective = float(np.interp(value, x, envelope))
        axis.scatter([value], [objective], s=34, color=BLUE, edgecolor="white", linewidth=0.4, zorder=5)
    selected_y = float(np.interp(selected, x, envelope))
    axis.scatter([selected], [selected_y], marker="*", s=190, color=RED, edgecolor=INK, linewidth=0.6, zorder=6)
    axis.annotate(
        rf"chosen $\widehat\lambda_u={selected:.2f}$",
        xy=(selected, selected_y),
        xytext=(1.42, selected_y + 0.08),
        color=RED,
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.0},
    )
    axis.set_xlim(0, cap)
    axis.set_ylim(envelope.min() - 0.18, envelope.max() + 0.24)
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel("worst-pair normalized margin")
    axis.set_title("Evaluate only the blue candidate points", fontweight="bold")
    axis.legend(frameon=False, loc="lower left")
    clean_axis(axis, "both")
    panel_label(axis, "(a)")

    flow = axes[1]
    flow.axis("off")
    boxes = [
        ("1  Build candidates", "boundaries\nflip/peak points\nmidpoint + 3 coverage"),
        ("2  Evaluate", r"compute $G_u(\lambda)$" + "\nonly at candidates"),
        ("3  Select", r"choose the largest $G_u$" + "\ntie → smaller λ"),
    ]
    y_positions = [0.77, 0.45, 0.13]
    for number, ((title, body), ypos) in enumerate(zip(boxes, y_positions)):
        flow.add_patch(
            Rectangle(
                (0.08, ypos),
                0.84,
                0.20,
                transform=flow.transAxes,
                facecolor=[LIGHT_BLUE, LIGHT_GREEN, LIGHT_RED][number],
                edgecolor=[BLUE, TEAL, RED][number],
                linewidth=1.1,
            )
        )
        flow.text(0.13, ypos + 0.145, title, transform=flow.transAxes, fontweight="bold", color=[BLUE, TEAL, RED][number])
        flow.text(0.13, ypos + 0.075, body, transform=flow.transAxes, va="center", fontsize=8)
        if number < 2:
            flow.annotate(
                "",
                xy=(0.50, ypos - 0.10),
                xytext=(0.50, ypos - 0.02),
                xycoords=flow.transAxes,
                arrowprops={"arrowstyle": "-|>", "color": MID_GRAY, "lw": 1.1},
            )
    flow.set_title("Online packet-level procedure", fontweight="bold")
    panel_label(flow, "(b)")
    fig.suptitle(
        "Figure 7: finite packet-level configuration",
        fontsize=11.5,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig7_finite_packet_configuration")
    return {
        "question": "How is lambda selected online without dense search?",
        "answer": "Evaluate G_u only at a finite candidate set and choose the largest value.",
        "selection": "Controlled measured-direction collision with three active worst-pair segments and checkpoint-adjacent switches.",
    }


def render_figure8(data_dir: Path, out_dir: Path) -> dict:
    snapshots = read_csv(data_dir / "fig8_snapshot_rows.csv")
    aggregate = read_csv(data_dir / "fig8_aggregate_estimates.csv")
    summary = read_json(data_dir / "fig8_summary.json")
    rows5 = sorted(
        [row for row in snapshots if row["kernel"] == "5-bin"],
        key=lambda row: int(row["preamble_window"]),
    )
    p = np.asarray([int(row["preamble_window"]) for row in rows5])
    angle = np.asarray([float(row["angle_to_clean_h_deg"]) for row in rows5])
    isolation = np.asarray([float(row["isolation"]) for row in rows5])
    weight = np.asarray([float(row["robust_weight"]) for row in rows5])

    fig, axes = plt.subplots(1, 3, figsize=(9.7, 3.25))
    axis = axes[0]
    axis.axvspan(2.5, 7.5, color=LIGHT_RED, alpha=0.65)
    axis.plot(p, angle, "o-", color=BLUE, linewidth=2.0)
    axis.axvline(2.5, color=RED, linestyle="--", linewidth=1.0)
    axis.text(4.8, angle.max() * 0.95, "interferer overlaps", ha="center", va="top", color=RED, fontweight="bold", fontsize=8)
    axis.set_xlabel("preamble window $p$")
    axis.set_ylabel(r"$d(\mathbf{g}_p,\mathbf{h}_{\rm clean})$ (degree)")
    axis.set_title("5-bin channel snapshots", fontweight="bold")
    clean_axis(axis)
    panel_label(axis, "(a)")

    axis = axes[1]
    axis.axvspan(2.5, 7.5, color=LIGHT_RED, alpha=0.65)
    axis.plot(p, isolation, "o-", color=TEAL, linewidth=2.0, label="local isolation")
    axis.plot(p, weight, "s--", color=PURPLE, linewidth=2.0, label="robust weight")
    axis.axvline(2.5, color=RED, linestyle="--", linewidth=1.0)
    axis.set_ylim(0, 1.05)
    axis.set_xlabel("preamble window $p$")
    axis.set_ylabel("normalized value")
    axis.set_title("Contaminated snapshots are downweighted", fontweight="bold")
    axis.legend(frameon=False, loc="lower left")
    clean_axis(axis)
    panel_label(axis, "(b)")

    axis = axes[2]
    plain = float(next(row["projective_angle_to_clean_h_deg"] for row in aggregate if row["estimator"] == "5-bin mean"))
    robust = float(next(row["projective_angle_to_clean_h_deg"] for row in aggregate if row["estimator"] == "5-bin robust"))
    values = [plain, robust]
    ypos = [1, 0]
    axis.barh(ypos, values, height=0.42, color=[MID_GRAY, TEAL])
    axis.set_yticks(ypos, ["unweighted mean", "robust estimate"])
    axis.set_xlabel(r"final $h$ error (degree)")
    axis.set_title("Packet-level channel estimate", fontweight="bold")
    for pos, value in zip(ypos, values):
        axis.text(value + 0.001, pos, f"{value:.3f}°", va="center", fontweight="bold")
    reduction = 100 * (1 - robust / plain)
    axis.text(0.98, 0.12, f"{reduction:.0f}% lower error", transform=axis.transAxes, ha="right", color=TEAL, fontweight="bold")
    clean_axis(axis, "x")
    panel_label(axis, "(c)")
    fig.suptitle(
        rf"Figure 8: robust preamble aggregation in a selected measured collision "
        rf"(SIR={summary['sir_db']:g} dB)",
        fontsize=11.1,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig8_robust_packet_statistics")
    return {
        "question": "How does robust packet-level channel estimation handle contaminated preambles?",
        "answer": "Isolation drops at p=3, the corresponding weights fall, and final direction error is 72% lower.",
        "selection": "Explicitly selected measured-pair case study; no aggregate pair claim.",
    }


def render_air_concurrent(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "air_concurrent_channel_estimation.csv")
    summary_rows = read_csv(data_dir / "air_concurrent_channel_summary.csv")
    summary = read_json(data_dir / "air_concurrent_channel_summary.json")
    sirs = [float(value) for value in summary["sir_db"]]
    distances = [float(value) for value in summary["fft_bin_distance"]]
    median = np.zeros((len(sirs), len(distances)))
    q1 = np.zeros_like(median)
    q3 = np.zeros_like(median)
    for i, sir in enumerate(sirs):
        for j, distance in enumerate(distances):
            match = next(
                row
                for row in summary_rows
                if float(row["sir_db"]) == sir and float(row["fft_bin_distance"]) == distance
            )
            median[i, j] = float(match["median_h_error_deg"])
            q1[i, j] = float(match["q25_h_error_deg"])
            q3[i, j] = float(match["q75_h_error_deg"])

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.45), gridspec_kw={"width_ratios": [1.15, 1.0]})
    axis = axes[0]
    image = axis.imshow(
        median,
        cmap="RdYlGn_r",
        norm=LogNorm(vmin=max(median.min(), 0.1), vmax=median.max()),
        aspect="auto",
    )
    for i in range(len(sirs)):
        for j in range(len(distances)):
            color = "white" if median[i, j] > 12 else INK
            axis.text(j, i, f"{median[i,j]:.1f}°", ha="center", va="center", color=color, fontweight="bold", fontsize=8)
    axis.set_xticks(np.arange(len(distances)), [f"{value:g}" for value in distances])
    axis.set_yticks(np.arange(len(sirs)), [f"{value:g}" for value in sirs])
    axis.set_xlabel("FFT-bin separation")
    axis.set_ylabel("SIR (dB)")
    axis.set_title("Median channel-direction error", fontweight="bold")
    colorbar = fig.colorbar(image, ax=axis, pad=0.025)
    colorbar.set_label("error (degree, log color scale)")
    panel_label(axis, "(a)")

    axis = axes[1]
    colors = [RED, ORANGE, TEAL]
    xpos = np.arange(len(distances))
    axis.axvspan(2.5, 5.5, color=LIGHT_GREEN, alpha=0.7)
    for i, (sir, color) in enumerate(zip(sirs, colors)):
        axis.fill_between(xpos, q1[i], q3[i], color=color, alpha=0.11)
        axis.plot(xpos, median[i], "o-", color=color, linewidth=2.0, label=f"SIR {sir:g} dB")
    axis.axvline(2.5, color=GREEN, linestyle="--", linewidth=1.0)
    axis.set_yscale("log")
    axis.set_xticks(xpos, [f"{value:g}" for value in distances])
    axis.set_xlabel("FFT-bin separation")
    axis.set_ylabel("channel-direction error (degree)")
    axis.set_title("Error drops after ≥4-bin separation", fontweight="bold")
    axis.legend(frameon=False)
    clean_axis(axis, "both")
    panel_label(axis, "(b)")
    fig.suptitle(
        rf"Air-channel measurement: staggered measured-waveform collisions "
        rf"($\Delta\tau={summary['offset_symbols']:g}T_s$)",
        fontsize=11.3,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig_air_concurrent_channel_estimation")
    return {
        "question": "How does spectral separation affect channel estimation under collision?",
        "answer": "Across every SIR, median error falls sharply once separation reaches four bins.",
        "scope": f"All {len(rows)} measured-waveform collision trials.",
    }


def write_manifest(out_dir: Path, data_dir: Path, source_dir: Path, figures: dict) -> None:
    payload = {
        "version": "clear-human-readable-v1",
        "design_policy": [
            "one research question per figure",
            "left-to-right phenomenon -> method action -> result",
            "two-dimensional comparisons instead of decorative 3D",
            "direct labels and common axes",
            "selected cases only for mechanism illustration; aggregate claims retain all samples",
        ],
        "data_dir": str(data_dir.resolve()),
        "source_figure_dir": str(source_dir.resolve()),
        "figures": figures,
    }
    with (out_dir / "clear_figure_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("real_usrp_outputs/sp_v2_mechanism_figures"))
    parser.add_argument("--source-figure-dir", type=Path, default=Path("real_usrp_outputs/sp_paper_figures"))
    parser.add_argument("--out-dir", type=Path, default=Path("real_usrp_outputs/sp_v2_publication_figures_clear"))
    parser.add_argument(
        "--only-fig2d",
        action="store_true",
        help="render only the collision direction-error robustness figure",
    )
    parser.add_argument(
        "--only-fig2c",
        action="store_true",
        help="render only the four-packet lambda-sensitivity figure",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_style()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.only_fig2c:
        figures = {
            "figure2c": render_figure2c(args.data_dir, args.out_dir)
        }
        write_manifest(
            args.out_dir,
            args.data_dir,
            args.source_figure_dir,
            figures,
        )
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figures": list(figures),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.only_fig2d:
        figures = {
            "figure2d": render_figure2d(args.data_dir, args.out_dir)
        }
        write_manifest(
            args.out_dir,
            args.data_dir,
            args.source_figure_dir,
            figures,
        )
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figures": list(figures),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
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
    write_manifest(args.out_dir, args.data_dir, args.source_figure_dir, figures)
    print(json.dumps({"out_dir": str(args.out_dir.resolve()), "figures": list(figures)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
