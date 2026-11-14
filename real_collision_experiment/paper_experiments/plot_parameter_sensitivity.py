#!/usr/bin/env python3
"""Aggregate fixed-scene SP parameter scans into a compact SER bar chart."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows: list[dict] = []
    for path in sorted(args.input_root.glob("*/candidate_winner_real_trace_metrics.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        scene_rows = payload["scenes"]
        rows.append(
            {
                "gamma": float(payload["sp_gamma"]),
                "lambda_max": float(payload["sp_lambda_max"]),
                "scene_count": int(payload["scene_count"]),
                "mean_ser": float(payload["finite_policy"]["mean_ser"]),
                "zero_ser_packet_fraction": float(
                    np.mean([float(row["finite_ser"]) == 0.0 for row in scene_rows])
                ),
                "mean_selected_lambda": float(
                    np.mean([float(row["finite_lambda"]) for row in scene_rows])
                ),
            }
        )
    rows.sort(key=lambda row: (row["gamma"], row["lambda_max"]))
    if len(rows) != 5:
        raise ValueError(f"expected exactly five parameter groups, found {len(rows)}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "parameter_sensitivity_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    labels = [rf"$({row['gamma']:g},{row['lambda_max']:g})$" for row in rows]
    values = [row["mean_ser"] for row in rows]
    colors = ["#9aa0a6", "#9aa0a6", "#1b9e77", "#9aa0a6", "#9aa0a6"]
    figure, axis = plt.subplots(figsize=(6.4, 3.8), constrained_layout=True)
    bars = axis.bar(np.arange(len(rows)), values, color=colors, width=0.66)
    axis.set_xticks(np.arange(len(rows)), labels)
    axis.set_xlabel(r"global constants $(\gamma,\lambda_{\max})$")
    axis.set_ylabel("mean SER")
    axis.set_ylim(0.0, max(values) * 1.28)
    axis.grid(axis="y", color="#d9d9d9", linewidth=0.8)
    axis.set_axisbelow(True)
    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2.0,
            value + 0.006,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    axis.text(
        2,
        max(values) * 1.19,
        "default",
        ha="center",
        va="bottom",
        color="#1b9e77",
        fontsize=10,
    )
    for suffix in ("png", "pdf"):
        figure.savefig(args.out_dir / f"parameter_sensitivity_mean_ser.{suffix}", dpi=240)
    plt.close(figure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
