#!/usr/bin/env python3
"""Deterministic no-network schedule shared by the RX and control computers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ScheduledRun:
    run: dict[str, Any]
    start_offset_s: float
    position_pause_before_s: float


def position_key(run: dict[str, Any]) -> str | None:
    value = run.get("tags", {}).get("position_index")
    return str(value) if value not in (None, "") else None


def build_schedule(
    runs: list[dict[str, Any]],
    *,
    slot_s: float,
    position_pause_s: float,
) -> list[ScheduledRun]:
    """Assign absolute offsets without accumulating command/capture runtime."""
    result: list[ScheduledRun] = []
    next_offset = 0.0
    previous_position: str | None = None
    for run in runs:
        current_position = position_key(run)
        pause = 0.0
        # The first selected Fig.12 run is positioned before the two scripts
        # start. Insert a break only between selected runs (or at the transition
        # from preceding scale runs into Fig.12).
        if (
            current_position is not None
            and current_position != previous_position
            and result
        ):
            pause = float(position_pause_s)
            next_offset += pause
        result.append(
            ScheduledRun(
                run=run,
                start_offset_s=next_offset,
                position_pause_before_s=pause,
            )
        )
        next_offset += float(slot_s)
        if current_position is not None:
            previous_position = current_position
    return result


def wait_until(
    deadline: float,
    *,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    remaining = deadline - monotonic()
    if remaining > 0:
        sleep(remaining)
    return monotonic() - deadline


def placement_message(run: dict[str, Any]) -> str:
    tags = run.get("tags", {})
    phase = str(run.get("phase", ""))
    if phase == "fig15_near_far":
        return (
            f"Fig.15 position {tags.get('position_index')}: keep Node A at "
            f"{tags.get('node_a_distance_m')} m from the gateway; move Node B to "
            f"{tags.get('node_b_distance_m')} m from the gateway "
            f"(next run mode={tags.get('mode')})"
        )
    return (
        f"Fig.12 position {tags.get('position_index')}: keep Node01 at "
        f"{tags.get('node1_distance_m')} m; move Node02 to "
        f"{tags.get('node2_distance_m')} m on bearing {tags.get('bearing_deg')} deg "
        f"(separation {tags.get('node_separation_m')} m)"
    )
