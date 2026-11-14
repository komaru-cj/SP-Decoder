#!/usr/bin/env python3
"""Merge independently calculated SP/eta collision-heatmap cells.

The waveform evaluator is intentionally limited to one SNR/SIR cell per
process so a 300-pair real-IQ computation remains restartable.  Every cell is
seeded identically, hence it uses the same sampled target/interferer pairs.
This utility verifies that pairing contract and emits the normal heatmap CSV
and JSON files consumed by the paper-native renderer.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def condition_rows(
    rows: list[dict[str, str]], sir_values: list[float], snr_values: list[float], *, error_key: str
) -> list[dict]:
    cells: list[dict] = []
    for sir_db in sir_values:
        for snr_db in snr_values:
            selected = [
                row
                for row in rows
                if float(row["sir_db"]) == sir_db and float(row["snr_db"]) == snr_db
            ]
            if not selected:
                raise ValueError(f"missing cell SIR={sir_db:g}, SNR={snr_db:g}")
            trials = {int(row["trial"]) for row in selected}
            if len(trials) != len(selected):
                raise ValueError(f"duplicate trial in SIR={sir_db:g}, SNR={snr_db:g}")
            errors = sum(int(row[error_key]) for row in selected)
            symbols = sum(int(row["symbol_count"]) for row in selected)
            cells.append(
                {
                    "sir_db": sir_db,
                    "snr_db": snr_db,
                    "ser": errors / max(symbols, 1),
                    "trial_count": len(selected),
                }
            )
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    cell_dirs = sorted(path for path in args.cell_root.iterdir() if path.is_dir())
    if not cell_dirs:
        raise FileNotFoundError(f"no cell directories in {args.cell_root}")
    sp_rows: list[dict[str, str]] = []
    eta_rows: list[dict[str, str]] = []
    sp_summaries: list[dict] = []
    eta_summaries: list[dict] = []
    for cell_dir in cell_dirs:
        sp_path = cell_dir / "air_collision_ser_heatmap.csv"
        eta_path = cell_dir / "air_collision_eta_rank_heatmap.csv"
        sp_summary_path = cell_dir / "air_collision_ser_heatmap_summary.json"
        eta_summary_path = cell_dir / "air_collision_eta_rank_heatmap_summary.json"
        if not all(path.exists() for path in (sp_path, eta_path, sp_summary_path, eta_summary_path)):
            raise FileNotFoundError(f"incomplete heatmap cell: {cell_dir}")
        sp_rows.extend(read_csv(sp_path))
        eta_rows.extend(read_csv(eta_path))
        sp_summaries.append(read_json(sp_summary_path))
        eta_summaries.append(read_json(eta_summary_path))

    reference = sp_summaries[0]
    eta_reference = eta_summaries[0]
    pairing_keys = (
        "target_packet_indices",
        "interferer_packet_indices",
        "sampled_target_interferer_direction_separation_deg",
        "offset_symbols",
    )
    for summary in sp_summaries[1:]:
        for key in pairing_keys:
            if summary[key] != reference[key]:
                raise ValueError(f"inconsistent pairing metadata: {key}")

    sir_values = sorted({float(row["sir_db"]) for row in sp_rows})
    snr_values = sorted({float(row["snr_db"]) for row in sp_rows})
    sp_cells = condition_rows(
        sp_rows, sir_values, snr_values, error_key="signed_symbol_errors"
    )
    eta_cells = condition_rows(
        eta_rows, sir_values, snr_values, error_key="eta_rank_symbol_errors"
    )
    pair_trials = int(sp_cells[0]["trial_count"])
    if any(int(cell["trial_count"]) != pair_trials for cell in sp_cells + eta_cells):
        raise ValueError("cells do not share one complete 300-pair trial set")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "air_collision_ser_heatmap.csv", sp_rows)
    write_csv(args.out_dir / "air_collision_eta_rank_heatmap.csv", eta_rows)
    sp_result = {
        **reference,
        "snr_db": snr_values,
        "sir_db": sir_values,
        "random_collision_groups": pair_trials,
        "condition_evaluations": pair_trials * len(sir_values) * len(snr_values),
        "random_collision_groups_per_cell": {
            f"SIR={cell['sir_db']:g},SNR={cell['snr_db']:g}": int(cell["trial_count"])
            for cell in sp_cells
        },
        "cells": sp_cells,
        "merged_from_cell_directories": [str(path.resolve()) for path in cell_dirs],
    }
    eta_result = {
        **eta_reference,
        "snr_db": snr_values,
        "sir_db": sir_values,
        "random_collision_groups": pair_trials,
        "condition_evaluations": pair_trials * len(sir_values) * len(snr_values),
        "cells": eta_cells,
        "merged_from_cell_directories": [str(path.resolve()) for path in cell_dirs],
    }
    write_json(args.out_dir / "air_collision_ser_heatmap_summary.json", sp_result)
    write_json(args.out_dir / "air_collision_eta_rank_heatmap_summary.json", eta_result)
    write_json(
        args.out_dir / "experiment_manifest.json",
        {
            "schema": "sp_eta_rank_collision_heatmap_merged_v1",
            "random_collision_groups_per_cell": pair_trials,
            "sp_summary": "air_collision_ser_heatmap_summary.json",
            "eta_summary": "air_collision_eta_rank_heatmap_summary.json",
            "source_cells": [str(path.resolve()) for path in cell_dirs],
        },
    )
    print(
        json.dumps(
            {
                "out_dir": str(args.out_dir.resolve()),
                "cells": len(sp_cells),
                "pair_trials_per_cell": pair_trials,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
