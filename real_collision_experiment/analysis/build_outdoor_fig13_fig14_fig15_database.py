#!/usr/bin/env python3
"""Build reproducible Fig.13/14/15 tables and plots from outdoor reports.

Every PRR uses the Fig.9/10 definition: unique CRC-valid payload identities
divided by min(planned packets in the strict formal window, detected
anonymous physical candidates). Fig.15 is therefore reported per traffic
mode, rather than assigning undecoded physical candidates to a node using
manifest identities.

Fig.13 TPS is decoder TPS: CRC-valid payload bits divided by the total
post-shared-sync decoder work time for that method.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-outdoor-figures")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from formal_window import formal_analysis_duration_s


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "real_collision_experiment"
METHODS = (
    ("sp_sync_refine", "SP-Decoder"),
    ("mrc", "MRC"),
    ("mrc_cic", "MRC+CIC"),
    ("pcube", "PCube"),
    ("maloragw", "MaLoRaGW"),
)
METHOD_LABELS = dict(METHODS)
METHOD_STYLES = {
    "sp_sync_refine": {"color": "#111111", "marker": "*", "linewidth": 2.1, "markersize": 9},
    "mrc": {"color": "#f58518", "marker": "s", "linestyle": "--"},
    "mrc_cic": {"color": "#54a24b", "marker": "^", "linestyle": "-."},
    "pcube": {"color": "#e45756", "marker": "D", "linestyle": ":"},
    "maloragw": {"color": "#4c78a8", "marker": "v", "linestyle": "--"},
}
FIG15_SERIES = (
    ("ab_simultaneous", "A+B simultaneous", "#111111", "o"),
    ("b_only", "B only", "#4c78a8", "^"),
)
FIG13_SPREADING_FACTORS = (8, 10)
FIG14_SNR_BIN_KEYS = ("lt_m30", "m30_to_m10", "m10_to_10", "ge_10")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def manifest_paths(runs_root: Path) -> list[Path]:
    paths = {path.stem: path.resolve() for path in (runs_root / "manifests").glob("run_*.json")}
    for directory in runs_root.glob("run_*"):
        candidate = directory / f"{directory.name}.json"
        if candidate.exists():
            paths[directory.name] = candidate.resolve()
    return [paths[name] for name in sorted(paths)]


def strict_window(
    report: dict,
    run_name: str,
    *,
    expected_duration_s: float,
) -> tuple[float, float, float]:
    strict = report.get("input", {}).get("strict_middle_business_window", {})
    if not isinstance(strict, dict) or not bool(strict.get("enabled")):
        raise ValueError(f"{run_name}: no strict middle-business-window audit")
    traffic_start_s = float(strict["traffic_start_s_from_full_iq"])
    analysis_start_s = float(strict["analysis_start_s_from_full_iq"])
    analysis_duration_s = float(strict["analysis_duration_s"])
    if abs(analysis_duration_s - expected_duration_s) > 1e-6:
        raise ValueError(
            f"{run_name}: strict analysis duration is {analysis_duration_s:g}, "
            f"expected {expected_duration_s:g} s"
        )
    slice_row = report.get("input", {}).get("analysis_slice", {})
    if not isinstance(slice_row, dict):
        raise ValueError(f"{run_name}: report has no analysis_slice")
    if abs(float(slice_row.get("start_time_s", math.nan)) - analysis_start_s) > 1e-6:
        raise ValueError(f"{run_name}: analysis_slice start does not match strict window")
    if abs(float(slice_row.get("requested_duration_s", math.nan)) - analysis_duration_s) > 1e-6:
        raise ValueError(f"{run_name}: analysis_slice duration does not match strict window")
    return traffic_start_s, analysis_start_s, analysis_duration_s


def manifest_starts_in_strict_window(
    manifest: dict, report: dict, run_name: str, *, expected_duration_s: float
) -> int:
    """Count scheduled TX starts in the report's strict formal window."""

    traffic_start_s, analysis_start_s, duration_s = strict_window(
        report, run_name, expected_duration_s=expected_duration_s
    )
    start_ms = (analysis_start_s - traffic_start_s) * 1000.0
    end_ms = start_ms + duration_s * 1000.0
    schedules = manifest.get("expected_node_schedules", {})
    if not isinstance(schedules, dict):
        raise ValueError(f"{run_name}: manifest has no expected node schedules")
    return sum(
        1
        for schedule in schedules.values()
        if isinstance(schedule, dict)
        for planned_start_ms in schedule.get("tx_start_ms_from_traffic_begin", [])
        if start_ms <= float(planned_start_ms) < end_ms
    )


