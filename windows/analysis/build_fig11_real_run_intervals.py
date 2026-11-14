#!/usr/bin/env python3
"""Build Fig. 11 latency/PRR from real SF10/BW250 collision intervals.

A scene is a maximal time segment in the strict middle-five-business-second
window during which exactly ``k`` complete packet frames overlap. The segment
sweep is computed from the manifest schedules (the same interval definition
used by ``planned_collision_recovery_statistics``), so a planned collision
group remains in Fig. 11 even when the shared fine-sync database misses one or
more of its packets. PRR counts only the intersection with that database in
its denominator.

The script consumes the fine-sync-database receiver reports, reconstructs the
transmitted symbol truth from the manifest payload seed (per-node source config
for the simulated merged runs), and aggregates each decoder's recorded
post-DB runtime and PRR.  SER is retained only as an auxiliary CSV audit.
LoRaWAN and CIC timings are single-antenna (Ch0-only dechirp-FFT), matching
their paper definitions; MRC/PCube/MaLoRaGW/SP use the dual-channel signal.
Fig. 11(b) reports PRR as unique CRC-valid decoded payload identities divided
by min(planned packets in the collision scene, anonymous detected physical
candidates). Manifest collision groups select a time interval only; they do
not bind a physical candidate to a node.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECEIVER = ROOT / "real_collision_experiment/node01_sp_receiver"
for path in (ROOT, RECEIVER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from real_collision_experiment.control_usrp.protocol import (  # noqa: E402
    RunConfig,
    build_data_payload,
)
from real_collision_experiment.paper_experiments.simulate_sp_mechanisms import (  # noqa: E402
    encode_explicit_payload,
)
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.lora_phy_decode import (  # noqa: E402
    decode_hamming_word,
    deinterleave_explicit,
    gray_inverse_map,
)
from real_collision_experiment.paper_experiments.simulate_sp_mechanisms import (  # noqa: E402
    payload_nibbles,
)


METHODS = ("lorawan", "mrc", "cic", "pcube", "maloragw", "sp_sync_refine")
METHOD_LABELS = {
    "lorawan": "LoRaWAN",
    "mrc": "MRC",
    "cic": "CIC",
    "pcube": "PCube",
    "maloragw": "MaLoRaGW",
    "sp_sync_refine": "SP-Decoder",
}
METHOD_COLORS = {
    "lorawan": "#6C757D",
    "mrc": "#457B9D",
    "cic": "#E76F51",
    "pcube": "#F4A261",
    "maloragw": "#6C5CE7",
    "sp_sync_refine": "#159D8A",
}
METHOD_MARKERS = {
    "lorawan": "v",
    "mrc": "o",
    "cic": "s",
    "pcube": "^",
    "maloragw": "D",
    "sp_sync_refine": "*",
}
PRR_DENOMINATOR_SOURCE = (
    "min_manifest_collision_scene_expected_or_anonymous_detected_packets"
)
PRR_COUNTING_POLICY = (
    "unique_crc_valid_payload_identities_over_"
    "min_manifest_collision_scene_expected_or_anonymous_detected_packets"
)


def parse_orders(text: str) -> tuple[int, ...]:
    values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    if not values or any(value < 2 for value in values):
        raise argparse.ArgumentTypeError("orders must be comma-separated integers >=2")
    return values


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_config(manifest: dict) -> RunConfig:
    keys = {
        "run_id",
        "active_mask",
        "num_active_nodes",
        "phy_profile_id",
        "traffic_profile_id",
        "node_tx_power_dbm",
        "duration_ms",
        "warmup_ms",
        "global_seed",
        "payload_seed",
        "flags",
    }
    return RunConfig(
        **{key: int(value) for key, value in manifest["config"].items() if key in keys}
    )


def manifest_paths(runs_root: Path) -> list[Path]:
    paths = {
        path.stem: path.resolve()
        for path in (runs_root / "manifests").glob("run_*.json")
    }
    for run_dir in runs_root.glob("run_*"):
        candidate = run_dir / f"{run_dir.name}.json"
        if candidate.exists():
            paths[candidate.stem] = candidate.resolve()
    return [paths[name] for name in sorted(paths)]


def payload_bytes_for_identity(
    manifest: dict, node_id: int, sequence: int
) -> bytes:
    """Reproduce the exact transmitted payload of a scheduled packet.

    Merged runs carry per-node ``source_config`` / ``source_node_id`` so the
    physical payload (transmitted under the source run) is rebuilt exactly.
    """

    schedule = manifest.get("expected_node_schedules", {}).get(str(node_id), {})
    source_config = (
        schedule.get("source_config") if isinstance(schedule, dict) else None
    )
    source_node_id = (
        schedule.get("source_node_id") if isinstance(schedule, dict) else None
    )
    cfg_dict = (
        source_config if isinstance(source_config, dict) else manifest.get("config", {})
    )
    keys = {
        "run_id",
        "active_mask",
        "num_active_nodes",
        "phy_profile_id",
        "traffic_profile_id",
        "node_tx_power_dbm",
        "duration_ms",
        "warmup_ms",
        "global_seed",
        "payload_seed",
        "flags",
    }
    run_cfg = RunConfig(**{key: int(cfg_dict[key]) for key in keys})
    transmit_node_id = (
        int(source_node_id) if source_node_id is not None else int(node_id)
    )
    return build_data_payload(run_cfg, transmit_node_id, int(sequence))


def report_slice(report: dict) -> tuple[float, float]:
    row = report.get("input", {}).get("analysis_slice", {})
    start = float(row.get("start_time_s", 0.0))
    duration = float(
        row.get(
            "requested_duration_s",
            report.get("planned_crc_delivery_and_tps", {}).get("capture_duration_s", 0.0),
        )
    )
    if duration <= 0.0:
        raise ValueError("report does not contain a positive analysis-slice duration")
    return start, duration


def method_row(candidate: dict, method: str) -> dict | None:
    return next(
        (row for row in candidate.get("methods", []) if row.get("method") == method),
        None,
    )


def sp_identity(candidate: dict) -> tuple[int, int] | None:
    row = method_row(candidate, "sp_sync_refine")
    if row is None or not row.get("application", {}).get("app_crc_ok"):
        return None
    decoded = row["application"].get("decoded")
    if not isinstance(decoded, dict):
        return None
    return int(decoded["node_id"]), int(decoded["sequence"])


def decoded_identity(row: dict | None) -> tuple[int, int] | None:
    """Identity embedded in a decoder's CRC-valid payload, if any."""

    if row is None:
        return None
    app = row.get("application", {})
    if not bool(app.get("app_crc_ok", False)):
        return None
    decoded = app.get("decoded")
    if not isinstance(decoded, dict):
        return None
    node_id = decoded.get("node_id")
    sequence = decoded.get("sequence")
    if node_id is None or sequence is None:
        return None
    return int(node_id), int(sequence)


