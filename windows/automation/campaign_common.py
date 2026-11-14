#!/usr/bin/env python3
"""Shared campaign loading and JSON-line protocol helpers."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = 1


def load_campaign(
    path: Path,
    *,
    start_sequence: int,
    end_sequence: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    campaign = json.loads(path.read_text(encoding="utf-8"))
    if campaign.get("schema") != "sp_fig9_12_campaign_v1":
        raise ValueError(f"unsupported campaign schema: {campaign.get('schema')!r}")
    runs = [
        run
        for run in campaign.get("runs", [])
        if int(run["sequence"]) >= start_sequence
        and (end_sequence is None or int(run["sequence"]) <= end_sequence)
    ]
    if not runs:
        raise ValueError("selected campaign range contains no runs")
    sequences = [int(run["sequence"]) for run in runs]
    if sequences != list(range(sequences[0], sequences[-1] + 1)):
        raise ValueError("selected campaign sequence range is not contiguous")
    identity = {
        "campaign_id": campaign["campaign_id"],
        "runs": [
            {
                **{
                    key: run[key]
                    for key in (
                    "sequence",
                    "run_id",
                    "active_nodes",
                    "offered_load",
                    "duration_s",
                    "warmup_s",
                    "node_tx_power_dbm",
                    "global_seed",
                    "payload_seed",
                    "recommended_capture_s",
                    "tags",
                    )
                },
                **{
                    key: run[key]
                    for key in (
                        "traffic_profile_load",
                        "firmware_active_node_count",
                        "per_node_duty_cycle",
                        "phy_profile_id",
                        "spreading_factor",
                        "bandwidth_hz",
                    )
                    if key in run
                },
            }
            for run in runs
        ],
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return campaign, runs, digest


class JsonLineConnection:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.reader = sock.makefile("r", encoding="utf-8", newline="\n")
        self.writer = sock.makefile("w", encoding="utf-8", newline="\n")

    def send(self, message: dict[str, Any]) -> None:
        self.writer.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.writer.flush()

    def receive(self) -> dict[str, Any]:
        line = self.reader.readline()
        if not line:
            raise ConnectionError("campaign peer closed the connection")
        message = json.loads(line)
        if not isinstance(message, dict):
            raise ValueError("campaign protocol message must be a JSON object")
        return message

    def close(self) -> None:
        self.reader.close()
        self.writer.close()
        self.sock.close()


def expect(message: dict[str, Any], message_type: str, *, run_id: int | None = None) -> None:
    if message.get("type") != message_type:
        raise RuntimeError(
            f"expected protocol message {message_type!r}, got {message.get('type')!r}: {message}"
        )
    if run_id is not None and int(message.get("run_id", -1)) != int(run_id):
        raise RuntimeError(
            f"protocol run mismatch: expected 0x{run_id:08X}, got {message.get('run_id')!r}"
        )


def run_name(run: dict[str, Any]) -> str:
    return f"run_{int(run['run_id']):08x}"