def shared_fine_sync_candidate_count(
    reports_root: Path,
    report: dict,
    run_name: str,
    *,
    expected_duration_s: float,
) -> int:
    """Load the anonymous detected-candidate count for the exact report window."""

    database_path = reports_root.parent / "fine_sync" / f"{run_name}.json"
    if not database_path.exists():
        raise ValueError(f"{run_name}: missing shared fine-sync database {database_path}")
    database = load_json(database_path)
    if database.get("schema") != "fine_sync_anonymous_physical_v2":
        raise ValueError(
            f"{run_name}: shared fine-sync database schema is "
            f"{database.get('schema')!r}, expected fine_sync_anonymous_physical_v2"
        )
    if database.get("run_id") != run_name:
        raise ValueError(f"{run_name}: shared fine-sync database run_id does not match")
    _, analysis_start_s, duration_s = strict_window(
        report, run_name, expected_duration_s=expected_duration_s
    )
    window = database.get("window", {})
    if (
        abs(float(window.get("analysis_start_s", math.nan)) - analysis_start_s) > 1e-6
        or abs(float(window.get("duration_s", math.nan)) - duration_s) > 1e-6
    ):
        raise ValueError(f"{run_name}: shared fine-sync database window does not match report")
    packets = database.get("packets", [])
    if not isinstance(packets, list) or not packets:
        raise ValueError(f"{run_name}: shared fine-sync database has no physical candidates")
    if any(
        not isinstance(row, dict)
        or row.get("node_id") is not None
        or row.get("sequence") is not None
        for row in packets
    ):
        raise ValueError(f"{run_name}: shared fine-sync database is not anonymous")
    discovery = database.get("candidate_discovery", {})
    if (
        discovery.get("scope") != "global_full_window"
        or discovery.get("manifest_schedule_exposed_to_detector") is not False
        or discovery.get("node_timing_calibration") is not False
        or discovery.get("planned_start_search_windows") is not False
        or discovery.get("score_truncation") is not False
    ):
        raise ValueError(f"{run_name}: fine-sync discovery used schedule guidance")
    return len(packets)