def infer_traffic_origin(report: dict, manifest: dict) -> tuple[float, dict]:
    strict = report.get("input", {}).get("strict_middle_business_window", {})
    if isinstance(strict, dict) and bool(strict.get("enabled")):
        origin = float(strict["traffic_start_s_from_full_iq"]) - float(
            strict["analysis_start_s_from_full_iq"]
        )
        return origin, {
            "traffic_origin_relative_to_slice_s": origin,
            "source": "strict_middle_business_window_audit",
            "manifest_or_cross_machine_utc_used": False,
        }
    raise ValueError(
        "report lacks a strict business-window audit; packet identities and "
        "manifest schedules are forbidden for traffic-origin calibration"
    )


def planned_events(manifest: dict, frame_s: float) -> list[dict]:
    events: list[dict] = []
    active = {int(value) for value in manifest.get("active_nodes", [])}
    for node_id in sorted(active):
        starts = manifest.get("expected_node_schedules", {}).get(str(node_id), {}).get(
            "tx_start_ms_from_traffic_begin", []
        )
        for sequence, start_ms in enumerate(starts):
            start = float(start_ms) / 1000.0
            events.append(
                {
                    "identity": (node_id, int(sequence)),
                    "start_traffic_s": start,
                    "end_traffic_s": start + frame_s,
                }
            )
    for target in events:
        overlaps = [
            other
            for other in events
            if max(target["start_traffic_s"], other["start_traffic_s"])
            < min(target["end_traffic_s"], other["end_traffic_s"])
        ]
        target["collision_order"] = len(overlaps)
        target["overlap_identities"] = [other["identity"] for other in overlaps]
    return events


