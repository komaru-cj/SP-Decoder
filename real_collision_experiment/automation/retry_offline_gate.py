#!/usr/bin/env python3
"""Retry only the one-time link gate from an already completed sequence-1 IQ file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from campaign_common import load_campaign, run_name  # noqa: E402
from offline_receiver_campaign import run_one_time_gate  # noqa: E402
from receiver_campaign_server import validate_capture  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "real_collision_experiment/runs")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--sample-rate", type=float, default=750_000.0)
    parser.add_argument("--gate-capture-start-seconds", type=float, default=None)
    parser.add_argument("--gate-capture-seconds", type=float, default=3.0)
    args = parser.parse_args()
    _, runs, _ = load_campaign(args.campaign, start_sequence=1, end_sequence=1)
    run = runs[0]
    args.repo_root = args.repo_root.resolve()
    args.runs_root = args.runs_root.resolve()
    args.campaign_id = "fig9_10_fig12_phy5_d05_d075_r1_20s"
    iq_path = args.runs_root / run_name(run) / f"{run_name(run)}.sc16"
    metadata = validate_capture(iq_path)
    print(
        f"REUSING_COMPLETE_CAPTURE {iq_path} samples={metadata['samples_per_channel']} "
        f"bytes={metadata['file_bytes']}",
        flush=True,
    )
    run_one_time_gate(args, run, iq_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