def decoder_prr_metrics(
    report: dict,
    method: str,
    run_name: str,
    manifest_expected_packet_count: int,
) -> dict[str, int | float]:
    """Read and validate min(planned, detected) decoder PRR counters."""

    try:
        row = report["detection_and_decode"]["by_method"][method]
        if row.get("execution_status") != "completed":
            raise ValueError(f"decoder status is {row.get('execution_status')!r}")
        detected = int(row["complete_detected_packet_count"])
        decoded = int(row["decoded_success_count"])
        denominator = int(row["prr_denominator_packet_count"])
        prr = float(row["prr"])
        reported_expected = int(
            row["manifest_expected_packet_count_in_analysis_window"]
        )
        reported_detected = int(row["prr_detected_physical_packet_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{run_name}: {method} lacks the detected-packet decoder-PRR audit"
        ) from exc
    if min(detected, decoded, denominator) < 0:
        raise ValueError(f"{run_name}: {method} has negative decoder-PRR counters")
    if (
        row.get("prr_denominator_source")
        != "min_manifest_window_expected_or_anonymous_detected_packets"
    ):
        raise ValueError(f"{run_name}: {method} does not use min(planned, detected)")
    if row.get("prr_counting_policy") != (
        "unique_crc_valid_payload_identities_over_"
        "min_manifest_window_expected_or_anonymous_detected_packets"
    ):
        raise ValueError(f"{run_name}: {method} has incompatible PRR counting policy")
    expected_denominator = min(manifest_expected_packet_count, detected)
    if (
        reported_expected != manifest_expected_packet_count
        or reported_detected != detected
        or decoded > expected_denominator
        or denominator != expected_denominator
    ):
        raise ValueError(f"{run_name}: {method} decoder-PRR denominator is inconsistent")
    expected_prr = decoded / denominator if denominator else None
    if expected_prr is None or not math.isfinite(prr) or abs(prr - expected_prr) > 1e-9:
        raise ValueError(f"{run_name}: {method} decoder-PRR value is inconsistent")
    return {
        "detected_packet_count": detected,
        "manifest_expected_packet_count_in_analysis_window": (
            manifest_expected_packet_count
        ),
        "decoded_success_packets": decoded,
        "prr_denominator_packets": denominator,
        "prr": prr,
    }


def method_decoder_work_s(
    report: dict,
    method: str,
    run_name: str,
    expected_candidate_count: int,
) -> float:
    """Return serial post-shared-sync decoder work time for one method.

    This reuses the candidate timings recorded during the completed decode;
    it is not a concurrent batch-latency measurement.  Failed candidate
    attempts and method-specific parameter estimation are included.  The
    shared fine-sync front end is excluded for every method.  SP's
    ``post_sp_total_elapsed_ms`` already includes its allocated batch lambda
    configuration work, so the report-level batch audit is not added again.
    """

    candidates = report.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError(f"{run_name}: candidates audit is not a list")
    total_ms = 0.0
    timed_candidate_count = 0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError(f"{run_name}: malformed candidate timing audit")
        rows = candidate.get("methods", [])
        if not isinstance(rows, list):
            raise ValueError(f"{run_name}: malformed method timing audit")
        for row in rows:
            if not isinstance(row, dict) or row.get("method") != method:
                continue
            value = row.get("post_sp_total_elapsed_ms")
            if value is None:
                value = row.get("decode_elapsed_ms")
            try:
                elapsed_ms = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{run_name}: {method} has no usable decoder timing"
                ) from exc
            if not math.isfinite(elapsed_ms) or elapsed_ms < 0.0:
                raise ValueError(f"{run_name}: {method} has invalid decoder timing")
            total_ms += elapsed_ms
            timed_candidate_count += 1
    if timed_candidate_count != expected_candidate_count:
        raise ValueError(
            f"{run_name}: {method} timed {timed_candidate_count} candidates, "
            f"expected {expected_candidate_count}"
        )
    return total_ms / 1000.0


def decoder_tps(decoded_count: int, payload_bits: int, decoder_work_s: float) -> float:
    """Compute TPS from successful payload bits and total decoder latency."""

    if decoded_count == 0:
        return 0.0
    if not math.isfinite(decoder_work_s) or decoder_work_s <= 0.0:
        raise ValueError("successful decoding requires a positive total decoder latency")
    return float(decoded_count) * payload_bits / decoder_work_s