def candidate_crc_identity(candidate: dict) -> tuple[int, int] | None:
    """Return an identity only when a CRC-valid decoder payload provides it."""

    identities = {
        identity
        for method in METHODS
        if (identity := decoded_identity(method_row(candidate, method))) is not None
    }
    return next(iter(identities)) if len(identities) == 1 else None


def scene_candidates(
    report: dict,
    *,
    start_slice_s: float,
    end_slice_s: float,
    frame_s: float,
) -> list[dict]:
    """Return anonymous candidates whose physical frames overlap this scene."""

    return [
        candidate
        for candidate in report.get("candidates", [])
        if isinstance(candidate, dict)
        and float(candidate.get("start_time_s", math.inf)) < end_slice_s
        and float(candidate.get("start_time_s", -math.inf)) + frame_s > start_slice_s
    ]


def symbol_errors_nibble(
    row: dict | None, truth_payload: bytes, cfg: RealCollisionLoRaConfig
) -> tuple[int, int]:
    """Symbol errors at the de-interleaved, pre-FEC nibble level.

    Raw bin-to-bin comparison is unreliable because several transmitted bin
    sequences can decode to the same payload (unused parity/padding bits in the
    tail), so a perfectly decoded packet can falsely score symbol errors.
    This metric follows the Fig. 11 convention: a packet that closes PHY/CRC
    scores zero symbol errors (FEC already restored the payload), while a
    failed packet is charged the de-interleaved pre-FEC nibble mismatch rate.
    The nibble-level comparison is used instead of raw bins because several
    transmitted bin sequences can decode to the same payload (unused tail
    bits), which would otherwise fabricate symbol errors on correct packets.
    """

    truth_nibbles = [1, 4, 3, 1, 7] + payload_nibbles(truth_payload, cfg)
    needed = len(truth_nibbles)
    if row is None:
        return needed, needed
    phy = row.get("phy", {})
    app = row.get("application", {})
    if bool(phy.get("phy_crc_ok", False)) or bool(app.get("app_crc_ok", False)):
        return 0, needed
    bins = [int(value) for value in row.get("symbol_bins", [])]
    if len(bins) < int(cfg.payload_symbol_count):
        return needed, needed
    inverse = gray_inverse_map(cfg)
    symbol_values = [
        inverse.get(int(bin_value) % int(cfg.m), 0)
        for bin_value in bins[: int(cfg.payload_symbol_count)]
    ]
    header_codewords, payload_codewords = deinterleave_explicit(symbol_values, cfg)
    errors = 0
    for index, word in enumerate(header_codewords[:5]):
        nibble, _, _ = decode_hamming_word(int(word), 4)
        errors += int(nibble != int(truth_nibbles[index]))
    for (word, cr_app), truth_nibble in zip(
        payload_codewords, truth_nibbles[5:]
    ):
        nibble, _, _ = decode_hamming_word(int(word), int(cr_app))
        errors += int(nibble != int(truth_nibble))
    return int(errors), needed


def bootstrap(values: list[float], seed: int) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(array))
    if array.size <= 1:
        return mean, mean, mean
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(20_000, array.size), replace=True)
    low, high = np.quantile(np.mean(samples, axis=1), [0.025, 0.975])
    return mean, float(low), float(high)


