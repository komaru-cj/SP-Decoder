#!/usr/bin/env python3
"""Run the Ubuntu dual-RX campaign on fixed slots without a network peer."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from campaign_common import load_campaign, run_name  # noqa: E402
from offline_schedule import build_schedule, placement_message, wait_until  # noqa: E402
from receiver_campaign_server import (  # noqa: E402
    capture_duration_s,
    capture_sample_rate_hz,
    capture_command,
    decoder_command,
    finish_capture,
    run_until_armed,
    validate_capture,
    validate_gate_report,
)


GIB = 1024**3
BYTES_PER_DUAL_CHANNEL_SAMPLE = 2 * 2 * 2


def required_capture_bytes(
    runs: list[dict],
    *,
    sample_rate: float,
    capture_guard_s: float,
) -> tuple[int, int]:
    sizes = [
        round(
            capture_duration_s(run, capture_guard_s)
            * capture_sample_rate_hz(sample_rate, run)
            * BYTES_PER_DUAL_CHANNEL_SAMPLE
        )
        for run in runs
    ]
    # During merge, one run temporarily needs both channel files and the final
    # interleaved file. The final-file sum already contains one copy.
    return sum(sizes), max(sizes)


def check_storage(args: argparse.Namespace, runs: list[dict]) -> None:
    args.runs_root.mkdir(parents=True, exist_ok=True)
    existing = []
    for run in runs:
        name = run_name(run)
        directory = args.runs_root / name
        if directory.exists() and any(directory.iterdir()):
            existing.append(directory)
    if existing:
        rendered = "\n".join(f"  {path}" for path in existing[:10])
        raise RuntimeError(
            "selected output directories are not empty; refusing to overwrite:\n"
            f"{rendered}"
        )

    final_bytes, merge_extra = required_capture_bytes(
        runs,
        sample_rate=args.sample_rate,
        capture_guard_s=args.capture_guard_s,
    )
    reserve = int(args.free_space_reserve_gib * GIB)
    required = final_bytes + merge_extra + reserve
    free = shutil.disk_usage(args.runs_root).free
    print(
        f"STORAGE_CHECK output={final_bytes / GIB:.2f} GiB "
        f"merge_headroom={merge_extra / GIB:.2f} GiB "
        f"reserve={reserve / GIB:.2f} GiB free={free / GIB:.2f} GiB",
        flush=True,
    )
    if free < required:
        raise RuntimeError(
            f"insufficient disk space at {args.runs_root}: "
            f"need {required / GIB:.2f} GiB, free {free / GIB:.2f} GiB. "
            "Set RUNS_ROOT to a disk with more free space."
        )


def full_capture_clipping_counts(
    iq_path: Path,
    *,
    channel_count: int = 2,
    chunk_samples: int = 1_000_000,
) -> list[int]:
    """Scan int16 IQ in bounded memory so the prefix gate still checks all ADC data."""
    counts = np.zeros(channel_count, dtype=np.int64)
    values_per_sample = channel_count * 2
    with iq_path.open("rb") as source:
        while True:
            raw = np.fromfile(
                source,
                dtype="<i2",
                count=max(1, int(chunk_samples)) * values_per_sample,
            )
            if raw.size == 0:
                break
            if raw.size % values_per_sample:
                raise RuntimeError("IQ file has a partial trailing dual-channel sample")
            framed = raw.reshape(-1, channel_count, 2)
            clipped = (framed >= 32760) | (framed <= -32760)
            counts += np.count_nonzero(np.any(clipped, axis=2), axis=0)
    return [int(value) for value in counts]


def run_one_time_gate(
    args: argparse.Namespace,
    run: dict,
    iq_path: Path,
) -> dict:
    full_clipped = full_capture_clipping_counts(iq_path)
    if any(full_clipped):
        raise RuntimeError(
            f"full-capture ADC clipping check failed: clipped_count={full_clipped}"
    )
    gate_duration_s = float(args.gate_capture_seconds)
    if args.gate_capture_start_seconds is None:
        metadata_path = iq_path.with_suffix(iq_path.suffix + ".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        actual = metadata.get("actual", {})
        requested = metadata.get("requested", {})
        rate = float(
            actual.get("rate_hz", requested.get("sample_rate_hz", args.sample_rate))
        )
        target_samples = int(
            metadata.get(
                "target_samples_per_channel",
                metadata.get("samples_per_channel", 0),
            )
        )
        gate_start_s = 0.5 * (float(target_samples) / rate - gate_duration_s)
        gate_window_mode = "target_capture_center"
    else:
        gate_start_s = float(args.gate_capture_start_seconds)
        gate_window_mode = "explicit_start"
    if gate_start_s < 0.0 or gate_duration_s <= 0.0:
        raise ValueError("gate capture start must be >= 0 and duration must be > 0")
    gate_end_s = gate_start_s + gate_duration_s
    print(
        f"FULL_CAPTURE_ADC_OK clipped_count={full_clipped}; "
        f"decoding bounded range {gate_start_s:g}-{gate_end_s:g}s "
        f"mode={gate_window_mode} to bound detection/sync/decode work",
        flush=True,
    )
    decode, report_path = decoder_command(args, run, iq_path)
    decode.extend(
        [
            "--capture-start-seconds",
            f"{gate_start_s:g}",
            "--max-capture-seconds",
            f"{gate_duration_s:g}",
            "--skip-comparison-decoders",
        ]
    )
    print("ONE-TIME LINK GATE DECODER:", subprocess.list2cmdline(decode), flush=True)
    result = subprocess.run(decode, cwd=args.repo_root)
    if result.returncode == -9:
        raise RuntimeError(
            "one-time gate was killed by SIGKILL/OOM even with the bounded window; "
            "increase VM RAM/swap or reduce --gate-capture-seconds"
        )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, decode)
    # A short gate slice is not guaranteed to contain one complete packet from
    # every active node. Treat missing identities as a recorded warning only.
    gate = validate_gate_report(
        report_path,
        run["active_nodes"],
        require_all_nodes=False,
    )
    gate["full_capture_clipped_count"] = full_clipped
    gate["decoded_capture_start_seconds"] = gate_start_s
    gate["decoded_capture_duration_seconds"] = gate_duration_s
    gate["decoded_capture_end_seconds"] = gate_end_s
    gate["decoded_capture_window_mode"] = gate_window_mode
    print(f"ONE_TIME_GATE_OK {gate}", flush=True)
    return gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--end-sequence", type=int, default=None)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "real_collision_experiment/runs")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--sample-rate", type=float, default=750_000.0)
    parser.add_argument("--rx-gain", type=float, default=20.0)
    parser.add_argument("--slot-s", type=float, default=70.0)
    parser.add_argument("--position-pause-s", type=float, default=20.0)
    parser.add_argument("--capture-guard-s", type=float, default=5.0)
    parser.add_argument(
        "--gate-capture-start-seconds",
        type=float,
        default=None,
        help=(
            "Explicit link-gate start offset. The default is None, which centers "
            "the gate in the requested capture duration."
        ),
    )
    parser.add_argument(
        "--gate-capture-seconds",
        type=float,
        default=3.0,
        help="Duration decoded by the link gate; formal default is the middle 3 s.",
    )
    parser.add_argument("--max-slot-lateness-s", type=float, default=15.0)
    parser.add_argument("--free-space-reserve-gib", type=float, default=1.0)
    parser.add_argument(
        "--decode-first",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Decode the first selected run after capture; use only for one-run preflight",
    )
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument(
        "--continue-on-run-error",
        action="store_true",
        help="Record a failed slot and continue the fixed schedule; intended for remaining only",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    campaign, runs, digest = load_campaign(
        args.campaign,
        start_sequence=args.start_sequence,
        end_sequence=args.end_sequence,
    )
    if args.decode_first and len(runs) != 1:
        raise SystemExit("--decode-first is restricted to a one-run preflight")
    longest_capture = max(
        capture_duration_s(run, args.capture_guard_s) for run in runs
    )
    if not args.simulate and args.slot_s < longest_capture + 10.0:
        raise SystemExit("--slot-s leaves less than 10 s for IQ merge and scheduling margin")

    args.campaign_id = campaign["campaign_id"]
    args.repo_root = args.repo_root.resolve()
    args.runs_root = args.runs_root.resolve()
    args.runs_root.mkdir(parents=True, exist_ok=True)
    if not args.simulate:
        check_storage(args, runs)

    schedule = build_schedule(
        runs,
        slot_s=args.slot_s,
        position_pause_s=args.position_pause_s,
    )
    epoch = time.monotonic()
    print(
        f"OFFLINE_RX_STARTED campaign={args.campaign_id} runs={len(runs)} "
        f"sequences={runs[0]['sequence']}-{runs[-1]['sequence']} digest={digest[:12]}",
        flush=True,
    )
    print(
        "START THE WINDOWS CONTROL SCRIPT NOW (within 10 seconds). "
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
            f"\nRX RUN {index + 1}/{len(runs)} sequence={run['sequence']} {name} "
            f"capture={capture_duration_s(run, args.capture_guard_s):g}s "
            f"slot_offset={item.start_offset_s:g}s",
            flush=True,
        )
        try:
            if lateness > args.max_slot_lateness_s:
                raise RuntimeError(
                    f"receiver missed slot by {lateness:.1f}s"
                )
            if args.simulate:
                time.sleep(min(0.01, max(args.slot_s / 10.0, 0.0)))
                print(f"RX_SIMULATED {name}", flush=True)
            else:
                command, iq_path = capture_command(args, run)
                iq_path.parent.mkdir(parents=True, exist_ok=True)
                process = run_until_armed(command, cwd=args.repo_root)
                finish_capture(process, recover_iq_path=iq_path)
                metadata = validate_capture(iq_path)
                print(
                    f"CAPTURE_VALIDATED {name} samples={metadata['samples_per_channel']} "
                    f"bytes={metadata['file_bytes']}",
                    flush=True,
                )
                if args.decode_first:
                    run_one_time_gate(args, run, iq_path)
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
                f"RX_RUN_FAILED_CONTINUING {failure}; next fixed slot remains unchanged",
                flush=True,
            )
        previous_offset = item.start_offset_s

    if failures:
        failure_path = (
            args.runs_root
            / f"offline_rx_failures_seq{runs[0]['sequence']}_{runs[-1]['sequence']}.json"
        )
        failure_path.write_text(
            json.dumps(
                {
                    "schema": "sp_offline_rx_failure_summary_v1",
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "campaign_id": args.campaign_id,
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"OFFLINE_RX_FAILURE_SUMMARY {failure_path}", flush=True)
    print(
        f"OFFLINE_RX_DONE runs={len(runs)} failures={len(failures)} "
        f"last_slot_offset={previous_offset:g}s",
        flush=True,
    )
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