def collect_fig13_and_fig15(
    runs_root: Path,
    reports_root: Path,
    *,
    include_fig15: bool = True,
) -> tuple[list[dict], list[dict], list[str]]:
    fig13_rows: list[dict] = []
    fig15_rows: list[dict] = []
    coverage: list[str] = []
    allowed_figures = {"fig13", "fig15"} if include_fig15 else {"fig13"}
    for manifest_path in manifest_paths(runs_root):
        manifest = load_json(manifest_path)
        experiment = manifest.get("experiment", {})
        figure = str(experiment.get("figure", ""))
        if figure not in allowed_figures:
            continue
        name = manifest_path.stem
        expected_duration_s = formal_analysis_duration_s(figure)
        if figure == "fig13":
            spreading_factor = int(
                manifest.get("radio", {}).get("spreading_factor", 0)
            )
            if spreading_factor not in FIG13_SPREADING_FACTORS:
                coverage.append(
                    f"- {name}: Fig.13 SF={spreading_factor} omitted; "
                    "only SF=8 and SF=10 are plotted"
                )
                continue
        report_path = reports_root / f"{name}.json"
        if not report_path.exists():
            coverage.append(f"- {name}: missing decoder report")
            continue
        try:
            report = load_json(report_path)
            _, _, analysis_duration_s = strict_window(
                report, name, expected_duration_s=expected_duration_s
            )
            manifest_expected_packet_count = manifest_starts_in_strict_window(
                manifest, report, name, expected_duration_s=expected_duration_s
            )
        except (KeyError, TypeError, ValueError) as exc:
            coverage.append(f"- {name}: excluded: {exc}")
            continue
        if figure == "fig13":
            sf = int(manifest.get("radio", {}).get("spreading_factor", 0))
            bandwidth_hz = int(manifest.get("radio", {}).get("bandwidth_hz", 0))
            node_count = int(manifest.get("active_node_count", len(manifest.get("active_nodes", []))))
            try:
                candidate_count = shared_fine_sync_candidate_count(
                    reports_root, report, name, expected_duration_s=expected_duration_s
                )
                metrics_by_method = {
                    method: decoder_prr_metrics(
                        report, method, name, manifest_expected_packet_count
                    )
                    for method, _ in METHODS
                }
                decoder_work_by_method = {
                    method: method_decoder_work_s(
                        report,
                        method,
                        name,
                        int(metrics_by_method[method]["detected_packet_count"]),
                    )
                    for method, _ in METHODS
                }
                for method, metrics in metrics_by_method.items():
                    if int(metrics["detected_packet_count"]) != candidate_count:
                        raise ValueError(
                            f"{name}: {method} reports "
                            f"D={metrics['detected_packet_count']}, but shared "
                            f"anonymous fine-sync database has D={candidate_count}"
                        )
            except ValueError as exc:
                coverage.append(f"- {name}: excluded: {exc}")
                continue
            for method, label in METHODS:
                payload_bits = int(
                    manifest.get("traffic", {}).get("data_payload_bytes", 20)
                ) * 8
                fig13_rows.append(
                    {
                        "run": name,
                        "sf": sf,
                        "bandwidth_hz": bandwidth_hz,
                        "node_count": node_count,
                        "merged": bool(experiment.get("simulated_merged", False)),
                        "method": method,
                        "method_label": label,
                        "strict_window_s": float(analysis_duration_s),
                        "payload_bits": payload_bits,
                        "radio_window_tps_bps": decoder_tps(
                            int(metrics_by_method[method]["decoded_success_packets"]),
                            payload_bits,
                            decoder_work_by_method[method],
                        ),
                        "decoder_work_s": decoder_work_by_method[method],
                        "decoder_work_realtime_factor": (
                            decoder_work_by_method[method]
                            / float(analysis_duration_s)
                        ),
                        "effective_tps_bps": decoder_tps(
                            int(metrics_by_method[method]["decoded_success_packets"]),
                            payload_bits,
                            decoder_work_by_method[method],
                        ),
                        **metrics_by_method[method],
                    }
                )
            continue

        try:
            candidate_count = shared_fine_sync_candidate_count(
                reports_root, report, name, expected_duration_s=expected_duration_s
            )
            metrics = decoder_prr_metrics(
                report, "sp_sync_refine", name, manifest_expected_packet_count
            )
            if int(metrics["detected_packet_count"]) != candidate_count:
                raise ValueError(
                    f"{name}: SP reports D={metrics['detected_packet_count']}, "
                    f"but anonymous fine-sync database has D={candidate_count}"
                )
        except (KeyError, TypeError, ValueError) as exc:
            coverage.append(f"- {name}: excluded: {exc}")
            continue
        tags = experiment
        mode = str(tags.get("mode", ""))
        distance_m = float(tags["node_b_distance_m"])
        position_index = int(tags["position_index"])
        if mode == "ab_simultaneous":
            series, label = "ab_simultaneous", "A+B simultaneous"
        elif mode == "b_only":
            series, label = "b_only", "B only"
        else:
            coverage.append(f"- {name}: Fig.15 has unknown mode {mode!r}")
            continue
        fig15_rows.append(
            {
                "run": name,
                "position_index": position_index,
                "node_a_distance_m": float(tags["node_a_distance_m"]),
                "node_b_distance_m": distance_m,
                "mode": mode,
                "series": series,
                "series_label": label,
                "method": "sp_sync_refine",
                "strict_window_s": float(analysis_duration_s),
                **metrics,
            }
        )
    return fig13_rows, fig15_rows, coverage


