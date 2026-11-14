#!/usr/bin/env python3
"""Render the Fig. 12 same-bearing placement schematic from campaign.json."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_matplotlib")

import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--out-prefix", type=Path, required=True)
    args = parser.parse_args()

    campaign = json.loads(args.campaign.read_text(encoding="utf-8"))
    geometry = campaign["fig12_geometry"]
    bearing_deg = float(geometry["bearing_deg"])
    bearing = np.deg2rad(bearing_deg)
    direction = np.asarray([np.cos(bearing), np.sin(bearing)])
    perpendicular = np.asarray([-np.sin(bearing), np.cos(bearing)])
    spacing = float(geometry["rx_antenna_spacing_m"])
    node1_distance = float(geometry["node1_distance_m"])
    node2_distances = [float(value) for value in geometry["node2_distances_m"]]

    rx0 = -0.5 * spacing * perpendicular
    rx1 = 0.5 * spacing * perpendicular
    node1 = node1_distance * direction
    node2 = np.asarray([distance * direction for distance in node2_distances])

    fig, axis = plt.subplots(figsize=(8.2, 3.5))
    maximum = max([node1_distance, *node2_distances])
    axis.plot([0, maximum * direction[0]], [0, maximum * direction[1]], "--", color="0.55", lw=1)
    axis.plot([rx0[0], rx1[0]], [rx0[1], rx1[1]], color="black", lw=1.5)
    axis.scatter([rx0[0], rx1[0]], [rx0[1], rx1[1]], marker="^", s=90, color="black", label="Gateway RX antennas")
    axis.scatter([node1[0]], [node1[1]], marker="s", s=80, color="#D55E00", label="Node01 fixed")
    axis.scatter(node2[:, 0], node2[:, 1], marker="o", s=55, color="#0072B2", label="Node02 positions")
    axis.annotate(f"Node01\n{node1_distance:g} m", node1, xytext=(0, 12), textcoords="offset points", ha="center")

    # The requested 2/5/10/20 cm positions are too close to label legibly on
    # the room-scale drawing.  Keep the main panel geometrically true and put
    # the exact relative positions in a compact centimetre-scale inset.
    separations_cm = [
        100.0 * (distance - node1_distance) for distance in node2_distances
    ]
    inset = axis.inset_axes([0.31, 0.10, 0.58, 0.23])
    inset.axhline(0.0, color="0.65", lw=0.8)
    inset.scatter([0.0], [0.0], marker="s", s=34, color="#D55E00", zorder=3)
    inset.scatter(
        separations_cm,
        np.zeros(len(separations_cm)),
        marker="o",
        s=28,
        color="#0072B2",
        zorder=3,
    )
    inset.annotate(
        "Node01",
        (0.0, 0.0),
        xytext=(0, -12),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=7,
    )
    for index, separation_cm in enumerate(separations_cm, start=1):
        offset = 7 if index % 2 else -12
        vertical_alignment = "bottom" if index % 2 else "top"
        inset.annotate(
            f"P{index}",
            (separation_cm, 0.0),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va=vertical_alignment,
            fontsize=7,
        )
    inset.set_xlim(-1.5, max(separations_cm) + 2.0)
    inset.set_ylim(-0.7, 0.7)
    inset.set_yticks([])
    inset.set_xticks([0.0, *separations_cm])
    inset.set_xticklabels(
        ["0", *[f"{value:g}" for value in separations_cm]],
        fontsize=7,
    )
    inset.set_xlabel("Node02 separation from Node01 (cm)", fontsize=7, labelpad=1)
    inset.tick_params(axis="x", length=2, pad=1)
    inset.set_facecolor("white")
    axis.annotate(
        f"RX spacing {spacing:g} m",
        0.5 * (rx0 + rx1),
        xytext=(8, 0),
        textcoords="offset points",
        va="center",
        fontsize=8,
    )
    axis.set_aspect("equal", adjustable="datalim")
    axis.set_xlabel("Room x coordinate (m)")
    axis.set_ylabel("Room y coordinate (m)")
    axis.set_title(f"Same-bearing indoor layout (nominal bearing {bearing_deg:g}°)")
    axis.grid(alpha=0.2)
    axis.legend(loc="best", fontsize=8)
    fig.tight_layout()
    args.out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".pdf", ".svg", ".png"):
        fig.savefig(args.out_prefix.with_suffix(suffix), dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(args.out_prefix.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
