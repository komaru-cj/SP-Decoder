#!/usr/bin/env python3
"""Ubuntu receiver-side server for an automatically synchronized campaign."""

from __future__ import annotations

import argparse
import json
import math
import selectors
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NODE_RECEIVER_DIR = ROOT / "real_collision_experiment/node01_sp_receiver"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(NODE_RECEIVER_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_RECEIVER_DIR))

from campaign_common import (  # noqa: E402
    PROTOCOL_VERSION,
    JsonLineConnection,
    expect,
    load_campaign,
    run_name,
)
from capture_dual_b210_gr import merge_channel_sc16  # noqa: E402


FORMAL_GLOBAL_CANDIDATE_MIN = 800
FORMAL_EXPECTED_PACKET_MULTIPLIER = 3
FORMAL_WINDOW_CANDIDATE_MIN = 256
FORMAL_WINDOW_CANDIDATES_PER_ACTIVE_NODE = 16


def formal_candidate_budgets(run: dict[str, Any]) -> tuple[int, int]:
    """Return high-recall global and per-window budgets for formal campaigns."""

    expected_packets = max(0, int(run.get("expected_tx_count", 0)))
    active_node_count = max(1, len(run.get("active_nodes", [])))
    global_limit = max(
        FORMAL_GLOBAL_CANDIDATE_MIN,
        FORMAL_EXPECTED_PACKET_MULTIPLIER * expected_packets,
    )
    per_window_limit = max(
        FORMAL_WINDOW_CANDIDATE_MIN,
        FORMAL_WINDOW_CANDIDATES_PER_ACTIVE_NODE * active_node_count,
    )
    return int(global_limit), int(per_window_limit)


def receiver_cfo_limit_bins(run: dict[str, Any]) -> int:
    """Keep a constant 15.625 kHz CFO span across LoRa bandwidths."""
    sf = int(run.get("spreading_factor", 10))
    bandwidth_hz = float(run.get("bandwidth_hz", 125_000.0))
    return max(32, int(math.ceil(15_625.0 / (bandwidth_hz / (2**sf)))))


def capture_sample_rate_hz(requested_rate: float, run: dict[str, Any]) -> float:
    """Select a safe capture rate while preserving the profile-5 field setup."""
    bandwidth_hz = float(run.get("bandwidth_hz", 125_000))
    if bandwidth_hz >= 500_000:
        return max(float(requested_rate), 1_000_000.0)
    return float(requested_rate)


def capture_analog_bandwidth_hz(run: dict[str, Any]) -> float:
    bandwidth_hz = float(run.get("bandwidth_hz", 125_000))
    return max(500_000.0, 2.0 * bandwidth_hz)


def capture_duration_s(run: dict[str, Any], capture_guard_s: float = 0.0) -> float:
    return float(run["recommended_capture_s"]) + float(capture_guard_s)


def capture_command(args: argparse.Namespace, run: dict[str, Any]) -> tuple[list[str], Path]:
    name = run_name(run)
    output = args.runs_root / name / f"{name}.sc16"
    sample_rate_hz = capture_sample_rate_hz(args.sample_rate, run)
    analog_bandwidth_hz = capture_analog_bandwidth_hz(run)
    # Offline campaigns budget a guard after the controller's planned capture
    # length.  Pass it through to UHD as well; otherwise the storage/schedule
    # audit claims a tail that the recorded IQ does not contain.
    duration_s = capture_duration_s(
        run,
        getattr(args, "capture_guard_s", 0.0)
    )
    command = [
        args.python_executable,
        str(args.repo_root / "real_collision_experiment/node01_sp_receiver/capture_dual_b210_gr.py"),
        "--out",
        str(output),
        "--run-id",
        f"0x{int(run['run_id']):08X}",
        "--duration",
        f"{duration_s:g}",
        "--center-freq",
        "487700000",
        "--rate",
        f"{sample_rate_hz:g}",
        "--gain",
        f"{args.rx_gain:g}",
        "--bandwidth",
        f"{analog_bandwidth_hz:g}",
        "--channels",
        "0,1",
        "--antenna",
        "RX2",
        "--notes",
        f"{args.campaign_id}:{run['sequence']}:{run['phase']}",
    ]
    return command, output