def aggregate(rows: list[dict], orders: tuple[int, ...], seed: int) -> list[dict]:
    output: list[dict] = []
    for order in orders:
        for method in METHODS:
            selected = [
                row
                for row in rows
                if int(row["collision_order"]) == order and row["method"] == method
            ]
            if not selected:
                continue
            sers = [float(row["ser"]) for row in selected]
            decoded_packet_count = sum(
                int(row["decoded_packet_count"]) for row in selected
            )
            fine_sync_detected_packet_count = sum(
                int(row["fine_sync_detected_packet_count"]) for row in selected
            )
            manifest_expected_packet_count = sum(
                int(row["planned_packet_count"]) for row in selected
            )
            prr_denominator_packet_count = sum(
                int(row["prr_denominator_packet_count"])
                for row in selected
            )
            times = [
                float(row["post_sp_time_ms"])
                for row in selected
                if row.get("post_sp_time_ms") not in (None, "")
            ]
            # SER is reported as a single mean per collision order (no CI).
            ser_mean = float(np.mean(sers)) if sers else math.nan
            ser_low = ser_high = ser_mean
            prr_mean = (
                float(decoded_packet_count) / prr_denominator_packet_count
                if prr_denominator_packet_count > 0
                else math.nan
            )
            if times:
                time_mean, time_low, time_high = bootstrap(
                    times, seed ^ (order << 12) ^ METHODS.index(method)
                )
            else:
                time_mean = time_low = time_high = math.nan
            output.append(
                {
                    "collision_order": order,
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "collision_scene_count": len(selected),
                    "timed_collision_scene_count": len(times),
                    "post_sp_time_mean_ms": time_mean,
                    "post_sp_time_ci95_low_ms": time_low,
                    "post_sp_time_ci95_high_ms": time_high,
                    "ser_mean": ser_mean,
                    "ser_ci95_low": ser_low,
                    "ser_ci95_high": ser_high,
                    "prr_mean": prr_mean,
                    "decoded_packet_count": decoded_packet_count,
                    "fine_sync_detected_packet_count": (
                        fine_sync_detected_packet_count
                    ),
                    "manifest_expected_packet_count_in_collision_scenes": (
                        manifest_expected_packet_count
                    ),
                    "prr_denominator_packet_count": prr_denominator_packet_count,
                    "prr_denominator_source": PRR_DENOMINATOR_SOURCE,
                    "prr_counting_policy": PRR_COUNTING_POLICY,
                }
            )
    return output


