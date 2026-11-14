#!/usr/bin/env python3
"""Merge restartable adaptive-SP and candidate-eta heatmap cells."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cells(
    rows: list[dict[str, str]],
    sir_values: list[float],
    snr_values: list[float],
    error_key: str,
    *,
    candidate: bool,
) -> list[dict]:
    result: list[dict] = []
    for sir_db in sir_values:
        for snr_db in snr_values:
            selected = [
                row for row in rows
                if float(row["sir_db"]) == sir_db and float(row["snr_db"]) == snr_db
            ]
            if not selected:
                raise ValueError(f"missing SIR={sir_db:g}, SNR={snr_db:g}")
            trials = [int(row["trial"]) for row in selected]
            if len(set(trials)) != len(trials):
                raise ValueError(f"duplicate trial in SIR={sir_db:g}, SNR={snr_db:g}")
            symbols = sum(int(row["symbol_count"]) for row in selected)
            item = {
                "sir_db": sir_db,
                "snr_db": snr_db,
                "ser": sum(int(row[error_key]) for row in selected) / max(symbols, 1),
                "trial_count": len(selected),
            }
            if candidate:
                item["candidate_recall"] = (
                    sum(int(row["truth_in_candidate_count"]) for row in selected)
                    / max(symbols, 1)
                )
            result.append(item)
    return result


def check_pairing(reference: dict, value: dict) -> None:
    for key in (
        "target_packet_indices",
        "interferer_packet_indices",
        "sampled_target_interferer_direction_separation_deg",
        "offset_symbols",
    ):
        if value[key] != reference[key]:
            raise ValueError(f"inconsistent pairing metadata: {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    directories = sorted(path for path in args.cell_root.iterdir() if path.is_dir())
    if not directories:
        raise FileNotFoundError(f"no cell directories in {args.cell_root}")

    sp_rows: list[dict[str, str]] = []
    sp_summaries: list[dict] = []
    sp_candidate_rows_by_k: dict[int, list[dict[str, str]]] = {}
    sp_candidate_summaries_by_k: dict[int, list[dict]] = {}
    eta_rows_by_k: dict[int, list[dict[str, str]]] = {}
    eta_summaries_by_k: dict[int, list[dict]] = {}
    pattern = re.compile(r"air_collision_eta_rank_top(\d+)_heatmap\.csv")
    sp_pattern = re.compile(r"air_collision_sp_top(\d+)_heatmap\.csv")
    for directory in directories:
        sp_rows.extend(read_csv(directory / "air_collision_ser_heatmap.csv"))
        sp_summaries.append(read_json(directory / "air_collision_ser_heatmap_summary.json"))
        found_sp = set()
        for path in directory.glob("air_collision_sp_top*_heatmap.csv"):
            match = sp_pattern.fullmatch(path.name)
            if match is None:
                continue
            count = int(match.group(1))
            sp_candidate_rows_by_k.setdefault(count, []).extend(read_csv(path))
            sp_candidate_summaries_by_k.setdefault(count, []).append(
                read_json(directory / f"{path.stem}_summary.json")
            )
            found_sp.add(count)
        if not found_sp:
            raise FileNotFoundError(f"no candidate-SP cells in {directory}")
        found = set()
        for path in directory.glob("air_collision_eta_rank_top*_heatmap.csv"):
            match = pattern.fullmatch(path.name)
            if match is None:
                continue
            count = int(match.group(1))
            eta_rows_by_k.setdefault(count, []).extend(read_csv(path))
            eta_summaries_by_k.setdefault(count, []).append(
                read_json(directory / f"{path.stem}_summary.json")
            )
            found.add(count)
        if not found:
            raise FileNotFoundError(f"no candidate-eta cells in {directory}")

    reference = sp_summaries[0]
    for summary in sp_summaries[1:]:
        check_pairing(reference, summary)
    sir_values = sorted({float(row["sir_db"]) for row in sp_rows})
    snr_values = sorted({float(row["snr_db"]) for row in sp_rows})
    sp_cells = cells(
        sp_rows, sir_values, snr_values, "signed_symbol_errors", candidate=False
    )
    trial_count = int(sp_cells[0]["trial_count"])
    if any(int(cell["trial_count"]) != trial_count for cell in sp_cells):
        raise ValueError("SP cells have inconsistent trial counts")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "air_collision_ser_heatmap.csv", sp_rows)
    sp_result = {
        **reference,
        "snr_db": snr_values,
        "sir_db": sir_values,
        "random_collision_groups": trial_count,
        "condition_evaluations": trial_count * len(sir_values) * len(snr_values),
        "random_collision_groups_per_cell": {
            f"SIR={cell['sir_db']:g},SNR={cell['snr_db']:g}": int(cell["trial_count"])
            for cell in sp_cells
        },
        "cells": sp_cells,
        "merged_from_cell_directories": [str(path.resolve()) for path in directories],
    }
    write_json(args.out_dir / "air_collision_ser_heatmap_summary.json", sp_result)

    for count, rows in sorted(sp_candidate_rows_by_k.items()):
        summaries = sp_candidate_summaries_by_k[count]
        for summary in summaries:
            check_pairing(reference, summary)
        candidate_cells = cells(
            rows, sir_values, snr_values, "sp_candidate_symbol_errors", candidate=True
        )
        if any(int(cell["trial_count"]) != trial_count for cell in candidate_cells):
            raise ValueError(f"candidate SP K={count} has inconsistent trial counts")
        stem = f"air_collision_sp_top{count}_heatmap"
        write_csv(args.out_dir / f"{stem}.csv", rows)
        result = {
            **summaries[0],
            "snr_db": snr_values,
            "sir_db": sir_values,
            "random_collision_groups": trial_count,
            "condition_evaluations": trial_count * len(sir_values) * len(snr_values),
            "cells": candidate_cells,
            "merged_from_cell_directories": [
                str(path.resolve()) for path in directories
            ],
        }
        write_json(args.out_dir / f"{stem}_summary.json", result)

    for count, rows in sorted(eta_rows_by_k.items()):
        summaries = eta_summaries_by_k[count]
        for summary in summaries:
            check_pairing(reference, summary)
        eta_cells = cells(
            rows, sir_values, snr_values, "eta_rank_symbol_errors", candidate=True
        )
        if any(int(cell["trial_count"]) != trial_count for cell in eta_cells):
            raise ValueError(f"eta K={count} has inconsistent trial counts")
        stem = f"air_collision_eta_rank_top{count}_heatmap"
        write_csv(args.out_dir / f"{stem}.csv", rows)
        result = {
            **summaries[0],
            "snr_db": snr_values,
            "sir_db": sir_values,
            "random_collision_groups": trial_count,
            "condition_evaluations": trial_count * len(sir_values) * len(snr_values),
            "cells": eta_cells,
            "merged_from_cell_directories": [
                str(path.resolve()) for path in directories
            ],
        }
        write_json(args.out_dir / f"{stem}_summary.json", result)

    write_json(
        args.out_dir / "experiment_manifest.json",
        {
            "schema": "adaptive_lambda_sp_eta_candidate_heatmap_merged_v1",
            "random_collision_groups_per_cell": trial_count,
            "sp_candidate_counts": sorted(sp_candidate_rows_by_k),
            "eta_candidate_counts": sorted(eta_rows_by_k),
            "source_cells": [str(path.resolve()) for path in directories],
        },
    )
    print(json.dumps({"out_dir": str(args.out_dir.resolve()), "cells": len(sp_cells), "pair_trials_per_cell": trial_count, "eta_candidate_counts": sorted(eta_rows_by_k)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