def decoder_command(
    args: argparse.Namespace,
    run: dict[str, Any],
    iq_path: Path,
) -> tuple[list[str], Path]:
    name = run_name(run)
    report_path = iq_path.parent / "six_methods_gate.json"
    global_candidate_limit, per_window_candidate_limit = formal_candidate_budgets(
        run
    )
    cfo_limit = receiver_cfo_limit_bins(run)
    command = [
        args.python_executable,
        str(args.repo_root / "real_collision_experiment/node01_sp_receiver/sp_node01_receiver.py"),
        "--iq",
        str(iq_path),
        "--metadata",
        str(iq_path.with_suffix(iq_path.suffix + ".json")),
        "--out",
        str(report_path),
        "--run-id",
        f"0x{int(run['run_id']):08X}",
        "--business-duration-s",
        f"{float(run['duration_s']):g}",
        "--sf",
        str(int(run.get("spreading_factor", 10))),
        "--bandwidth-hz",
        f"{float(run.get('bandwidth_hz', 125000)):g}",
        "--threshold",
        "3",
        "--max-candidates",
        str(global_candidate_limit),
        "--frontend-candidates-per-window",
        str(per_window_candidate_limit),
        "--energy-min-ratio",
        "3",
        "--comparison-frontend-scope",
        "common",
        "--cfo-min",
        str(-cfo_limit),
        "--cfo-max",
        str(cfo_limit),
    ]
    for node_id in run["active_nodes"]:
        if int(node_id) != 1:
            command.extend(["--active-node", str(int(node_id))])
    return command, report_path


def run_until_armed(command: list[str], *, cwd: Path) -> subprocess.Popen[str]:
    print("RX COMMAND:", subprocess.list2cmdline(command), flush=True)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            remainder = process.stdout.read()
            if remainder:
                print(remainder, end="", flush=True)
            raise RuntimeError(
                f"receiver exited before CAPTURE_STREAMING_GR with code {process.returncode}"
            )
        events = selector.select(timeout=1.0)
        for key, _ in events:
            line = key.fileobj.readline()
            if line:
                print(line, end="", flush=True)
                if "CAPTURE_STREAMING_GR" in line:
                    selector.close()
                    return process
    process.terminate()
    raise TimeoutError("receiver did not print CAPTURE_STREAMING_GR within 45 seconds")


def recover_complete_temp_capture(
    iq_path: Path,
    *,
    child_return_code: int,
) -> dict[str, Any] | None:
    """Recover a full capture if GNU Radio aborts only during flowgraph teardown."""
    metadata_path = iq_path.with_suffix(iq_path.suffix + ".json")
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    target = int(metadata.get("target_samples_per_channel", 0))
    channel_files = [Path(value) for value in metadata.get("channel_temp_files", [])]
    if target <= 0 or len(channel_files) != 2:
        return None
    expected_channel_bytes = target * 2 * 2
    if any(
        not path.exists() or path.stat().st_size != expected_channel_bytes
        for path in channel_files
    ):
        return None
    if iq_path.exists() and iq_path.stat().st_size:
        return None

    print(
        f"RECOVERING_COMPLETE_TEMP_CAPTURE child_return_code={child_return_code} "
        f"target_samples={target}",
        flush=True,
    )
    merged_samples = merge_channel_sc16(channel_files[0], channel_files[1], iq_path)
    if merged_samples != target:
        raise RuntimeError(
            f"recovered merge sample mismatch: expected {target}, got {merged_samples}"
        )
    expected_output_bytes = target * 2 * 2 * 2
    if iq_path.stat().st_size != expected_output_bytes:
        raise RuntimeError(
            "recovered IQ byte count mismatch: "
            f"expected {expected_output_bytes}, got {iq_path.stat().st_size}"
        )
    for path in channel_files:
        path.unlink()
    metadata.update(
        {
            "status": "done",
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "channel_temp_bytes": [0, 0],
            "samples_per_channel": target,
            "file_bytes": expected_output_bytes,
            "fatal_error": "",
            "recovery": {
                "recovered_complete_channel_files": True,
                "child_return_code": int(child_return_code),
                "reason": (
                    "Both channel files reached the exact target before the GNU Radio "
                    "process aborted during teardown; parent merged and validated them."
                ),
            },
        }
    )
    temporary = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    temporary.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    temporary.replace(metadata_path)
    print(
        f"RECOVERED_CAPTURE_DONE samples={target} bytes={expected_output_bytes}",
        flush=True,
    )
    return metadata


