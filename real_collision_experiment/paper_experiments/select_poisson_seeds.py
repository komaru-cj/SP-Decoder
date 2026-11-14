#!/usr/bin/env python3
"""Search reproducible Poisson seeds that contain useful real collisions.

This follows the CONFIG v2 duty-profile firmware.  The script reproduces the
firmware scheduler, ranks seeds by the number of packets that
belong to the requested collision orders, and prints controller-ready seeds.
The resulting schedule is planning information only; it is never passed to
the RF detector or decoder.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL_DIR = ROOT / "real_collision_experiment" / "control_usrp"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from protocol import (  # noqa: E402
    DEFAULT_PHY_PROFILE_ID,
    TRAFFIC_DUTY_CYCLES,
    RunConfig,
    active_nodes_to_mask,
    expected_tx_schedule_ms,
    firmware_time_on_air_ms,
    traffic_profile_id_from_duty,
)


def parse_nodes(text: str) -> list[int]:
    nodes: set[int] = set()
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            first, last = (int(value) for value in token.split("-", 1))
            nodes.update(range(first, last + 1))
        else:
            nodes.add(int(token))
    out = sorted(nodes)
    active_nodes_to_mask(out)
    return out


def parse_orders(text: str) -> set[int]:
    orders = {int(value) for value in text.split(",") if value.strip()}
    if not orders or min(orders) < 1:
        raise argparse.ArgumentTypeError("collision orders must be positive integers")
    return orders


def build_config(args: argparse.Namespace, global_seed: int) -> RunConfig:
    return RunConfig(
        run_id=args.run_id,
        active_mask=active_nodes_to_mask(args.active_nodes),
        num_active_nodes=len(args.active_nodes),
        phy_profile_id=args.phy_profile_id,
        traffic_profile_id=traffic_profile_id_from_duty(args.per_node_duty_cycle),
        node_tx_power_dbm=args.node_tx_power,
        duration_ms=round(args.duration_s * 1000),
        warmup_ms=round(args.warmup_s * 1000),
        global_seed=global_seed & 0xFFFFFFFF,
        payload_seed=args.payload_seed & 0xFFFFFFFF,
    )


def schedule_rows(config: RunConfig, nodes: list[int]) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for node_id in nodes:
        for sequence, start_ms in enumerate(expected_tx_schedule_ms(config, node_id)):
            rows.append(
                {
                    "node_id": node_id,
                    "sequence": sequence,
                    "start_ms": start_ms,
                    "end_ms": start_ms + firmware_time_on_air_ms(config),
                }
            )
    rows.sort(key=lambda row: (row["start_ms"], row["node_id"], row["sequence"]))
    return rows


def add_collision_orders(rows: list[dict[str, int]]) -> None:
    """Label each packet by the maximum simultaneous order during its airtime."""

    if not rows:
        return
    starts = [row["start_ms"] for row in rows]
    toa_ms = int(rows[0]["end_ms"] - rows[0]["start_ms"])
    # Concurrent order immediately after each distinct start. bisect_right
    # includes every packet sharing that start and excludes packets whose
    # half-open interval ended exactly at it.
    concurrency = [
        bisect.bisect_right(starts, start)
        - bisect.bisect_right(starts, start - toa_ms)
        for start in starts
    ]
    # A packet's maximum order is the range maximum of concurrency at packet
    # starts occurring during its airtime.  The monotonic deque evaluates all
    # equal-length sliding time windows in O(packet_count).
    maxima = [1] * len(rows)
    candidates: deque[int] = deque()
    right = 0
    for left, start in enumerate(starts):
        end = start + toa_ms
        while right < len(rows) and starts[right] < end:
            while candidates and concurrency[candidates[-1]] <= concurrency[right]:
                candidates.pop()
            candidates.append(right)
            right += 1
        while candidates and candidates[0] < left:
            candidates.popleft()
        maxima[left] = concurrency[candidates[0]] if candidates else concurrency[left]
    for row, maximum in zip(rows, maxima):
        row["collision_order"] = int(maximum)


def seed_statistics(config: RunConfig, nodes: list[int], wanted: set[int]) -> dict:
    rows = schedule_rows(config, nodes)
    add_collision_orders(rows)
    counts: dict[int, int] = {}
    for row in rows:
        order = row["collision_order"]
        counts[order] = counts.get(order, 0) + 1
    wanted_hits = sum(counts.get(order, 0) for order in wanted)
    wanted_coverage = sum(1 for order in wanted if counts.get(order, 0) > 0)
    # Coverage is ranked before raw count so a seed with several requested
    # orders is more useful than one dominated by a single order.
    score = (wanted_coverage, wanted_hits, max(counts, default=0))
    return {
        "global_seed": config.global_seed,
        "packet_count": len(rows),
        "collision_packet_count": sum(value for order, value in counts.items() if order >= 2),
        "collision_fraction": (
            sum(value for order, value in counts.items() if order >= 2) / len(rows)
            if rows
            else 0.0
        ),
        "packets_by_collision_order": {str(key): counts[key] for key in sorted(counts)},
        "_score": score,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--active-nodes", type=parse_nodes, required=True)
    parser.add_argument("--per-node-duty-cycle", type=float, choices=TRAFFIC_DUTY_CYCLES, required=True)
    parser.add_argument("--phy-profile-id", type=int, default=DEFAULT_PHY_PROFILE_ID)
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--warmup-s", type=float, default=5.0)
    parser.add_argument("--node-tx-power", type=int, default=10)
    parser.add_argument("--payload-seed", type=lambda value: int(value, 0), default=0x22222222)
    parser.add_argument("--seed-start", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--seed-count", type=int, default=2000)
    parser.add_argument("--target-orders", type=parse_orders, default=parse_orders("2,3,4"))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ranked: list[dict] = []
    for offset in range(max(1, args.seed_count)):
        seed = (args.seed_start + offset) & 0xFFFFFFFF
        config = build_config(args, seed)
        config.validate()
        ranked.append(seed_statistics(config, args.active_nodes, args.target_orders))
    ranked.sort(key=lambda row: (row["_score"], -row["global_seed"]), reverse=True)

    selected = []
    for row in ranked[: max(1, args.top)]:
        clean = {key: value for key, value in row.items() if key != "_score"}
        clean["controller_seed_argument"] = f"--global-seed 0x{row['global_seed']:08X}"
        selected.append(clean)
    result = {
        "schema": "sp_poisson_seed_search_v1",
        "run_id": f"0x{args.run_id:08X}",
        "active_nodes": args.active_nodes,
        "per_node_duty_cycle": args.per_node_duty_cycle,
        "duration_s": args.duration_s,
        "payload_seed": f"0x{args.payload_seed:08X}",
        "target_collision_orders": sorted(args.target_orders),
        "searched_seed_count": max(1, args.seed_count),
        "selected": selected,
        "warning": (
            "Schedules reproduce firmware planning but are not detector input or exact RF TX ground truth."
        ),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
