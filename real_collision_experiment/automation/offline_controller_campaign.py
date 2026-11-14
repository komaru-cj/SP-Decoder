#!/usr/bin/env python3
"""Run the control B210 on fixed slots without contacting the RX computer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from campaign_common import load_campaign, run_name  # noqa: E402
from controller_campaign_client import controller_command  # noqa: E402
from offline_schedule import build_schedule, placement_message, wait_until  # noqa: E402


def offline_controller_command(args: argparse.Namespace, run: dict) -> list[str]:
    command = controller_command(args, run)
    command.extend(
        [
            "--pre-config-delay-s",
            f"{args.pre_config_delay_s:g}",
            "--config-repeat",
            "5",
            "--config-interval-s",
            "1",
            "--pre-start-delay-s",
            "3",
            "--start-repeat",
            "5",
            "--start-interval-s",
            "0.6",
            "--start-arm-delay-s",
            "4",
        ]
    )
    return command


def check_manifests(args: argparse.Namespace, runs: list[dict]) -> None:
    existing = [
        args.manifest_dir / f"run_{int(run['run_id']):08x}.json"
        for run in runs
        if (args.manifest_dir / f"run_{int(run['run_id']):08x}.json").exists()
    ]
    if existing:
        rendered = "\n".join(f"  {path}" for path in existing[:10])
        raise RuntimeError(
            "selected manifests already exist; refusing to overwrite:\n" + rendered
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--end-sequence", type=int, default=None)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=ROOT / "real_collision_experiment/run_manifests/fig9_10_fig12_phy5_d05_d075_r1_20s_offline",
    )
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--control-tx-gain", type=float, default=60.0)
    parser.add_argument("--slot-s", type=float, default=70.0)
    parser.add_argument("--position-pause-s", type=float, default=20.0)
    parser.add_argument("--pre-config-delay-s", type=float, default=5.0)
    parser.add_argument("--max-slot-lateness-s", type=float, default=15.0)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument(
        "--continue-on-run-error",
        action="store_true",
        help="Record a failed control slot and continue; intended for remaining only",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    campaign, runs, digest = load_campaign(
        args.campaign,
        start_sequence=args.start_sequence,
        end_sequence=args.end_sequence,
    )
    args.repo_root = args.repo_root.resolve()
    args.manifest_dir = args.manifest_dir.resolve()
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    if not args.simulate:
        check_manifests(args, runs)

    schedule = build_schedule(
        runs,
        slot_s=args.slot_s,
        position_pause_s=args.position_pause_s,
    )
    epoch = time.monotonic()
    print(
        f"OFFLINE_CONTROL_STARTED campaign={campaign['campaign_id']} runs={len(runs)} "
        f"sequences={runs[0]['sequence']}-{runs[-1]['sequence']} digest={digest[:12]}",
        flush=True,
    )
    print(
        "The Ubuntu RX script must already be running. "
        f"Each run uses a {args.slot_s:g}s fixed slot.",
        flush=True,
    )

    previous_offset = 0.0
    failures: list[dict] = []
    for index, item in enumerate(schedule):
        run = item.run
        name = run_name(run)
        if item.position_pause_before_s:
            pause_start = epoch + item.start_offset_s - item.position_pause_before_s
            wait_until(pause_start)
            print(
                f"\nPOSITION_BREAK {item.position_pause_before_s:g}s: "
                f"{placement_message(run)}",
                flush=True,
            )
        due = epoch + item.start_offset_s
        lateness = wait_until(due)
        print(
            f"\nCONTROL RUN {index + 1}/{len(runs)} sequence={run['sequence']} {name} "
            f"N={len(run['active_nodes'])} G={run['offered_load']} "
            f"slot_offset={item.start_offset_s:g}s",
            flush=True,
        )
        try:
            if lateness > args.max_slot_lateness_s:
                raise RuntimeError(
                    f"controller missed slot by {lateness:.1f}s"
                )
            if args.simulate:
                time.sleep(min(0.01, max(args.slot_s / 10.0, 0.0)))
                return_code = 0
            else:
                command = offline_controller_command(args, run)
                print("CONTROL COMMAND:", subprocess.list2cmdline(command), flush=True)
                return_code = subprocess.run(command, cwd=args.repo_root).returncode
            if return_code != 0:
                raise RuntimeError(
                    f"control transmitter failed for {name}: {return_code}"
                )
            print(f"CONTROL_DONE {name}; idle until next fixed slot", flush=True)
        except Exception as exc:
            if not args.continue_on_run_error:
                raise
            failure = {
                "sequence": int(run["sequence"]),
                "run_id": int(run["run_id"]),
                "run_id_hex": f"0x{int(run['run_id']):08X}",
                "phase": run["phase"],
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            failures.append(failure)
            print(
                f"CONTROL_RUN_FAILED_CONTINUING {failure}; "
                "next fixed slot remains unchanged",
                flush=True,
            )
        previous_offset = item.start_offset_s

    if failures:
        failure_path = (
            args.manifest_dir
            / f"offline_control_failures_seq{runs[0]['sequence']}_{runs[-1]['sequence']}.json"
        )
        failure_path.write_text(
            json.dumps(
                {
                    "schema": "sp_offline_control_failure_summary_v1",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "campaign_id": campaign["campaign_id"],
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"OFFLINE_CONTROL_FAILURE_SUMMARY {failure_path}", flush=True)
    print(
        f"OFFLINE_CONTROL_DONE runs={len(runs)} failures={len(failures)} "
        f"manifests={args.manifest_dir} "
        f"last_slot_offset={previous_offset:g}s",
        flush=True,
    )
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
