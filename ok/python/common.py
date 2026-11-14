"""Shared CSV loading and visual rules for the separated 4:3 figures."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "output"
FIGSIZE = (8.0, 6.0)  # Exact 4:3 canvas.


def rows(filename: str) -> list[dict[str, str]]:
    with (DATA_DIR / filename).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.edgecolor": "#000000",
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "legend.fontsize": 9,
            "axes.linewidth": 1.0,
            "savefig.dpi": 200,
            "pdf.fonttype": 42,
        }
    )


def figure():
    configure()
    return plt.subplots(figsize=FIGSIZE)


def style_axes(
    axis,
    *,
    grid: str | None = "both",
    boxed: bool = False,
    line_x_limits: tuple[float, float] | None = None,
) -> None:
    """Apply the requested neutral dashed grid and no line-chart x padding."""

    axis.set_axisbelow(True)
    if grid:
        axis.grid(
            True,
            axis=grid,
            color="#AEB6BF",
            linestyle="--",
            linewidth=0.7,
            alpha=0.65,
            zorder=0,
        )
    # Every separated panel uses a complete black outer frame.  Tick labels
    # remain on the conventional bottom/left sides, while their tick marks
    # point into the plotting area as requested.
    for spine in axis.spines.values():
        spine.set_visible(True)
        spine.set_color("#000000")
        spine.set_linewidth(1.0)
    axis.tick_params(axis="both", which="both", direction="in", colors="#000000")
    if line_x_limits is not None:
        axis.set_xlim(*line_x_limits)
    axis.margins(x=0)


def save(fig, stem: str) -> None:
    """Save both editable-vector-friendly PDF and raster PNG, always 4:3."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.14, right=0.97, bottom=0.14, top=0.97)
    for suffix in ("png", "pdf"):
        fig.savefig(OUTPUT_DIR / f"{stem}.{suffix}", facecolor="white")
    plt.close(fig)
