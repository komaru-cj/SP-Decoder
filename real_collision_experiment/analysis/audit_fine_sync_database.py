#!/usr/bin/env python3
"""Verify that an anonymous fine-sync database contains certified physical tracks."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_fine_sync_database import (  # noqa: E402
    ANALYSIS_DURATION_S,
    ANONYMOUS_FINE_SYNC_SCHEMA,
    MIN_FRAME_STRUCTURE_SCORE,
    MIN_PREAMBLE_RATIO,
    MIN_SFD_CONFIDENCE,
    MIN_SYNC_CONFIDENCE,
    same_physical_candidate,
)
from formal_window import formal_analysis_duration_s  # noqa: E402


def audit(database: dict) -> list[str]:
    """Return every violated anonymous-database invariant; an empty list means pass."""

    errors: list[str] = []
    if database.get("schema") != ANONYMOUS_FINE_SYNC_SCHEMA:
        errors.append(
            f"schema is {database.get('schema')!r}, expected {ANONYMOUS_FINE_SYNC_SCHEMA}"
        )
    window = database.get("window", {})
    expected_duration_s = formal_analysis_duration_s(str(database.get("figure", "")))
    if not math.isclose(
        float(window.get("duration_s", 0.0)),
        expected_duration_s,
        abs_tol=1e-9,
    ):
        errors.append(
            f"window.duration_s is {window.get('duration_s')!r}, "
            f"expected {expected_duration_s}"
        )

    discovery = database.get("candidate_discovery", {})
    expected_discovery = {
        "scope": "global_full_window",
        "manifest_schedule_exposed_to_detector": False,
        "node_timing_calibration": False,
        "planned_start_search_windows": False,
        "score_truncation": False,
    }
    for field, expected in expected_discovery.items():
        if discovery.get(field) != expected:
            errors.append(
                f"candidate_discovery.{field} is {discovery.get(field)!r}, "
                f"expected {expected!r}"
            )
    overflow_policy = discovery.get("candidate_overflow_policy")
    if overflow_policy not in {
        "fail_closed_without_truncation",
        "retain_excess_candidates_without_truncation",
    }:
        errors.append(
            f"candidate_discovery.candidate_overflow_policy is {overflow_policy!r}"
        )
    high_recall_admission = (
        discovery.get("candidate_admission_policy") == "sfd_anchored_high_recall"
    )

    rate = float(database.get("sample_rate_hz", 0.0))
    bandwidth = float(database.get("bandwidth_hz", 0.0))
    sf = int(database.get("spreading_factor", 0))
    if rate <= 0.0 or bandwidth <= 0.0 or sf <= 0:
        errors.append("missing valid sample_rate_hz/bandwidth_hz/spreading_factor")
        return errors
    packets = database.get("packets", [])
    if not isinstance(packets, list):
        errors.append("database packets is not a list")
        return errors
    forbidden_fragments = (
        "node_id",
        "sequence",
        "planned",
        "expected_start",
        "node_offset",
        "association",
    )
    for index, row in enumerate(packets):
        label = f"packet[{index}]"
        forbidden = sorted(
            key
            for key in row
            if any(fragment in str(key).lower() for fragment in forbidden_fragments)
        )
        if forbidden:
            errors.append(f"{label} contains forbidden prior fields {forbidden}")
        if row.get("structure_certified"):
            for field, threshold in (
                ("preamble_ratio", MIN_PREAMBLE_RATIO),
                ("sync_confidence", MIN_SYNC_CONFIDENCE),
                ("sfd_confidence", MIN_SFD_CONFIDENCE),
                ("structure_score", MIN_FRAME_STRUCTURE_SCORE),
            ):
                value = float(row.get(field, float("nan")))
                if not math.isfinite(value) or value < threshold:
                    errors.append(f"{label} {field}={value!r} below {threshold}")
        elif high_recall_admission:
            if row.get("candidate_evidence") != "plausible_preamble_sfd_anchor":
                errors.append(f"{label} has no high-recall SFD-anchor evidence")
            if float(row.get("sfd_anchor_score", 0.0)) <= 0.0:
                errors.append(f"{label} has no positive SFD-anchor score")
            for field in ("preamble_ratio", "sync_confidence", "sfd_confidence", "structure_score"):
                if not math.isfinite(float(row.get(field, float("nan")))):
                    errors.append(f"{label} {field} is not finite")
        else:
            errors.append(f"{label} is not structurally certified")
    if int(database.get("detected_physical_candidate_count", -1)) != len(packets):
        errors.append(
            "detected_physical_candidate_count does not equal the number of packets"
        )
    scheduled_count = int(
        database.get(
            "scheduled_packet_count_reference",
            database.get("scheduled_packet_upper_bound", -1),
        )
    )
    if scheduled_count < 0:
        errors.append(
            "missing valid scheduled_packet_count_reference"
        )
    n_symbol = int(round((2**sf) * rate / bandwidth))
    for left in range(len(packets)):
        for right in range(left + 1, len(packets)):
            if same_physical_candidate(packets[left], packets[right], n_symbol):
                errors.append(
                    f"packet[{left}] and packet[{right}] remain strict physical aliases"
                )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = json.loads(args.database.read_text(encoding="utf-8"))
    errors = audit(database)
    if errors:
        print(f"FINE_SYNC_DATABASE_AUDIT_FAILED errors={len(errors)}")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "FINE_SYNC_DATABASE_AUDIT_OK "
        f"run={database.get('run_id')} detected_physical="
        f"{database.get('detected_physical_candidate_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
