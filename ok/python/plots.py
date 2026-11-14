"""Independent 4:3 CSV-driven plot renderers.

Every registered name below produces exactly one panel.  No function draws a
figure title or a subfigure label; edit the nearby function and its CSV file to
change one panel without affecting the others.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm

from common import figure, rows, save, style_axes


COLORS = {
    "blue": "#2878B5",
    "teal": "#18A68D",
    "orange": "#EE7B13",
    "purple": "#7754A6",
    "green": "#44A050",
    "red": "#DE4D4D",
    "navy": "#1C4969",
    "ink": "#18232F",
    "gray": "#7A858E",
}
METHOD_STYLES = {
    "lorawan": dict(color="#4C78A8", marker="o", linestyle="--"),
    "mrc": dict(color="#F58518", marker="s", linestyle="--"),
    "mrc_cic": dict(color="#54A24B", marker="^", linestyle="-."),
    "mrc_cora": dict(color="#C2185B", marker="X", linestyle="--"),
    "pcube": dict(color="#E45756", marker="D", linestyle=":"),
    "maloragw": dict(color="#B279A2", marker="v", linestyle="-."),
    "sp_sync_refine": dict(color="#151515", marker="*", linestyle="-", linewidth=2.4, markersize=10),
}
METHOD_ORDER = ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw", "mrc_cora", "sp_sync_refine")


def f(value: str) -> float:
    return float(value)


def groups(values: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for value in values:
        output[value[key]].append(value)
    return output


def exact_edges(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if len(array) == 1:
        return np.asarray([array[0] - 0.5, array[0] + 0.5])
    middle = 0.5 * (array[:-1] + array[1:])
    return np.concatenate(([array[0] - (middle[0] - array[0])], middle, [array[-1] + (array[-1] - middle[-1])]))


def fig2a_spectrum(column: str, ylabel: str, stem: str, *, zero_line: bool = False) -> None:
    data = rows("fig2a_spectra.csv")
    x = np.asarray([f(row["fft_bin"]) for row in data])
    y = np.asarray([f(row[column]) for row in data])
    truth = int(data[0]["truth_bin"])
    wrong = int(data[0]["wrong_bin"])
    fig, axis = figure()
    axis.plot(x, y, color="#234F8F", linewidth=1.2)
    axis.scatter([truth, wrong], [y[truth], y[wrong]], s=38, zorder=5, color=["#1B9E77", "#D95F02"])
    axis.axvline(truth, color="#1B9E77", linestyle="--", linewidth=1.5, label="target bin")
    axis.axvline(wrong, color="#D95F02", linestyle=":", linewidth=1.8, label="MRC wrong bin")
    if zero_line:
        axis.axhline(0.0, color="#707070", linewidth=0.9, zorder=1)
    axis.set_xlabel("LoRa FFT bin")
    axis.set_ylabel(ylabel)
    if column != "signed_margin":
        axis.set_ylim(-68, 8)
    style_axes(axis, grid="both", line_x_limits=(float(x.min()), float(x.max())))
    axis.legend(loc="upper right", ncol=2, frameon=True)
    save(fig, stem)


def fig2b_spatial_inconsistency() -> None:
    data = rows("fig2b_spatial_inconsistency.csv")
    target = np.asarray([f(row["eta"]) for row in data if row["group"] == "target bin"])
    wrong = np.asarray([f(row["eta"]) for row in data if row["group"] == "MRC wrong bin"])
    fig, axis = figure()
    violins = axis.violinplot([target, wrong], positions=[1, 2], vert=False, showextrema=False)
    for body, color in zip(violins["bodies"], ["#1B9E77", "#D95F02"]):
        body.set_facecolor(color)
        body.set_alpha(0.22)
        body.set_edgecolor("none")
    axis.boxplot([target, wrong], positions=[1, 2], vert=False, widths=0.24, showfliers=False, patch_artist=True,
                 boxprops={"facecolor": "white", "edgecolor": "#333333"},
                 medianprops={"color": "black", "linewidth": 1.5})
    rng = np.random.default_rng(20260718)
    axis.scatter(target, 1 + rng.normal(0, 0.035, len(target)), color="#1B9E77", s=10, alpha=0.22, linewidths=0)
    axis.scatter(wrong, 2 + rng.normal(0, 0.035, len(wrong)), color="#D95F02", s=10, alpha=0.22, linewidths=0)
    axis.axvline(float(np.median(target)), color="#1B9E77", linestyle="--", linewidth=1.2)
    axis.axvline(float(np.median(wrong)), color="#D95F02", linestyle="--", linewidth=1.2)
    axis.set_xscale("log")
    axis.set_xlim(1e-5, 1.0)
    axis.set_yticks([1, 2], ["target bin", "MRC wrong bin"])
    axis.set_xlabel("spatial inconsistency η (target-orthogonal energy ratio)")
    style_axes(axis, grid="x")
    save(fig, "fig2b_spatial_inconsistency")


def fig2c_packet_dependent() -> None:
    data = rows("fig2c_packet_dependent.csv")
    palette = [COLORS[key] for key in ("blue", "teal", "orange", "purple", "green", "red", "navy")]
    markers = ["o", "s", "^", "D", "P", "v", "X"]
    fig, axis = figure()
    for (label, selected), color, marker in zip(sorted(groups(data, "case_label").items()), palette, markers):
        selected.sort(key=lambda row: f(row["evaluation_lambda"]))
        x = [f(row["evaluation_lambda"]) for row in selected]
        y = [f(row["ser"]) for row in selected]
        axis.plot(x, y, color=color, marker=marker, linewidth=1.7, markersize=4.0, label=label)
        best = int(np.argmin(y))
        axis.scatter([x[best]], [y[best]], marker="*", s=105, color=color, edgecolor=COLORS["ink"], zorder=6)
    axis.set_xlabel("counter-evidence weight λ")
    axis.set_ylabel("full-payload SER")
    axis.set_ylim(-0.035, 1.035)
    style_axes(axis, grid="both", line_x_limits=(0.0, 7.0))
    axis.legend(loc="upper right", ncol=2, frameon=True)
    save(fig, "fig2c_packet_dependent_lambda")


def fig2c_fixed_lambda() -> None:
    data = rows("fig2c_fixed_lambda_prr.csv")
    x = np.asarray([f(row["evaluation_lambda"]) for row in data])
    y = 100.0 * np.asarray([f(row["full_payload_recovery_rate"]) for row in data])
    fig, axis = figure()
    axis.bar(x, y, width=0.18, color=COLORS["blue"], edgecolor="white", zorder=3)
    axis.set_xlabel("counter-evidence weight λ")
    axis.set_ylabel("full-payload PRR across 7 packets (%)")
    axis.set_ylim(0, 35)
    axis.set_xticks(np.arange(0, 7.1, 1))
    style_axes(axis, grid="y")
    save(fig, "fig2c_fixed_lambda_prr")


def fig2d_heatmap(kind: str) -> None:
    if kind == "lower":
        data = rows("fig2d_lower_heatmap.csv")
        boundary = rows("fig2d_lower_boundary.csv")
        x_field, y_field = "sir_db", "evaluation_lambda"
        boundary_y = "lambda_low"
        xlabel, stem = "payload SIR (dB)", "fig2d_competition_lower_bound_heatmap"
    else:
        data = rows("fig2d_upper_heatmap.csv")
        boundary = rows("fig2d_upper_boundary.csv")
        x_field, y_field = "theta_u_deg", "evaluation_lambda"
        boundary_y = "lambda_high"
        xlabel, stem = "target-reference uncertainty θu (degree)", "fig2d_target_reliability_upper_bound_heatmap"
    xs = sorted({f(row[x_field]) for row in data})
    ys = sorted({f(row[y_field]) for row in data})
    lookup = {(f(row[x_field]), f(row[y_field])): f(row["ser"]) for row in data}
    matrix = np.asarray([[lookup[(x, y)] for x in xs] for y in ys])
    fig, axis = figure()
    # Rasterize the contiguous cells in the PDF.  Otherwise some PDF viewers
    # anti-alias neighbouring QuadMesh cells separately, creating spurious
    # thin white seams even through uniform red/green regions.
    image = axis.pcolormesh(
        exact_edges(xs), exact_edges(ys), matrix,
        cmap="RdYlGn_r", vmin=0, vmax=1, shading="flat",
        antialiased=False, edgecolors="none", linewidth=0.0, rasterized=True,
    )
    bx = [f(row[x_field]) for row in boundary]
    by = [f(row[boundary_y]) for row in boundary]
    axis.plot(bx, by, color=COLORS["ink"], marker="o", markerfacecolor="white", linewidth=2.0, label="usable-interval boundary")
    axis.set_xlabel(xlabel)
    axis.set_ylabel("counter-evidence weight λ")
    style_axes(axis, grid=None)
    axis.legend(loc="upper right", frameon=True)
    colorbar = fig.colorbar(image, ax=axis, pad=0.03)
    colorbar.set_label("full-payload SER")
    save(fig, stem)


def fig5_timeline() -> None:
    data = sorted(rows("fig5_timeline.csv"), key=lambda row: int(row["packet_index"]))
    meta = rows("fig5_meta.csv")[0]
    frame = f(meta["frame_symbols"])
    payload_start = f(meta["payload_start_symbols"])
    starts = [f(row["start_symbols"]) for row in data]
    origin = min(starts)
    fig, axis = figure()
    target_start = f(data[0]["start_symbols"]) - origin
    axis.axvspan(target_start + payload_start, target_start + frame, color="#A9CCE3", alpha=0.35, zorder=0)
    labels = []
    for index, row in enumerate(data):
        start = f(row["start_symbols"]) - origin
        y = len(data) - 1 - index
        color = COLORS["blue"] if row["is_target"] == "1" else COLORS["orange"]
        axis.broken_barh([(start, payload_start)], (y - 0.31, 0.62), facecolors=color, alpha=0.28, edgecolors="none")
        axis.broken_barh([(start + payload_start, frame - payload_start)], (y - 0.31, 0.62), facecolors=color, alpha=0.78, edgecolors="none")
        labels.append((y, ("u  " if index == 0 else f"v{index}  ") + row["source_label"]))
    axis.set_yticks([value[0] for value in labels], [value[1] for value in labels])
    axis.set_xlabel("time (LoRa symbols)")
    style_axes(axis, grid="y")
    save(fig, "fig5_overlap_timeline")


def fig5_pair_risk() -> None:
    data = rows("fig5_pair_risk.csv")
    xs = sorted({f(row["lambda"]) for row in data})
    pairs = sorted({int(row["pair_index"]) for row in data})
    lookup = {(f(row["lambda"]), int(row["pair_index"])): f(row["risk"]) for row in data}
    matrix = np.asarray([[lookup[(x, pair)] for x in xs] for pair in pairs])
    active = np.argmin(matrix, axis=0)
    fig, axis = figure()
    image = axis.imshow(matrix, aspect="auto", origin="upper", extent=[xs[0], xs[-1], pairs[-1] + 0.5, pairs[0] - 0.5],
                        cmap="RdBu", norm=TwoSlopeNorm(vcenter=0.0, vmin=float(np.quantile(matrix, 0.02)), vmax=float(np.quantile(matrix, 0.98))))
    axis.plot(xs, active, color="white", linewidth=3.0, zorder=4)
    axis.plot(xs, active, color=COLORS["ink"], linewidth=1.0, zorder=5, label="active worst pair")
    axis.set_yticks(pairs, [f"v{index + 1}" for index in pairs])
    axis.set_xlabel("counter-evidence weight λ")
    axis.set_ylabel("member of Iu")
    style_axes(axis, grid=None, line_x_limits=(xs[0], xs[-1]))
    axis.legend(loc="upper right", frameon=True)
    colorbar = fig.colorbar(image, ax=axis, pad=0.03)
    colorbar.set_label("Ruv(λ)")
    save(fig, "fig5_pair_risk_heatmap")


def fig7_configuration() -> None:
    curves = rows("fig7_pair_curves.csv")
    candidates = rows("fig7_candidates.csv")
    meta = rows("fig7_meta.csv")[0]
    by_pair = groups(curves, "pair_index")
    envelope_source = sorted(by_pair["0"], key=lambda row: f(row["lambda"]))
    x = np.asarray([f(row["lambda"]) for row in envelope_source])
    envelope = np.asarray([f(row["envelope"]) for row in envelope_source])
    fig, axis = figure()
    for pair, selected in sorted(by_pair.items()):
        selected.sort(key=lambda row: f(row["lambda"]))
        axis.plot([f(row["lambda"]) for row in selected], [f(row["risk"]) for row in selected], color="#A9B1B8", linestyle="--", linewidth=1.5,
                  label="pair curves" if pair == "0" else None)
    axis.fill_between(x, -0.6, envelope, color="#D8EAF7", alpha=0.8, label="lower-envelope region")
    axis.plot(x, envelope, color=COLORS["ink"], linewidth=3.5, label="worst-pair envelope")
    marker_map = {"boundary": ("o", COLORS["gray"]), "analytic": ("^", COLORS["orange"]), "coverage": ("o", COLORS["blue"]), "midpoint": ("D", COLORS["purple"])}
    for category, selected in sorted(groups(candidates, "category").items()):
        marker, color = marker_map[category]
        axis.scatter([f(row["lambda"]) for row in selected], [f(row["objective"]) for row in selected], marker=marker, s=78, color=color, edgecolor=COLORS["ink"], zorder=6, label=category.replace("_", " "))
    axis.scatter([f(meta["finite_lambda"])], [f(meta["finite_objective"])], marker="*", s=260, color="#D64242", edgecolor=COLORS["ink"], zorder=7, label="selected λ")
    axis.set_xlabel("counter-evidence weight λ")
    axis.set_ylabel("normalized worst-pair margin")
    axis.set_ylim(-0.65, max(envelope) + 0.25)
    style_axes(axis, grid="both", line_x_limits=(0.0, f(meta["lambda_cap"])))
    axis.legend(loc="lower right", ncol=2, frameon=True)
    save(fig, "fig7_finite_packet_configuration")


def air_trace(kind: str) -> None:
    filename = "air_within_chirps.csv" if kind == "within" else "air_concurrent_chirps.csv"
    field = "snr_db" if kind == "within" else "sir_db"
    data = [row for row in rows(filename) if abs(f(row[field]) + 20.0) < 1e-9]
    data.sort(key=lambda row: f(row["chirp_start_symbols"]))
    section_style = {"preamble": (COLORS["blue"], "o"), "sync": (COLORS["purple"], "s"), "SFD": (COLORS["red"], "D"), "payload": (COLORS["teal"], "^")}
    values = np.asarray([f(row["signed_direction_deviation_deg"]) for row in data])
    x = np.asarray([f(row["chirp_start_symbols"]) for row in data])
    fig, axis = figure()
    axis.axhspan(float(values.min()), float(values.max()), color="#D8EAF7" if kind == "within" else "#F8DDDA", alpha=0.38, zorder=0)
    for section, (color, marker) in section_style.items():
        selected = [row for row in data if row["section"] == section]
        axis.scatter([f(row["chirp_start_symbols"]) for row in selected], [f(row["signed_direction_deviation_deg"]) for row in selected],
                     color=color, marker=marker, s=38, label=section, zorder=4)
    axis.axhline(0.0, color=COLORS["ink"], linestyle="--", linewidth=1.4)
    for boundary in (8.0, 10.0, 12.25):
        axis.axvline(boundary, color="#8D99A5", linestyle=":", linewidth=1.0)
    axis.set_xlabel("chirp start from packet start (Ts)")
    axis.set_ylabel("signed direction offset Δψ (degree)")
    style_axes(axis, grid="both", boxed=(kind == "within"), line_x_limits=(float(x.min()), float(x.max())))
    axis.legend(loc="upper center", ncol=4, frameon=False, fontsize=8)
    save(fig, f"fig_air_{kind}_trace")


def air_hist(kind: str, level: int) -> None:
    filename = "air_within_chirps.csv" if kind == "within" else "air_concurrent_chirps.csv"
    field = "snr_db" if kind == "within" else "sir_db"
    data = [row for row in rows(filename) if abs(f(row[field]) - level) < 1e-9]
    values = np.asarray([f(row["signed_direction_deviation_deg"]) for row in data])
    limit = max(20.0, float(np.quantile(np.abs(values), 0.995)) * 1.2)
    color = {"-20": "#2B7BBB", "-10": "#EF7D18", "0": "#7655A6"}[str(level)]
    fig, axis = figure()
    height, edges, _ = axis.hist(values, bins=np.linspace(-limit, limit, 19), density=True, color=color, alpha=0.32, edgecolor="white", linewidth=0.7, zorder=2)
    centers = 0.5 * (edges[:-1] + edges[1:])
    axis.plot(centers, height, "o-", color=color, linewidth=1.7, markersize=4)
    axis.set_xlim(-limit, limit)
    axis.set_xlabel("signed direction offset Δψ (degree)")
    axis.set_ylabel("probability density")
    style_axes(axis, grid="both", boxed=(kind == "within"))
    save(fig, f"fig_air_{kind}_{field}_{level}db_distribution")


def air_collision_heatmap() -> None:
    data = rows("air_collision_ser_heatmap.csv")
    xs = sorted({f(row["snr_db"]) for row in data})
    ys = sorted({f(row["sir_db"]) for row in data})
    lookup = {(f(row["snr_db"]), f(row["sir_db"])): f(row["ser"]) for row in data}
    matrix = np.asarray([[lookup[(x, y)] for x in xs] for y in ys])
    fig, axis = figure()
    image = axis.imshow(matrix, cmap="YlOrRd", vmin=0, vmax=1, origin="upper", aspect="auto")
    for yi, y in enumerate(ys):
        for xi, x in enumerate(xs):
            axis.text(xi, yi, f"{matrix[yi, xi]:.3f}", ha="center", va="center", fontsize=11, color=COLORS["ink"])
    axis.set_xticks(range(len(xs)), [f"{value:g}" for value in xs])
    axis.set_yticks(range(len(ys)), [f"{value:g}" for value in ys])
    axis.set_xlabel("injected SNR (dB)")
    axis.set_ylabel("SIR (dB)")
    style_axes(axis, grid=None)
    colorbar = fig.colorbar(image, ax=axis, pad=0.03)
    colorbar.set_label("SER")
    save(fig, "fig_air_collision_ser_heatmap")


def candidate_share(policy: str) -> None:
    data = [row for row in rows("candidate_winner_share.csv") if row["policy"] == policy]
    fig, axis = figure()
    labels = [row["candidate_source"].replace(" ", "\n") for row in data]
    values = [f(row["winner_share_percent"]) for row in data]
    colors = ["#4C78A8", "#59A14F", "#9C755F", "#F28E2B"]
    axis.bar(np.arange(len(data)), values, color=colors[:len(data)], edgecolor="white", zorder=3)
    axis.set_xticks(np.arange(len(data)), labels)
    axis.set_ylabel("winner share (%)")
    axis.set_ylim(0, max(values) * 1.2)
    style_axes(axis, grid="y")
    save(fig, f"candidate_winner_share_{policy}")


def aggregate_panel(figure_name: str, bandwidth: int, metric: str, stem: str) -> None:
    data = [row for row in rows("fig9_10_12_aggregate.csv") if row["figure"] == figure_name and int(row["bandwidth_hz"]) == bandwidth]
    fig, axis = figure()
    for method in METHOD_ORDER:
        selected = sorted([row for row in data if row["method"] == method], key=lambda row: int(float(row["setting"])))
        if not selected:
            continue
        x = [int(float(row["setting"])) for row in selected]
        y = [f(row[metric]) for row in selected]
        axis.plot(x, y, label=selected[0]["method_label"], **METHOD_STYLES[method])
    all_x = sorted({int(float(row["setting"])) for row in data})
    axis.set_xticks(all_x)
    axis.set_xlabel("Number of active nodes, N")
    axis.set_ylabel("PRR" if metric == "conditional_prr_mean" else "Effective TPS (CRC-valid payload bit/s)")
    if metric == "conditional_prr_mean":
        axis.set_ylim(-0.03, 1.05)
    style_axes(axis, grid="both", line_x_limits=(min(all_x), max(all_x)))
    axis.legend(loc="upper right" if metric == "conditional_prr_mean" else "upper left", ncol=2, frameon=True)
    save(fig, stem)


def fig12_prr() -> None:
    data = [row for row in rows("fig9_10_12_aggregate.csv") if row["figure"] == "fig12"]
    order = ["2cm", "5cm", "10cm", "20cm", ">20cm"]
    fig, axis = figure()
    for method in ("mrc", "pcube", "maloragw", "sp_sync_refine"):
        selected = {row["setting"]: row for row in data if row["method"] == method}
        x = np.arange(len(order))
        y = [f(selected[key]["conditional_prr_mean"]) for key in order]
        axis.plot(x, y, label=selected[order[0]]["method_label"], **METHOD_STYLES[method])
    axis.set_xticks(np.arange(len(order)), order)
    axis.set_xlabel("Separation between two nodes")
    axis.set_ylabel("PRR")
    axis.set_ylim(-0.03, 1.05)
    style_axes(axis, grid="both", line_x_limits=(0, len(order) - 1))
    axis.legend(loc="lower left", ncol=2, frameon=True)
    save(fig, "fig12_prr")


def fig11_decoder_time() -> None:
    data = rows("fig11_summary.csv")
    orders = sorted({int(row["collision_order"]) for row in data})
    methods = [method for method in METHOD_ORDER if any(row["method"] == method for row in data)]
    fig, axis = figure()
    x = np.arange(len(orders), dtype=float)
    width = 0.84 / len(methods)
    for index, method in enumerate(methods):
        lookup = {int(row["collision_order"]): row for row in data if row["method"] == method}
        values = np.asarray([f(lookup[order]["post_sp_time_mean_ms"]) for order in orders])
        low = np.asarray([f(lookup[order]["post_sp_time_ci95_low_ms"]) for order in orders])
        high = np.asarray([f(lookup[order]["post_sp_time_ci95_high_ms"]) for order in orders])
        positions = x - 0.42 + width / 2 + index * width
        axis.bar(positions, values, width, yerr=np.vstack((values - low, high - values)), capsize=2, color=METHOD_STYLES[method]["color"], label=lookup[orders[0]]["method_label"], zorder=3)
    axis.set_xticks(x, [str(value) for value in orders])
    axis.set_xlabel("Packets in the target collision group")
    axis.set_ylabel("Estimation + decode time / collision scene (ms)")
    style_axes(axis, grid="y")
    axis.legend(loc="upper left", ncol=2, frameon=False)
    save(fig, "fig11_decoder_time")


def fig11_prr() -> None:
    data = rows("fig11_summary.csv")
    orders = sorted({int(row["collision_order"]) for row in data})
    fig, axis = figure()
    for method in METHOD_ORDER:
        selected = sorted([row for row in data if row["method"] == method], key=lambda row: int(row["collision_order"]))
        if selected:
            axis.plot(orders, [f(row["prr_mean"]) for row in selected], label=selected[0]["method_label"], **METHOD_STYLES[method])
    axis.set_xticks(orders)
    axis.set_xlabel("Packets in the target collision group")
    axis.set_ylabel("PRR")
    axis.set_ylim(-0.03, 1.03)
    style_axes(axis, grid="both", line_x_limits=(orders[0], orders[-1]))
    axis.legend(loc="upper right", ncol=2, frameon=True)
    save(fig, "fig11_prr")


def fig13_panel(sf: int, metric: str) -> None:
    data = [row for row in rows("fig13_prr.csv") if int(row["sf"]) == sf]
    methods = ("sp_sync_refine", "mrc", "mrc_cic", "mrc_cora", "pcube", "maloragw")
    fig, axis = figure()
    for method in methods:
        selected = sorted([row for row in data if row["method"] == method], key=lambda row: int(row["node_count"]))
        if selected:
            axis.plot([int(row["node_count"]) for row in selected], [f(row[metric]) for row in selected], label=selected[0]["method_label"], **METHOD_STYLES[method])
    x = sorted({int(row["node_count"]) for row in data})
    axis.set_xticks(x)
    axis.set_xlabel("Active nodes N")
    axis.set_ylabel("PRR" if metric == "prr" else "Effective TPS (CRC-valid payload bit/s)")
    if metric == "prr":
        axis.set_ylim(-0.02, 1.02)
    else:
        axis.set_ylim(bottom=0.0)
    style_axes(axis, grid="both", line_x_limits=(x[0], x[-1]))
    axis.legend(loc="upper right", ncol=2, frameon=True)
    metric_name = "prr" if metric == "prr" else "tps"
    save(fig, f"fig13_sf{sf}_{metric_name}")


PLOTS: dict[str, Callable[[], None]] = {
    "fig2a_target_spectrum": lambda: fig2a_spectrum("target_spectrum_db", "relative power (dB)", "fig2a_target_spectrum"),
    "fig2a_orthogonal_spectrum": lambda: fig2a_spectrum("orthogonal_spectrum_db", "relative power (dB)", "fig2a_orthogonal_spectrum"),
    "fig2a_signed_margin": lambda: fig2a_spectrum("signed_margin", "normalized margin", "fig2a_signed_margin", zero_line=True),
    "fig2b_spatial_inconsistency": fig2b_spatial_inconsistency,
    "fig2c_packet_dependent_lambda": fig2c_packet_dependent,
    "fig2c_fixed_lambda_prr": fig2c_fixed_lambda,
    "fig2d_competition_lower_bound_heatmap": lambda: fig2d_heatmap("lower"),
    "fig2d_target_reliability_upper_bound_heatmap": lambda: fig2d_heatmap("upper"),
    "fig5_overlap_timeline": fig5_timeline,
    "fig5_pair_risk_heatmap": fig5_pair_risk,
    "fig7_finite_packet_configuration": fig7_configuration,
    "fig_air_within_trace": lambda: air_trace("within"),
    "fig_air_within_snr_-20db_distribution": lambda: air_hist("within", -20),
    "fig_air_within_snr_-10db_distribution": lambda: air_hist("within", -10),
    "fig_air_within_snr_0db_distribution": lambda: air_hist("within", 0),
    "fig_air_concurrent_trace": lambda: air_trace("concurrent"),
    "fig_air_concurrent_sir_-20db_distribution": lambda: air_hist("concurrent", -20),
    "fig_air_concurrent_sir_-10db_distribution": lambda: air_hist("concurrent", -10),
    "fig_air_concurrent_sir_0db_distribution": lambda: air_hist("concurrent", 0),
    "fig_air_collision_ser_heatmap": air_collision_heatmap,
    "candidate_winner_share_three_checkpoints": lambda: candidate_share("three_checkpoints"),
    "candidate_winner_share_10000_checkpoints": lambda: candidate_share("10000_checkpoints"),
    "fig9_prr_bw125": lambda: aggregate_panel("fig9_10", 125000, "conditional_prr_mean", "fig9_prr_bw125"),
    "fig9_prr_bw250": lambda: aggregate_panel("fig9_10", 250000, "conditional_prr_mean", "fig9_prr_bw250"),
    "fig10_tps_bw125": lambda: aggregate_panel("fig9_10", 125000, "effective_tps_mean", "fig10_tps_bw125"),
    "fig10_tps_bw250": lambda: aggregate_panel("fig9_10", 250000, "effective_tps_mean", "fig10_tps_bw250"),
    "fig12_prr": fig12_prr,
    "fig11_decoder_time": fig11_decoder_time,
    "fig11_prr": fig11_prr,
    "fig13_sf8_prr": lambda: fig13_panel(8, "prr"),
    "fig13_sf10_prr": lambda: fig13_panel(10, "prr"),
    "fig13_sf8_tps": lambda: fig13_panel(8, "effective_tps_bps"),
    "fig13_sf10_tps": lambda: fig13_panel(10, "effective_tps_bps"),
}


def render(name: str) -> None:
    try:
        PLOTS[name]()
    except KeyError as exc:
        raise SystemExit(f"unknown panel {name}; choose one of: {', '.join(PLOTS)}") from exc
