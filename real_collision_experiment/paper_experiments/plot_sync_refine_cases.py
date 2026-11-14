#!/usr/bin/env python3
"""Plot real SP-core failures rescued by bounded sync-refine.

The input is a normal receiver report containing per-candidate method rows.
The script does not rerun detection or decoding; it only selects candidates for
which SP-core fails PHY CRC while SP+sync-refine closes PHY CRC.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_matplotlib")

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


def method_row(candidate: dict, name: str) -> dict | None:
    return next(
        (row for row in candidate.get("methods", []) if row.get("method") == name),
        None,
    )


def phy_ok(row: dict | None) -> bool:
    return bool(row and row.get("phy", {}).get("phy_crc_ok", False))


def payload_bytes(hex_value: str | None) -> bytes | None:
    if not hex_value:
        return None
    try:
        return bytes.fromhex(hex_value)
    except ValueError:
        return None


def expected_payload(core: dict, refined: dict) -> bytes | None:
    app = refined.get("application", {})
    manifest_hex = app.get("manifest_expected_payload_hex")
    expected = payload_bytes(manifest_hex)
    if expected is not None:
        return expected
    if phy_ok(refined):
        return payload_bytes(refined.get("phy", {}).get("payload_hex"))
    return None


def byte_errors(decoded: bytes | None, expected: bytes | None) -> int | None:
    if decoded is None or expected is None:
        return None
    n = max(len(decoded), len(expected))
    errors = 0
    for index in range(n):
        left = decoded[index] if index < len(decoded) else None
        right = expected[index] if index < len(expected) else None
        errors += int(left != right)
    return errors


def collect_cases(report_path: Path) -> list[dict]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for candidate in report.get("candidates", []):
        core = method_row(candidate, "sp_core")
        refined = method_row(candidate, "sp_sync_refine")
        if not core or not refined:
            continue
        if phy_ok(core) or not phy_ok(refined):
            continue
        expected = expected_payload(core, refined)
        core_payload = payload_bytes(core.get("phy", {}).get("payload_hex"))
        refined_payload = payload_bytes(refined.get("phy", {}).get("payload_hex"))
        decoded = refined.get("application", {}).get("decoded") or {}
        rows.append(
            {
                "report": str(report_path),
                "candidate_id": int(candidate.get("candidate_id", -1)),
                "packet_index": int(candidate.get("packet_index", -1)),
                "start_time_s": float(candidate.get("start_time_s", math.nan)),
                "node_id": decoded.get("node_id", ""),
                "sequence": decoded.get("sequence", ""),
                "lambda_sp": float(refined.get("lambda_sp", candidate.get("lambda_sp", math.nan))),
                "L_u": float(candidate.get("L_u", math.nan)),
                "U_max_sp": float(candidate.get("U_max_sp", math.nan)),
                "theta_total": float(candidate.get("theta_total", math.nan)),
                "sync_trials": int(refined.get("synchronization_trials", 1)),
                "start_delta_samples": float(
                    refined.get("sync_refine_start_delta_samples", 0.0)
                ),
                "cfo_delta_bins": float(refined.get("sync_refine_cfo_delta_bins", 0.0)),
                "core_corrected_codewords": int(
                    core.get("phy", {}).get("corrected_codewords", 0)
                ),
                "core_uncorrected_codewords": int(
                    core.get("phy", {}).get("uncorrected_codewords", 0)
                ),
                "refined_corrected_codewords": int(
                    refined.get("phy", {}).get("corrected_codewords", 0)
                ),
                "refined_uncorrected_codewords": int(
                    refined.get("phy", {}).get("uncorrected_codewords", 0)
                ),
                "core_payload_byte_errors": byte_errors(core_payload, expected),
                "refined_payload_byte_errors": byte_errors(refined_payload, expected),
                "_candidate": candidate,
                "_core": core,
                "_refined": refined,
                "_expected_payload": expected,
                "_core_payload": core_payload,
                "_refined_payload": refined_payload,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "report",
        "candidate_id",
        "packet_index",
        "start_time_s",
        "node_id",
        "sequence",
        "lambda_sp",
        "L_u",
        "U_max_sp",
        "theta_total",
        "sync_trials",
        "start_delta_samples",
        "cfo_delta_bins",
        "core_corrected_codewords",
        "core_uncorrected_codewords",
        "refined_corrected_codewords",
        "refined_uncorrected_codewords",
        "core_payload_byte_errors",
        "refined_payload_byte_errors",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def mismatch_vector(decoded: bytes | None, expected: bytes | None) -> list[int]:
    if decoded is None or expected is None:
        return []
    n = max(len(decoded), len(expected))
    out = []
    for index in range(n):
        left = decoded[index] if index < len(decoded) else None
        right = expected[index] if index < len(expected) else None
        out.append(int(left != right))
    return out


def pick_case(rows: list[dict], case_index: int | None) -> dict:
    if case_index is not None:
        for row in rows:
            if int(row["candidate_id"]) == int(case_index):
                return row
        raise SystemExit(f"candidate_id={case_index} is not a rescued case")
    return sorted(
        rows,
        key=lambda row: (
            -int(row.get("core_payload_byte_errors") or 0),
            abs(float(row["start_delta_samples"])),
            int(row["sync_trials"]),
            int(row["candidate_id"]),
        ),
    )[0]


def plot_cases(rows: list[dict], selected: dict, out_pdf: Path) -> None:
    fig = plt.figure(figsize=(11.8, 6.9))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.05, 1.0])
    axis = fig.add_subplot(grid[0, 0])

    core_mismatch = mismatch_vector(
        selected["_core_payload"], selected["_expected_payload"]
    )
    refined_mismatch = mismatch_vector(
        selected["_refined_payload"], selected["_expected_payload"]
    )
    matrix = np.asarray([core_mismatch, refined_mismatch], dtype=np.float64)
    cmap = mcolors.ListedColormap(["#2ca25f", "#de2d26"])
    norm = mcolors.BoundaryNorm([-0.5, 0.5, 1.5], cmap.N)
    axis.imshow(matrix, aspect="auto", cmap=cmap, norm=norm)
    axis.set_yticks([0, 1], ["SP-core", "SP+sync-refine"])
    axis.set_xticks(range(matrix.shape[1]))
    axis.set_xlabel("payload byte index")
    axis.set_title(
        (
            f"One rescued packet: candidate {selected['candidate_id']}, "
            f"node {selected['node_id']} seq {selected['sequence']}"
        )
    )
    axis.text(
        0.01,
        -0.30,
        (
            f"green=matches expected payload, red=mismatch; "
            f"start delta={selected['start_delta_samples']:+g} samples, "
            f"CFO delta={selected['cfo_delta_bins']:+g} bins, "
            f"trials={selected['sync_trials']}"
        ),
        transform=axis.transAxes,
        fontsize=8,
        va="top",
    )

    axis = fig.add_subplot(grid[0, 1])
    start = np.asarray([row["start_delta_samples"] for row in rows], dtype=float)
    cfo = np.asarray([row["cfo_delta_bins"] for row in rows], dtype=float)
    trials = np.asarray([row["sync_trials"] for row in rows], dtype=float)
    scatter = axis.scatter(
        start,
        cfo,
        c=trials,
        s=70,
        cmap="viridis",
        edgecolor="black",
        linewidth=0.35,
        alpha=0.88,
    )
    axis.scatter(
        [selected["start_delta_samples"]],
        [selected["cfo_delta_bins"]],
        marker="*",
        s=190,
        color="#fdae61",
        edgecolor="black",
        linewidth=0.55,
        label="shown packet",
        zorder=4,
    )
    axis.axhline(0.0, color="0.5", linestyle=":", linewidth=1.0)
    axis.axvline(0.0, color="0.5", linestyle=":", linewidth=1.0)
    axis.set_xlabel("selected start correction (samples)")
    axis.set_ylabel("selected CFO correction (bins)")
    axis.set_title("CRC-closing bounded search points")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8, loc="best")
    fig.colorbar(scatter, ax=axis, label="sync trials")

    axis = fig.add_subplot(grid[1, 0])
    x = np.arange(len(rows))
    core_errors = np.asarray(
        [row.get("core_payload_byte_errors") or 0 for row in rows], dtype=float
    )
    refined_errors = np.asarray(
        [row.get("refined_payload_byte_errors") or 0 for row in rows], dtype=float
    )
    order = np.argsort(core_errors)[::-1]
    axis.plot(x, core_errors[order], marker="o", label="SP-core")
    axis.plot(x, refined_errors[order], marker="o", label="SP+sync-refine")
    axis.set_xlabel("rescued packet index, sorted by core byte errors")
    axis.set_ylabel("payload byte errors vs expected")
    axis.set_title("Payload defects removed by refinement")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)

    axis = fig.add_subplot(grid[1, 1])
    labels = ["corrected\ncodewords", "uncorrected\ncodewords", "byte\nerrors"]
    core_means = [
        float(np.mean([row["core_corrected_codewords"] for row in rows])),
        float(np.mean([row["core_uncorrected_codewords"] for row in rows])),
        float(np.mean(core_errors)),
    ]
    refined_means = [
        float(np.mean([row["refined_corrected_codewords"] for row in rows])),
        float(np.mean([row["refined_uncorrected_codewords"] for row in rows])),
        float(np.mean(refined_errors)),
    ]
    width = 0.36
    xpos = np.arange(len(labels))
    axis.bar(xpos - width / 2.0, core_means, width, label="SP-core", color="#de2d26")
    axis.bar(
        xpos + width / 2.0,
        refined_means,
        width,
        label="SP+sync-refine",
        color="#2ca25f",
    )
    axis.set_xticks(xpos, labels)
    axis.set_ylabel("mean over rescued packets")
    axis.set_title(f"Aggregate rescued cases: n={len(rows)}")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8)

    fig.suptitle(
        "D2: SP-core failures rescued by bounded start/CFO refinement",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(out_pdf, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--case-candidate-id",
        type=int,
        default=None,
        help="rescued candidate_id to highlight; default picks a visible case",
    )
    parser.add_argument(
        "--max-sync-trials",
        type=int,
        default=32,
        help="only include rescued packets that satisfy the production trial cap",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    all_rows = collect_cases(args.report)
    rows = [
        row for row in all_rows if int(row["sync_trials"]) <= int(args.max_sync_trials)
    ]
    if not rows:
        raise SystemExit(
            "no SP-core failure rescued by SP+sync-refine found inside "
            f"max_sync_trials={args.max_sync_trials}"
        )
    selected = pick_case(rows, args.case_candidate_id)
    write_csv(args.out_dir / "d2_sync_refine_rescued_cases.csv", rows)
    plot_cases(rows, selected, args.out_dir / "d2_sync_refine_rescued_cases.pdf")
    summary = {
        "report": str(args.report),
        "rescued_count": len(rows),
        "rescued_count_before_trial_cap": len(all_rows),
        "max_sync_trials": int(args.max_sync_trials),
        "excluded_by_trial_cap": len(all_rows) - len(rows),
        "highlight_candidate_id": int(selected["candidate_id"]),
        "mean_start_delta_samples": float(np.mean([r["start_delta_samples"] for r in rows])),
        "mean_cfo_delta_bins": float(np.mean([r["cfo_delta_bins"] for r in rows])),
        "mean_sync_trials": float(np.mean([r["sync_trials"] for r in rows])),
    }
    (args.out_dir / "d2_sync_refine_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"rescued={len(rows)} excluded_by_trial_cap={len(all_rows) - len(rows)} "
        f"wrote {args.out_dir.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
