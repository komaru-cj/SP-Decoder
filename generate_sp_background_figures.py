"""Generate background-system figures for SP.md."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "real_usrp_outputs/sp_paper_figures"


def save_fig(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.png", dpi=240, bbox_inches="tight", pad_inches=0.05)
    fig.savefig(OUT_DIR / f"{name}.svg", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def draw_node(ax: plt.Axes, xy: tuple[float, float], color: str, label: str, detail: str) -> None:
    x, y = xy
    ax.add_patch(Circle((x, y), 0.035, facecolor=color, edgecolor="white", linewidth=1.2, zorder=4))
    ax.text(x, y + 0.050, label, ha="center", va="bottom", fontsize=7.4, weight="bold")
    ax.text(x, y - 0.052, detail, ha="center", va="top", fontsize=6.2, color="0.25")


def draw_gateway(ax: plt.Axes, xy: tuple[float, float]) -> None:
    x, y = xy
    ax.add_patch(Rectangle((x - 0.05, y - 0.03), 0.10, 0.06, facecolor="#f5f5f5", edgecolor="0.25", linewidth=1.0, zorder=4))
    ax.plot([x - 0.025, x - 0.045], [y + 0.03, y + 0.105], color="0.15", linewidth=1.2)
    ax.plot([x + 0.025, x + 0.045], [y + 0.03, y + 0.105], color="0.15", linewidth=1.2)
    ax.scatter([x - 0.045, x + 0.045], [y + 0.105, y + 0.105], s=18, color="0.15", zorder=5)
    ax.text(x, y - 0.065, "dual-antenna\nLoRa gateway", ha="center", va="top", fontsize=7.0)


def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], color: str, label: str, rad: float = 0.0) -> None:
    arr = FancyArrowPatch(
        start,
        end,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>",
        mutation_scale=9,
        linewidth=1.1,
        color=color,
        alpha=0.78,
        zorder=2,
    )
    ax.add_patch(arr)
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    ax.text(mid[0], mid[1] + 0.035, label, ha="center", va="bottom", fontsize=6.6, color=color)


def chirp_track(ax: plt.Axes, x0: float, x1: float, y0: float, height: float, color: str, label: str) -> None:
    xs = np.linspace(x0, x1, 60)
    phase = (xs - x0) / (x1 - x0)
    ys = y0 + height * phase
    ax.plot(xs, ys, color=color, linewidth=1.4)
    ax.text(x0 - 0.005, y0, label, ha="right", va="center", fontsize=6.5, color=color)


def draw_receiver_flow(ax: plt.Axes) -> None:
    ax.text(0.50, 0.93, "standard LoRa demodulation", ha="center", va="top", fontsize=8.2, weight="bold")
    boxes = [
        (0.50, 0.75, "symbol window\n$N=LM$ samples"),
        (0.50, 0.54, "multiply by\ndownchirp $d[n]$"),
        (0.50, 0.33, "polyphase\n$M$-point FFT"),
        (0.50, 0.13, "$\\arg\\max_k |Z[k]|^2$"),
    ]
    for x, y, text in boxes:
        ax.add_patch(Rectangle((x - 0.16, y - 0.055), 0.32, 0.11, facecolor="#f7f7f7", edgecolor="0.35", linewidth=0.9))
        ax.text(x, y, text, ha="center", va="center", fontsize=6.7)
    for i in range(len(boxes) - 1):
        ax.add_patch(FancyArrowPatch((0.50, boxes[i][1] - 0.065), (0.50, boxes[i + 1][1] + 0.065), arrowstyle="-|>", mutation_scale=9, linewidth=1.0, color="0.25"))


def make_spectrum(seed: int, collision: bool) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    m = 96
    x = np.arange(m)
    y = 0.035 + 0.02 * rng.random(m)
    if not collision:
        y += 1.05 * np.exp(-0.5 * ((x - 53) / 1.25) ** 2)
        y += 0.06 * np.exp(-0.5 * ((x - 21) / 2.2) ** 2)
    else:
        y += 0.85 * np.exp(-0.5 * ((x - 34) / 1.7) ** 2)
        y += 0.74 * np.exp(-0.5 * ((x - 53) / 1.4) ** 2)
        y += 0.50 * np.exp(-0.5 * ((x - 68) / 2.2) ** 2)
        y += 0.32 * np.exp(-0.5 * ((x - 18) / 3.2) ** 2)
        y += 0.12 * rng.random(m)
    y = y / np.max(y)
    return x, y


def draw_spectrum(ax: plt.Axes, rect: tuple[float, float, float, float], title: str, collision: bool) -> None:
    x0, y0, w, h = rect
    x, y = make_spectrum(7 if not collision else 11, collision)
    xs = x0 + w * (x / (len(x) - 1))
    ys = y0 + h * y
    ax.plot(xs, ys, color="#245493", linewidth=1.2)
    ax.fill_between(xs, y0, ys, color="#245493", alpha=0.10)
    ax.plot([x0, x0 + w], [y0, y0], color="0.25", linewidth=0.8)
    ax.plot([x0, x0], [y0, y0 + h], color="0.25", linewidth=0.8)
    if collision:
        peak_bins = [34, 53, 68]
        colors = ["#d95f02", "#1b9e77", "#7570b3"]
    else:
        peak_bins = [53]
        colors = ["#1b9e77"]
    for b, c in zip(peak_bins, colors):
        bx = x0 + w * (b / (len(x) - 1))
        by = y0 + h * y[b]
        ax.scatter([bx], [by], s=20, color=c, zorder=5)
        ax.plot([bx, bx], [y0, by], color=c, linestyle="--", linewidth=0.9)
    ax.text(x0, y0 + h + 0.042, title, ha="left", va="bottom", fontsize=7.9, weight="bold")
    ax.text(x0 + w / 2, y0 - 0.055, "LoRa FFT bin", ha="center", va="top", fontsize=6.8)
    ax.text(x0 - 0.035, y0 + h / 2, "relative power", ha="right", va="center", rotation=90, fontsize=6.8)


def generate_dual_antenna_reception_figure() -> None:
    fig = plt.figure(figsize=(9.4, 4.25))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.38, 0.90, 1.24], wspace=0.12)
    scene = fig.add_subplot(gs[0, 0])
    flow = fig.add_subplot(gs[0, 1])
    spectra = fig.add_subplot(gs[0, 2])
    for ax in [scene, flow, spectra]:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    scene.text(0.03, 0.95, "dual-antenna concurrent reception", ha="left", va="top", fontsize=8.2, weight="bold")
    gw = (0.77, 0.47)
    draw_gateway(scene, gw)
    nodes = [
        ((0.17, 0.78), "#1b9e77", "node $u$", "$s_u$, near"),
        ((0.10, 0.30), "#d95f02", "node $v$", "$s_v$, far"),
        ((0.40, 0.18), "#7570b3", "node $w$", "$s_w$, mid"),
    ]
    for xy, color, label, detail in nodes:
        draw_node(scene, xy, color, label, detail)
    draw_arrow(scene, (0.21, 0.75), (0.70, 0.53), "#1b9e77", "$h_u,\\tau_u$", -0.05)
    draw_arrow(scene, (0.14, 0.31), (0.70, 0.45), "#d95f02", "$h_v,\\tau_v$", 0.06)
    draw_arrow(scene, (0.44, 0.20), (0.72, 0.40), "#7570b3", "$h_w,\\tau_w$", -0.02)

    scene.add_patch(Rectangle((0.56, 0.77), 0.34, 0.11, facecolor="#f7f7f7", edgecolor="0.55", linewidth=0.8))
    chirp_track(scene, 0.59, 0.80, 0.795, 0.050, "#1b9e77", "$u$")
    chirp_track(scene, 0.62, 0.86, 0.785, 0.045, "#d95f02", "$v$")
    chirp_track(scene, 0.66, 0.88, 0.775, 0.040, "#7570b3", "$w$")
    scene.text(0.73, 0.895, "overlapped arrivals", ha="center", va="bottom", fontsize=7.0)

    draw_receiver_flow(flow)
    flow.add_patch(FancyArrowPatch((0.02, 0.50), (0.27, 0.50), arrowstyle="-|>", mutation_scale=10, linewidth=1.0, color="0.25"))
    flow.add_patch(FancyArrowPatch((0.73, 0.50), (0.98, 0.50), arrowstyle="-|>", mutation_scale=10, linewidth=1.0, color="0.25"))

    spectra.text(0.02, 0.95, "FFT observation after dechirp", ha="left", va="top", fontsize=8.2, weight="bold")
    draw_spectrum(spectra, (0.13, 0.58, 0.78, 0.24), "single packet: one dominant bin", collision=False)
    draw_spectrum(spectra, (0.13, 0.17, 0.78, 0.25), "overlapped packets: multiple peaks and leakage", collision=True)
    save_fig(fig, "fig2_dual_antenna_lora_reception")


if __name__ == "__main__":
    generate_dual_antenna_reception_figure()
