#!/usr/bin/env python3
"""Build preliminary Fig. 9/10/12 plots from receiver reports.

The script deliberately tolerates incomplete campaigns: each usable method row is
kept independently, while missing reports/method rows are recorded in coverage.md.
All figures use the same shared anonymous physical-candidate database.  PRR is
CRC-valid decoded candidates divided by detected physical candidates.

The evaluation window is the strict centered 5 business seconds
(``traffic_start + 7.5 s`` to ``traffic_start + 12.5 s``).  Fig. 10 reports
decoder TPS: CRC-valid payload bits divided by the method's total
post-shared-sync decoder work time.  The total includes every candidate attempt
(including failed ones), so it directly measures each scheme's decoding
throughput.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-fig9-12-preview")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from formal_window import FORMAL_ANALYSIS_DURATION_S


METHODS = (
    ("lorawan", "LoRaWAN"),
    ("mrc", "MRC"),
    ("mrc_cic", "MRC+CIC"),
    ("pcube", "PCube"),
    ("maloragw", "MaLoRaGW"),
    ("sp_sync_refine", "SP-Decoder"),
)

# The proximity experiment retains the collision-decoding baselines against
# SP-Decoder, while omitting the LoRaWAN and CIC reference curves.  All methods
# remain in the Fig. 9/10 load experiment.
FIG12_METHODS = tuple(
    item
    for item in METHODS
    if item[0] in {"mrc", "pcube", "maloragw", "sp_sync_refine"}
)

DEFAULT_PAYLOAD_BITS = 20 * 8

STYLES = {
    "lorawan": dict(color="#4c78a8", marker="o", linestyle="--"),
    "mrc": dict(color="#f58518", marker="s", linestyle="--"),
    "mrc_cic": dict(color="#54a24b", marker="^", linestyle="-."),
    "pcube": dict(color="#e45756", marker="D", linestyle=":"),
    "maloragw": dict(color="#b279a2", marker="v", linestyle="-."),
    "sp_sync_refine": dict(
        color="#111111", marker="*", linestyle="-", linewidth=2.2, markersize=9
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--runs", type=Path, default=root / "runs")
    parser.add_argument(
        "--reports",
        type=Path,
        default=root / "analysis" / "fig9_10_12_preview" / "reports",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "analysis" / "fig9_10_12_preview",
    )
    parser.add_argument("--window-start-s", type=float, default=None)
    parser.add_argument(
        "--window-duration-s", type=float, default=FORMAL_ANALYSIS_DURATION_S
    )
    parser.add_argument(
        "--window-map",
        type=Path,
        default=root / "analysis" / "fig9_10_12_preview" / "evaluation_windows.json",
    )
    parser.add_argument(
        "--fig12-only",
        action="store_true",
        help="Render only the filtered Fig. 12 PRR plot; leave other preview files intact.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def t95(n: int) -> float:
    # Two-sided Student-t critical values; enough for the small repeated campaigns.
    table = {
        2: 12.706,
        3: 4.303,
        4: 3.182,
        5: 2.776,
        6: 2.571,
        7: 2.447,
        8: 2.365,
        9: 2.306,
        10: 2.262,
    }
    return table.get(n, 1.96 if n >= 31 else 2.086)


def summarize(values: list[float]) -> tuple[float, float | None]:
    if not values:
        return math.nan, None
    if len(values) == 1:
        return float(values[0]), None
    return mean(values), t95(len(values)) * stdev(values) / math.sqrt(len(values))


def method_decoder_work_s(report: dict, method: str) -> float:
    """Return total post-shared-sync decoder work time for one method.

    The report stores per-candidate timing rather than a standalone rerun of
    each decoder.  Therefore this is the serial work sum, not a concurrent
    end-to-end batch-latency measurement.  It includes failed candidates,
    method-specific parameter estimation, and payload decoding.  For SP,
    ``post_sp_total_elapsed_ms`` already includes its allocated batch lambda
    configuration work, so the report-level ``batch_elapsed_ms`` audit must
    not be added again.  The common front-end/fine-sync database construction
    is intentionally excluded for every method.
    """

    timing_method = method
    total_ms = 0.0
    for candidate in report.get("candidates", []):
        for row in candidate.get("methods", []):
            if row.get("method") != timing_method:
                continue
            value = row.get("post_sp_total_elapsed_ms")
            if value is None:
                value = row.get("decode_elapsed_ms", 0.0)
            try:
                total_ms += float(value)
            except (TypeError, ValueError):
                pass
    return total_ms / 1000.0


def decoder_tps(decoded_count: int, payload_bits: int, decoder_work_s: float) -> float:
    """Compute TPS from successful payload bits and total decoder latency."""

    if decoded_count == 0:
        return 0.0
    if not math.isfinite(decoder_work_s) or decoder_work_s <= 0.0:
        raise ValueError("successful decoding requires a positive total decoder latency")
    return float(decoded_count) * payload_bits / decoder_work_s


def manifest_paths(runs_root: Path) -> list[Path]:
    """Prefer the controller manifest copied into each run directory."""

    paths = {
        path.stem: path.resolve()
        for path in (runs_root / "manifests").glob("run_*.json")
    }
    for run_dir in runs_root.glob("run_*"):
        candidate = run_dir / f"{run_dir.name}.json"
        if candidate.exists():
            paths[candidate.stem] = candidate.resolve()
    return [paths[name] for name in sorted(paths)]


def collect(args: argparse.Namespace) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    notes: list[str] = []
    for manifest_path in manifest_paths(args.runs):
        manifest = load_json(manifest_path)
        experiment = manifest.get("experiment", {})
        figure = experiment.get("figure")
        if figure not in {"fig9_10", "fig12"}:
            continue
        run_name = manifest_path.stem
        report_path = args.reports / f"{run_name}.json"
        if not report_path.exists():
            notes.append(f"- {run_name}: no decoded report; omitted")
            continue
        report = load_json(report_path)
        strict_window = report.get("input", {}).get(
            "strict_middle_business_window", {}
        )
        if not strict_window.get("enabled"):
            notes.append(
                f"- {run_name}: stale report has no strict middle-business-window audit; omitted"
            )
            continue
        window_start_s = float(
            strict_window.get("analysis_start_s_from_full_iq", math.nan)
        )
        window_duration_s = float(strict_window.get("analysis_duration_s", math.nan))
        analysis_slice = report.get("input", {}).get("analysis_slice")
        if isinstance(analysis_slice, dict):
            decoded_start_s = float(analysis_slice.get("start_time_s", math.nan))
            decoded_duration_s = float(
                analysis_slice.get("requested_duration_s", math.nan)
            )
        else:
            details = report.get("frontend", {}).get("window_details", [])
            decoded_start_s = math.nan
            decoded_duration_s = (
                max(float(item.get("end_time_s", 0.0)) for item in details)
                if details
                else math.nan
            )
        duration_matches = (
            math.isfinite(decoded_duration_s)
            and math.isfinite(window_duration_s)
            and abs(decoded_duration_s - window_duration_s) <= 1e-6
            and abs(window_duration_s - float(args.window_duration_s)) <= 1e-6
        )
        start_matches = (
            math.isfinite(decoded_start_s)
            and math.isfinite(window_start_s)
            and abs(decoded_start_s - window_start_s) <= 1e-6
        )
        if not duration_matches or not start_matches:
            notes.append(
                f"- {run_name}: report slice does not match its strict middle "
                f"{args.window_duration_s:g} business-second audit; omitted"
            )
            continue
        fine_sync_audit = report.get("input", {}).get("fine_sync_database")
        discovery = (
            fine_sync_audit.get("candidate_discovery", {})
            if isinstance(fine_sync_audit, dict)
            else {}
        )
        if (
            not isinstance(fine_sync_audit, dict)
            or fine_sync_audit.get("schema") != "fine_sync_anonymous_physical_v2"
            or discovery.get("scope") != "global_full_window"
            or discovery.get("manifest_schedule_exposed_to_detector") is not False
            or discovery.get("node_timing_calibration") is not False
            or discovery.get("planned_start_search_windows") is not False
            or discovery.get("score_truncation") is not False
        ):
            notes.append(
                f"- {run_name}: report did not use the schedule-free global "
                "anonymous v2 database; omitted"
            )
            continue
        method_rows = report.get("detection_and_decode", {}).get("by_method", {})
        input_iq = str(report.get("input", {}).get("iq", ""))
        warnings = report.get("capture_warnings", []) or []
        truncated = ".partial.sc16" in input_iq or any(
            "truncat" in str(item).lower() for item in warnings
        )
        if truncated:
            notes.append(f"- {run_name}: truncated/partial capture retained (usable common slice)")
        traffic_start_s = float(
            strict_window.get("traffic_start_s_from_full_iq", math.nan)
        )
        rel_window_start = window_start_s - traffic_start_s
        rel_window_end = rel_window_start + window_duration_s
        schedules = manifest.get("expected_node_schedules", {})
        scheduled_in_slice: list[tuple[int, int, float]] = []
        for node_text, schedule in schedules.items():
            if not isinstance(schedule, dict):
                continue
            node_id = int(node_text)
            for sequence, start_ms in enumerate(
                schedule.get("tx_start_ms_from_traffic_begin", [])
            ):
                offset_s = float(start_ms) / 1000.0
                if rel_window_start <= offset_s < rel_window_end:
                    scheduled_in_slice.append((node_id, int(sequence), offset_s))
        bandwidth_hz = int(
            manifest.get("radio", {}).get(
                "bandwidth_hz", experiment.get("bandwidth_hz", 0)
            )
        )
        payload_bytes = int(
            manifest.get("traffic", {}).get(
                "data_payload_bytes",
                report.get("config", {}).get("payload_len", DEFAULT_PAYLOAD_BITS // 8),
            )
        )
        payload_bits = payload_bytes * 8
        for method, label in METHODS:
            metric = method_rows.get(method)
            if not isinstance(metric, dict):
                notes.append(f"- {run_name}/{label}: method row absent; omitted")
                continue
            complete = metric.get("complete_detected_packet_count")
            decoded = metric.get("decoded_success_count")
            prr = metric.get("prr")
            prr_denominator = metric.get("prr_denominator_packet_count")
            metric_scope = "min_planned_or_anonymous_detected_packets"
            if (
                metric.get("prr_denominator_source")
                != "min_manifest_window_expected_or_anonymous_detected_packets"
                or metric.get("prr_counting_policy")
                != (
                    "unique_crc_valid_payload_identities_over_"
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                )
            ):
                notes.append(
                    f"- {run_name}/{label}: stale PRR semantics; "
                    "requires min(planned, anonymous-detected) metrics"
                )
                continue
            if complete is None or decoded is None or prr is None:
                notes.append(f"- {run_name}/{label}: no valid denominator; omitted")
                continue
            decoder_work_s = method_decoder_work_s(report, method)
            if prr_denominator is None:
                notes.append(
                    f"- {run_name}/{label}: incomplete detected-candidate audit; omitted"
                )
                continue
            complete_count = int(complete)
            decoded_count = int(decoded)
            denominator_count = int(prr_denominator)
            scheduled_count = len(scheduled_in_slice)
            reported_scheduled_count = metric.get(
                "manifest_expected_packet_count_in_analysis_window"
            )
            reported_detected_count = metric.get("prr_detected_physical_packet_count")
            expected_denominator = min(scheduled_count, complete_count)
            expected_prr = (
                float(decoded_count) / expected_denominator
                if expected_denominator > 0
                else None
            )
            if (
                complete_count < 0
                or decoded_count < 0
                or denominator_count < 0
                or reported_scheduled_count is None
                or int(reported_scheduled_count) != scheduled_count
                or reported_detected_count is None
                or int(reported_detected_count) != complete_count
                or decoded_count > expected_denominator
                or denominator_count != expected_denominator
                or (
                    expected_prr is None
                    and prr is not None
                )
                or (
                    expected_prr is not None
                    and (
                        prr is None
                        or not math.isclose(float(prr), expected_prr, abs_tol=1e-12)
                    )
                )
            ):
                notes.append(
                    f"- {run_name}/{label}: inconsistent min(planned, detected) PRR "
                    "audit; omitted"
                )
                continue
            detected_count = complete_count
            if expected_prr is None:
                notes.append(
                    f"- {run_name}/{label}: zero min(planned, detected) denominator; omitted"
                )
                continue
            rows.append(
                {
                    "figure": figure,
                    "run_id": run_name,
                    "round": int(experiment.get("round", 1)),
                    "active_node_count": int(manifest.get("active_node_count", 0)),
                    "simulated": bool(experiment.get("simulated_merged", False)),
                    "source_runs": experiment.get("merged_source_run_names", []),
                    "duty_cycle": float(experiment.get("per_node_duty_cycle", "nan")),
                    "bandwidth_hz": bandwidth_hz,
                    "distance_label": experiment.get("node_separation_label", ""),
                    "distance_m": float(experiment.get("node_separation_m", "nan")),
                    "method": method,
                    "method_label": label,
                    "complete_candidates": complete_count,
                    "decoded_successes": decoded_count,
                    "prr_denominator_packets": denominator_count,
                    "conditional_prr": expected_prr,
                    "min_planned_or_detected_prr": expected_prr,
                    "scheduled_in_slice": scheduled_count,
                    "detected_in_slice": detected_count,
                    "detection_rate": (
                        float(detected_count) / scheduled_count
                        if scheduled_count
                        else math.nan
                    ),
                    "scheduled_prr": expected_prr,
                    "radio_window_tps": decoder_tps(
                        decoded_count, payload_bits, decoder_work_s
                    ),
                    "radio_window_goodput_kbps": decoder_tps(
                        decoded_count, payload_bits, decoder_work_s
                    ) / 1000.0,
                    "payload_bytes": payload_bytes,
                    "payload_bits": payload_bits,
                    "decoder_work_s": decoder_work_s,
                    "decoder_work_realtime_factor": (
                        decoder_work_s / window_duration_s
                    ),
                    "effective_tps": decoder_tps(
                        decoded_count, payload_bits, decoder_work_s
                    ),
                    "effective_goodput_kbps": decoder_tps(
                        decoded_count, payload_bits, decoder_work_s
                    ) / 1000.0,
                    "metric_scope": metric_scope,
                    "window_start_s": window_start_s,
                    "window_duration_s": window_duration_s,
                    "truncated_capture_retained": truncated,
                    "report": str(report_path.resolve()),
                }
            )
    return rows, notes


def write_raw_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        raise RuntimeError("no usable method rows found")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        setting = (
            row["active_node_count"]
            if row["figure"] == "fig9_10"
            else row["distance_label"]
        )
        grouped[
            (
                row["figure"],
                row["duty_cycle"],
                row["bandwidth_hz"],
                setting,
                row["simulated"],
                row["method"],
                row["method_label"],
            )
        ].append(row)
    result: list[dict] = []
    for (
        figure,
        duty,
        bandwidth_hz,
        setting,
        simulated,
        method,
        label,
    ), items in sorted(grouped.items(), key=str):
        window_durations = {float(item["window_duration_s"]) for item in items}
        if len(window_durations) != 1:
            raise ValueError(
                "cannot aggregate rows with different evaluation-window durations"
            )
        prr_mean, prr_ci = summarize([item["conditional_prr"] for item in items])
        scheduled_prr_mean, scheduled_prr_ci = summarize(
            [item["scheduled_prr"] for item in items]
        )
        detection_mean, detection_ci = summarize(
            [item["detection_rate"] for item in items]
        )
        radio_tps_mean, radio_tps_ci = summarize(
            [item["radio_window_tps"] for item in items]
        )
        radio_goodput_mean, radio_goodput_ci = summarize(
            [item["radio_window_goodput_kbps"] for item in items]
        )
        effective_tps_mean, effective_tps_ci = summarize(
            [item["effective_tps"] for item in items]
        )
        effective_goodput_mean, effective_goodput_ci = summarize(
            [item["effective_goodput_kbps"] for item in items]
        )
        decoder_work_mean, decoder_work_ci = summarize(
            [item["decoder_work_s"] for item in items]
        )
        realtime_factor_mean, realtime_factor_ci = summarize(
            [item["decoder_work_realtime_factor"] for item in items]
        )
        result.append(
            {
                "figure": figure,
                "duty_cycle": duty,
                "bandwidth_hz": bandwidth_hz,
                "setting": setting,
                "simulated": bool(simulated),
                "method": method,
                "method_label": label,
                "usable_rounds": len(items),
                "window_duration_s": window_durations.pop(),
                "conditional_prr_mean": prr_mean,
                "conditional_prr_ci95": prr_ci,
                "scheduled_prr_mean": scheduled_prr_mean,
                "scheduled_prr_ci95": scheduled_prr_ci,
                "detection_rate_mean": detection_mean,
                "detection_rate_ci95": detection_ci,
                "radio_window_tps_mean": radio_tps_mean,
                "radio_window_tps_ci95": radio_tps_ci,
                "radio_window_goodput_kbps_mean": radio_goodput_mean,
                "radio_window_goodput_kbps_ci95": radio_goodput_ci,
                "effective_tps_mean": effective_tps_mean,
                "effective_tps_ci95": effective_tps_ci,
                "effective_goodput_kbps_mean": effective_goodput_mean,
                "effective_goodput_kbps_ci95": effective_goodput_ci,
                "decoder_work_s_mean": decoder_work_mean,
                "decoder_work_s_ci95": decoder_work_ci,
                "decoder_work_realtime_factor_mean": realtime_factor_mean,
                "decoder_work_realtime_factor_ci95": realtime_factor_ci,
                "complete_candidates_total": sum(item["complete_candidates"] for item in items),
                "decoded_successes_total": sum(item["decoded_successes"] for item in items),
            }
        )
    return result


def write_aggregate_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_metric(
    aggregate_rows: list[dict],
    *,
    figure: str,
    metric: str,
    ci_metric: str,
    ylabel: str,
    output_stem: Path,
    title_prefix: str | None = None,
    methods: tuple[tuple[str, str], ...] | None = None,
) -> None:
    subset = [row for row in aggregate_rows if row["figure"] == figure]
    if not subset:
        return
    if figure == "fig9_10":
        panels = [("bandwidth", value) for value in sorted({row["bandwidth_hz"] for row in subset})]
    else:
        panels = [("duty", value) for value in sorted({row["duty_cycle"] for row in subset})]
    fig, axes = plt.subplots(1, len(panels), figsize=(7.2 * len(panels), 4.7), squeeze=False)
    for ax, (panel_kind, panel_value) in zip(axes[0], panels):
        if panel_kind == "bandwidth":
            duty_rows = [row for row in subset if row["bandwidth_hz"] == panel_value]
        else:
            duty_rows = [row for row in subset if row["duty_cycle"] == panel_value]
        if figure == "fig9_10":
            settings = sorted({int(row["setting"]) for row in duty_rows})
            x = np.asarray(settings, dtype=float)
            labels = [str(value) for value in settings]
            xlabel = "Number of active nodes, N"
        else:
            preferred = ["2cm", "5cm", "10cm", "20cm", ">20cm"]
            found = {str(row["setting"]) for row in duty_rows}
            labels = [value for value in preferred if value in found]
            labels += sorted(found - set(labels))
            settings = labels
            x = np.arange(len(settings), dtype=float)
            xlabel = "Separation between two nodes"
        for method, label in methods or METHODS:
            method_rows = {row["setting"]: row for row in duty_rows if row["method"] == method}
            values = []
            errors = []
            present_x = []
            for index, setting in enumerate(settings):
                row = method_rows.get(setting)
                if row is None:
                    continue
                present_x.append(x[index])
                values.append(row[metric])
                errors.append(0.0 if row[ci_metric] is None else row[ci_metric])
            if not values:
                continue
            style = STYLES[method].copy()
            ax.errorbar(
                present_x,
                values,
                yerr=errors if any(errors) else None,
                label=label,
                capsize=3,
                **style,
            )
        ax.set_xticks(x, labels)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, color="#dddddd", linewidth=0.7, alpha=0.8)
        if panel_kind == "bandwidth":
            duties = sorted({100.0 * row["duty_cycle"] for row in duty_rows})
            duty_text = "/".join(f"{value:g}" for value in duties)
            ax.set_title(f"BW = {panel_value/1000:g} kHz; duty = {duty_text}%")
        else:
            ax.set_title(f"Per-node duty cycle = {100*panel_value:g}%")
        if metric in {"conditional_prr_mean", "scheduled_prr_mean", "detection_rate_mean"}:
            ax.set_ylim(-0.03, 1.05)
        ax.legend(ncol=2, fontsize=8.5, frameon=True)
    durations = sorted({float(row["window_duration_s"]) for row in subset})
    duration_label = "/".join(f"{value:g}" for value in durations)
    prefix = f"{title_prefix}; " if title_prefix else ""
    fig.suptitle(
        f"{prefix}strict middle-{duration_label}-business-second evaluation; "
        "n=1 per point (no 95% CI)",
        fontsize=10,
        y=0.98,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.88))
    for suffix in ("png", "pdf"):
        fig.savefig(output_stem.with_suffix(f".{suffix}"), dpi=220)
    plt.close(fig)


def write_coverage(args: argparse.Namespace, rows: list[dict], notes: list[str], path: Path) -> None:
    run_ids = sorted({row["run_id"] for row in rows})
    windows = sorted({(row["run_id"], row["window_start_s"], row["window_duration_s"]) for row in rows})
    merged_runs = sorted({row["run_id"] for row in rows if row["simulated"]})
    lines = [
        "# Fig. 9/10/12 preview data coverage",
        "",
        f"- Evaluation slices: strict middle {args.window_duration_s:g} seconds of each aligned node-business interval",
        "- Fig. 9/10/12 PRR: unique CRC-valid payload identities / min(scheduled packets, detected anonymous physical candidates)",
        "- Fig. 9 detection rate: anonymous detected physical candidates / scheduled-packet scalar upper bound",
        "- Fig. 10 TPS: CRC-valid decoded payload bits / "
        "total post-shared-sync decoder work time",
        "- Decoder work time includes all candidate attempts and each method's parameter estimation; "
        "the shared fine-sync front end is excluded for every method",
        "- Candidate/sync source: shared anonymous SP physical-candidate database; "
        "this is a common-detector evaluation, not each baseline's native front end",
        f"- Usable decoded runs: {len(run_ids)}",
        "- Repetitions per setting: one; therefore no 95% confidence interval is drawn",
        "- Missing method rows and zero-denominator rows are omitted, never imputed as zero",
        "",
        "## Included runs",
        "",
    ]
    lines.extend(f"- {run_id}" for run_id in run_ids)
    lines += ["", "## Per-run IQ windows", ""]
    lines.extend(f"- {run_id}: {start:g}–{start + duration:g} s" for run_id, start, duration in windows)
    lines += ["", "## Omitted/retained diagnostics", ""]
    lines.extend(notes or ["- None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows, notes = collect(args)
    aggregate_rows = aggregate(rows)
    if args.fig12_only:
        plot_metric(
            aggregate_rows,
            figure="fig12",
            metric="conditional_prr_mean",
            ci_metric="conditional_prr_ci95",
            ylabel="PRR (unique decoded / min(scheduled, detected physical packets))",
            output_stem=args.out_dir / "fig12_prr_preview",
            methods=FIG12_METHODS,
        )
        print(f"rows={len(rows)} runs={len(set(row['run_id'] for row in rows))}")
        print(f"out={args.out_dir.resolve()}")
        return 0

    raw_csv = args.out_dir / "fig9_10_12_preview_raw.csv"
    aggregate_csv = args.out_dir / "fig9_10_12_preview_aggregate.csv"
    write_raw_csv(rows, raw_csv)
    write_aggregate_csv(aggregate_rows, aggregate_csv)
    plot_metric(
        aggregate_rows,
        figure="fig9_10",
        metric="conditional_prr_mean",
        ci_metric="conditional_prr_ci95",
        ylabel="PRR (unique decoded / min(scheduled, detected physical packets))",
        output_stem=args.out_dir / "fig9_prr_preview",
    )
    plot_metric(
        aggregate_rows,
        figure="fig9_10",
        metric="detection_rate_mean",
        ci_metric="detection_rate_ci95",
        ylabel="Detection rate (detected / scheduled packets)",
        output_stem=args.out_dir / "fig9_detection_preview",
    )
    plot_metric(
        aggregate_rows,
        figure="fig9_10",
        metric="effective_tps_mean",
        ci_metric="effective_tps_ci95",
        ylabel="Decoder TPS (CRC-valid payload bit/s)",
        output_stem=args.out_dir / "fig10_tps_preview",
        title_prefix="Decoder TPS = valid payload bits / total decoder work time",
    )
    plot_metric(
        aggregate_rows,
        figure="fig12",
        metric="conditional_prr_mean",
        ci_metric="conditional_prr_ci95",
        ylabel="PRR (unique decoded / min(scheduled, detected physical packets))",
        output_stem=args.out_dir / "fig12_prr_preview",
        methods=FIG12_METHODS,
    )
    write_coverage(args, rows, notes, args.out_dir / "coverage.md")
    print(f"rows={len(rows)} runs={len(set(row['run_id'] for row in rows))}")
    print(f"out={args.out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
