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


def audit(database: dict) -> list[str]:
    """Return every violated anonymous-database invariant; an empty list means pass."""

    errors: list[str] = []
    if database.get("schema") != ANONYMOUS_FINE_SYNC_SCHEMA:
        errors.append(
            f"schema is {database.get('schema')!r}, expected {ANONYMOUS_FINE_SYNC_SCHEMA}"
        )
    window = database.get("window", {})
    if not math.isclose(
        float(window.get("duration_s", 0.0)),
        ANALYSIS_DURATION_S,
        abs_tol=1e-9,
    ):
        errors.append(
            f"window.duration_s is {window.get('duration_s')!r}, "
            f"expected {ANALYSIS_DURATION_S}"
        )

    discovery = database.get("candidate_discovery", {})
    expected_discovery = {
        "scope": "global_full_window",
        "manifest_schedule_exposed_to_detector": False,
        "node_timing_calibration": False,
        "planned_start_search_windows": False,
        "score_truncation": False,
        "candidate_overflow_policy": "fail_closed_without_truncation",
    }
    for field, expected in expected_discovery.items():
        if discovery.get(field) != expected:
            errors.append(
                f"candidate_discovery.{field} is {discovery.get(field)!r}, "
                f"expected {expected!r}"
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
        if not row.get("structure_certified"):
            errors.append(f"{label} is not structurally certified")
        for field, threshold in (
            ("preamble_ratio", MIN_PREAMBLE_RATIO),
            ("sync_confidence", MIN_SYNC_CONFIDENCE),
            ("sfd_confidence", MIN_SFD_CONFIDENCE),
            ("structure_score", MIN_FRAME_STRUCTURE_SCORE),
        ):
            value = float(row.get(field, float("nan")))
            if not math.isfinite(value) or value < threshold:
                errors.append(f"{label} {field}={value!r} below {threshold}")
    if int(database.get("detected_physical_candidate_count", -1)) != len(packets):
        errors.append(
            "detected_physical_candidate_count does not equal the number of packets"
        )
    upper_bound = int(database.get("scheduled_packet_upper_bound", -1))
    if upper_bound < 0 or len(packets) > upper_bound:
        errors.append(
            f"candidate count {len(packets)} exceeds invalid/declared upper bound "
            f"{upper_bound}"
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
