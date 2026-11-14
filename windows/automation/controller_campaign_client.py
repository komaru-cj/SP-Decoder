#!/usr/bin/env python3
"""Windows controller-side client for an automatically synchronized campaign."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from campaign_common import (  # noqa: E402
    PROTOCOL_VERSION,
    JsonLineConnection,
    expect,
    load_campaign,
    run_name,
)


def controller_command(args: argparse.Namespace, run: dict[str, Any]) -> list[str]:
    command = [
        args.python_executable,
        str(args.repo_root / "real_collision_experiment/control_usrp/usrp_run_controller.py"),
        "--run-id",
        f"0x{int(run['run_id']):08X}",
        "--active-nodes",
        ",".join(str(int(node)) for node in run["active_nodes"]),
        "--phy-profile-id",
        str(int(run.get("phy_profile_id", 5))),
        "--per-node-duty-cycle",
        f"{float(run['per_node_duty_cycle']):g}",
        "--duration-s",
        f"{float(run['duration_s']):g}",
        "--warmup-s",
        f"{float(run['warmup_s']):g}",
        "--node-tx-power",
        str(int(run["node_tx_power_dbm"])),
        "--global-seed",
        f"0x{int(run['global_seed']):08X}",
        "--payload-seed",
        f"0x{int(run['payload_seed']):08X}",
        "--usrp-tx-gain",
        f"{args.control_tx_gain:g}",
        "--manifest-dir",
        str(args.manifest_dir),
    ]
    for key, value in sorted(run.get("tags", {}).items()):
        command.extend(["--experiment-tag", f"{key}={value}"])
    return command


def connect_with_retry(host: str, port: int, timeout_s: float) -> socket.socket:
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=10.0)
            sock.settimeout(None)
            return sock
        except OSError as exc:
            last_error = exc
            time.sleep(1.0)
    raise TimeoutError(f"could not connect to receiver {host}:{port}: {last_error}")


def position_prompt(run: dict[str, Any], previous_position: str | None, *, non_interactive: bool) -> str | None:
    tags = run.get("tags", {})
    position = tags.get("position_index")
    if not position or position == previous_position:
        return previous_position
    message = (
        f"Fig.12 position {position}: keep Node01 at {tags.get('node1_distance_m')} m; "
        f"move Node02 to {tags.get('node2_distance_m')} m on bearing "
        f"{tags.get('bearing_deg')} deg (separation {tags.get('node_separation_m')} m)."
    )
    print("\n" + "=" * 72)
    print(message)
    print("=" * 72)
    if non_interactive:
        print("NON-INTERACTIVE simulation: continuing without prompt")
    else:
        input("Complete the placement and field record, then press Enter; Ctrl+C aborts: ")
    return position


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--receiver-host", required=True)
    parser.add_argument("--port", type=int, default=39091)
    parser.add_argument("--connect-timeout-s", type=float, default=120.0)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--end-sequence", type=int, default=None)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=ROOT / "real_collision_experiment/run_manifests/fig9_10_fig12_phy5_20s",
    )
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--control-tx-gain", type=float, default=60.0)
    parser.add_argument("--inter-run-gap-s", type=float, default=10.0)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--simulate", action="store_true")
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
    campaign_id = campaign["campaign_id"]

    sock = connect_with_retry(args.receiver_host, args.port, args.connect_timeout_s)
    connection = JsonLineConnection(sock)
    try:
        hello = connection.receive()
        expect(hello, "receiver_hello")
        if hello.get("digest") != digest or hello.get("campaign_id") != campaign_id:
            raise RuntimeError("receiver and controller campaign files/ranges do not match")
        connection.send(
            {
                "type": "controller_hello",
                "protocol": PROTOCOL_VERSION,
                "campaign_id": campaign_id,
                "digest": digest,
                "run_ids": [int(run["run_id"]) for run in runs],
            }
        )
        print(
            f"CAMPAIGN_MATCHED id={campaign_id} runs={len(runs)} digest={digest[:12]}",
            flush=True,
        )

        previous_position: str | None = None
        for index, run in enumerate(runs):
            previous_position = position_prompt(
                run, previous_position, non_interactive=args.non_interactive
            )
            name = run_name(run)
            print(
                f"\nRUN {index + 1}/{len(runs)} sequence={run['sequence']} {name} "
                f"N={len(run['active_nodes'])} G={run['offered_load']}",
                flush=True,
            )
            connection.send(
                {
                    "type": "prepare",
                    "run_id": int(run["run_id"]),
                    "sequence": int(run["sequence"]),
                }
            )
            armed = connection.receive()
            if armed.get("type") == "abort":
                raise RuntimeError(f"receiver aborted: {armed.get('error')}")
            expect(armed, "armed", run_id=int(run["run_id"]))
            print(f"RECEIVER_ARMED {name}; starting CONFIG/START transmitter", flush=True)

            if args.simulate:
                time.sleep(0.05)
                return_code = 0
            else:
                command = controller_command(args, run)
                print("CONTROL COMMAND:", subprocess.list2cmdline(command), flush=True)
                return_code = subprocess.run(command, cwd=args.repo_root).returncode
            connection.send(
                {
                    "type": "control_done",
                    "run_id": int(run["run_id"]),
                    "return_code": int(return_code),
                }
            )
            if return_code != 0:
                raise RuntimeError(f"control transmitter failed for {name}: {return_code}")

            done = connection.receive()
            if done.get("type") == "abort":
                raise RuntimeError(f"receiver aborted: {done.get('error')}")
            expect(done, "run_done", run_id=int(run["run_id"]))
            if done.get("gate") is not None:
                print(f"FIRST_RUN_GATE_RESULT {done['gate']}", flush=True)
            print(f"RUN_COMPLETE {name}", flush=True)
            if index + 1 < len(runs):
                print(f"INTER_RUN_GAP {args.inter_run_gap_s:g}s", flush=True)
                time.sleep(max(0.0, args.inter_run_gap_s))

        finished = connection.receive()
        expect(finished, "campaign_done")
        print(
            f"CONTROLLER_CAMPAIGN_DONE runs={finished.get('run_count')} "
            f"manifests={args.manifest_dir}",
            flush=True,
        )
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