def recover_middle_window_partial_capture(
    iq_path: Path,
    *,
    child_return_code: int,
    required_middle_window_s: float = 3.0,
) -> dict[str, Any] | None:
    """Promote a partial capture when the target-centered window is complete."""

    metadata_path = iq_path.with_suffix(iq_path.suffix + ".json")
    if not metadata_path.exists() or (iq_path.exists() and iq_path.stat().st_size):
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    recovery = metadata.get("recovery", {})
    partial_value = recovery.get("partial_output_file")
    if not partial_value:
        return None
    partial_path = Path(partial_value)
    if not partial_path.exists():
        return None
    target = int(metadata.get("target_samples_per_channel", 0))
    available = int(recovery.get("partial_samples_per_channel", 0))
    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    if target <= 0 or available <= 0 or rate <= 0.0:
        return None
    required_end = int(math.ceil(0.5 * target + 0.5 * required_middle_window_s * rate))
    expected_bytes = available * 2 * 2 * 2
    if available < required_end or partial_path.stat().st_size != expected_bytes:
        return None

    original_fatal_error = str(metadata.get("fatal_error", ""))
    partial_path.replace(iq_path)
    channel_files = [Path(value) for value in metadata.get("channel_temp_files", [])]
    for path in channel_files:
        path.unlink(missing_ok=True)
    metadata.update(
        {
            "status": "usable_partial",
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "channel_temp_bytes": [0, 0],
            "samples_per_channel": available,
            "file_bytes": expected_bytes,
            "fatal_error": "",
            "recovery": {
                **recovery,
                "partial_output_file": str(iq_path.resolve()),
                "promoted_to_canonical_iq": True,
                "middle_window_preserved": True,
                "required_middle_window_s": float(required_middle_window_s),
                "required_end_sample": int(required_end),
                "child_return_code": int(child_return_code),
                "original_fatal_error": original_fatal_error,
            },
        }
    )
    temporary = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    temporary.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    temporary.replace(metadata_path)
    print(
        "RECOVERED_MIDDLE_WINDOW_PARTIAL_CAPTURE "
        f"samples={available}/{target} middle_window={required_middle_window_s:g}s ",
        flush=True,
    )
    return metadata


def finish_capture(
    process: subprocess.Popen[str],
    *,
    recover_iq_path: Path | None = None,
) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
    return_code = process.wait()
    if return_code != 0:
        if recover_iq_path is not None:
            recovered = recover_complete_temp_capture(
                recover_iq_path,
                child_return_code=return_code,
            )
            if recovered is not None:
                return
            recovered = recover_middle_window_partial_capture(
                recover_iq_path,
                child_return_code=return_code,
            )
            if recovered is not None:
                return
        raise RuntimeError(f"receiver capture failed with exit code {return_code}")


