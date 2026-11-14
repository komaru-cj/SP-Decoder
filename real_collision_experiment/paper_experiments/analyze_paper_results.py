#!/usr/bin/env python3
"""Aggregate paper receiver reports and calibrated-AWGN sweeps.

The ``reports`` subcommand consumes a small CSV index so experimental labels
remain outside the decoder. Every plotted PRR is the Fig.9/10 metric
``unique decoded / min(planned, detected)`` over the strict five-second
business window; inputs without that audit are rejected rather than silently
relabelled. It writes tidy CSV files and compact
figures for packet detection, PRR, payload goodput, collision order, near-far
weak-node recovery, and the SP-core/sync-refine ablation.

The ``awgn`` subcommand combines multiple noise seeds produced by
``evaluate_awgn_prr_sweep.py`` and plots decoder PRR versus measured SNR.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_matplotlib")

import matplotlib.pyplot as plt
import numpy as np

FORMAL_METHODS = (
    "sp_sync_refine",
    "mrc",
    "mrc_cic",
    "pcube",
    "maloragw",
)
END_TO_END_METHODS = ("ch0",) + FORMAL_METHODS
RUNTIME_METHODS = ("mrc_cic", "pcube", "maloragw", "sp_sync_refine")
ABLATION_METHODS = ("mrc", "sp_core", "sp_sync_refine", "sp_repair")
METHOD_LABELS = {
    "ch0": "Standard LoRaWAN",
    "sp_core": "SP-core",
    "sp_sync_refine": "SP-Decoder",
    "sp_repair": "SP+repair",
    "mrc": "MRC",
    "mrc_cic": "MRC+CIC",
    "pcube": "PCube-2Rx",
    "maloragw": "MaLoRaGW-2Rx",
}
EXPERIMENT_XLABELS = {
    "scale_n": "Active nodes N",
    "load_g": "Aggregate offered load G",
    "near_far": "Strong-minus-weak received-power gap (dB)",
}
PAYLOAD_BYTES = 20
SHARED_PRR_SOURCE = "min_manifest_window_expected_or_anonymous_detected_packets"
SHARED_PRR_POLICY = (
    "unique_crc_valid_payload_identities_over_"
    "min_manifest_window_expected_or_anonymous_detected_packets"
)


def validated_shared_prr(values: dict, report_path: Path, method: str) -> tuple[int, int, int, float]:
    """Return D, decoded, denominator, and PRR after enforcing Fig.9/10 semantics."""

    if values.get("execution_status", "completed") != "completed":
        raise ValueError(f"{report_path}: method {method} was not formally completed")
    if values.get("prr_denominator_source") != SHARED_PRR_SOURCE:
        raise ValueError(f"{report_path}: method {method} does not use shared fine-sync D")
    if values.get("prr_counting_policy") != SHARED_PRR_POLICY:
        raise ValueError(f"{report_path}: method {method} has incompatible PRR counting policy")
    try:
        detected = int(values["complete_detected_packet_count"])
        decoded = int(values["decoded_success_count"])
        denominator = int(values["prr_denominator_packet_count"])
        planned = int(values["manifest_expected_packet_count_in_analysis_window"])
        prr = float(values["prr"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{report_path}: method {method} lacks shared fine-sync PRR counters") from exc
    if min(detected, decoded, denominator) < 0:
        raise ValueError(f"{report_path}: method {method} has negative PRR counters")
    if decoded > min(planned, detected) or denominator != min(planned, detected):
        raise ValueError(
            f"{report_path}: method {method} has inconsistent min(planned, detected) counters"
        )
    if denominator <= 0 or not math.isfinite(prr) or abs(prr - decoded / denominator) > 1e-9:
        raise ValueError(f"{report_path}: method {method} has inconsistent PRR value")
    return detected, decoded, denominator, prr


def report_payload_goodput_kbps(values: dict) -> float | None:
    """Read the new metric or derive it from legacy packets/s reports."""
    goodput = values.get("payload_goodput_kbps")
    if goodput is not None:
        return float(goodput)
    packets_per_s = values.get("tps_business_s")
    if packets_per_s is None:
        return None
    return float(packets_per_s) * PAYLOAD_BYTES * 8 / 1000.0


def complex_vector(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(real, imag) for real, imag in values], dtype=np.complex128)


def complex_matrix(values: list[list[list[float]]]) -> np.ndarray:
    return np.asarray(
        [[complex(real, imag) for real, imag in row] for row in values],
        dtype=np.complex128,
    )


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_index(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"experiment", "x_value", "x_label", "report"}
    missing = required - set(rows[0] if rows else {})
    if missing:
        raise ValueError(f"index is missing columns: {sorted(missing)}")
    return rows


def app_identity(method_row: dict) -> tuple[int, int] | None:
    app = method_row.get("application", {})
    decoded = app.get("decoded")
    if not app.get("app_crc_ok") or not isinstance(decoded, dict):
        return None
    return int(decoded["node_id"]), int(decoded["sequence"])


def candidate_method(candidate: dict, name: str) -> dict | None:
    return next(
        (row for row in candidate.get("methods", []) if row.get("method") == name),
        None,
    )


def candidate_analysis_identity(candidate: dict) -> tuple[int, int] | None:
    """Choose an offline identity for schedule matching without decoder oracle input."""
    sp_row = candidate_method(candidate, "sp_sync_refine")
    sp_identity = app_identity(sp_row) if sp_row is not None else None
    if sp_identity is not None:
        return sp_identity
    identities = []
    for method in END_TO_END_METHODS:
        row = candidate_method(candidate, method)
        identity = app_identity(row) if row is not None else None
        if identity is not None:
            identities.append(identity)
    if not identities:
        return None
    counts = Counter(identities)
    return min(counts, key=lambda identity: (-counts[identity], identity))


def bootstrap_mean(values: list[float], rng: np.random.Generator) -> tuple[float, float, float]:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if finite.size == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(np.mean(finite))
    if finite.size == 1:
        return mean, mean, mean
    samples = rng.choice(finite, size=(4000, finite.size), replace=True)
    distribution = np.mean(samples, axis=1)
    low, high = np.percentile(distribution, [2.5, 97.5])
    return mean, float(low), float(high)


def report_rows(index_rows: list[dict[str, str]]) -> tuple[list[dict], list[dict], list[dict]]:
    runs: list[dict] = []
    methods: list[dict] = []
    packets: list[dict] = []
    for index_row in index_rows:
        report_path = Path(index_row["report"]).expanduser()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        detection = report.get("detection_and_decode", {})
        planned = report.get("planned_crc_delivery_and_tps", {})
        planned_methods = planned.get("by_method", {})
        business_s = detection.get("business_duration_s")
        expected = detection.get("expected_packet_count")
        complete = detection.get("complete_detected_packet_count", 0)
        observed_nodes = {
            int(row["node_id"])
            for row in report.get("unique_protocol_valid_before_filters", [])
            if isinstance(row, dict) and "node_id" in row
        }
        active_nodes = {int(node) for node in report.get("active_nodes", [])}
        zero_observed_active_nodes = sorted(active_nodes - observed_nodes)
        run_key = {
            "experiment": index_row["experiment"],
            "x_value": float(index_row["x_value"]),
            "x_label": index_row["x_label"],
            "report": str(report_path),
            "run_id": report.get("run_id"),
            "nodes": index_row.get("nodes", len(report.get("active_nodes", []))),
            "offered_load": index_row.get("offered_load", ""),
            "seed": index_row.get("seed", ""),
            "power_gap_db": index_row.get("power_gap_db", ""),
            "weak_node": index_row.get("weak_node", ""),
            "layout": index_row.get("layout", ""),
            "zero_observed_active_nodes": ",".join(
                str(node) for node in zero_observed_active_nodes
            ),
            "node_outage_review_required": bool(zero_observed_active_nodes),
            "zero_node_metric_policy": (
                "included_unmodified_in_planned_prr_and_measured_throughput"
            ),
        }
        runs.append(
            {
                **run_key,
                "expected_packets": expected,
                "complete_detected_packets": complete,
                "packet_detection_rate": (
                    float(complete) / float(expected) if expected not in (None, 0) else ""
                ),
                "business_duration_s": business_s,
                "capture_warning_count": len(report.get("capture_warnings", [])),
            }
        )
        for name, values in detection.get("by_method", {}).items():
            if name == "sp":
                continue
            target_count, decoded_count, denominator_count, prr = validated_shared_prr(
                values, report_path, name
            )
            planned_values = planned_methods.get(name, {})
            methods.append(
                {
                    **run_key,
                    "method": name,
                    "method_label": METHOD_LABELS.get(name, name),
                    "execution_status": "completed",
                    "frontend_scope": values.get("frontend_scope", "common_frontend"),
                    "successes": int(decoded_count),
                    "complete_targets": int(target_count),
                    "prr_denominator_packets": denominator_count,
                    "conditional_prr": prr,
                    "tps_bps": values.get("decoded_success_tps"),
                    "end_to_end_prr": planned_values.get("planned_crc_delivery_ratio"),
                    "throughput_bps": values.get("decoded_success_tps"),
                    "payload_goodput_kbps": report_payload_goodput_kbps(values),
                    "expected_packets": planned_values.get("expected_tx_count"),
                }
            )

        planned_orders = {
            (int(row["node_id"]), int(row["sequence"])): int(row["collision_order"])
            for row in report.get("planned_collision_recovery", {}).get(
                "collision_order_by_identity", []
            )
        }
        for candidate in report.get("candidates", []):
            target = candidate_analysis_identity(candidate)
            planned_order = planned_orders.get(target) if target is not None else None
            estimated_order = 1 + int(candidate.get("overlapping_interferer_count_sp", 0))
            for name in set(FORMAL_METHODS) | set(ABLATION_METHODS):
                row = candidate_method(candidate, name)
                identity = app_identity(row) if row is not None else None
                packets.append(
                    {
                        **run_key,
                        "candidate_id": candidate.get("candidate_id"),
                        "target_node": target[0] if target else "",
                        "target_sequence": target[1] if target else "",
                        "collision_order": planned_order or estimated_order,
                        "collision_order_source": (
                            "manifest_schedule" if planned_order is not None else "frontend_estimate"
                        ),
                        "method": name,
                        "method_label": METHOD_LABELS.get(name, name),
                        "success": int(target is not None and identity == target),
                        "lambda_sp": candidate.get("lambda_sp", ""),
                        "L_u": candidate.get("L_u", ""),
                        "sync_refine_applied": (
                            row.get("sync_refine_applied", "") if row is not None else ""
                        ),
                        "sync_start_delta_samples": (
                            row.get("sync_refine_start_delta_samples", "")
                            if row is not None
                            else ""
                        ),
                        "sync_cfo_delta_bins": (
                            row.get("sync_refine_cfo_delta_bins", "") if row is not None else ""
                        ),
                        "decode_elapsed_ms": (
                            row.get("decode_elapsed_ms", "") if row is not None else ""
                        ),
                        "decode_timing_scope": (
                            row.get("decode_timing_scope", "") if row is not None else ""
                        ),
                    }
                )
    return runs, methods, packets


def aggregate_run_methods(rows: list[dict], method_set: tuple[str, ...]) -> list[dict]:
    rng = np.random.default_rng(20260723)
    groups: dict[tuple[str, float, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row["method"] in method_set:
            groups[
                (row["experiment"], row["x_value"], row["x_label"], row["method"])
            ].append(row)
    result: list[dict] = []
    for (experiment, x_value, x_label, method), group in sorted(groups.items()):
        prr = [float(row["conditional_prr"]) for row in group if row["conditional_prr"] is not None]
        tps = [
            float(row["tps_bps"])
            for row in group
            if row["tps_bps"] is not None
        ]
        end_to_end_prr = [
            float(row["end_to_end_prr"])
            for row in group
            if row.get("end_to_end_prr") is not None
        ]
        throughput = [
            float(row["throughput_bps"])
            for row in group
            if row.get("throughput_bps") is not None
        ]
        payload_goodput = [
            float(row["payload_goodput_kbps"])
            for row in group
            if row.get("payload_goodput_kbps") is not None
        ]
        prr_mean, prr_low, prr_high = bootstrap_mean(prr, rng)
        tps_mean, tps_low, tps_high = bootstrap_mean(tps, rng)
        e2e_mean, e2e_low, e2e_high = bootstrap_mean(end_to_end_prr, rng)
        throughput_mean, throughput_low, throughput_high = bootstrap_mean(throughput, rng)
        goodput_mean, goodput_low, goodput_high = bootstrap_mean(payload_goodput, rng)
        result.append(
            {
                "experiment": experiment,
                "x_value": x_value,
                "x_label": x_label,
                "method": method,
                "method_label": METHOD_LABELS.get(method, method),
                "run_count": len(group),
                "conditional_prr_mean": prr_mean,
                "conditional_prr_ci_low": prr_low,
                "conditional_prr_ci_high": prr_high,
                "tps_bps_mean": tps_mean,
                "tps_bps_ci_low": tps_low,
                "tps_bps_ci_high": tps_high,
                "end_to_end_prr_mean": e2e_mean,
                "end_to_end_prr_ci_low": e2e_low,
                "end_to_end_prr_ci_high": e2e_high,
                "throughput_bps_mean": throughput_mean,
                "throughput_bps_ci_low": throughput_low,
                "throughput_bps_ci_high": throughput_high,
                "payload_goodput_kbps_mean": goodput_mean,
                "payload_goodput_kbps_ci_low": goodput_low,
                "payload_goodput_kbps_ci_high": goodput_high,
            }
        )
    return result


def aggregate_detection(rows: list[dict]) -> list[dict]:
    rng = np.random.default_rng(20260723)
    groups: dict[tuple[str, float, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["experiment"], row["x_value"], row["x_label"])].append(row)
    out: list[dict] = []
    for (experiment, x_value, x_label), group in sorted(groups.items()):
        values = [
            float(row["packet_detection_rate"])
            for row in group
            if row["packet_detection_rate"] != ""
        ]
        mean, low, high = bootstrap_mean(values, rng)
        out.append(
            {
                "experiment": experiment,
                "x_value": x_value,
                "x_label": x_label,
                "run_count": len(group),
                "packet_detection_rate_mean": mean,
                "packet_detection_rate_ci_low": low,
                "packet_detection_rate_ci_high": high,
            }
        )
    return out


def aggregate_packets(rows: list[dict], key: str, methods: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple[object, str], list[int]] = defaultdict(list)
    for row in rows:
        if row["method"] not in methods or row[key] == "":
            continue
        groups[(row[key], row["method"])].append(int(row["success"]))
    return [
        {
            key: group_key,
            "method": method,
            "method_label": METHOD_LABELS.get(method, method),
            "target_count": len(values),
            "success_count": sum(values),
            "conditional_prr": sum(values) / len(values),
        }
        for (group_key, method), values in sorted(groups.items())
    ]


def aggregate_environment(rows: list[dict]) -> list[dict]:
    rng = np.random.default_rng(20260723)
    groups: dict[tuple[str, float, str], list[float]] = defaultdict(list)
    for row in rows:
        if row["experiment"] != "environment" or not row.get("layout"):
            continue
        if row["method"] not in FORMAL_METHODS or row["conditional_prr"] is None:
            continue
        groups[
            (
                str(row["layout"]),
                float(row["offered_load"]),
                str(row["method"]),
            )
        ].append(float(row["conditional_prr"]))
    out: list[dict] = []
    for (layout, load, method), values in sorted(groups.items()):
        mean, low, high = bootstrap_mean(values, rng)
        out.append(
            {
                "layout": layout,
                "offered_load": load,
                "method": method,
                "method_label": METHOD_LABELS.get(method, method),
                "run_count": len(values),
                "conditional_prr_mean": mean,
                "conditional_prr_ci_low": low,
                "conditional_prr_ci_high": high,
            }
        )
    return out


def aggregate_runtime(rows: list[dict]) -> list[dict]:
    """Aggregate decoder-only wall time for actual collision orders 2/4/8."""
    rng = np.random.default_rng(20260730)
    groups: dict[tuple[int, str], list[float]] = defaultdict(list)
    for row in rows:
        if row.get("method") not in RUNTIME_METHODS:
            continue
        if row.get("decode_elapsed_ms") == "":
            continue
        if row.get("collision_order_source") != "manifest_schedule":
            continue
        order = int(row.get("collision_order", 0))
        if order not in (2, 4, 8):
            continue
        groups[(order, str(row["method"]))].append(float(row["decode_elapsed_ms"]))
    result: list[dict] = []
    for (order, method), values in sorted(groups.items()):
        mean, low, high = bootstrap_mean(values, rng)
        result.append(
            {
                "collision_order": order,
                "method": method,
                "method_label": METHOD_LABELS.get(method, method),
                "sample_count": len(values),
                "decode_time_mean_ms": mean,
                "decode_time_ci_low_ms": low,
                "decode_time_ci_high_ms": high,
                "decode_time_median_ms": float(np.median(values)),
                "decode_time_p95_ms": float(np.percentile(values, 95)),
            }
        )
    return result


def projective_angle_deg(first: np.ndarray, second: np.ndarray) -> float:
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= 0:
        return float("nan")
    cosine = float(np.clip(abs(np.vdot(first, second)) / denominator, 0.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def fig12_channel_angles(index_rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """Measure Node01/Node02 channel-direction separation within each capture."""
    run_rows: list[dict] = []
    for index_row in index_rows:
        if index_row.get("experiment") != "fig12_distance":
            continue
        report_path = Path(index_row["report"]).expanduser()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        whitener = complex_matrix(report["calibration"]["whitener"])
        by_node: dict[int, list[np.ndarray]] = {1: [], 2: []}
        for candidate in report.get("candidates", []):
            method_row = candidate_method(candidate, "sp_sync_refine")
            identity = app_identity(method_row) if method_row is not None else None
            if identity is None or identity[0] not in by_node or candidate.get("channel_sp") is None:
                continue
            physical = np.linalg.solve(whitener, complex_vector(candidate["channel_sp"]))
            norm = float(np.linalg.norm(physical))
            if norm > 0:
                by_node[identity[0]].append(physical / norm)
        angles = [
            projective_angle_deg(first, second)
            for first in by_node[1]
            for second in by_node[2]
        ]
        angles = [value for value in angles if math.isfinite(value)]
        run_rows.append(
            {
                "report": str(report_path),
                "run_id": report.get("run_id"),
                "node_separation_m": float(index_row["x_value"]),
                "node1_channel_count": len(by_node[1]),
                "node2_channel_count": len(by_node[2]),
                "cross_pair_count": len(angles),
                "projective_angle_median_deg": float(np.median(angles)) if angles else float("nan"),
                "projective_angle_p10_deg": float(np.percentile(angles, 10)) if angles else float("nan"),
                "projective_angle_p90_deg": float(np.percentile(angles, 90)) if angles else float("nan"),
            }
        )
    rng = np.random.default_rng(20260730)
    groups: dict[float, list[float]] = defaultdict(list)
    for row in run_rows:
        value = float(row["projective_angle_median_deg"])
        if math.isfinite(value):
            groups[float(row["node_separation_m"])].append(value)
    aggregate: list[dict] = []
    for separation, values in sorted(groups.items()):
        mean, low, high = bootstrap_mean(values, rng)
        aggregate.append(
            {
                "node_separation_m": separation,
                "run_count": len(values),
                "projective_angle_mean_deg": mean,
                "projective_angle_ci_low_deg": low,
                "projective_angle_ci_high_deg": high,
            }
        )
    return run_rows, aggregate


def plot_fig12_channel_angle(rows: list[dict], output: Path) -> None:
    if not rows:
        return
    selected = sorted(rows, key=lambda row: row["node_separation_m"])
    x = np.asarray([row["node_separation_m"] for row in selected])
    y = np.asarray([row["projective_angle_mean_deg"] for row in selected])
    low = np.asarray([row["projective_angle_ci_low_deg"] for row in selected])
    high = np.asarray([row["projective_angle_ci_high_deg"] for row in selected])
    fig, axis = plt.subplots(figsize=(5.8, 3.8))
    axis.plot(x, y, marker="o")
    axis.fill_between(x, low, high, alpha=0.15)
    axis.set_xlabel("Node separation along the same bearing (m)")
    axis.set_ylabel("Projective channel angle (degrees)")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_runtime(rows: list[dict], output: Path) -> None:
    if not rows:
        return
    orders = (2, 4, 8)
    x = np.arange(len(orders), dtype=float)
    width = 0.8 / len(RUNTIME_METHODS)
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    for method_index, method in enumerate(RUNTIME_METHODS):
        selected = {
            int(row["collision_order"]): row for row in rows if row["method"] == method
        }
        values = np.asarray(
            [selected[order]["decode_time_mean_ms"] if order in selected else np.nan for order in orders]
        )
        low = np.asarray(
            [selected[order]["decode_time_ci_low_ms"] if order in selected else np.nan for order in orders]
        )
        high = np.asarray(
            [selected[order]["decode_time_ci_high_ms"] if order in selected else np.nan for order in orders]
        )
        positions = x - 0.4 + width / 2 + method_index * width
        axis.bar(
            positions,
            values,
            width=width,
            yerr=np.vstack([np.maximum(values - low, 0.0), np.maximum(high - values, 0.0)]),
            capsize=2,
            label=METHOD_LABELS[method],
        )
    axis.set_xticks(x, [str(order) for order in orders])
    axis.set_xlabel("Actual collision order (target included)")
    axis.set_ylabel("Payload decoder time per target (ms)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_environment(rows: list[dict], output: Path) -> None:
    if not rows:
        return
    loads = sorted({float(row["offered_load"]) for row in rows})
    layouts = sorted({str(row["layout"]) for row in rows})
    fig, axes = plt.subplots(1, len(loads), figsize=(6.5 * len(loads), 4.0), squeeze=False)
    for axis, load in zip(axes[0], loads):
        x = np.arange(len(FORMAL_METHODS), dtype=float)
        width = 0.8 / max(1, len(layouts))
        for layout_index, layout in enumerate(layouts):
            selected = {
                row["method"]: row
                for row in rows
                if float(row["offered_load"]) == load and row["layout"] == layout
            }
            values = [
                selected[method]["conditional_prr_mean"] if method in selected else np.nan
                for method in FORMAL_METHODS
            ]
            axis.bar(
                x - 0.4 + width / 2 + layout_index * width,
                values,
                width=width,
                label=f"Layout {layout}",
            )
        axis.set_xticks(
            x,
            [METHOD_LABELS[method] for method in FORMAL_METHODS],
            rotation=18,
            ha="right",
        )
        axis.set_ylim(0.0, 1.02)
        axis.set_ylabel("PRR, shared fine-sync targets")
        axis.set_title(f"G={load:g}")
        axis.grid(axis="y", alpha=0.25)
        axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_grouped(
    rows: list[dict],
    output: Path,
    *,
    y_key: str,
    low_key: str | None,
    high_key: str | None,
    ylabel: str,
    methods: tuple[str, ...] = FORMAL_METHODS,
    xlabel: str = "experiment x",
) -> None:
    if not rows:
        return
    fig, axis = plt.subplots(figsize=(7.0, 4.2))
    for method in methods:
        selected = sorted(
            (row for row in rows if row.get("method") == method),
            key=lambda row: row["x_value"],
        )
        if not selected:
            continue
        x = np.asarray([row["x_value"] for row in selected], dtype=float)
        y = np.asarray([row[y_key] for row in selected], dtype=float)
        axis.plot(x, y, marker="o", label=METHOD_LABELS[method])
        if low_key and high_key:
            low = np.asarray([row[low_key] for row in selected], dtype=float)
            high = np.asarray([row[high_key] for row in selected], dtype=float)
            axis.fill_between(x, low, high, alpha=0.12)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    if "prr" in y_key:
        axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_packet_groups(rows: list[dict], output: Path, *, x_key: str, xlabel: str) -> None:
    if not rows:
        return
    fig, axis = plt.subplots(figsize=(7.0, 4.2))
    for method in FORMAL_METHODS:
        selected = sorted(
            (row for row in rows if row["method"] == method),
            key=lambda row: float(row[x_key]),
        )
        if not selected:
            continue
        axis.plot(
            [float(row[x_key]) for row in selected],
            [float(row["conditional_prr"]) for row in selected],
            marker="o",
            label=METHOD_LABELS[method],
        )
    axis.set_xlabel(xlabel)
    axis.set_ylabel("PRR, shared fine-sync targets")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_detection(rows: list[dict], output: Path, *, xlabel: str) -> None:
    if not rows:
        return
    selected = sorted(rows, key=lambda row: row["x_value"])
    x = np.asarray([row["x_value"] for row in selected], dtype=float)
    y = np.asarray([row["packet_detection_rate_mean"] for row in selected], dtype=float)
    low = np.asarray([row["packet_detection_rate_ci_low"] for row in selected], dtype=float)
    high = np.asarray([row["packet_detection_rate_ci_high"] for row in selected], dtype=float)
    fig, axis = plt.subplots(figsize=(5.8, 3.8))
    axis.plot(x, y, marker="o", color="black")
    axis.fill_between(x, low, high, color="black", alpha=0.12)
    axis.set_xlabel(xlabel)
    axis.set_ylabel("Schedule-normalized packet detection rate")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_lambda_and_sync(packets: list[dict], out: Path) -> None:
    # One row per candidate is sufficient; method rows duplicate candidate
    # lambda/L_u values.
    unique: dict[tuple[object, object], dict] = {}
    for row in packets:
        unique.setdefault((row["report"], row["candidate_id"]), row)
    lambda_values = [
        float(row["lambda_sp"]) for row in unique.values() if row["lambda_sp"] != ""
    ]
    l_values = [float(row["L_u"]) for row in unique.values() if row["L_u"] != ""]
    if lambda_values:
        fig, axis = plt.subplots(figsize=(5.4, 3.6))
        axis.hist(lambda_values, bins=min(20, max(5, int(math.sqrt(len(lambda_values))))))
        axis.set_xlabel(r"selected packet-level $\lambda_u$")
        axis.set_ylabel("complete targets")
        axis.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(out / "lambda_distribution.pdf", dpi=200, bbox_inches="tight")
        plt.close(fig)
    write_csv(
        out / "lambda_summary.csv",
        [
            {
                "target_count": len(unique),
                "lambda_median": float(np.median(lambda_values)) if lambda_values else "",
                "lambda_p10": float(np.percentile(lambda_values, 10)) if lambda_values else "",
                "lambda_p90": float(np.percentile(lambda_values, 90)) if lambda_values else "",
                "L_u_median": float(np.median(l_values)) if l_values else "",
            }
        ],
    )

    sync_rows = [
        row
        for row in packets
        if row["method"] == "sp_sync_refine" and row["sync_refine_applied"] != ""
    ]
    start_delta = [
        abs(float(row["sync_start_delta_samples"]))
        for row in sync_rows
        if row["sync_start_delta_samples"] != ""
    ]
    cfo_delta = [
        abs(float(row["sync_cfo_delta_bins"]))
        for row in sync_rows
        if row["sync_cfo_delta_bins"] != ""
    ]
    write_csv(
        out / "sync_refine_summary.csv",
        [
            {
                "target_count": len(sync_rows),
                "trigger_count": sum(bool(row["sync_refine_applied"]) for row in sync_rows),
                "trigger_fraction": (
                    sum(bool(row["sync_refine_applied"]) for row in sync_rows) / len(sync_rows)
                    if sync_rows
                    else ""
                ),
                "median_abs_start_delta_samples": (
                    float(np.median(start_delta)) if start_delta else ""
                ),
                "median_abs_cfo_delta_bins": (
                    float(np.median(cfo_delta)) if cfo_delta else ""
                ),
            }
        ],
    )


def reports_command(args: argparse.Namespace) -> int:
    index_rows = read_index(args.index)
    runs, methods, packets = report_rows(index_rows)
    for row in runs:
        if row.get("node_outage_review_required"):
            print(
                "NODE_OUTAGE_REVIEW_REQUIRED "
                f"run_id={row.get('run_id')} report={row.get('report')} "
                f"zero_observed_active_nodes={row.get('zero_observed_active_nodes')}; "
                "metrics remain unchanged; verify hardware/control logs and rerun the "
                "whole run if an outage is confirmed",
                file=sys.stderr,
                flush=True,
            )
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "runs.csv", runs)
    write_csv(out / "method_runs.csv", methods)
    write_csv(out / "packets.csv", packets)

    aggregate = aggregate_run_methods(methods, END_TO_END_METHODS)
    ablation = aggregate_run_methods(methods, ABLATION_METHODS)
    detection = aggregate_detection(runs)
    collision = aggregate_packets(packets, "collision_order", FORMAL_METHODS)
    weak = aggregate_packets(
        [row for row in packets if str(row.get("target_node")) == str(row.get("weak_node"))],
        "power_gap_db",
        FORMAL_METHODS,
    )
    environment = aggregate_environment(methods)
    runtime = aggregate_runtime(packets)
    fig12_angle_runs, fig12_angles = fig12_channel_angles(index_rows)
    write_csv(out / "method_aggregate.csv", aggregate)
    write_csv(out / "ablation_aggregate.csv", ablation)
    write_csv(out / "detection_aggregate.csv", detection)
    write_csv(out / "collision_order.csv", collision)
    write_csv(out / "weak_node_near_far.csv", weak)
    write_csv(out / "environment_aggregate.csv", environment)
    write_csv(out / "decoder_runtime.csv", runtime)
    write_csv(out / "fig12_channel_angle_runs.csv", fig12_angle_runs)
    write_csv(out / "fig12_channel_angle_aggregate.csv", fig12_angles)
    plot_environment(environment, out / "environment_prr.pdf")
    plot_runtime(runtime, out / "decoder_runtime.pdf")
    plot_fig12_channel_angle(fig12_angles, out / "fig12_channel_angle.pdf")
    plot_packet_groups(
        collision,
        out / "collision_order_prr.pdf",
        x_key="collision_order",
        xlabel="Collision order (target included)",
    )
    plot_packet_groups(
        weak,
        out / "near_far_weak_prr.pdf",
        x_key="power_gap_db",
        xlabel="Strong-minus-weak received-power gap (dB)",
    )
    plot_lambda_and_sync(packets, out)

    for experiment in sorted({row["experiment"] for row in aggregate}):
        subset = [row for row in aggregate if row["experiment"] == experiment]
        xlabel = EXPERIMENT_XLABELS.get(experiment, "experiment x")
        if experiment.startswith("fig9_10_"):
            xlabel = "Active nodes N"
        elif experiment == "fig12_distance":
            xlabel = "Node separation along the same bearing (m)"
        plot_detection(
            [row for row in detection if row["experiment"] == experiment],
            out / f"{experiment}_detection.pdf",
            xlabel=xlabel,
        )
        plot_grouped(
            subset,
            out / f"{experiment}_prr.pdf",
            y_key="conditional_prr_mean",
            low_key="conditional_prr_ci_low",
            high_key="conditional_prr_ci_high",
            ylabel="PRR, shared fine-sync targets",
            xlabel=xlabel,
        )
        plot_grouped(
            subset,
            out / f"{experiment}_end_to_end_prr.pdf",
            y_key="end_to_end_prr_mean",
            low_key="end_to_end_prr_ci_low",
            high_key="end_to_end_prr_ci_high",
            ylabel="End-to-end PRR",
            methods=END_TO_END_METHODS,
            xlabel=xlabel,
        )
        plot_grouped(
            subset,
            out / f"{experiment}_payload_goodput.pdf",
            y_key="payload_goodput_kbps_mean",
            low_key="payload_goodput_kbps_ci_low",
            high_key="payload_goodput_kbps_ci_high",
            ylabel="Payload goodput (kbps)",
            methods=END_TO_END_METHODS,
            xlabel=xlabel,
        )
        ablation_subset = [row for row in ablation if row["experiment"] == experiment]
        plot_grouped(
            ablation_subset,
            out / f"{experiment}_ablation.pdf",
            y_key="conditional_prr_mean",
            low_key="conditional_prr_ci_low",
            high_key="conditional_prr_ci_high",
            ylabel="PRR, shared fine-sync targets",
            methods=ABLATION_METHODS,
            xlabel=xlabel,
        )
    print(f"wrote {out.resolve()}")
    return 0


def awgn_command(args: argparse.Namespace) -> int:
    rows: list[dict] = []
    for path in args.sweeps:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema") != "real_iq_awgn_decoder_prr_sweep_v5":
            raise ValueError(
                f"{path}: AWGN PRR schema is {report.get('schema')!r}; "
                "rebuild with the shared-fine-sync evaluator"
            )
        if report.get("source_target_policy") != "fine_sync_database":
            raise ValueError(f"{path}: AWGN sweep does not use shared fine-sync targets")
        for point in report.get("sweep", []):
            for method, values in point.get("by_method", {}).items():
                if method == "sp_repair":
                    continue
                detected, decoded, denominator, prr = validated_shared_prr(
                    {
                        "execution_status": "completed",
                        "complete_detected_packet_count": values.get("detected_packet_count"),
                        "decoded_success_count": values.get("decoded_success_count"),
                        "manifest_expected_packet_count_in_analysis_window": values.get(
                            "manifest_expected_packet_count_in_analysis_window"
                        ),
                        "prr_denominator_packet_count": values.get("prr_denominator_packet_count"),
                        "prr": values.get("prr"),
                        "prr_denominator_source": values.get("prr_denominator_source"),
                        "prr_counting_policy": values.get("prr_counting_policy"),
                    },
                    path,
                    method,
                )
                rows.append(
                    {
                        "source": str(path),
                        "seed": report.get("random_seed"),
                        "noise_floor_rise_db": point["noise_floor_rise_db"],
                        "median_snr_db": point["median_estimated_preamble_snr_db"],
                        "method": method,
                        "method_label": METHOD_LABELS.get(method, method),
                        "successes": decoded,
                        "targets": detected,
                        "prr_denominator_packets": denominator,
                        "conditional_prr": prr,
                    }
                )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "awgn_runs.csv", rows)
    rng = np.random.default_rng(20260723)
    groups: dict[tuple[float, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row["method"] in FORMAL_METHODS:
            groups[(float(row["noise_floor_rise_db"]), row["method"])].append(row)
    aggregate: list[dict] = []
    for (rise, method), group in sorted(groups.items()):
        mean, low, high = bootstrap_mean(
            [float(row["conditional_prr"]) for row in group], rng
        )
        aggregate.append(
            {
                "noise_floor_rise_db": rise,
                "median_snr_db": float(np.mean([row["median_snr_db"] for row in group])),
                "method": method,
                "method_label": METHOD_LABELS.get(method, method),
                "seed_count": len(group),
                "conditional_prr_mean": mean,
                "conditional_prr_ci_low": low,
                "conditional_prr_ci_high": high,
            }
        )
    write_csv(args.out_dir / "awgn_aggregate.csv", aggregate)

    fig, axis = plt.subplots(figsize=(7.0, 4.2))
    for method in FORMAL_METHODS:
        selected = sorted(
            (row for row in aggregate if row["method"] == method),
            key=lambda row: row["median_snr_db"],
        )
        if not selected:
            continue
        x = np.asarray([row["median_snr_db"] for row in selected])
        y = np.asarray([row["conditional_prr_mean"] for row in selected])
        low = np.asarray([row["conditional_prr_ci_low"] for row in selected])
        high = np.asarray([row["conditional_prr_ci_high"] for row in selected])
        axis.plot(x, y, marker="o", label=METHOD_LABELS[method])
        axis.fill_between(x, low, high, alpha=0.12)
    axis.set_xlabel("Median estimated preamble SNR (dB)")
    axis.set_ylabel("PRR, shared fine-sync targets")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(args.out_dir / "awgn_prr.pdf", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {args.out_dir.resolve()}")
    return 0


def median_physical_channel_power(report: dict, node_id: int | None) -> tuple[float, int]:
    whitener = complex_matrix(report["calibration"]["whitener"])
    powers: list[float] = []
    for candidate in report.get("candidates", []):
        sp_row = candidate_method(candidate, "sp_sync_refine")
        identity = app_identity(sp_row) if sp_row is not None else None
        if node_id is not None and (identity is None or identity[0] != node_id):
            continue
        channel_values = candidate.get("channel_sp")
        if channel_values is None:
            continue
        physical_channel = np.linalg.solve(whitener, complex_vector(channel_values))
        powers.append(float(np.vdot(physical_channel, physical_channel).real))
    if not powers:
        raise ValueError(f"no CRC-closed channel estimates for node {node_id}")
    return float(np.median(powers)), len(powers)


def power_gap_command(args: argparse.Namespace) -> int:
    strong_report = json.loads(args.strong_report.read_text(encoding="utf-8"))
    weak_report = json.loads(args.weak_report.read_text(encoding="utf-8"))
    strong_power, strong_count = median_physical_channel_power(
        strong_report, args.strong_node
    )
    weak_power, weak_count = median_physical_channel_power(weak_report, args.weak_node)
    result = {
        "strong_report": str(args.strong_report),
        "weak_report": str(args.weak_report),
        "strong_node": args.strong_node,
        "weak_node": args.weak_node,
        "strong_target_count": strong_count,
        "weak_target_count": weak_count,
        "strong_median_channel_power_db": 10.0 * math.log10(max(strong_power, 1e-30)),
        "weak_median_channel_power_db": 10.0 * math.log10(max(weak_power, 1e-30)),
        "strong_minus_weak_gap_db": 10.0
        * math.log10(max(strong_power, 1e-30) / max(weak_power, 1e-30)),
        "definition": (
            "10log10 ratio of median dual-channel physical channel-vector powers; "
            "reports must use identical RX gain, antenna geometry, PHY, and node TX power"
        ),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reports = commands.add_parser("reports", help="aggregate receiver JSON reports")
    reports.add_argument("--index", type=Path, required=True)
    reports.add_argument("--out-dir", type=Path, required=True)
    reports.set_defaults(func=reports_command)
    awgn = commands.add_parser("awgn", help="aggregate shared-fine-sync AWGN sweeps")
    awgn.add_argument("--sweeps", type=Path, nargs="+", required=True)
    awgn.add_argument("--out-dir", type=Path, required=True)
    awgn.set_defaults(func=awgn_command)
    power_gap = commands.add_parser(
        "power-gap", help="measure strong-minus-weak channel-power gap from two calibration reports"
    )
    power_gap.add_argument("--strong-report", type=Path, required=True)
    power_gap.add_argument("--weak-report", type=Path, required=True)
    power_gap.add_argument("--strong-node", type=int, default=None)
    power_gap.add_argument("--weak-node", type=int, default=None)
    power_gap.add_argument("--out", type=Path, default=None)
    power_gap.set_defaults(func=power_gap_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