def plot(summary: list[dict], out_prefix: Path, orders: tuple[int, ...]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.2))
    x = np.arange(len(orders), dtype=np.float64)
    width = 0.84 / len(METHODS)
    for method_index, method in enumerate(METHODS):
        lookup = {
            int(row["collision_order"]): row
            for row in summary
            if row["method"] == method
        }
        values = np.asarray(
            [float(lookup[order]["post_sp_time_mean_ms"]) for order in orders]
        )
        low = np.asarray(
            [float(lookup[order]["post_sp_time_ci95_low_ms"]) for order in orders]
        )
        high = np.asarray(
            [float(lookup[order]["post_sp_time_ci95_high_ms"]) for order in orders]
        )
        pos = x - 0.42 + width / 2 + method_index * width
        timed = np.isfinite(values) & np.isfinite(low) & np.isfinite(high)
        if np.any(timed):
            axes[0].bar(
                pos[timed],
                values[timed],
                width,
                yerr=np.vstack(
                    [values[timed] - low[timed], high[timed] - values[timed]]
                ),
                color=METHOD_COLORS[method],
                capsize=2,
                label=METHOD_LABELS[method],
            )
        prr = np.asarray([float(lookup[order]["prr_mean"]) for order in orders])
        axes[1].errorbar(
            orders,
            prr,
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            linestyle="-",
            capsize=0,
            label=METHOD_LABELS[method],
        )
    axes[0].set_xticks(x, [str(value) for value in orders])
    axes[0].set_xlabel("Packets in the target collision group")
    axes[0].set_ylabel("Estimation + decode time / collision scene (ms)")
    axes[1].set_xticks(orders)
    all_prr = [float(row["prr_mean"]) for row in summary]
    axes[1].set_ylim(-0.03, max(1.03, max(all_prr, default=1.0) + 0.03))
    axes[1].set_xlabel("Packets in the target collision group")
    axes[1].set_ylabel("PRR (unique decoded / min(planned, detected))")
    for axis in axes:
        axis.grid(alpha=0.24)
    axes[0].legend(ncol=2, fontsize=7.5, frameon=False)
    fig.tight_layout()
    for suffix in (".png", ".pdf", ".svg"):
        fig.savefig(out_prefix.with_suffix(suffix), dpi=240, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root", type=Path, default=ROOT / "real_collision_experiment/runs"
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=ROOT / "real_collision_experiment/analysis/fig9_10_12_preview/reports",
    )
    parser.add_argument(
        "--fine-sync-dir",
        type=Path,
        default=ROOT
        / "real_collision_experiment/analysis/fig9_10_12_preview/fine_sync",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "real_usrp_outputs/fig11_real_run_intervals",
    )
    parser.add_argument("--orders", type=parse_orders, default=(4, 8, 12, 16))
    parser.add_argument("--scenes-per-order", type=int, default=50)
    parser.add_argument("--sf", type=int, default=10)
    parser.add_argument("--bandwidth-hz", type=int, default=250_000)
    parser.add_argument("--seed", type=int, default=20260803)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    candidates_by_order: dict[int, list[dict]] = defaultdict(list)
    alignments: dict[str, dict] = {}
    skipped: list[dict] = []
    for manifest_path in manifest_paths(args.runs_root):
        manifest = load_json(manifest_path)
        if manifest.get("experiment", {}).get("figure") != "fig9_10":
            continue
        radio = manifest.get("radio", {})
        config = manifest.get("config", {})
        sf = int(radio.get("spreading_factor", config.get("sf", 0)) or 0)
        bw = int(radio.get("bandwidth_hz", config.get("bandwidth_hz", 0)) or 0)
        if sf != args.sf or bw != args.bandwidth_hz:
            continue
        run_name = manifest_path.stem
        report_path = args.reports / f"{run_name}.json"
        if not report_path.exists():
            skipped.append({"run": run_name, "reason": "formal report missing"})
            continue
        report = load_json(report_path)
        decoder = report.get("decoder", {})
        if decoder.get("comparison_frontend_scope") != "common":
            skipped.append({"run": run_name, "reason": "report is not common-SP mode"})
            continue
        if decoder.get("shared_sp_parameters") != [
            "anonymous_physical_candidate",
            "pre_payload_fine_start_sample",
            "CFO",
            "STO",
        ]:
            skipped.append(
                {
                    "run": run_name,
                    "reason": (
                        "stale report: regenerate after the final shared-SP-fine-sync "
                        "decoder revision"
                    ),
                }
            )
            continue
        fine_db_path = args.fine_sync_dir / f"{run_name}.json"
        if not fine_db_path.exists():
            skipped.append({"run": run_name, "reason": "fine-sync DB missing"})
            continue
        fine_db = load_json(fine_db_path)
        if fine_db.get("schema") != "fine_sync_anonymous_physical_v2":
            skipped.append(
                {"run": run_name, "reason": "fine-sync DB is not global anonymous physical v2"}
            )
            continue
        discovery = fine_db.get("candidate_discovery", {})
        if (
            discovery.get("scope") != "global_full_window"
            or discovery.get("manifest_schedule_exposed_to_detector") is not False
            or discovery.get("node_timing_calibration") is not False
            or discovery.get("planned_start_search_windows") is not False
            or discovery.get("score_truncation") is not False
        ):
            skipped.append(
                {"run": run_name, "reason": "fine-sync DB used schedule-guided discovery"}
            )
            continue
        db_packets = fine_db.get("packets", [])
        if not isinstance(db_packets, list) or not db_packets or any(
            not isinstance(row, dict)
            or row.get("node_id") is not None
            or row.get("sequence") is not None
            for row in db_packets
        ):
            skipped.append(
                {"run": run_name, "reason": "fine-sync DB has no valid anonymous candidates"}
            )
            continue
        try:
            slice_start_s, slice_duration_s = report_slice(report)
            origin, alignment = infer_traffic_origin(report, manifest)
        except ValueError as exc:
            skipped.append({"run": run_name, "reason": str(exc)})
            continue
        db_window = fine_db.get("window", {})
        db_start_s = float(db_window.get("analysis_start_s", math.nan))
        db_duration_s = float(db_window.get("duration_s", math.nan))
        if not (
            math.isfinite(db_start_s)
            and math.isfinite(db_duration_s)
            and abs(slice_start_s - db_start_s) <= 1e-6
            and abs(slice_duration_s - db_duration_s) <= 1e-6
            and abs(db_duration_s - 5.0) <= 1e-6
        ):
            skipped.append(
                {
                    "run": run_name,
                    "reason": (
                        "report/fine-sync DB window mismatch; regenerate the "
                        "strict middle-5-second report after rebuilding the DB"
                    ),
                }
            )
            continue
        report_candidates = [
            row for row in report.get("candidates", []) if isinstance(row, dict)
        ]
        if len(report_candidates) != len(db_packets):
            skipped.append(
                {
                    "run": run_name,
                    "reason": (
                        "stale report does not cover all anonymous fine-sync DB entries "
                        f"({len(report_candidates)} != {len(db_packets)})"
                    ),
                }
            )
            continue
        alignments[run_name] = alignment
        cfg = RealCollisionLoRaConfig(
            sf=sf,
            bw_hz=float(bw),
            sample_rate_hz=float(report.get("config", {}).get("sample_rate_hz", 750_000)),
        )
        frame_s = float(cfg.frame_samples) / float(cfg.sample_rate_hz)
        intervals: list[tuple[tuple[int, int], float, float]] = []
        relative_window_start_s = -float(origin)
        relative_window_end_s = relative_window_start_s + float(slice_duration_s)
        for node_text, schedule in manifest.get("expected_node_schedules", {}).items():
            if not isinstance(schedule, dict):
                continue
            node_id = int(node_text)
            for sequence, start_ms in enumerate(
                schedule.get("tx_start_ms_from_traffic_begin", [])
            ):
                start = float(start_ms) / 1000.0
                if (
                    relative_window_start_s <= start
                    and start + frame_s <= relative_window_end_s
                ):
                    identity = (node_id, int(sequence))
                    intervals.append((identity, start, start + frame_s))
        # A scene is a target-centric collision group: the target complete frame
        # plus every other complete frame whose interval overlaps it, exactly
        # ``k`` frames in total.  The scene spans from the first member frame's
        # start to the last member frame's end.
        seen_groups: set[tuple[tuple[int, int], ...]] = set()
        for target_identity, target_start, target_end in intervals:
            overlaps = [
                identity
                for identity, start, end in intervals
                if identity != target_identity
                and max(target_start, start) < min(target_end, end)
            ]
            order = len(overlaps) + 1
            if order not in args.orders:
                continue
            active = tuple(sorted([target_identity] + overlaps))
            if active in seen_groups:
                continue
            seen_groups.add(active)
            left = min(
                interval[1]
                for interval in intervals
                if interval[0] in active
            )
            right = max(
                interval[2]
                for interval in intervals
                if interval[0] in active
            )
            candidates_by_order[order].append(
                {
                    "run_name": run_name,
                    "manifest": manifest,
                    "report": report,
                    "collision_order": int(order),
                    "active_identities": active,
                    "segment_start_slice_s": origin + left,
                    "segment_end_slice_s": origin + right,
                }
            )

    selected_scenes: list[dict] = []
    missing_orders: list[int] = []
    for order in args.orders:
        rows = sorted(
            candidates_by_order.get(order, []),
            key=lambda row: (
                row["run_name"],
                row["segment_start_slice_s"],
                row["segment_end_slice_s"],
            ),
        )
        if not rows:
            missing_orders.append(order)
            continue
        seen_segments: set[tuple] = set()
        unique_rows = []
        for row in rows:
            key = (
                row["run_name"],
                round(row["segment_start_slice_s"], 5),
                round(row["segment_end_slice_s"], 5),
                row["active_identities"],
            )
            if key in seen_segments:
                continue
            seen_segments.add(key)
            unique_rows.append(row)
        rows = unique_rows
        if len(rows) < args.scenes_per_order:
            print(
                f"NOTE order {order}: only {len(rows)} scenes available "
                f"(requested {args.scenes_per_order})",
                flush=True,
            )
        selected_scenes.extend(rows[: args.scenes_per_order])

    raw_rows: list[dict] = []
    interval_rows: list[dict] = []
    for scene_index, scene in enumerate(selected_scenes, start=1):
        manifest = scene["manifest"]
        group_identities = scene["active_identities"]
        collision_order = int(scene["collision_order"])
        cfg = RealCollisionLoRaConfig(
            sf=int(manifest["radio"]["spreading_factor"]),
            bw_hz=float(manifest["radio"]["bandwidth_hz"]),
            sample_rate_hz=float(manifest["radio"]["sample_rate_hz"]),
        )
        scene_frame_s = float(cfg.frame_samples) / float(cfg.sample_rate_hz)
        truths = {
            identity: payload_bytes_for_identity(
                manifest, identity[0], identity[1]
            )
            for identity in group_identities
        }
        anonymous_candidates = scene_candidates(
            scene["report"],
            start_slice_s=float(scene["segment_start_slice_s"]),
            end_slice_s=float(scene["segment_end_slice_s"]),
            frame_s=scene_frame_s,
        )
        report_start_s, _ = report_slice(scene["report"])
        interval_start = report_start_s + float(scene["segment_start_slice_s"])
        interval_end = report_start_s + float(scene["segment_end_slice_s"])
        sp_candidate_count = len(anonymous_candidates)
        fine_sync_detected_packet_count = len(anonymous_candidates)
        interval_rows.append(
            {
                "scene_index": scene_index,
                "run": scene["run_name"],
                "collision_order": collision_order,
                "planned_packet_count": len(group_identities),
                "fine_sync_detected_packet_count": fine_sync_detected_packet_count,
                "full_capture_start_s": interval_start,
                "full_capture_end_s": interval_end,
                "duration_s": interval_end - interval_start,
                "collision_group_identities": ";".join(
                    f"{node}:{sequence}" for node, sequence in group_identities
                ),
                "sp_candidate_count": sp_candidate_count,
                "anonymous_detected_candidate_count": fine_sync_detected_packet_count,
            }
        )
        for method in METHODS:
            symbol_error_count = 0
            symbol_count = 0
            decode_times: list[float] = []
            estimation_times: list[float] = []
            total_times: list[float] = []
            timed_packet_count = 0
            timing_complete = True
            for candidate in anonymous_candidates:
                row = method_row(candidate, method) if candidate is not None else None
                identity = candidate_crc_identity(candidate)
                truth = truths.get(identity) if identity is not None else None
                errors, count = (
                    symbol_errors_nibble(row, truth, cfg)
                    if truth is not None
                    else (0, 0)
                )
                symbol_error_count += errors
                symbol_count += count
                decode_ms = None if row is None else row.get("decode_elapsed_ms")
                estimation_ms = (
                    None if row is None else row.get("parameter_estimation_elapsed_ms")
                )
                total_ms = None if row is None else row.get("post_sp_total_elapsed_ms")
                if total_ms is None and decode_ms is not None:
                    total_ms = float(decode_ms) + float(estimation_ms or 0.0)
                if decode_ms is not None:
                    decode_times.append(float(decode_ms))
                if estimation_ms is not None:
                    estimation_times.append(float(estimation_ms))
                if total_ms is None:
                    timing_complete = False
                else:
                    total_times.append(float(total_ms))
                    timed_packet_count += 1
            decoded_identities = {
                identity
                for candidate in anonymous_candidates
                if (
                    identity := decoded_identity(method_row(candidate, method))
                ) is not None
            }
            decoded_packet_count = len(decoded_identities)
            prr_denominator_packet_count = min(
                len(group_identities), fine_sync_detected_packet_count
            )
            raw_rows.append(
                {
                    "scene_index": scene_index,
                    "run": scene["run_name"],
                    "collision_order": collision_order,
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "packet_count": fine_sync_detected_packet_count,
                    "decoded_packet_count": decoded_packet_count,
                    "fine_sync_detected_packet_count": fine_sync_detected_packet_count,
                    "prr_denominator_packet_count": prr_denominator_packet_count,
                    # Compatibility alias for consumers of the previous CSV.
                    "prr_packet_count": prr_denominator_packet_count,
                    "prr_denominator_source": PRR_DENOMINATOR_SOURCE,
                    "prr_counting_policy": PRR_COUNTING_POLICY,
                    "symbol_error_count": symbol_error_count,
                    "symbol_count": symbol_count,
                    "ser": float(symbol_error_count) / max(1, symbol_count),
                    "decode_time_ms": sum(decode_times) if total_times else None,
                    "parameter_estimation_time_ms": (
                        sum(estimation_times) if total_times else None
                    ),
                    "post_sp_time_ms": sum(total_times) if total_times else None,
                    "timing_complete_for_collision_group": timing_complete,
                    "timed_packet_count": timed_packet_count,
                    "sp_candidate_count": sp_candidate_count,
                }
            )

    summary = aggregate(raw_rows, args.orders, args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "fig11_real_collision_intervals.csv", interval_rows)
    write_csv(args.out_dir / "fig11_real_decoder_time_ser_raw.csv", raw_rows)
    write_csv(args.out_dir / "fig11_real_decoder_time_ser_summary.csv", summary)
    if not missing_orders:
        plot(summary, args.out_dir / "fig11_real_decoder_time_ser", args.orders)
    audit = {
        "schema": "fig11_real_sf10_bw250_intervals_v4",
        "collision_order_definition": (
            "target-centric collision group inside the strict "
            "middle-5-business-second window: the target complete frame plus "
            "every other complete frame whose interval overlaps it, exactly k "
            "frames in total; the scene spans from the first member frame's "
            "start to the last member frame's end"
        ),
        "instantaneous_concurrency_interpretation": False,
        "sf": args.sf,
        "bandwidth_hz": args.bandwidth_hz,
        "requested_orders": list(args.orders),
        "missing_orders": missing_orders,
        "selected_interval_count": len(interval_rows),
        "alignments": alignments,
        "skipped_runs": skipped,
        "scene_selection": (
            "manifest-schedule segment sweep inside the 5s window; every planned "
            "collision group of a requested order is eligible. The matching anonymous "
            "physical candidates are selected only by temporal frame overlap with that scene"
        ),
        "candidate_matching": (
            "no planned start or node identity is attached to an anonymous candidate; "
            "all candidates whose physical frames overlap the preselected scene are "
            "included, and payload truth is available only after a CRC-valid decoder "
            "payload supplies one unambiguous identity"
        ),
        "truth_source": "manifest payload seed encoded by the formal LoRa PHY encoder",
        "timing_scope": (
            "sum over every candidate with a recorded post-shared-SP runtime in the "
            "selected collision group; packets without an associated/timed candidate "
            "contribute no post-DB decoder work and are recorded by timed_packet_count "
            "and timing_complete_for_collision_group; includes each method's parameter "
            "estimation plus payload decoding; "
            "LoRaWAN and CIC use Ch0-only single-antenna dechirp-FFT timing"
        ),
        "prr_scope": (
            "Fig. 11(b) uses PRR = unique CRC-valid payload identities / "
            "min(manifest planned packets, anonymous detected physical candidates) "
            "within selected collision scenes. Counts are pooled per collision order "
            "and method before division; SER is kept in the raw/summary CSVs for reference"
        ),
        "summary": summary,
    }
    (args.out_dir / "fig11_real_run_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"FIG11_REAL_DONE intervals={len(interval_rows)} missing_orders={missing_orders} "
        f"out={args.out_dir}",
        flush=True,
    )
    if missing_orders:
        raise SystemExit(
            "no complete decoded interval for collision orders: "
            + ",".join(str(value) for value in missing_orders)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