def collect_fig14(fig14_path: Path | None, coverage: list[str]) -> list[dict]:
    if fig14_path is None:
        coverage.append("- Fig.14: no --fig14-report supplied")
        return []
    if not fig14_path.exists():
        coverage.append(f"- Fig.14: missing SNR-bin report {fig14_path}")
        return []
    payload = load_json(fig14_path)
    if payload.get("schema") != "fig14_outdoor_awgn_snr_bins_v7":
        raise ValueError(f"unsupported Fig.14 report schema: {payload.get('schema')!r}")
    order = {key: index for index, key in enumerate(FIG14_SNR_BIN_KEYS)}
    rows = []
    for row in payload.get("aggregate", []):
        method = str(row.get("method", ""))
        if method not in METHOD_LABELS:
            continue
        try:
            if (
                row.get("prr_denominator_source")
                != "min_manifest_window_expected_or_anonymous_detected_packets"
            ):
                raise ValueError("Fig.14 aggregate does not use min(planned, detected)")
            if row.get("prr_counting_policy") != (
                "unique_crc_valid_payload_identities_over_"
                "min_manifest_window_expected_or_anonymous_detected_packets"
            ):
                raise ValueError("Fig.14 aggregate has incompatible PRR counting policy")
            detected = int(row["detected_packet_count"])
            decoded = int(row["decoded_success_count"])
            denominator = int(row["prr_denominator_packet_count"])
            planned = int(row["manifest_expected_packet_count_in_analysis_window"])
            prr = float(row["conditional_prr"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Fig.14 aggregate row lacks PRR counters: {row!r}") from exc
        if min(detected, decoded, denominator) < 0:
            raise ValueError("Fig.14 aggregate has negative PRR counters")
        if decoded > min(planned, detected) or denominator != min(planned, detected):
            raise ValueError("Fig.14 aggregate has inconsistent min(planned, detected) counters")
        if denominator <= 0 or not math.isfinite(prr) or abs(prr - decoded / denominator) > 1e-9:
            raise ValueError("Fig.14 aggregate has inconsistent PRR value")
        key = str(row["snr_bin_key"])
        rows.append(
            {
                "snr_bin_key": key,
                "snr_bin_order": order[key],
                "snr_bin_label": str(row["snr_bin_label"]),
                "method": method,
                "method_label": METHOD_LABELS[method],
                "source_point_count": int(row["source_point_count"]),
                "detected_packet_count": detected,
                "manifest_expected_packet_count_in_analysis_window": planned,
                "decoded_success_packets": decoded,
                "prr_denominator_packets": denominator,
                "prr": prr,
                "median_measured_snr_db": float(row["median_measured_snr_db"]),
            }
        )
    if not rows:
        coverage.append("- Fig.14: no accepted aggregate point for the selected formal methods")
    return rows


def save_database(
    out_dir: Path,
    fig13: list[dict],
    fig14: list[dict],
    fig15: list[dict],
    coverage: list[str],
    *,
    fig13_only: bool = False,
) -> None:
    write_csv(
        out_dir / "fig13_prr.csv",
        fig13,
        ["run", "sf", "bandwidth_hz", "node_count", "merged", "method", "method_label", "strict_window_s", "payload_bits", "manifest_expected_packet_count_in_analysis_window", "detected_packet_count", "decoded_success_packets", "prr_denominator_packets", "prr", "radio_window_tps_bps", "decoder_work_s", "decoder_work_realtime_factor", "effective_tps_bps"],
    )
    if not fig13_only:
        write_csv(
            out_dir / "fig14_prr.csv",
            fig14,
            ["snr_bin_key", "snr_bin_order", "snr_bin_label", "method", "method_label", "source_point_count", "manifest_expected_packet_count_in_analysis_window", "detected_packet_count", "decoded_success_packets", "prr_denominator_packets", "prr", "median_measured_snr_db"],
        )
        write_csv(
            out_dir / "fig15_prr.csv",
            fig15,
            ["run", "position_index", "node_a_distance_m", "node_b_distance_m", "mode", "series", "series_label", "method", "strict_window_s", "manifest_expected_packet_count_in_analysis_window", "detected_packet_count", "decoded_success_packets", "prr_denominator_packets", "prr"],
        )
    (out_dir / "coverage.md").write_text(
        ("# 室外 Fig.13 数据覆盖\n\n" if fig13_only else "# 室外 Fig.13--15 数据覆盖\n\n")
        + ("Fig.13 使用居中 5 秒窗口。" if fig13_only else "Fig.13--14 使用居中 5 秒窗口，Fig.15 使用居中 10 秒窗口。")
        + "PRR 均为"
        "`去重后的 CRC 成功 payload / min(窗口计划发包数, 匿名物理候选数)`。"
        "Fig.13 TPS 为 CRC 成功 payload bits / "
        "post-shared-sync decoder work time。"
        "解码工作时间包括全部候选（含失败）的方案参数估计和 payload 解码；"
        "共享 fine-sync 前端在各方案中均排除。"
        "匿名库在各自完整居中窗口的 IQ 上做全局结构检测；"
        "manifest 计划时刻不进入候选发现、排序、精细化或去重，只在解码后统计分母。"
        + (
            "\n\n"
            if fig13_only
            else "库中不保存节点或序号；Fig.15 因此按业务模式统计，不能把未解码候选虚假归属到某个节点。\n\n"
        )
        + ("\n".join(coverage) if coverage else "全部已发现报告均通过窗口检查。")
        + "\n",
        encoding="utf-8",
    )


def plot_fig13(rows: list[dict], output_dir: Path) -> None:
    if not rows:
        return
    available = {int(row["sf"]) for row in rows}
    missing = set(FIG13_SPREADING_FACTORS) - available
    if missing:
        raise ValueError(
            "Fig.13 rendering requires SF=8 and SF=10 data; missing "
            + ", ".join(f"SF={value}" for value in sorted(missing))
        )
    panels = (
        (8, "prr", "(a) SF=8, PRR", "fig13_sf8_prr"),
        (10, "prr", "(b) SF=10, PRR", "fig13_sf10_prr"),
        (8, "effective_tps_bps", "(c) SF=8, decoder TPS", "fig13_sf8_tps"),
        (10, "effective_tps_bps", "(d) SF=10, decoder TPS", "fig13_sf10_tps"),
    )
    for spreading_factor, metric, title, stem in panels:
        figure, axis = plt.subplots(figsize=(5.6, 4.1))
        subset = [row for row in rows if int(row["sf"]) == spreading_factor]
        for method, label in METHODS:
            points = sorted(
                (row for row in subset if row["method"] == method),
                key=lambda row: int(row["node_count"]),
            )
            if not points:
                continue
            axis.plot(
                [int(row["node_count"]) for row in points],
                [float(row[metric]) for row in points],
                label=label,
                **METHOD_STYLES[method],
            )
        axis.set_title(title)
        axis.set_xlabel("Active nodes N")
        axis.set_xticks(sorted({int(row["node_count"]) for row in subset}))
        axis.set_ylabel(
            "PRR (unique decoded / min(planned, detected physical packets))"
            if metric == "prr"
            else "Decoder TPS (CRC-valid payload bit/s)"
        )
        if metric == "prr":
            axis.set_ylim(-0.02, 1.02)
        else:
            axis.set_ylim(bottom=0.0)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8, ncol=2, loc="best")
        figure.tight_layout()
        for suffix in ("pdf", "png"):
            figure.savefig(
                (output_dir / stem).with_suffix(f".{suffix}"),
                dpi=220,
                bbox_inches="tight",
            )
        plt.close(figure)


def plot_fig13_combined(rows: list[dict], output: Path) -> None:
    """Render the legacy combined Fig.13 filename with the new TPS metric."""

    if not rows:
        return
    spreading_factors = sorted({int(row["sf"]) for row in rows})
    figure, axes = plt.subplots(1, 2, figsize=(11.2, 4.1), squeeze=False)
    line_styles = ("-", "--", ":", "-.")
    panels = (
        (
            axes[0][0],
            "prr",
            "(a) PRR",
            "PRR (unique decoded / min(planned, detected physical packets))",
        ),
        (
            axes[0][1],
            "effective_tps_bps",
            "(b) Decoder TPS",
            "Decoder TPS (CRC-valid payload bit/s)",
        ),
    )
    for axis, metric, title, ylabel in panels:
        for sf_index, spreading_factor in enumerate(spreading_factors):
            subset = [row for row in rows if int(row["sf"]) == spreading_factor]
            for method, label in METHODS:
                points = sorted(
                    (row for row in subset if row["method"] == method),
                    key=lambda row: int(row["node_count"]),
                )
                if not points:
                    continue
                style = dict(METHOD_STYLES[method])
                style["linestyle"] = line_styles[sf_index % len(line_styles)]
                axis.plot(
                    [int(row["node_count"]) for row in points],
                    [float(row[metric]) for row in points],
                    label=f"{label}, SF={spreading_factor}",
                    **style,
                )
        axis.set_title(title)
        axis.set_xlabel("Active nodes N")
        axis.set_xticks(sorted({int(row["node_count"]) for row in rows}))
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
    axes[0][0].set_ylim(-0.02, 1.02)
    axes[0][1].set_ylim(bottom=0.0)
    axes[0][1].legend(fontsize=7, ncol=2, loc="best")
    figure.tight_layout()
    for suffix in ("pdf", "png"):
        figure.savefig(output.with_suffix(f".{suffix}"), dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_fig14(rows: list[dict], output: Path) -> None:
    if not rows:
        return
    labels = ["<-30 dB", "[-30,-10) dB", "[-10,10) dB", ">=10 dB"]
    figure, axis = plt.subplots(figsize=(8.4, 4.3))
    x = np.arange(len(FIG14_SNR_BIN_KEYS), dtype=float)
    width = 0.82 / len(METHODS)
    lookup = {
        (str(row["snr_bin_key"]), str(row["method"])): float(row["prr"])
        for row in rows
    }
    for method_index, (method, label) in enumerate(METHODS):
        values = [lookup.get((key, method), math.nan) for key in FIG14_SNR_BIN_KEYS]
        offset = -0.41 + width / 2 + method_index * width
        axis.bar(
            x + offset,
            values,
            width=width,
            color=METHOD_STYLES[method]["color"],
            label=label,
        )
    axis.set_xticks(x, labels)
    axis.set_xlabel("Measured median preamble SNR bin")
    axis.set_ylabel("PRR (unique decoded / min(planned, detected physical packets))")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.set_axisbelow(True)
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    for suffix in ("pdf", "png"):
        figure.savefig(output.with_suffix(f".{suffix}"), dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_fig15(rows: list[dict], output: Path) -> None:
    if not rows:
        return
    figure, axis = plt.subplots(figsize=(7.0, 4.1))
    for series, label, color, marker in FIG15_SERIES:
        points = sorted((row for row in rows if row["series"] == series), key=lambda row: float(row["node_b_distance_m"]))
        if not points:
            continue
        axis.plot(
            [float(row["node_b_distance_m"]) for row in points],
            [float(row["prr"]) for row in points],
            color=color,
            marker=marker,
            linewidth=2.0,
            label=label,
        )
    distances = sorted({float(row["node_b_distance_m"]) for row in rows})
    axis.set_xticks(distances)
    axis.set_xlabel("Node B distance to gateway (m)")
    axis.set_ylabel("PRR (unique decoded / min(planned, detected physical packets))")
    axis.set_ylim(-0.02, 1.02)
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    for suffix in ("pdf", "png"):
        figure.savefig(output.with_suffix(f".{suffix}"), dpi=220, bbox_inches="tight")
    plt.close(figure)


def plot_database(
    database_dir: Path,
    output_dir: Path,
    *,
    fig13_only: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig13 = read_csv(database_dir / "fig13_prr.csv")
    plot_fig13(fig13, output_dir)
    plot_fig13_combined(fig13, output_dir / "fig13_prr_tps")
    if not fig13_only:
        fig14 = read_csv(database_dir / "fig14_prr.csv")
        fig15 = read_csv(database_dir / "fig15_prr.csv")
        plot_fig14(fig14, output_dir / "fig14_prr_by_snr")
        plot_fig15(fig15, output_dir / "fig15_near_far_prr")


def build_command(args: argparse.Namespace) -> int:
    fig13, fig15, coverage = collect_fig13_and_fig15(
        args.runs, args.reports, include_fig15=not args.fig13_only
    )
    fig14 = [] if args.fig13_only else collect_fig14(args.fig14_report, coverage)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    save_database(
        args.out_dir, fig13, fig14, fig15, coverage, fig13_only=args.fig13_only
    )
    save_json(
        args.out_dir / "database_manifest.json",
        {
            "schema": "outdoor_fig13_fig14_fig15_database_v7",
            "runs_root": str(args.runs.resolve()),
            "reports_root": str(args.reports.resolve()),
            "fig14_report": str(args.fig14_report.resolve()) if args.fig14_report else None,
            "fig13_only": bool(args.fig13_only),
            "fig13_rows": len(fig13),
            "fig14_rows": len(fig14),
            "fig15_rows": len(fig15),
            "prr_definition": (
                "unique CRC-valid payload identities / min(manifest planned "
                "packets in each figure's strict business window, "
                "anonymous detected physical candidates)"
            ),
            "fig13_tps_definition": (
                "CRC-valid decoded payload bits / total post-shared-sync "
                "decoder work time"
            ),
            "fig15_scope": "Each series is a complete traffic mode. Anonymous candidates are not assigned to a node after failed decoding.",
        },
    )
    if not args.skip_plots:
        plot_database(args.out_dir, args.out_dir, fig13_only=args.fig13_only)
    print(f"OUTDOOR_DATABASE_DONE fig13_rows={len(fig13)} fig14_rows={len(fig14)} fig15_rows={len(fig15)} out={args.out_dir.resolve()}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="validate strict reports and write tidy CSV tables")
    build.add_argument("--runs", type=Path, default=EXPERIMENT / "runs_outdoor")
    build.add_argument("--reports", type=Path, default=EXPERIMENT / "analysis/outdoor_fig13_fig15/reports")
    build.add_argument("--fig14-report", type=Path, default=None)
    build.add_argument("--out-dir", type=Path, required=True)
    build.add_argument("--skip-plots", action="store_true")
    build.add_argument(
        "--fig13-only",
        action="store_true",
        help="skip Fig.14 and Fig.15 collection, tables, and plots",
    )
    build.set_defaults(func=build_command)
    plot = commands.add_parser("plot", help="render figures from existing tidy CSV tables")
    plot.add_argument("--database-dir", type=Path, required=True)
    plot.add_argument("--out-dir", type=Path, default=None)
    plot.add_argument(
        "--fig13-only",
        action="store_true",
        help="render only the four Fig.13 panels",
    )
    plot.set_defaults(
        func=lambda args: (
            plot_database(
                args.database_dir,
                args.out_dir or args.database_dir,
                fig13_only=args.fig13_only,
            ),
            0,
        )[1]
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
