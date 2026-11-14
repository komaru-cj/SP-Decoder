#!/usr/bin/env python3
"""Render the compact, paper-native SP-Decoder figure set.

Each figure is assigned one proof obligation by its manuscript position.  The
renderer minimizes subplot count and decorative whitespace while retaining the
validated experiment sidecars unchanged.
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
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Arc, FancyArrowPatch, Rectangle, Wedge
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from render_sp_v2_publication_figures import (
    BLUE,
    GREEN,
    INK,
    LIGHT_BLUE,
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
    pair_risk,
    panel_label,
    read_csv,
    read_json,
    save_figure,
)
def render_figure2c(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "fig2c_trace_curve_suite.csv")
    summary = read_json(data_dir / "fig2c_trace_curve_suite_summary.json")
    colors = [BLUE, TEAL, ORANGE, PURPLE, GREEN, RED, NAVY]
    markers = ["o", "s", "^", "D", "P", "v", "X"]
    fig, axis = plt.subplots(figsize=(7.8, 6.25))

    rendered_cases: list[dict] = []
    for case, color, marker in zip(summary["cases"], colors, markers):
        case_label = str(case["case_label"])
        selected = sorted(
            [row for row in rows if row["case_label"] == case_label],
            key=lambda row: float(row["evaluation_lambda"]),
        )
        lambdas = np.asarray(
            [float(row["evaluation_lambda"]) for row in selected]
        )
        ser = np.asarray([float(row["ser"]) for row in selected])
        lambda_star = float(case["minimum_lambda_low"])
        star_index = int(np.where(np.isclose(lambdas, lambda_star))[0][0])
        axis.plot(
            lambdas,
            ser,
            color=color,
            linewidth=1.62,
            marker=marker,
            markersize=3.25,
            markeredgecolor="white",
            markeredgewidth=0.38,
            label=case_label,
            zorder=3,
        )
        axis.scatter(
            [lambda_star],
            [ser[star_index]],
            marker="*",
            s=66,
            color=color,
            edgecolor=INK,
            linewidth=0.40,
            zorder=6,
        )
        rendered_cases.append(
            {
                "case_label": case_label,
                "target_label": case["target_label"],
                "interferer_label": case["interferer_label"],
                "sir_db": float(case["sir_db"]),
                "offset_symbols": float(case["offset_symbols"]),
                "preamble_bin_separation": float(
                    case["preamble_bin_separation"]
                ),
                "minimum_lambda_low": lambda_star,
                "minimum_lambda_high": float(case["minimum_lambda_high"]),
                "minimum_ser": float(case["minimum_ser"]),
            }
        )

    best_weights = summary["best_recovery_weights"]

    axis.set_xlim(0.0, 7.0)
    axis.set_ylim(-0.035, 1.035)
    axis.set_xticks(np.arange(0.0, 7.1, 1.0))
    axis.set_xticks(np.arange(0.0, 7.01, 0.25), minor=True)
    axis.tick_params(axis="x", which="minor", length=2.0)
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel("full-payload SER")
    axis.set_title(
        r"Trace-driven collisions have packet-dependent SER minima",
        fontweight="bold",
        fontsize=11.1,
    )
    axis.grid(axis="y", color="#DCE2E6", linewidth=0.60, zorder=0)
    axis.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.265),
        ncol=4,
        fontsize=7.45,
        columnspacing=1.28,
        handlelength=2.0,
    )
    clean_axis(axis, "both")
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.12, top=0.76)
    save_figure(fig, out_dir, "fig2c_packet_dependent_lambda")
    return {
        "question": "Why does a fixed counter-evidence weight fail across packets?",
        "answer": (
            "The displayed collision packets attain their lowest SER at "
            "different weights; the best full-payload recovery rate remains "
            "below 0.60 at every evaluated weight."
        ),
        "scope": summary["collision_source"],
        "curve_count": summary["curve_count"],
        "lambda_step": summary["lambda_step"],
        "recovery_definition": summary["recovery_definition"],
        "best_recovery_rate": summary["best_recovery_rate"],
        "best_recovery_weights": best_weights,
        "cases": rendered_cases,
    }


def render_figure2c_fixed_lambda_prr(data_dir: Path, out_dir: Path) -> dict:
    """Render the fixed-lambda full-payload PRR over the seven displayed packets."""

    rows = read_csv(data_dir / "fig2c_trace_curve_suite_recovery.csv")
    summary = read_json(data_dir / "fig2c_trace_curve_suite_summary.json")
    lambdas = np.asarray([float(row["evaluation_lambda"]) for row in rows])
    prr_percent = 100.0 * np.asarray(
        [float(row["full_payload_recovery_rate"]) for row in rows]
    )
    fig, axis = plt.subplots(figsize=(7.8, 6.25))
    axis.bar(
        lambdas,
        prr_percent,
        width=0.18,
        color=BLUE,
        edgecolor="white",
        linewidth=0.28,
        zorder=3,
    )
    axis.set_xlim(-0.125, 7.125)
    axis.set_ylim(0.0, 35.0)
    axis.set_xticks(np.arange(0.0, 7.1, 1.0))
    axis.set_xticks(np.arange(0.0, 7.01, 0.25), minor=True)
    axis.set_yticks(np.arange(0.0, 35.1, 5.0))
    axis.tick_params(axis="x", which="minor", length=2.0)
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel("full-payload PRR across 7 packets (%)")
    axis.set_title(
        r"Fixed-$\lambda$ full-payload recovery across trace-driven collisions",
        fontweight="bold",
        fontsize=11.1,
    )
    clean_axis(axis, "y")
    fig.subplots_adjust(left=0.16, right=0.985, bottom=0.14, top=0.88)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out_dir / "fig2c_fixed_lambda_prr.png",
        dpi=320,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    return {
        "curve_count": summary["curve_count"],
        "lambda_step": summary["lambda_step"],
        "recovery_definition": summary["recovery_definition"],
        "maximum_prr_percent": float(np.max(prr_percent)),
    }


def heatmap_cell_edges(values: np.ndarray) -> np.ndarray:
    """Turn monotonically increasing cell centers into pcolormesh edges."""

    if values.size == 1:
        return np.asarray([values[0] - 0.5, values[0] + 0.5])
    midpoints = 0.5 * (values[:-1] + values[1:])
    return np.concatenate(
        [
            [values[0] - 0.5 * (values[1] - values[0])],
            midpoints,
            [values[-1] + 0.5 * (values[-1] - values[-2])],
        ]
    )


def render_usable_interval_heatmap(
    *,
    rows: list[dict[str, str]],
    boundary_rows: list[dict[str, str]],
    x_key: str,
    boundary_key: str,
    x_label: str,
    boundary_label: str,
    title: str,
    output_name: str,
    out_dir: Path,
) -> dict:
    x_values = np.asarray(
        sorted({float(row[x_key]) for row in boundary_rows}), dtype=np.float64
    )
    lambda_values = np.asarray(
        sorted({float(row["evaluation_lambda"]) for row in rows}),
        dtype=np.float64,
    )
    ser = np.full((lambda_values.size, x_values.size), np.nan, dtype=np.float64)
    x_index = {value: index for index, value in enumerate(x_values)}
    lambda_index = {value: index for index, value in enumerate(lambda_values)}
    for row in rows:
        ser[
            lambda_index[float(row["evaluation_lambda"])],
            x_index[float(row[x_key])],
        ] = float(row["ser"])
    if not np.all(np.isfinite(ser)):
        raise RuntimeError(f"incomplete SER heatmap for {output_name}")

    boundaries = {
        float(row[x_key]): float(row[boundary_key]) for row in boundary_rows
    }
    boundary_values = np.asarray(
        [boundaries[value] for value in x_values], dtype=np.float64
    )
    fig, axis = plt.subplots(figsize=(7.8, 6.0))
    mesh = axis.pcolormesh(
        heatmap_cell_edges(x_values),
        heatmap_cell_edges(lambda_values),
        ser,
        cmap="RdYlGn_r",
        vmin=0.0,
        vmax=1.0,
        shading="flat",
        rasterized=True,
    )
    axis.plot(
        x_values,
        boundary_values,
        color=INK,
        linewidth=2.15,
        marker="o",
        markersize=4.6,
        markerfacecolor="white",
        markeredgewidth=1.05,
        label=boundary_label,
        zorder=6,
    )
    axis.set_xlim(float(heatmap_cell_edges(x_values)[0]), float(heatmap_cell_edges(x_values)[-1]))
    axis.set_ylim(0.0, 10.0)
    axis.set_xticks(x_values)
    axis.set_yticks(np.arange(0.0, 10.1, 2.0))
    axis.set_xlabel(x_label)
    axis.set_ylabel(r"counter-evidence weight $\lambda$")
    axis.set_title(title, fontweight="bold", fontsize=11.0, pad=10)
    axis.legend(loc="upper right", frameon=True, framealpha=0.92, fontsize=8.0)
    axis.text(
        0.02,
        0.02,
        r"usable cells: full-payload SER $< 0.20$",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.0,
        color=INK,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.8},
    )
    clean_axis(axis, "both")
    colorbar = fig.colorbar(mesh, ax=axis, pad=0.025, fraction=0.048)
    colorbar.set_label("full-payload SER", rotation=90)
    colorbar.set_ticks(np.arange(0.0, 1.01, 0.2))
    fig.subplots_adjust(left=0.14, right=0.875, bottom=0.135, top=0.89)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / output_name
    fig.savefig(output_path, dpi=320, facecolor="white")
    plt.close(fig)
    return {
        "output": str(output_path),
        "x_values": [float(value) for value in x_values],
        "boundary_values": [float(value) for value in boundary_values],
        "cell_count": int(ser.size),
    }


def render_figure2d(data_dir: Path, out_dir: Path) -> dict:
    summary = read_json(data_dir / "fig2d_controlled_usable_interval_summary.json")
    lower = render_usable_interval_heatmap(
        rows=read_csv(data_dir / "fig2d_competition_lower_bound_heatmap.csv"),
        boundary_rows=read_csv(data_dir / "fig2d_competition_lower_bound_boundary.csv"),
        x_key="sir_db",
        boundary_key="lambda_low",
        x_label="payload SIR (dB)",
        boundary_label=r"$\lambda_{\mathrm{low}}=\min\{\lambda:\mathrm{SER}<0.20\}$",
        title="Competition sets the lower usable weight",
        output_name="fig2d_competition_lower_bound_heatmap.png",
        out_dir=out_dir,
    )
    upper = render_usable_interval_heatmap(
        rows=read_csv(data_dir / "fig2d_target_reliability_upper_bound_heatmap.csv"),
        boundary_rows=read_csv(data_dir / "fig2d_target_reliability_upper_bound_boundary.csv"),
        x_key="theta_u_deg",
        boundary_key="lambda_high",
        x_label=r"target direction error $\theta_u$ (deg)",
        boundary_label=r"$\lambda_{\mathrm{high}}=\max\{\lambda:\mathrm{SER}<0.20\}$",
        title="Target reliability sets the upper usable weight",
        output_name="fig2d_target_reliability_upper_bound_heatmap.png",
        out_dir=out_dir,
    )
    return {
        "question": summary["research_question"],
        "answer": (
            "Competition raises the lower usable bound, while target-reference "
            "error lowers the upper usable bound of the same interval."
        ),
        "scope": summary["collision_source"],
        "usable_interval_definition": summary["usable_interval_definition"],
        "competition_lower_heatmap": lower,
        "target_reliability_upper_heatmap": upper,
    }


def arrow(axis, angle_deg: float, radius: float, color: str, width: float, zorder: int = 3) -> None:
    angle = math.radians(angle_deg)
    endpoint = (radius * math.cos(angle), radius * math.sin(angle))
    axis.add_patch(
        FancyArrowPatch(
            (0, 0),
            endpoint,
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=width,
            color=color,
            zorder=zorder,
        )
    )


def render_figure4(data_dir: Path, out_dir: Path) -> dict:
    geometry = read_json(data_dir / "fig4_geometry.json")
    theta_u = float(geometry["theta_u_deg"])
    L = float(geometry["L_u"])
    easy, near = geometry["cases"]
    easy_theta = float(easy["theta_hat_deg"])
    near_theta = float(near["theta_hat_deg"])
    easy_u = float(easy["U_uv"])
    near_u = float(near["U_uv"])

    fig, axis = plt.subplots(figsize=(7.5, 3.45))
    # Left: projective direction geometry.
    axis.add_patch(Wedge((0, 0), 1.0, -theta_u, theta_u, color=LIGHT_BLUE, alpha=0.95, ec="none"))
    axis.add_patch(
        Wedge(
            (0, 0),
            0.92,
            easy_theta - float(easy["theta_v_deg"]),
            easy_theta + float(easy["theta_v_deg"]),
            color=LIGHT_GREEN,
            alpha=0.95,
            ec="none",
        )
    )
    axis.add_patch(
        Wedge(
            (0, 0),
            0.88,
            near_theta - float(near["theta_v_deg"]),
            near_theta + float(near["theta_v_deg"]),
            color=LIGHT_RED,
            alpha=0.95,
            ec="none",
        )
    )
    arrow(axis, near_theta, 0.91, RED, 5.0, 2)
    arrow(axis, 0.0, 1.0, BLUE, 2.6, 4)
    arrow(axis, easy_theta, 0.94, TEAL, 2.8, 4)
    axis.add_patch(Arc((0, 0), 0.72, 0.72, theta1=0, theta2=easy_theta, color=MID_GRAY, linewidth=1.1))
    angle_mid = math.radians(easy_theta / 2)
    axis.text(0.43 * math.cos(angle_mid), 0.43 * math.sin(angle_mid), rf"${easy_theta:.1f}^\circ$", ha="center")
    axis.text(0.40, 0.09, rf"${near_theta:.1f}^\circ$", color=RED, fontweight="bold")
    axis.text(1.02, -0.02, "target", color=BLUE, fontweight="bold", va="center")
    axis.text(0.02, 1.02, "easy competitor", color=TEAL, fontweight="bold", ha="center")
    axis.text(0.67, 0.12, "near-collinear\ncompetitor", color=RED, fontweight="bold", ha="center")
    arc = np.linspace(0, np.pi / 2, 100)
    axis.plot(np.cos(arc), np.sin(arc), color="#CCD3D8", linewidth=0.8)

    # Divider and quantitative bounds on the same canvas.
    axis.plot([1.24, 1.24], [-0.08, 1.05], color="#D8DDE1", linewidth=1.0)
    bar_x0 = 1.46
    bar_width = 1.05
    axis.text(bar_x0, 1.02, "Worst-case retained-energy bounds", fontweight="bold", fontsize=9.5)
    axis.text(bar_x0, 0.89, rf"same target: $L_u={L:.3f}$", color=BLUE, fontweight="bold", fontsize=8.5)
    axis.plot(
        [bar_x0 + bar_width * L, bar_x0 + bar_width * L],
        [0.20, 0.82],
        color=BLUE,
        linestyle="--",
        linewidth=2.0,
    )
    for ypos, value, label, color in [
        (0.66, easy_u, "easy $U_{uv}$", TEAL),
        (0.34, near_u, "near-collinear $U_{uv}$", RED),
    ]:
        axis.add_patch(Rectangle((bar_x0, ypos - 0.09), bar_width, 0.18, facecolor="#EEF1F3", edgecolor="none"))
        axis.add_patch(Rectangle((bar_x0, ypos - 0.09), bar_width * value, 0.18, facecolor=color, edgecolor="none"))
        axis.text(bar_x0 - 0.03, ypos, label, ha="right", va="center", fontsize=8.2)
        axis.text(
            bar_x0 + max(bar_width * value + 0.03, 0.06),
            ypos,
            f"{value:.3f}",
            va="center",
            color=color,
            fontweight="bold",
        )
    axis.text(bar_x0, 0.09, "same target, 73× different competitor bound", color=INK, fontsize=8.3, fontweight="bold")

    axis.set_xlim(-0.08, 2.78)
    axis.set_ylim(-0.10, 1.12)
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_title("Spatial ambiguity determines how aggressively counter-evidence can be used", fontweight="bold", pad=5)
    fig.tight_layout()
    save_figure(fig, out_dir, "fig4_reliability_geometry")
    return {
        "proof_obligation": "The same target reliability can coexist with radically different competitor ambiguity.",
        "selection": "One measured target with its least- and most-coherent measured competitors.",
        "values": {"L_u": L, "easy_U_uv": easy_u, "near_U_uv": near_u},
    }


def load_timeline(data_dir: Path) -> dict:
    spec = read_json(data_dir / "fig5_overlap_and_pair_risks.json")
    if "timeline_starts_symbols" in spec:
        return {
            "spec": spec,
            "scene_path": None,
            "packets": [
                {"source_label": label}
                for label in spec["source_labels_target_first"]
            ],
            "samples_per_symbol": 1.0,
            "payload_start_symbols": float(spec["payload_start_symbols"]),
            "target": int(spec["target_packet_index"]),
            "overlaps": [int(value) for value in spec["overlap_packet_indices"]],
            "starts": [float(value) for value in spec["timeline_starts_symbols"]],
            "frame": float(spec["frame_symbols"]),
            "nearest_excluded": None,
        }
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
    excluded = [index for index in range(len(packets)) if index != target and index not in overlaps]
    nearest_excluded = min(excluded, key=lambda index: abs(starts[index] - starts[target]))
    return {
        "spec": spec,
        "scene_path": scene_path,
        "packets": packets,
        "samples_per_symbol": samples_per_symbol,
        "payload_start_symbols": payload_start_symbols,
        "target": target,
        "overlaps": overlaps,
        "starts": starts,
        "frame": frame,
        "nearest_excluded": nearest_excluded,
    }


def render_figure5(data_dir: Path, out_dir: Path) -> dict:
    timeline = load_timeline(data_dir)
    spec = timeline["spec"]
    packets = timeline["packets"]
    target = timeline["target"]
    overlaps = timeline["overlaps"]
    starts = timeline["starts"]
    samples_per_symbol = timeline["samples_per_symbol"]
    payload_start_symbols = timeline["payload_start_symbols"]
    frame = timeline["frame"]
    nearest_excluded = timeline["nearest_excluded"]
    display = [target] + overlaps
    if nearest_excluded is not None:
        display.append(nearest_excluded)
    origin = min(starts[index] for index in display)
    payload_x0 = (starts[target] - origin) / samples_per_symbol + payload_start_symbols
    payload_x1 = (starts[target] - origin + frame) / samples_per_symbol

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(11.5, 4.65),
        gridspec_kw={"width_ratios": [1.02, 1.28], "wspace": 0.27},
    )
    axis = axes[0]
    axis.axvspan(payload_x0, payload_x1, color=LIGHT_BLUE, alpha=0.72)
    axis.text((payload_x0 + payload_x1) / 2, len(display) - 0.43, "target payload interval", ha="center", color=BLUE, fontweight="bold", fontsize=8)
    labels = []
    for row_number, packet_index in enumerate(display):
        y = len(display) - 1 - row_number
        start = (starts[packet_index] - origin) / samples_per_symbol
        preamble_end = start + payload_start_symbols
        end = (starts[packet_index] - origin + frame) / samples_per_symbol
        is_target = packet_index == target
        is_overlap = packet_index in overlaps
        color = BLUE if is_target else ORANGE if is_overlap else "#AEB6BC"
        axis.broken_barh([(start, payload_start_symbols)], (y - 0.30, 0.60), facecolor=color, alpha=0.28, edgecolor="none")
        axis.broken_barh([(preamble_end, end - preamble_end)], (y - 0.30, 0.60), facecolor=color, alpha=0.92 if is_target else 0.66, edgecolor="none")
        source = packets[packet_index].get("source_label", f"packet {packet_index}")
        if is_target:
            labels.append(r"$u$  " + source)
        elif is_overlap:
            labels.append(rf"$v_{{{row_number}}}$  " + source)
        else:
            labels.append("excluded  " + source)
    axis.set_yticks(np.arange(len(display)), labels[::-1])
    axis.set_xlabel("time (LoRa symbols)")
    axis.set_title(r"(a) Ten intervals construct $\mathcal{I}_u$", fontweight="bold")
    clean_axis(axis, "x")

    axis = axes[1]
    pair_rows = spec["pair_rows"]
    cap = float(spec["lambda_cap"])
    lambdas = np.linspace(0, cap, 601)
    values = np.vstack([pair_risk(row, lambdas) for row in pair_rows])
    lower = min(float(np.quantile(values, 0.02)), -0.5)
    upper = max(float(np.quantile(values, 0.98)), 0.5)
    image = axis.imshow(
        values,
        aspect="auto",
        origin="upper",
        extent=[0, cap, len(pair_rows) - 0.5, -0.5],
        cmap="RdBu",
        norm=TwoSlopeNorm(vmin=lower, vcenter=0, vmax=upper),
        interpolation="nearest",
    )
    active = np.argmin(values, axis=0)
    axis.plot(lambdas, active, color="white", linewidth=2.8, zorder=4)
    axis.plot(
        lambdas,
        active,
        color=INK,
        linewidth=0.9,
        zorder=5,
        label="active worst pair",
    )
    for index, row in enumerate(pair_rows):
        flip = float(row.get("lambda_flip_under", math.inf))
        if 0 <= flip <= cap:
            axis.scatter([flip], [index], marker="*", s=58, color="#FFD166", edgecolor=INK, linewidth=0.45)
    competitor_labels = spec.get("source_labels_target_first", [])[1:]
    sir_values = spec.get("sir_db_each", [])
    tick_labels = []
    for index in range(len(pair_rows)):
        source = (
            str(competitor_labels[index]).split("#", 1)[0]
            if index < len(competitor_labels)
            else f"v{index + 1}"
        )
        sir = float(sir_values[index]) if index < len(sir_values) else math.nan
        tick_labels.append(
            rf"$v_{{{index + 1}}}$  {source}  ({sir:+.1f} dB)"
        )
    axis.set_yticks(np.arange(len(pair_rows)), tick_labels)
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel("member of " + r"$\mathcal{I}_u$")
    axis.set_title(r"(b) Ten position-diverse pair margins", fontweight="bold")
    cbar = fig.colorbar(image, ax=axis, pad=0.025, fraction=0.06)
    cbar.set_label(r"$R_{uv}(\lambda)$")
    axis.legend(frameon=False, fontsize=7.2, loc="upper right")
    switching = np.flatnonzero(active[1:] != active[:-1])
    fig.suptitle(
        "Figure 5: interval-derived competitors impose position-dependent risk",
        fontsize=11.5,
        fontweight="bold",
        y=1.01,
    )
    fig.subplots_adjust(left=0.08, right=0.965, bottom=0.15, top=0.87)
    save_figure(fig, out_dir, "fig5_overlap_to_pair_risk")
    return {
        "proof_obligation": "Time overlap determines the competitor set; each member imposes a distinct lambda constraint.",
        "scene": spec.get("scene_kind", str(timeline["scene_path"])),
        "overlap_count": len(overlaps),
        "envelope_switch_count": int(len(switching)),
    }


def render_figure6(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "fig6_representative_scene.csv")
    summary = read_json(data_dir / "fig6_representative_scene_summary.json")
    x = np.asarray(
        [int(row["uniform_interior_point_count"]) for row in rows],
        dtype=float,
    )
    ser = 100 * np.asarray([float(row["ser"]) for row in rows])
    prr = 100 * np.asarray([float(row["prr"]) for row in rows])
    index3 = int(np.flatnonzero(x == 3)[0])
    index63 = int(np.flatnonzero(x == 63)[0])

    fig, axis = plt.subplots(figsize=(7.2, 3.75))
    axis.axvspan(3, float(np.max(x)), color=LIGHT_GREEN, alpha=0.30)
    axis.axvline(
        3,
        color=MID_GRAY,
        linestyle=":",
        linewidth=1.25,
        zorder=1,
    )
    ser_line = axis.plot(
        x,
        ser,
        "o-",
        color=RED,
        linewidth=2.25,
        markersize=4.4,
        label="SER",
        zorder=4,
    )
    axis.scatter(
        [3, 63],
        [ser[index3], ser[index63]],
        marker="*",
        s=120,
        color=RED,
        edgecolor=INK,
        linewidth=0.45,
        zorder=6,
    )
    axis.set_xscale("symlog", linthresh=1.0)
    axis.set_xticks(x)
    axis.set_xticklabels([str(int(value)) for value in x])
    axis.set_xlabel("number of uniform interior coverage points, $J$")
    axis.set_ylabel("SER (%)", color=RED)
    axis.tick_params(axis="y", labelcolor=RED)
    axis.set_ylim(0.0, max(0.72, 1.15 * float(np.max(ser))))
    clean_axis(axis, "both")

    prr_axis = axis.twinx()
    prr_line = prr_axis.plot(
        x,
        prr,
        "s-",
        color=TEAL,
        linewidth=2.25,
        markersize=4.2,
        label="PRR after FEC/CRC",
        zorder=4,
    )
    prr_axis.scatter(
        [3, 63],
        [prr[index3], prr[index63]],
        marker="*",
        s=120,
        color=TEAL,
        edgecolor=INK,
        linewidth=0.45,
        zorder=6,
    )
    prr_axis.set_ylabel("PRR (%)", color=TEAL)
    prr_axis.tick_params(axis="y", labelcolor=TEAL)
    prr_axis.set_ylim(
        max(0.0, math.floor(float(np.min(prr))) - 1.0),
        max(100.4, math.ceil(float(np.max(prr))) + 0.4),
    )
    prr_axis.spines["top"].set_visible(False)
    prr_axis.annotate(
        (
            f"$J=3$: PRR {prr[index3]:.3f}%\n"
            f"$J=63$: PRR {prr[index63]:.0f}%, "
            f"SER {ser[index63]:.3f}%"
        ),
        xy=(63, prr[index63]),
        xytext=(-118, -50),
        textcoords="offset points",
        color=PURPLE,
        fontsize=7.3,
        fontweight="bold",
        va="top",
        arrowprops={"arrowstyle": "->", "color": PURPLE, "linewidth": 0.85},
    )
    handles = ser_line + prr_line
    axis.legend(
        handles,
        [item.get_label() for item in handles],
        frameon=False,
        ncol=2,
        fontsize=7.7,
        loc="lower right",
    )
    axis.set_title(
        (
            f"One fixed {summary['collision_number']}-packet collision, "
            f"{summary['trials']} repeated packets"
        ),
        fontweight="bold",
        fontsize=9.6,
    )
    fig.tight_layout()
    save_figure(fig, out_dir, "fig6_uniform_coverage")
    return {
        "proof_obligation": (
            "Show a high-quality controlled collision in which three interior "
            "points reach 99.x% PRR and a denser grid reaches 100%."
        ),
        "scope": summary["selection_scope"],
        "scene_index": int(summary["scene_index"]),
        "trials": int(summary["trials"]),
        "ser_j0_percent": float(ser[0]),
        "ser_j3_percent": float(ser[index3]),
        "prr_j0_percent": float(prr[0]),
        "prr_j3_percent": float(prr[index3]),
        "ser_j63_percent": float(ser[index63]),
        "prr_j63_percent": float(prr[index63]),
    }


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
    active_segments = spec.get("active_pair_segments")
    if not active_segments:
        active = curves.argmin(axis=0)
        changes = np.flatnonzero(active[1:] != active[:-1]) + 1
        starts = np.r_[0, changes]
        ends = np.r_[changes, len(x)]
        active_segments = [
            {
                "pair_index": int(active[start]),
                "lambda_start": float(x[start]),
                "lambda_end": float(x[end - 1]),
            }
            for start, end in zip(starts, ends)
        ]

    fig, axis = plt.subplots(figsize=(7.2, 3.75))
    for number, index in enumerate(shown):
        axis.plot(x, curves[index], color="#AEB6BC", linewidth=1.0, linestyle="--", label="pair curves" if number == 0 else None)
    for switch in switches:
        axis.axvline(switch, color="#C0C7CC", linestyle=":", linewidth=0.9)
    envelope_floor = float(np.min(envelope))
    axis.fill_between(
        x,
        envelope_floor,
        envelope,
        color=LIGHT_BLUE,
        alpha=0.55,
        label="lower-envelope region",
    )
    axis.plot(x, envelope, color=INK, linewidth=3.0, label=r"worst-pair envelope $G_u$")
    for number, switch in enumerate(switches):
        before = int(active_segments[number]["pair_index"]) + 1
        after = int(active_segments[number + 1]["pair_index"]) + 1
        axis.text(
            switch,
            0.975,
            rf"$v_{{{before}}}\!\rightarrow\!v_{{{after}}}$",
            transform=axis.get_xaxis_transform(),
            ha="center",
            va="top",
            color=MID_GRAY,
            fontsize=7.4,
            fontweight="bold",
        )
    category_style = {
        "boundary": ("|", MID_GRAY, "interval boundaries"),
        "analytic": ("^", ORANGE, "pair flip/peak points"),
        "midpoint": ("D", PURPLE, "adaptive midpoint"),
        "coverage": ("o", BLUE, "three uniform coverage points"),
    }
    seen_categories: set[str] = set()
    for candidate in candidates:
        value = float(candidate["lambda"])
        category = candidate["category"]
        marker, color, label = category_style[category]
        axis.scatter(
            [value],
            [float(np.interp(value, x, envelope))],
            s=55 if marker != "|" else 105,
            marker=marker,
            color=color,
            edgecolor=INK if marker != "|" else None,
            linewidth=0.45,
            zorder=5,
            label=label if category not in seen_categories else None,
        )
        seen_categories.add(category)
    selected_y = float(np.interp(selected, x, envelope))
    axis.scatter([selected], [selected_y], marker="*", s=200, color=RED, edgecolor=INK, linewidth=0.6, zorder=6)
    axis.annotate(
        rf"$\widehat\lambda_u={selected:.2f}$",
        xy=(selected, selected_y),
        xytext=(1.38, selected_y + 0.09),
        color=RED,
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.0},
    )
    axis.set_xlim(0, cap)
    axis.set_ylim(envelope_floor - 0.18, envelope.max() + 0.24)
    axis.set_xlabel(r"counter-evidence weight $\lambda$")
    axis.set_ylabel("normalized worst-pair margin")
    axis.set_title("Figure 7: evaluate a finite set and choose the largest worst-pair margin", fontweight="bold")
    axis.legend(frameon=False, loc="best", ncol=2, fontsize=7.1)
    clean_axis(axis, "both")
    fig.tight_layout()
    save_figure(fig, out_dir, "fig7_finite_packet_configuration")
    return {
        "proof_obligation": "The online finite set covers a useful envelope maximum without dense search.",
        "selection": (
            "Controlled measured-direction collision with three active worst-pair "
            "segments and uniform-checkpoint-adjacent switches."
        ),
        "selected_lambda": selected,
        "candidate_color_mapping": {
            category: label for category, (_, _, label) in category_style.items()
        },
    }


def render_figure8(data_dir: Path, out_dir: Path) -> dict:
    snapshots = read_csv(data_dir / "fig8_snapshot_rows.csv")
    per_bin = read_csv(data_dir / "fig8_per_bin_snapshot_rows.csv")
    summary = read_json(data_dir / "fig8_summary.json")
    rows5 = sorted(
        [row for row in snapshots if row["kernel"] == "5-bin"],
        key=lambda row: int(row["preamble_window"]),
    )
    p = np.asarray([int(row["preamble_window"]) for row in rows5])
    aggregate_error = np.asarray(
        [float(row["signed_direction_error_deg"]) for row in rows5]
    )
    offsets = [-2, -1, 0, 1, 2]
    coefficients = [0.12, 0.45, 1.0, 0.45, 0.12]
    per_offset: dict[int, np.ndarray] = {}
    for offset in offsets:
        selected = sorted(
            [
                row
                for row in per_bin
                if int(row["bin_offset"]) == offset
            ],
            key=lambda row: int(row["preamble_window"]),
        )
        per_offset[offset] = np.asarray(
            [float(row["signed_direction_error_deg"]) for row in selected]
        )

    tf = np.load(data_dir / "fig8_time_frequency.npz")
    tf_time = np.asarray(tf["time_symbols"], dtype=np.float64)
    tf_frequency = np.asarray(tf["frequency_khz"], dtype=np.float64)
    tf_power = np.asarray(tf["power_db"], dtype=np.float64)
    target_start = float(tf["target_start_symbols"])
    interferer_start = float(tf["interferer_start_symbols"])
    target_cfo = float(tf["target_cfo_khz"])
    interferer_cfo = float(tf["interferer_cfo_khz"])
    bandwidth = float(tf["bandwidth_khz"])
    sir_db = float(tf["sir_db"])

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12.2, 4.70),
        gridspec_kw={"width_ratios": [1.08, 1.0]},
    )
    axis = axes[0]
    mesh = axis.pcolormesh(
        tf_time,
        tf_frequency,
        tf_power,
        shading="auto",
        cmap="magma",
        vmin=-35.0,
        vmax=0.0,
        rasterized=True,
    )
    half_bw = bandwidth / 2.0
    for chirp in range(8):
        begin = target_start + chirp
        end = begin + 1.0
        if begin > tf_time[-1]:
            break
        axis.plot(
            [begin, min(end, tf_time[-1])],
            [
                -half_bw + target_cfo,
                (-half_bw + target_cfo)
                + bandwidth * min(1.0, tf_time[-1] - begin),
            ],
            color="#4CC9F0",
            linewidth=1.15,
            alpha=0.95,
        )
    for chirp in range(8):
        begin = interferer_start + chirp
        end = begin + 1.0
        if begin > tf_time[-1]:
            break
        axis.plot(
            [begin, min(end, tf_time[-1])],
            [
                -half_bw + interferer_cfo,
                (-half_bw + interferer_cfo)
                + bandwidth * min(1.0, tf_time[-1] - begin),
            ],
            color="#FFD166",
            linewidth=1.25,
            linestyle="--",
            alpha=0.98,
        )
    axis.axvline(
        interferer_start,
        color="#FFD166",
        linewidth=1.3,
        linestyle=":",
    )
    axis.text(
        0.02,
        0.97,
        "target preamble",
        color="#4CC9F0",
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontweight="bold",
        bbox={"facecolor": "black", "edgecolor": "none", "alpha": 0.50},
    )
    axis.text(
        0.98,
        0.97,
        (
            "stronger interferer preamble\n"
            rf"starts at ${interferer_start:g}T_s$; SIR={sir_db:g} dB"
        ),
        color="#FFD166",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontweight="bold",
        bbox={"facecolor": "black", "edgecolor": "none", "alpha": 0.50},
    )
    axis.set_xlim(0.0, 8.0)
    axis.set_ylim(-72.0, 72.0)
    axis.set_xlabel(r"time from target start ($T_s$)")
    axis.set_ylabel("frequency offset (kHz)")
    axis.set_title("(a) Collision seen in target preamble", fontweight="bold")
    colorbar = fig.colorbar(mesh, ax=axis, pad=0.015, fraction=0.052)
    colorbar.set_label("energy (dB, normalized)")
    clean_axis(axis, "both")

    axis = axes[1]
    colors = [PURPLE, ORANGE, BLUE, TEAL, RED]
    markers = ["o", "s", "^", "D", "v"]
    for offset, coefficient, color, marker in zip(
        offsets,
        coefficients,
        colors,
        markers,
    ):
        axis.plot(
            p,
            per_offset[offset],
            marker=marker,
            markersize=4.0,
            linewidth=1.25,
            alpha=0.82,
            color=color,
            label=(
                rf"$d={offset:+d}$, $c_d={coefficient:g}$"
            ),
        )
    axis.plot(
        p,
        aggregate_error,
        "P--",
        color=MID_GRAY,
        linewidth=1.8,
        markersize=5.5,
        markerfacecolor="white",
        markeredgecolor=MID_GRAY,
        label=r"five-bin aggregate $\mathbf{g}_p$",
        zorder=6,
    )
    axis.axvspan(2.5, 7.5, color=LIGHT_RED, alpha=0.34)
    all_signed = np.concatenate(
        [aggregate_error]
        + [per_offset[offset] for offset in offsets]
    )
    signed_limit = max(0.15, float(np.max(np.abs(all_signed))) * 1.12)
    axis.axhline(0.0, color=MID_GRAY, linestyle=":", linewidth=1.0)
    axis.set_ylim(-signed_limit, signed_limit)
    axis.set_xticks(p)
    axis.set_xlabel("preamble window $p$")
    axis.set_ylabel(
        r"signed direction offset $\Delta\psi$ (degree)"
    )
    axis.set_title(
        r"(b) Local snapshots form the five-bin aggregate $\mathbf{g}_p$",
        fontweight="bold",
    )
    axis.legend(
        frameon=False,
        fontsize=6.8,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.24),
        title=r"colored curves: local snapshots $\mathbf{g}_{u,p}^{(d)}$",
        title_fontsize=7.0,
    )
    clean_axis(axis, "both")
    fig.suptitle(
        "Figure 8: spectral isolation and robust packet-level channel estimation",
        fontsize=11.1,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout(rect=(0.0, 0.17, 1.0, 0.98))
    save_figure(fig, out_dir, "fig8_robust_packet_statistics")
    return {
        "proof_obligation": (
            "Show the target/interferer chirps in the selected collision, then "
            "separate local-bin snapshots and the five-bin aggregate; the "
            "final robust packet channel is intentionally omitted here."
        ),
        "selection": "Explicitly selected measured-pair case study; no aggregate pair claim.",
        "kernel_coefficients": {
            str(offset): coefficient
            for offset, coefficient in zip(offsets, coefficients)
        },
        "aggregate_curve": "gray dashed 5-bin snapshot g_p",
        "packet_channel_curve": "thick black robust packet channel h_hat_u",
        "signed_direction_definition": (
            "projective channel angle in degrees, signed by the relative-phase side"
        ),
    }


def render_air_within_legacy(data_dir: Path, out_dir: Path) -> dict:
    rows = read_csv(data_dir / "air_within_packet_coherence.csv")
    packet_rows = read_csv(data_dir / "air_within_packet_estimates.csv")
    summary = read_json(data_dir / "air_within_packet_coherence_summary.json")
    display_snr = float(summary["display_snr_db"])
    selected = [row for row in rows if float(row["snr_db"]) == display_snr]
    best_key = (
        int(summary["representative_source_index"]),
        int(summary["representative_trial"]),
    )
    representative = sorted(
        [
            row
            for row in selected
            if (int(row["source_index"]), int(row["trial"])) == best_key
        ],
        key=lambda row: int(row["preamble_window"]),
    )
    display_values = np.asarray([float(row["angle_to_packet_mean_deg"]) for row in selected])
    snrs = sorted(set(float(row["snr_db"]) for row in rows))

    fig, axes = plt.subplots(1, 3, figsize=(11.7, 3.55))
    axis = axes[0]
    chirps = [int(row["preamble_window"]) for row in representative]
    chirp_errors = [
        float(row["angle_to_clean_h_deg"]) for row in representative
    ]
    packet_error = float(
        representative[0]["packet_h_error_to_clean_deg"]
    )
    axis.plot(
        chirps,
        chirp_errors,
        "o-",
        color=BLUE,
        linewidth=1.8,
        markersize=4.6,
        label=r"chirp estimate $\widehat{\mathbf{h}}_{u,p}$",
    )
    axis.axhline(
        packet_error,
        color=RED,
        linewidth=1.7,
        linestyle="--",
        label=(
            rf"packet estimate $\widehat{{\mathbf{{h}}}}_u$ "
            rf"({packet_error:.2f}°)"
        ),
    )
    axis.set_xticks(chirps)
    axis.set_xlabel("preamble chirp index")
    axis.set_ylabel(
        r"$d(\widehat{\mathbf{h}},\mathbf{h}_{u,\rm clean})$ (degree)"
    )
    axis.set_title(
        f"(a) One high-quality packet at {display_snr:g} dB",
        fontweight="bold",
    )
    axis.legend(frameon=False, fontsize=7.0, loc="best")
    clean_axis(axis, "both")

    axis = axes[1]
    axis.hist(display_values, bins=28, density=True, color=LIGHT_BLUE, edgecolor="white", linewidth=0.6)
    median = float(np.median(display_values))
    p90 = float(np.quantile(display_values, 0.9))
    axis.axvline(median, color=TEAL, linewidth=2.0, label=f"median {median:.2f}°")
    axis.axvline(p90, color=RED, linewidth=1.8, linestyle="--", label=f"90th {p90:.2f}°")
    axis.set_xlabel("chirp-to-packet direction error (degree)")
    axis.set_ylabel("density")
    axis.set_title(
        f"(b) Selected packet pool at {display_snr:g} dB",
        fontweight="bold",
    )
    axis.legend(frameon=False)
    clean_axis(axis)

    axis = axes[2]
    grouped = []
    for snr in snrs:
        grouped.append(
            [
                float(row["packet_h_error_to_clean_deg"])
                for row in packet_rows
                if float(row["snr_db"]) == snr
            ]
        )
    positions = np.arange(len(snrs))
    boxes = axis.boxplot(
        grouped,
        positions=positions,
        widths=0.60,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": LIGHT_BLUE, "alpha": 0.82},
        medianprops={"color": RED, "linewidth": 1.6},
        whiskerprops={"color": NAVY},
        capprops={"color": NAVY},
    )
    del boxes
    medians = [float(np.median(values)) for values in grouped]
    axis.plot(
        positions,
        medians,
        "o-",
        color=NAVY,
        linewidth=1.45,
        markersize=3.8,
    )
    axis.set_yscale("log")
    axis.set_xticks(positions, [f"{value:g}" for value in snrs])
    axis.set_xlabel("injected SNR (dB)")
    axis.set_ylabel(
        r"$d(\widehat{\mathbf{h}}_u,\mathbf{h}_{u,\rm clean})$ (degree)"
    )
    axis.set_title(
        "(c) Packet-level estimate versus SNR",
        fontweight="bold",
    )
    clean_axis(axis, "both")
    fig.suptitle(
        "Indoor channel measurement I: within-packet spatial coherence",
        fontsize=11.3,
        fontweight="bold",
        y=1.01,
    )
    fig.subplots_adjust(
        left=0.065,
        right=0.99,
        bottom=0.18,
        top=0.80,
        wspace=0.28,
    )
    save_figure(fig, out_dir, "fig_air_within_packet_coherence")
    return {
        "proof_obligation": (
            "Repeated preamble chirps yield a stable packet estimate and "
            "packet-level direction error falls with SNR."
        ),
        "aggregate_scope": (
            f"All {len(rows)} chirp observations from the shared "
            f"{summary['quality_pool_size']}-packet quality pool."
        ),
        "selected_quality_packet_indices": summary[
            "selected_quality_packet_indices"
        ],
        "representative_packet": best_key,
        "representative_rule": summary["representative_selection_rule"],
    }


def render_air_within_complex_legacy(data_dir: Path, out_dir: Path) -> dict:
    chirps = read_csv(data_dir / "air_full_packet_channel_chirps.csv")
    estimates = read_csv(data_dir / "air_full_packet_channel_snr.csv")
    summary = read_json(data_dir / "air_within_packet_coherence_summary.json")
    positions = np.asarray(
        [float(row["chirp_start_symbols"]) for row in chirps]
    )
    gain = np.asarray([float(row["gain_db"]) for row in chirps])
    phase = np.asarray(
        [float(row["relative_phase_deg"]) for row in chirps]
    )
    gain_deviation = np.asarray(
        [float(row["gain_deviation_db"]) for row in chirps]
    )
    phase_deviation = np.asarray(
        [float(row["phase_deviation_deg"]) for row in chirps]
    )
    sections = [row["section"] for row in chirps]
    section_style = {
        "preamble": (BLUE, "o"),
        "sync": (PURPLE, "s"),
        "SFD": (RED, "D"),
        "payload": (TEAL, "^"),
    }

    fig = plt.figure(figsize=(12.7, 4.45))
    outer = fig.add_gridspec(
        1,
        3,
        width_ratios=[1.38, 1.02, 1.12],
        wspace=0.34,
    )
    grid_a = outer[0].subgridspec(2, 1, hspace=0.08)
    gain_axis = fig.add_subplot(grid_a[0])
    phase_axis = fig.add_subplot(grid_a[1], sharex=gain_axis)
    for section, (color, marker) in section_style.items():
        keep = np.asarray([value == section for value in sections])
        gain_axis.scatter(
            positions[keep],
            gain[keep],
            color=color,
            marker=marker,
            s=20,
            label=section,
            zorder=4,
        )
        phase_axis.scatter(
            positions[keep],
            phase[keep],
            color=color,
            marker=marker,
            s=20,
            zorder=4,
        )
    mean_gain = float(summary["mean_gain_db"])
    mean_phase = float(summary["mean_relative_phase_deg"])
    gain_axis.axhspan(
        float(np.min(gain)),
        float(np.max(gain)),
        color=LIGHT_BLUE,
        alpha=0.24,
        zorder=0,
    )
    phase_axis.axhspan(
        float(np.min(phase)),
        float(np.max(phase)),
        color=LIGHT_GREEN,
        alpha=0.24,
        zorder=0,
    )
    gain_axis.axhline(
        mean_gain,
        color=INK,
        linestyle="--",
        linewidth=1.55,
        label=r"packet mean $\widehat{\mathbf{h}}_u$",
    )
    phase_axis.axhline(
        mean_phase,
        color=INK,
        linestyle="--",
        linewidth=1.55,
    )
    for boundary in [8.0, 10.0, 12.25]:
        gain_axis.axvline(boundary, color=MID_GRAY, linestyle=":", linewidth=0.9)
        phase_axis.axvline(boundary, color=MID_GRAY, linestyle=":", linewidth=0.9)
    gain_axis.text(
        0.5,
        1.03,
        "(a) One complete 45.25-symbol packet at 10 dB",
        transform=gain_axis.transAxes,
        ha="center",
        va="bottom",
        fontweight="bold",
    )
    gain_axis.set_ylabel(r"$20\log_{10}\|\widehat{\mathbf{h}}_{u,p}\|$ (dB)")
    phase_axis.set_ylabel(r"$\angle(h_{1,p}h_{0,p}^{*})$ (degree)")
    phase_axis.set_xlabel(r"chirp start from packet start ($T_s$)")
    phase_axis.set_xlim(-0.5, float(summary["frame_symbols"]))
    gain_axis.tick_params(labelbottom=False)
    gain_axis.legend(
        frameon=False,
        fontsize=6.5,
        ncol=3,
        loc="best",
    )
    clean_axis(gain_axis, "both")
    clean_axis(phase_axis, "both")

    grid_b = outer[1].subgridspec(2, 1, hspace=0.14)
    gain_hist = fig.add_subplot(grid_b[0])
    phase_hist = fig.add_subplot(grid_b[1])
    histogram_specs = [
        (
            gain_hist,
            gain_deviation,
            BLUE,
            r"gain deviation (dB)",
        ),
        (
            phase_hist,
            phase_deviation,
            TEAL,
            r"relative-phase deviation (degree)",
        ),
    ]
    for axis, values, color, xlabel in histogram_specs:
        extent = max(
            float(np.max(np.abs(values))) * 1.08,
            0.10,
        )
        edges = np.linspace(-extent, extent, 17)
        height, edges, _ = axis.hist(
            values,
            bins=edges,
            density=True,
            color=color,
            alpha=0.34,
            edgecolor="white",
            linewidth=0.7,
        )
        centers = 0.5 * (edges[:-1] + edges[1:])
        axis.plot(
            centers,
            height,
            "o-",
            color=color,
            linewidth=1.45,
            markersize=3.2,
        )
        axis.axvline(0.0, color=INK, linestyle="--", linewidth=1.1)
        axis.set_xlim(-extent, extent)
        axis.set_xlabel(xlabel)
        clean_axis(axis, "both")
    gain_hist.set_ylabel("density")
    phase_hist.set_ylabel("density")
    gain_hist.set_title(
        "(b) Signed deviations around packet mean",
        fontweight="bold",
    )

    axis = fig.add_subplot(outer[2])
    snrs = sorted(set(float(row["snr_db"]) for row in estimates))
    grouped = [
        [
            float(row["signed_direction_error_deg"])
            for row in estimates
            if float(row["snr_db"]) == snr
        ]
        for snr in snrs
    ]
    x = np.arange(len(snrs), dtype=np.float64)
    axis.boxplot(
        grouped,
        positions=x,
        widths=0.58,
        showfliers=False,
        patch_artist=True,
        boxprops={
            "facecolor": LIGHT_BLUE,
            "edgecolor": NAVY,
            "alpha": 0.65,
        },
        medianprops={"color": RED, "linewidth": 1.6},
        whiskerprops={"color": NAVY},
        capprops={"color": NAVY},
    )
    jitter_rng = np.random.default_rng(20260730)
    for index, values in enumerate(grouped):
        jitter = jitter_rng.uniform(-0.20, 0.20, size=len(values))
        axis.scatter(
            index + jitter,
            values,
            s=9,
            color=BLUE,
            alpha=0.30,
            edgecolors="none",
            zorder=2,
        )
    medians = np.asarray([float(np.median(values)) for values in grouped])
    axis.plot(x, medians, "o-", color=INK, linewidth=1.45, markersize=3.6)
    axis.axhline(0.0, color=MID_GRAY, linestyle="--", linewidth=1.0)
    axis.set_xticks(x, [f"{value:g}" for value in snrs])
    axis.set_xlabel("injected SNR (dB)")
    axis.set_ylabel(
        r"signed direction offset $\Delta\psi$ (degree)"
    )
    axis.set_title(
        "(c) Production preamble estimate versus SNR",
        fontweight="bold",
    )
    signed_limit = max(
        0.25,
        float(
            np.quantile(
                np.abs(np.concatenate([np.asarray(v) for v in grouped])),
                0.995,
            )
        )
        * 1.15,
    )
    axis.set_ylim(-signed_limit, signed_limit)
    axis.annotate(
        "closer to zero is better",
        xy=(0.97, 0.04),
        xycoords="axes fraction",
        ha="right",
        color=TEAL,
        fontsize=7.2,
    )
    clean_axis(axis, "both")

    fig.suptitle(
        "Indoor channel measurement I: amplitude and inter-antenna phase",
        fontsize=11.3,
        fontweight="bold",
        y=1.01,
    )
    fig.subplots_adjust(
        left=0.06,
        right=0.992,
        bottom=0.17,
        top=0.84,
    )
    save_figure(fig, out_dir, "fig_air_within_packet_coherence")
    return {
        "proof_obligation": (
            "A complete 45.25-symbol packet preserves both complex gain and "
            "inter-antenna phase, and signed direction spread contracts with SNR."
        ),
        "source_report": summary["source_report"],
        "selected_quality_candidate_ids": summary[
            "selected_quality_candidate_ids"
        ],
        "display_snr_db": summary["display_snr_db"],
        "representative_candidate_id": summary[
            "representative_candidate_id"
        ],
        "signed_direction_definition": (
            "projective channel angle in degrees, signed by the relative-phase side"
        ),
    }


def render_air_within(data_dir: Path, out_dir: Path) -> dict:
    """Render one -20 dB trajectory and aligned -20/-10/0 dB densities."""

    chirps = read_csv(data_dir / "air_full_packet_channel_chirps.csv")
    summary = read_json(data_dir / "air_within_packet_coherence_summary.json")
    display_snrs = [
        float(value)
        for value in summary.get("display_snr_db_by_panel", [-20.0, -10.0, 0.0])
    ]
    if len(display_snrs) != 3:
        raise ValueError("within-packet figure requires three display SNRs")
    frame_symbols = float(summary["frame_symbols"])
    grouped_rows = {
        snr_db: [
            row
            for row in chirps
            if math.isclose(float(row["snr_db"]), snr_db, abs_tol=1e-9)
        ]
        for snr_db in display_snrs
    }
    if any(not rows for rows in grouped_rows.values()):
        raise ValueError("missing full-packet chirps for one of the display SNRs")
    grouped_direction = {
        snr_db: np.asarray(
            [float(row["signed_direction_deviation_deg"]) for row in rows]
        )
        for snr_db, rows in grouped_rows.items()
    }
    all_direction = np.concatenate(list(grouped_direction.values()))
    # Keep every observed chirp in the displayed support.  Histograms below
    # encode probability mass (count / all chirps at this SNR), so silently
    # clipping an outlier would otherwise make the visible bars misleading.
    within_limit = max(20.0, float(np.max(np.abs(all_direction))) * 1.05)
    section_style = {
        "preamble": (BLUE, "o"),
        "sync": (PURPLE, "s"),
        "SFD": (RED, "D"),
        "payload": (TEAL, "^"),
    }
    hist_colors = [BLUE, ORANGE, PURPLE]
    fig, axes = plt.subplots(
        1,
        4,
        figsize=(15.4, 3.65),
        gridspec_kw={"width_ratios": [1.30, 0.95, 0.95, 0.95]},
    )

    trace_rows = grouped_rows[display_snrs[0]]
    positions = np.asarray(
        [float(row["chirp_start_symbols"]) for row in trace_rows]
    )
    direction = grouped_direction[display_snrs[0]]
    sections = [row["section"] for row in trace_rows]
    axis = axes[0]
    axis.axhspan(
        float(np.min(direction)),
        float(np.max(direction)),
        color=LIGHT_BLUE,
        alpha=0.28,
        zorder=0,
        label="full-packet min--max range",
    )
    for section, (color, marker) in section_style.items():
        keep = np.asarray([value == section for value in sections])
        axis.scatter(
            positions[keep], direction[keep], color=color, marker=marker,
            s=22, label=section, zorder=4,
        )
    axis.axhline(
        0.0, color=INK, linestyle="--", linewidth=1.6,
        label=r"packet estimate $\widehat{\mathbf{h}}_u$",
    )
    for boundary in [8.0, 10.0, 12.25]:
        axis.axvline(boundary, color=MID_GRAY, linestyle=":", linewidth=0.9)
    axis.set_xlim(-0.5, float(summary["frame_symbols"]))
    axis.set_ylim(-within_limit, within_limit)
    axis.set_xlabel(r"chirp start from packet start ($T_s$)")
    axis.set_ylabel(r"signed direction offset $\Delta\psi$ (degree)")
    axis.set_title(
        f"(a) One complete {frame_symbols:g}-symbol packet at {display_snrs[0]:g} dB",
        fontweight="bold",
    )
    axis.legend(frameon=False, fontsize=6.1, ncol=3, loc="upper right")
    clean_axis(axis, "both")

    for panel_index, (axis, snr_db, color) in enumerate(
        zip(axes[1:], display_snrs, hist_colors), start=1
    ):
        values = grouped_direction[snr_db]
        edges = np.linspace(-within_limit, within_limit, 19)
        counts, _ = np.histogram(values, bins=edges)
        probability_mass = counts / float(values.size)
        axis.bar(
            edges[:-1], probability_mass, width=np.diff(edges), align="edge",
            color=color, alpha=0.34, edgecolor="white", linewidth=0.7,
        )
        centers = 0.5 * (edges[:-1] + edges[1:])
        axis.plot(
            centers, probability_mass, "o-", color=color, linewidth=1.55,
            markersize=3.2,
        )
        axis.axvline(0.0, color=INK, linestyle="--", linewidth=1.1)
        axis.set_xlim(-within_limit, within_limit)
        axis.set_xlabel(r"signed direction offset $\Delta\psi$ (degree)")
        if panel_index == 1:
            axis.set_ylabel("probability mass")
            title = f"(b) SNR = {snr_db:g} dB: error distribution"
        else:
            label = chr(97 + panel_index)
            title = f"({label}) SNR = {snr_db:g} dB: error distribution"
        axis.set_title(title, fontweight="bold")
        clean_axis(axis, "both")

    fig.suptitle(
        f"Indoor channel measurement I: {frame_symbols:g}-symbol signed estimation error",
        fontsize=11.3, fontweight="bold", y=1.01,
    )
    fig.subplots_adjust(
        left=0.065, right=0.992, bottom=0.18, top=0.82, wspace=0.31,
    )
    save_figure(fig, out_dir, "fig_air_within_packet_coherence")
    return {
        "proof_obligation": (
            "The same full-packet direction-error representation is shown at "
            "-20, -10, and 0 dB input SNR."
        ),
        "source_report": summary["source_report"],
        "selected_quality_candidate_ids": summary[
            "selected_quality_candidate_ids"
        ],
        "display_snr_db": display_snrs,
        "frame_symbols": frame_symbols,
        "signed_direction_definition": (
            "projective channel angle in degrees, signed by the relative-phase side"
        ),
        "direction_limit_deg": within_limit,
        "histogram_normalization": "probability mass: count / all chirps at each SNR",
    }


def render_air_concurrent(data_dir: Path, out_dir: Path) -> dict:
    """Render the collision counterpart using the same four-panel form."""

    chirps = read_csv(data_dir / "air_concurrent_channel_chirps.csv")
    summary = read_json(data_dir / "air_concurrent_channel_summary.json")
    display_sirs = [
        float(value)
        for value in summary.get("display_sir_db_by_panel", [-20.0, -10.0, 0.0])
    ]
    if len(display_sirs) != 3:
        raise ValueError("concurrent figure requires three display SIRs")
    frame_symbols = float(summary["frame_symbols"])
    grouped_rows = {
        sir_db: [
            row
            for row in chirps
            if math.isclose(float(row["sir_db"]), sir_db, abs_tol=1e-9)
        ]
        for sir_db in display_sirs
    }
    if any(not rows for rows in grouped_rows.values()):
        raise ValueError("missing collision chirps for one of the display SIRs")
    grouped_direction = {
        sir_db: np.asarray(
            [float(row["signed_direction_deviation_deg"]) for row in rows]
        )
        for sir_db, rows in grouped_rows.items()
    }
    all_direction = np.concatenate(list(grouped_direction.values()))
    # Keep every observed chirp in the displayed support; see the within-
    # packet counterpart for why probability-mass bins must not clip samples.
    direction_limit = max(20.0, float(np.max(np.abs(all_direction))) * 1.05)
    section_style = {
        "preamble": (BLUE, "o"),
        "sync": (PURPLE, "s"),
        "SFD": (RED, "D"),
        "payload": (TEAL, "^"),
    }
    hist_colors = [RED, ORANGE, PURPLE]
    fig, axes = plt.subplots(
        1,
        4,
        figsize=(15.4, 3.65),
        gridspec_kw={"width_ratios": [1.30, 0.95, 0.95, 0.95]},
    )

    trace_rows = grouped_rows[display_sirs[0]]
    positions = np.asarray(
        [float(row["chirp_start_symbols"]) for row in trace_rows]
    )
    direction = grouped_direction[display_sirs[0]]
    sections = [row["section"] for row in trace_rows]
    axis = axes[0]
    axis.axhspan(
        float(np.min(direction)), float(np.max(direction)), color=LIGHT_RED,
        alpha=0.30, zorder=0, label="full-packet min--max range",
    )
    for section, (color, marker) in section_style.items():
        keep = np.asarray([value == section for value in sections])
        axis.scatter(
            positions[keep], direction[keep], color=color, marker=marker,
            s=22, label=section, zorder=4,
        )
    axis.axhline(
        0.0, color=INK, linestyle="--", linewidth=1.6,
        label=r"collision estimate $\widehat{\mathbf{h}}_u$",
    )
    for boundary in [8.0, 10.0, 12.25]:
        axis.axvline(boundary, color=MID_GRAY, linestyle=":", linewidth=0.9)
    axis.set_xlim(-0.5, frame_symbols)
    axis.set_ylim(-direction_limit, direction_limit)
    axis.set_xlabel(r"chirp start from packet start ($T_s$)")
    axis.set_ylabel(r"signed direction offset $\Delta\psi$ (degree)")
    axis.set_title(
        f"(a) One complete {frame_symbols:g}-symbol collision at SIR = {display_sirs[0]:g} dB",
        fontweight="bold",
    )
    axis.legend(frameon=False, fontsize=6.1, ncol=3, loc="upper right")
    clean_axis(axis, "both")

    for panel_index, (axis, sir_db, color) in enumerate(
        zip(axes[1:], display_sirs, hist_colors), start=1
    ):
        values = grouped_direction[sir_db]
        edges = np.linspace(-direction_limit, direction_limit, 19)
        counts, _ = np.histogram(values, bins=edges)
        probability_mass = counts / float(values.size)
        axis.bar(
            edges[:-1], probability_mass, width=np.diff(edges), align="edge",
            color=color, alpha=0.34, edgecolor="white", linewidth=0.7,
        )
        centers = 0.5 * (edges[:-1] + edges[1:])
        axis.plot(
            centers, probability_mass, "o-", color=color, linewidth=1.55,
            markersize=3.2,
        )
        axis.axvline(0.0, color=INK, linestyle="--", linewidth=1.1)
        axis.set_xlim(-direction_limit, direction_limit)
        axis.set_xlabel(r"signed direction offset $\Delta\psi$ (degree)")
        if panel_index == 1:
            axis.set_ylabel("probability mass")
            title = f"(b) SIR = {sir_db:g} dB: error distribution"
        else:
            label = chr(97 + panel_index)
            title = f"({label}) SIR = {sir_db:g} dB: error distribution"
        axis.set_title(title, fontweight="bold")
        clean_axis(axis, "both")

    fig.suptitle(
        "Indoor channel measurement II: 0.2-symbol staggered measured-waveform collisions",
        fontsize=11.1, fontweight="bold", y=1.01,
    )
    fig.subplots_adjust(
        left=0.065, right=0.992, bottom=0.18, top=0.82, wspace=0.31,
    )
    save_figure(fig, out_dir, "fig_air_concurrent_channel_estimation")
    return {
        "proof_obligation": (
            "At 0.2-symbol timing offset and zero additional FFT-bin separation, "
            "the same full-packet direction-error view is used for -20, -10, "
            "and 0 dB SIR."
        ),
        "display_sir_db": display_sirs,
        "frame_symbols": frame_symbols,
        "offset_symbols": float(summary["offset_symbols"]),
        "fixed_fft_bin_distance": float(summary["fixed_fft_bin_distance"]),
        "direction_limit_deg": direction_limit,
        "histogram_normalization": "probability mass: count / all chirps at each SIR",
    }


def render_air_collision_ser_heatmap(data_dir: Path, out_dir: Path) -> dict:
    """Render aggregate SER over the common 300 random collision groups."""

    summary = read_json(data_dir / "air_collision_ser_heatmap_summary.json")
    snrs = [float(value) for value in summary["snr_db"]]
    sirs = [float(value) for value in summary["sir_db"]]
    cell_ser = {
        (float(cell["sir_db"]), float(cell["snr_db"])): float(cell["ser"])
        for cell in summary["cells"]
    }
    matrix = np.asarray(
        [[cell_ser[(sir_db, snr_db)] for snr_db in snrs] for sir_db in sirs]
    )
    fig, axis = plt.subplots(figsize=(5.9, 4.65))
    image = axis.imshow(
        matrix, cmap="YlOrRd", vmin=0.0, vmax=1.0, origin="upper",
        aspect="auto",
    )
    for row_index, sir_db in enumerate(sirs):
        for column_index, snr_db in enumerate(snrs):
            value = matrix[row_index, column_index]
            axis.text(
                column_index, row_index, f"{value:.3f}", ha="center",
                va="center", fontsize=8.4,
                color="white" if value >= 0.55 else INK,
            )
    axis.set_xticks(np.arange(len(snrs)), [f"{value:g}" for value in snrs])
    axis.set_yticks(np.arange(len(sirs)), [f"{value:g}" for value in sirs])
    axis.set_xlabel("injected SNR (dB)")
    axis.set_ylabel("SIR (dB)")
    axis.set_title(
        "Random 300-pair collision SER\n"
        rf"($\Delta\tau={float(summary['offset_symbols']):g}T_s$)",
        fontweight="bold",
    )
    colorbar = fig.colorbar(image, ax=axis, fraction=0.048, pad=0.04)
    colorbar.set_label("SER")
    fig.tight_layout()
    save_figure(fig, out_dir, "fig_air_collision_ser_heatmap")
    return {
        "random_collision_groups": int(summary["random_collision_groups"]),
        "snr_db": snrs,
        "sir_db": sirs,
        "offset_symbols": float(summary["offset_symbols"]),
        "min_ser": float(np.min(matrix)),
        "max_ser": float(np.max(matrix)),
    }


def collision_ser_matrix(summary: dict) -> tuple[list[float], list[float], np.ndarray]:
    """Return the ordered SIR/SNR grid and aggregate SER matrix."""

    snrs = [float(value) for value in summary["snr_db"]]
    sirs = [float(value) for value in summary["sir_db"]]
    values = {
        (float(cell["sir_db"]), float(cell["snr_db"])): float(cell["ser"])
        for cell in summary["cells"]
    }
    matrix = np.asarray(
        [[values[(sir_db, snr_db)] for snr_db in snrs] for sir_db in sirs]
    )
    return sirs, snrs, matrix


def render_air_collision_eta_rank_heatmap(data_dir: Path, out_dir: Path) -> dict:
    """Render the pure eta-min decoder on the shared 300-pair experiment."""

    summary = read_json(data_dir / "air_collision_eta_rank_heatmap_summary.json")
    sirs, snrs, matrix = collision_ser_matrix(summary)
    fig, axis = plt.subplots(figsize=(5.9, 4.65))
    image = axis.imshow(
        matrix, cmap="YlOrRd", vmin=0.0, vmax=1.0, origin="upper",
        aspect="auto",
    )
    for row_index, sir_db in enumerate(sirs):
        for column_index, snr_db in enumerate(snrs):
            value = matrix[row_index, column_index]
            axis.text(
                column_index, row_index, f"{value:.3f}", ha="center",
                va="center", fontsize=8.4,
                color="white" if value >= 0.55 else INK,
            )
    axis.set_xticks(np.arange(len(snrs)), [f"{value:g}" for value in snrs])
    axis.set_yticks(np.arange(len(sirs)), [f"{value:g}" for value in sirs])
    axis.set_xlabel("injected SNR (dB)")
    axis.set_ylabel("SIR (dB)")
    axis.set_title(
        "Direct $\\eta$-rank collision SER\n"
        r"($\arg\min_k\eta[k]$, no energy gate)",
        fontweight="bold",
    )
    colorbar = fig.colorbar(image, ax=axis, fraction=0.048, pad=0.04)
    colorbar.set_label("SER")
    fig.tight_layout()
    save_figure(fig, out_dir, "fig_air_collision_eta_rank_heatmap")
    return {
        "random_collision_groups": int(summary["random_collision_groups"]),
        "snr_db": snrs,
        "sir_db": sirs,
        "offset_symbols": float(summary["offset_symbols"]),
        "decision_rule": summary["decision_rule"],
        "min_ser": float(np.min(matrix)),
        "max_ser": float(np.max(matrix)),
    }


def render_air_collision_sp_vs_eta_rank(data_dir: Path, out_dir: Path) -> dict:
    """Render SP and direct eta ranking on an identical SER color scale."""

    sp_summary = read_json(data_dir / "air_collision_ser_heatmap_summary.json")
    eta_summary = read_json(data_dir / "air_collision_eta_rank_heatmap_summary.json")
    sp_sirs, sp_snrs, sp_matrix = collision_ser_matrix(sp_summary)
    eta_sirs, eta_snrs, eta_matrix = collision_ser_matrix(eta_summary)
    if sp_sirs != eta_sirs or sp_snrs != eta_snrs:
        raise RuntimeError("SP and eta-rank heatmaps do not share the same grid")
    if int(sp_summary["random_collision_groups"]) != int(
        eta_summary["random_collision_groups"]
    ):
        raise RuntimeError("SP and eta-rank heatmaps do not share the same pair count")

    fig, axes = plt.subplots(1, 2, figsize=(10.7, 4.65), sharey=True)
    panels = (
        (axes[0], sp_matrix, r"SP: $\arg\max_k(|P[k]|^2-4|Q[k]|^2)$"),
        (axes[1], eta_matrix, r"$\eta$-rank: $\arg\min_k\eta[k]$"),
    )
    image = None
    for axis, matrix, title in panels:
        image = axis.imshow(
            matrix, cmap="YlOrRd", vmin=0.0, vmax=1.0, origin="upper",
            aspect="auto",
        )
        for row_index, sir_db in enumerate(sp_sirs):
            for column_index, snr_db in enumerate(sp_snrs):
                value = matrix[row_index, column_index]
                axis.text(
                    column_index, row_index, f"{value:.3f}", ha="center",
                    va="center", fontsize=8.1,
                    color="white" if value >= 0.55 else INK,
                )
        axis.set_xticks(
            np.arange(len(sp_snrs)), [f"{value:g}" for value in sp_snrs]
        )
        axis.set_xlabel("injected SNR (dB)")
        axis.set_title(title, fontsize=9.4, fontweight="bold", pad=8)
    axes[0].set_yticks(
        np.arange(len(sp_sirs)), [f"{value:g}" for value in sp_sirs]
    )
    axes[0].set_ylabel("SIR (dB)")
    axes[1].tick_params(axis="y", labelleft=False)
    fig.suptitle(
        "Same 300 measured-waveform collision pairs "
        rf"($\Delta\tau={float(sp_summary['offset_symbols']):g}T_s$)",
        fontweight="bold",
        fontsize=11.0,
    )
    # Reserve a dedicated colorbar axis.  Letting ``fig.colorbar`` resize a
    # two-panel layout after ``subplots_adjust`` can overlap the last eta
    # column and hide its numerical annotation.
    colorbar_axis = fig.add_axes([0.91, 0.14, 0.022, 0.68])
    colorbar = fig.colorbar(image, cax=colorbar_axis)
    colorbar.set_label("SER")
    fig.subplots_adjust(left=0.09, right=0.875, bottom=0.14, top=0.82, wspace=0.16)
    save_figure(fig, out_dir, "fig_air_collision_sp_vs_eta_rank_heatmap")
    return {
        "random_collision_groups": int(sp_summary["random_collision_groups"]),
        "snr_db": sp_snrs,
        "sir_db": sp_sirs,
        "offset_symbols": float(sp_summary["offset_symbols"]),
        "sp_ser": sp_matrix.tolist(),
        "eta_rank_ser": eta_matrix.tolist(),
        "eta_minus_sp_ser": (eta_matrix - sp_matrix).tolist(),
    }


def render_adaptive_lambda_sp_vs_eta_candidates(
    data_dir: Path,
    out_dir: Path,
) -> dict:
    """Render adaptive SP next to eta ranking over FFT peak candidates."""

    sp_summary = read_json(data_dir / "air_collision_ser_heatmap_summary.json")
    sirs, snrs, sp_matrix = collision_ser_matrix(sp_summary)
    candidate_counts = tuple(
        sorted(
            int(path.name.removeprefix("air_collision_sp_top").removesuffix(
                "_heatmap_summary.json"
            ))
            for path in data_dir.glob("air_collision_sp_top*_heatmap_summary.json")
        )
    )
    if not candidate_counts:
        raise FileNotFoundError("no candidate-constrained SP heatmap summaries")
    eta_summaries = {
        count: read_json(
            data_dir / f"air_collision_eta_rank_top{count}_heatmap_summary.json"
        )
        for count in candidate_counts
    }
    eta_matrices: dict[int, np.ndarray] = {}
    candidate_recalls: dict[int, np.ndarray] = {}
    for count, summary in eta_summaries.items():
        eta_sirs, eta_snrs, eta_matrix = collision_ser_matrix(summary)
        if eta_sirs != sirs or eta_snrs != snrs:
            raise RuntimeError(f"eta candidate K={count} does not share SP grid")
        eta_matrices[count] = eta_matrix
        values = {
            (float(cell["sir_db"]), float(cell["snr_db"])): float(
                cell["candidate_recall"]
            )
            for cell in summary["cells"]
        }
        candidate_recalls[count] = np.asarray(
            [[values[(sir_db, snr_db)] for snr_db in snrs] for sir_db in sirs]
        )

    figure_width = max(7.2, 3.6 * (len(candidate_counts) + 1))
    fig, axes = plt.subplots(
        1, len(candidate_counts) + 1, figsize=(figure_width, 4.4), sharey=True,
        squeeze=False,
    )
    axes = axes[0]
    panels = [(axes[0], sp_matrix, r"Adaptive SP\n$\arg\max_k(|P|^2-\lambda_u|Q|^2)$")]
    panels.extend(
        (
            axes[index + 1],
            eta_matrices[count],
            rf"$\eta$-rank, $K={count}$",
        )
        for index, count in enumerate(candidate_counts)
    )
    image = None
    for axis, matrix, title in panels:
        image = axis.imshow(
            matrix, cmap="YlOrRd", vmin=0.0, vmax=1.0, origin="upper",
            aspect="auto",
        )
        for row_index in range(len(sirs)):
            for column_index in range(len(snrs)):
                value = matrix[row_index, column_index]
                axis.text(
                    column_index, row_index, f"{value:.3f}", ha="center",
                    va="center", fontsize=7.7,
                    color="white" if value >= 0.55 else INK,
                )
        axis.set_xticks(np.arange(len(snrs)), [f"{value:g}" for value in snrs])
        axis.set_xlabel("injected SNR (dB)")
        axis.set_title(title, fontsize=8.8, fontweight="bold", pad=8)
    axes[0].set_yticks(np.arange(len(sirs)), [f"{value:g}" for value in sirs])
    axes[0].set_ylabel("SIR (dB)")
    for axis in axes[1:]:
        axis.tick_params(axis="y", labelleft=False)
    fig.suptitle(
        "Same 300 measured-waveform collision pairs: adaptive SP and $\\eta$ candidate ranking",
        fontsize=11.0,
        fontweight="bold",
    )
    colorbar_axis = fig.add_axes([0.925, 0.16, 0.015, 0.65])
    colorbar = fig.colorbar(image, cax=colorbar_axis)
    colorbar.set_label("SER")
    fig.subplots_adjust(left=0.055, right=0.905, bottom=0.16, top=0.80, wspace=0.22)
    save_figure(fig, out_dir, "fig_adaptive_lambda_sp_vs_eta_candidates")

    sp_rows = read_csv(data_dir / "air_collision_ser_heatmap.csv")
    lambda_median = np.empty((len(sirs), len(snrs)))
    certified_rate = np.empty((len(sirs), len(snrs)))
    for row_index, sir_db in enumerate(sirs):
        for column_index, snr_db in enumerate(snrs):
            selected = [
                row for row in sp_rows
                if float(row["sir_db"]) == sir_db and float(row["snr_db"]) == snr_db
            ]
            lambda_median[row_index, column_index] = np.median(
                [float(row["signed_lambda"]) for row in selected]
            )
            certified_rate[row_index, column_index] = np.mean(
                [str(row["lambda_certified_sp"]).lower() == "true" for row in selected]
            )
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.7), sharey=True)
    for axis, matrix, title, maximum in (
        (axes[0], lambda_median, r"median selected $\lambda_u$", 4.0),
        (axes[1], certified_rate, "lambda certificate rate", 1.0),
    ):
        image = axis.imshow(
            matrix, cmap="YlGnBu", vmin=0.0, vmax=maximum, origin="upper",
            aspect="auto",
        )
        for row_index in range(len(sirs)):
            for column_index in range(len(snrs)):
                axis.text(
                    column_index, row_index, f"{matrix[row_index, column_index]:.3f}",
                    ha="center", va="center", fontsize=8.2,
                    color="white" if matrix[row_index, column_index] >= 0.55 * maximum else INK,
                )
        axis.set_xticks(np.arange(len(snrs)), [f"{value:g}" for value in snrs])
        axis.set_xlabel("injected SNR (dB)")
        axis.set_title(title, fontsize=9.2, fontweight="bold")
    axes[0].set_yticks(np.arange(len(sirs)), [f"{value:g}" for value in sirs])
    axes[0].set_ylabel("SIR (dB)")
    axes[1].tick_params(axis="y", labelleft=False)
    fig.tight_layout()
    save_figure(fig, out_dir, "fig_adaptive_lambda_selection")
    return {
        "random_collision_groups": int(sp_summary["random_collision_groups"]),
        "snr_db": snrs,
        "sir_db": sirs,
        "adaptive_sp_ser": sp_matrix.tolist(),
        "eta_candidate_ser": {
            str(count): matrix.tolist() for count, matrix in eta_matrices.items()
        },
        "eta_candidate_recall": {
            str(count): matrix.tolist()
            for count, matrix in candidate_recalls.items()
        },
        "lambda_median": lambda_median.tolist(),
        "lambda_certified_rate": certified_rate.tolist(),
    }


def render_score_matched_adaptive_sp_vs_eta_candidates(
    data_dir: Path,
    out_dir: Path,
) -> dict:
    """Compare adaptive SP and eta after fixing the same peak candidate set.

    This is deliberately separate from the end-to-end plot above: for each
    value of K, both rows use the same locally maximal-energy bins C_K on every
    symbol.  The only difference is the final score, so the plot cannot mix a
    candidate-generation advantage with a scoring-rule advantage.
    """

    reference = read_json(data_dir / "air_collision_ser_heatmap_summary.json")
    sirs, snrs, _ = collision_ser_matrix(reference)
    lambda_selection = reference.get("lambda_selection", {})
    fixed_lambda = lambda_selection.get("fixed_lambda")
    if fixed_lambda is None:
        sp_rule = r"Adaptive SP: $\arg\max_{k\in C_K}(|P|^2-\lambda_u|Q|^2)$"
        title_prefix = "Strict score-only comparison"
    else:
        sp_rule = (
            rf"Fixed $\lambda={float(fixed_lambda):g}$ SP: "
            r"$\arg\max_{k\in C_K}(|P|^2-\lambda|Q|^2)$"
        )
        title_prefix = rf"Strict score-only comparison, fixed $\lambda={float(fixed_lambda):g}$"
    candidate_counts = tuple(
        sorted(
            int(path.name.removeprefix("air_collision_sp_top").removesuffix(
                "_heatmap_summary.json"
            ))
            for path in data_dir.glob("air_collision_sp_top*_heatmap_summary.json")
        )
    )
    if not candidate_counts:
        raise FileNotFoundError("no candidate-constrained SP heatmap summaries")
    sp_matrices: dict[int, np.ndarray] = {}
    eta_matrices: dict[int, np.ndarray] = {}
    candidate_recalls: dict[int, np.ndarray] = {}
    for count in candidate_counts:
        sp_summary = read_json(
            data_dir / f"air_collision_sp_top{count}_heatmap_summary.json"
        )
        eta_summary = read_json(
            data_dir / f"air_collision_eta_rank_top{count}_heatmap_summary.json"
        )
        sp_sirs, sp_snrs, sp_matrix = collision_ser_matrix(sp_summary)
        eta_sirs, eta_snrs, eta_matrix = collision_ser_matrix(eta_summary)
        if sp_sirs != sirs or sp_snrs != snrs:
            raise RuntimeError(f"candidate SP K={count} does not share the grid")
        if eta_sirs != sirs or eta_snrs != snrs:
            raise RuntimeError(f"candidate eta K={count} does not share the grid")
        if int(sp_summary["random_collision_groups"]) != int(
            eta_summary["random_collision_groups"]
        ):
            raise RuntimeError(f"candidate SP and eta K={count} differ in pair count")
        sp_matrices[count] = sp_matrix
        eta_matrices[count] = eta_matrix
        recall_values = {
            (float(cell["sir_db"]), float(cell["snr_db"])): float(
                cell["candidate_recall"]
            )
            for cell in sp_summary["cells"]
        }
        candidate_recalls[count] = np.asarray(
            [
                [recall_values[(sir_db, snr_db)] for snr_db in snrs]
                for sir_db in sirs
            ]
        )

    figure_width = max(4.8, 3.6 * len(candidate_counts))
    fig, axes = plt.subplots(
        2, len(candidate_counts), figsize=(figure_width, 7.2),
        sharex=True, sharey=True, squeeze=False,
    )
    image = None
    for column_index, count in enumerate(candidate_counts):
        for row_index, (matrix, rule) in enumerate(
            (
                (sp_matrices[count], sp_rule),
                (eta_matrices[count], r"$\eta$ rank: $\arg\min_{k\in C_K}\eta[k]$"),
            )
        ):
            axis = axes[row_index, column_index]
            image = axis.imshow(
                matrix, cmap="YlOrRd", vmin=0.0, vmax=1.0, origin="upper",
                aspect="auto",
            )
            for sir_index in range(len(sirs)):
                for snr_index in range(len(snrs)):
                    value = matrix[sir_index, snr_index]
                    axis.text(
                        snr_index, sir_index, f"{value:.3f}", ha="center",
                        va="center", fontsize=7.6,
                        color="white" if value >= 0.55 else INK,
                    )
            if row_index == 0:
                axis.set_title(f"K={count}", fontsize=9.4, fontweight="bold", pad=8)
            if column_index == 0:
                axis.set_ylabel(
                    f"{rule}\nSIR (dB)", fontsize=8.1,
                )
                axis.set_yticks(
                    np.arange(len(sirs)), [f"{value:g}" for value in sirs]
                )
            else:
                axis.tick_params(axis="y", labelleft=False)
            if row_index == 1:
                axis.set_xticks(
                    np.arange(len(snrs)), [f"{value:g}" for value in snrs]
                )
                axis.set_xlabel("injected SNR (dB)")
            else:
                axis.tick_params(axis="x", labelbottom=False)

    fig.suptitle(
        f"{title_prefix}: same 300 collision pairs and same $C_K$",
        fontsize=11.4,
        fontweight="bold",
    )
    colorbar_axis = fig.add_axes([0.925, 0.14, 0.015, 0.70])
    colorbar = fig.colorbar(image, cax=colorbar_axis)
    colorbar.set_label("SER")
    fig.subplots_adjust(left=0.13, right=0.905, bottom=0.12, top=0.85, wspace=0.12, hspace=0.18)
    save_figure(fig, out_dir, "fig_score_matched_adaptive_sp_vs_eta_candidates")
    return {
        "random_collision_groups": int(reference["random_collision_groups"]),
        "snr_db": snrs,
        "sir_db": sirs,
        "candidate_sp_ser": {
            str(count): matrix.tolist() for count, matrix in sp_matrices.items()
        },
        "eta_candidate_ser": {
            str(count): matrix.tolist() for count, matrix in eta_matrices.items()
        },
        "eta_minus_sp_ser": {
            str(count): (eta_matrices[count] - sp_matrices[count]).tolist()
            for count in candidate_counts
        },
        "candidate_recall": {
            str(count): matrix.tolist()
            for count, matrix in candidate_recalls.items()
        },
    }


def write_manifest(out_dir: Path, data_dir: Path, source_dir: Path, figures: dict) -> None:
    payload = {
        "version": "paper-native-minimal-v1",
        "principles": [
            "one proof obligation per figure",
            "minimum subplot count",
            "compact use of canvas",
            "mechanism cases are labeled; aggregate claims retain all samples",
        ],
        "data_dir": str(data_dir.resolve()),
        "source_figure_dir": str(source_dir.resolve()),
        "figures": figures,
    }
    with (out_dir / "paper_native_figure_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("real_usrp_outputs/sp_v2_mechanism_figures"))
    parser.add_argument("--source-figure-dir", type=Path, default=Path("real_usrp_outputs/sp_paper_figures"))
    parser.add_argument("--out-dir", type=Path, default=Path("real_usrp_outputs/sp_v2_paper_native_figures"))
    parser.add_argument(
        "--only-air",
        action="store_true",
        help="render the two indoor channel-measurement figures and SER heatmap",
    )
    parser.add_argument(
        "--only-air-eta-rank",
        action="store_true",
        help="render only the direct eta-rank heatmap and its paired SP comparison",
    )
    parser.add_argument(
        "--only-adaptive-lambda-eta",
        action="store_true",
        help="render adaptive-lambda SP and candidate-constrained eta heatmaps",
    )
    parser.add_argument(
        "--only-score-matched-adaptive-lambda-eta",
        action="store_true",
        help="render adaptive SP and eta under the identical peak candidate set",
    )
    parser.add_argument(
        "--only-fig2d",
        action="store_true",
        help="render only the controlled usable-interval Figure 2(d) heatmaps",
    )
    parser.add_argument(
        "--only-fig7",
        action="store_true",
        help="render only the finite-candidate Figure 7 configuration",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_style()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.only_score_matched_adaptive_lambda_eta:
        figures = {
            "score_matched_adaptive_sp_vs_eta_candidates": (
                render_score_matched_adaptive_sp_vs_eta_candidates(
                    args.data_dir,
                    args.out_dir,
                )
            )
        }
        manifest_path = args.out_dir / "score_matched_adaptive_lambda_eta_figure_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": "score-matched-adaptive-lambda-eta-v1",
                    "data_dir": str(args.data_dir.resolve()),
                    "figures": figures,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figures": list(figures),
                    "manifest": str(manifest_path.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.only_adaptive_lambda_eta:
        figures = {
            "adaptive_lambda_sp_vs_eta_candidates": (
                render_adaptive_lambda_sp_vs_eta_candidates(
                    args.data_dir,
                    args.out_dir,
                )
            )
        }
        manifest_path = args.out_dir / "adaptive_lambda_eta_figure_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": "adaptive-lambda-eta-candidate-v1",
                    "data_dir": str(args.data_dir.resolve()),
                    "figures": figures,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figures": list(figures),
                    "manifest": str(manifest_path.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.only_air_eta_rank:
        figures = {
            "air_collision_eta_rank_heatmap": render_air_collision_eta_rank_heatmap(
                args.data_dir,
                args.out_dir,
            ),
            "air_collision_sp_vs_eta_rank_heatmap": render_air_collision_sp_vs_eta_rank(
                args.data_dir,
                args.out_dir,
            ),
        }
        manifest_path = args.out_dir / "air_collision_eta_rank_figure_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": "air-collision-eta-rank-v1",
                    "data_dir": str(args.data_dir.resolve()),
                    "figures": figures,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figures": list(figures),
                    "manifest": str(manifest_path.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.only_air:
        figures = {
            "air_within_packet": render_air_within(
                args.data_dir,
                args.out_dir,
            ),
            "air_concurrent": render_air_concurrent(
                args.data_dir,
                args.out_dir,
            ),
            "air_collision_ser_heatmap": render_air_collision_ser_heatmap(
                args.data_dir,
                args.out_dir,
            ),
        }
        manifest_path = args.out_dir / "air_channel_figure_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": "indoor-air-channel-v1",
                    "data_dir": str(args.data_dir.resolve()),
                    "figures": figures,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figures": list(figures),
                    "manifest": str(manifest_path.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.only_fig2d:
        result = render_figure2d(args.data_dir, args.out_dir)
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figure2d": result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.only_fig7:
        result = render_figure7(args.data_dir, args.out_dir)
        print(
            json.dumps(
                {
                    "out_dir": str(args.out_dir.resolve()),
                    "figure7": result,
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
        "figure5": render_figure5(args.data_dir, args.out_dir),
        "figure6": render_figure6(args.data_dir, args.out_dir),
        "figure7": render_figure7(args.data_dir, args.out_dir),
        "figure8": render_figure8(args.data_dir, args.out_dir),
        "air_within_packet": render_air_within(args.data_dir, args.out_dir),
        "air_concurrent": render_air_concurrent(args.data_dir, args.out_dir),
        "air_collision_ser_heatmap": render_air_collision_ser_heatmap(
            args.data_dir,
            args.out_dir,
        ),
    }
    write_manifest(args.out_dir, args.data_dir, args.source_figure_dir, figures)
    print(json.dumps({"out_dir": str(args.out_dir.resolve()), "figures": list(figures)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