def validate_capture(iq_path: Path) -> dict[str, Any]:
    metadata_path = iq_path.with_suffix(iq_path.suffix + ".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    status = metadata.get("status")
    if status not in {"done", "usable_partial"}:
        raise RuntimeError(f"capture metadata status is not usable: {status!r}")
    if status == "done" and int(metadata.get("samples_per_channel", -1)) != int(
        metadata.get("target_samples_per_channel", -2)
    ):
        raise RuntimeError("complete capture sample count does not match its target")
    if status == "usable_partial" and not bool(
        metadata.get("recovery", {}).get("middle_window_preserved", False)
    ):
        raise RuntimeError("partial capture does not preserve the required middle window")
    if metadata.get("fatal_error"):
        raise RuntimeError(f"capture fatal_error: {metadata['fatal_error']}")
    expected_bytes = int(metadata.get("file_bytes", -1))
    if not iq_path.exists() or iq_path.stat().st_size != expected_bytes:
        raise RuntimeError("capture IQ byte count does not match metadata")
    return metadata


def validate_gate_report(
    report_path: Path,
    active_nodes: list[int],
    *,
    require_all_nodes: bool = True,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("capture_warnings"):
        raise RuntimeError(f"first-run decoder reported capture warnings: {report['capture_warnings']}")
    clipped = report.get("adc", {}).get("clipped_count")
    if clipped is None or any(int(value) != 0 for value in clipped):
        raise RuntimeError(f"first-run ADC clipping check failed: {clipped}")
    observed_nodes = {
        int(row["node_id"]) for row in report.get("unique_successes", []) if "node_id" in row
    }
    missing = sorted(set(int(node) for node in active_nodes) - observed_nodes)
    if missing and require_all_nodes:
        raise RuntimeError(f"first-run link gate did not decode nodes: {missing}")
    return {
        "observed_nodes": sorted(observed_nodes),
        "missing_nodes": missing,
        "all_active_nodes_observed": not bool(missing),
        "clipped_count": clipped,
        "capture_warning_count": len(report.get("capture_warnings", [])),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=39091)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--end-sequence", type=int, default=None)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "real_collision_experiment/runs")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--sample-rate", type=float, default=750_000.0)
    parser.add_argument("--rx-gain", type=float, default=20.0)
    parser.add_argument(
        "--decode-first",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Decode only the first selected run and require every active node",
    )
    parser.add_argument("--simulate", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    campaign, runs, digest = load_campaign(
        args.campaign,
        start_sequence=args.start_sequence,
        end_sequence=args.end_sequence,
    )
    args.campaign_id = campaign["campaign_id"]
    args.repo_root = args.repo_root.resolve()
    args.runs_root = args.runs_root.resolve()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.listen_host, args.port))
        server.listen(1)
        print(
            f"RECEIVER_CAMPAIGN_LISTENING {args.listen_host}:{args.port} "
            f"campaign={args.campaign_id} runs={len(runs)} digest={digest[:12]}",
            flush=True,
        )
        sock, address = server.accept()
        print(f"CONTROLLER_CONNECTED {address}", flush=True)
        connection = JsonLineConnection(sock)
        try:
            connection.send(
                {
                    "type": "receiver_hello",
                    "protocol": PROTOCOL_VERSION,
                    "campaign_id": args.campaign_id,
                    "digest": digest,
                    "run_ids": [int(run["run_id"]) for run in runs],
                }
            )
            hello = connection.receive()
            expect(hello, "controller_hello")
            if hello.get("digest") != digest or hello.get("campaign_id") != args.campaign_id:
                raise RuntimeError("controller and receiver campaign files/ranges do not match")

            for run_index, run in enumerate(runs):
                prepare = connection.receive()
                expect(prepare, "prepare", run_id=int(run["run_id"]))
                name = run_name(run)
                print(
                    f"\nRUN {run_index + 1}/{len(runs)} sequence={run['sequence']} "
                    f"{name} capture={run['recommended_capture_s']}s",
                    flush=True,
                )
                if args.simulate:
                    time.sleep(0.05)
                    connection.send({"type": "armed", "run_id": int(run["run_id"])})
                    control_done = connection.receive()
                    expect(control_done, "control_done", run_id=int(run["run_id"]))
                    if int(control_done.get("return_code", -1)) != 0:
                        raise RuntimeError("simulated controller reported failure")
                    time.sleep(0.05)
                    gate = {"simulated": True} if args.decode_first and run_index == 0 else None
                else:
                    command, iq_path = capture_command(args, run)
                    iq_path.parent.mkdir(parents=True, exist_ok=True)
                    process = run_until_armed(command, cwd=args.repo_root)
                    connection.send({"type": "armed", "run_id": int(run["run_id"])})
                    finish_capture(process, recover_iq_path=iq_path)
                    metadata = validate_capture(iq_path)
                    control_done = connection.receive()
                    expect(control_done, "control_done", run_id=int(run["run_id"]))
                    if int(control_done.get("return_code", -1)) != 0:
                        raise RuntimeError("control transmitter failed during this capture")
                    gate = None
                    if args.decode_first and run_index == 0:
                        decode, report_path = decoder_command(args, run, iq_path)
                        print("FIRST-RUN GATE DECODER:", subprocess.list2cmdline(decode), flush=True)
                        subprocess.run(decode, cwd=args.repo_root, check=True)
                        gate = validate_gate_report(report_path, run["active_nodes"])
                        print(f"FIRST_RUN_GATE_OK {gate}", flush=True)
                    print(
                        f"CAPTURE_VALIDATED {name} samples={metadata['samples_per_channel']} "
                        f"bytes={metadata['file_bytes']}",
                        flush=True,
                    )
                connection.send(
                    {
                        "type": "run_done",
                        "run_id": int(run["run_id"]),
                        "sequence": int(run["sequence"]),
                        "gate": gate,
                    }
                )
            connection.send({"type": "campaign_done", "run_count": len(runs)})
            print(f"RECEIVER_CAMPAIGN_DONE runs={len(runs)}", flush=True)
        except BaseException as exc:
            try:
                connection.send({"type": "abort", "error": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass
            raise
        finally:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
