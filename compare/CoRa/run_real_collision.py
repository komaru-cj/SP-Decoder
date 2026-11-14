#!/usr/bin/env python3
"""Run faithful CoRa+TnB-BEC decoding on the formal shared-sync datasets.

The formal experiment deliberately supplies every method with the same
schedule-free anonymous fine-synchronization database.  This runner therefore
starts at the paper's CoRa symbol detector, retains its published Bayesian
PMD/HPD classifier, and then executes TnB's BEC/CRC closure.  Shared sync is
excluded from decoder work time exactly as it is for the existing comparison
methods.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
NODE_RECEIVER = ROOT / "real_collision_experiment" / "node01_sp_receiver"
CONTROL = ROOT / "real_collision_experiment" / "control_usrp"
for source_path in (ROOT, NODE_RECEIVER, CONTROL):
    if str(source_path) not in sys.path:
        sys.path.insert(0, str(source_path))

from cora_detector import CoRaDetector  # noqa: E402
from protocol import decode_data_payload  # noqa: E402
from real_lora_config import RealCollisionLoRaConfig  # noqa: E402
from sc16_io import load_capture  # noqa: E402
from tnb_bec import TnBBECDecoder  # noqa: E402


PAYLOAD_BITS = 160
WINDOW_SECONDS = 5.0
POSTERIOR = (
    Path(__file__).parent
    / "upstream/cora_v2/artifacts/python/models/dist.pkl"
)
RESULTS_ROOT = Path(__file__).parent / "results"


@dataclass(frozen=True)
class DatasetPoint:
    scope: str
    setting: str
    sf: int
    bandwidth_hz: int
    node_count: int
    run: str
    analysis_dir: Path
    window_seconds: float = WINDOW_SECONDS


def dataset_points() -> list[DatasetPoint]:
    indoor = ROOT / "real_collision_experiment/analysis/fig9_10_12_5s"
    outdoor = ROOT / "real_collision_experiment/analysis/outdoor_fig13_10s"
    points: list[DatasetPoint] = []
    for nodes, token in zip((3, 6, 9, 12, 15), ("03", "06", "09", "0c", "0f")):
        points.append(
            DatasetPoint(
                "indoor", "SF10_BW125k", 10, 125_000, nodes,
                f"run_{token}012131", indoor,
            )
        )
        points.append(
            DatasetPoint(
                "indoor", "SF10_BW250k", 10, 250_000, nodes,
                f"run_{token}015131", indoor,
            )
        )
        points.append(
            DatasetPoint(
                "outdoor", "SF8_BW250k", 8, 250_000, nodes,
                f"run_{token}014161", outdoor, 10.0,
            )
        )
        points.append(
            DatasetPoint(
                "outdoor", "SF10_BW250k", 10, 250_000, nodes,
                f"run_{token}015161", outdoor, 10.0,
            )
        )
    for nodes, indoor_token, outdoor_token in (
        (18, "120", "12"),
        (21, "150", "15"),
        (24, "180", "18"),
    ):
        points.append(
            DatasetPoint(
                "indoor", "SF10_BW125k", 10, 125_000, nodes,
                f"run_{indoor_token}12131", indoor,
            )
        )
        points.append(
            DatasetPoint(
                "indoor", "SF10_BW250k", 10, 250_000, nodes,
                f"run_{indoor_token}15131", indoor,
            )
        )
        points.append(
            DatasetPoint(
                "outdoor", "SF8_BW250k", 8, 250_000, nodes,
                f"run_e04{outdoor_token}600", outdoor, 10.0,
            )
        )
        points.append(
            DatasetPoint(
                "outdoor", "SF10_BW250k", 10, 250_000, nodes,
                f"run_e05{outdoor_token}600", outdoor, 10.0,
            )
        )
    return sorted(points, key=lambda row: (row.scope, row.setting, row.node_count))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_expected_in_window(
    fine: dict, manifest: dict, expected_window_s: float
) -> int:
    window = fine.get("window", {})
    traffic_start_s = float(window["traffic_start_s"])
    analysis_start_s = float(window["analysis_start_s"])
    duration_s = float(window["duration_s"])
    if abs(duration_s - expected_window_s) > 1e-9:
        raise ValueError(
            f"formal strict window is {duration_s}, expected {expected_window_s} seconds"
        )
    begin_ms = (analysis_start_s - traffic_start_s) * 1000.0
    end_ms = begin_ms + duration_s * 1000.0
    schedules = manifest.get("expected_node_schedules", {})
    return sum(
        1
        for schedule in schedules.values()
        if isinstance(schedule, dict)
        for planned_ms in schedule.get("tx_start_ms_from_traffic_begin", [])
        if begin_ms <= float(planned_ms) < end_ms
    )


def identity_aliases(manifest: dict) -> dict[tuple[int, int], int]:
    aliases: dict[tuple[int, int], int] = {}
    for merged_node, schedule in manifest.get("expected_node_schedules", {}).items():
        if not isinstance(schedule, dict):
            continue
        source_run = schedule.get("source_run_id")
        source_node = schedule.get("source_node_id")
        if source_run is not None and source_node is not None:
            aliases[(int(source_run), int(source_node))] = int(merged_node)
    return aliases


def validate_inputs(
    point: DatasetPoint, fine: dict, report: dict | None
) -> None:
    if fine.get("schema") != "fine_sync_anonymous_physical_v2":
        raise ValueError(f"{point.run}: incompatible fine-sync schema")
    discovery = fine.get("candidate_discovery", {})
    required = {
        "scope": "global_full_window",
        "manifest_schedule_exposed_to_detector": False,
        "node_timing_calibration": False,
        "planned_start_search_windows": False,
        "score_truncation": False,
    }
    for key, expected in required.items():
        if discovery.get(key) != expected:
            raise ValueError(f"{point.run}: invalid shared-sync audit {key}")
    if int(fine["spreading_factor"]) != point.sf:
        raise ValueError(f"{point.run}: spreading factor mismatch")
    if int(fine["bandwidth_hz"]) != point.bandwidth_hz:
        raise ValueError(f"{point.run}: bandwidth mismatch")
    if abs(float(fine["window"]["duration_s"]) - point.window_seconds) > 1e-9:
        raise ValueError(
            f"{point.run}: fine-sync window is not {point.window_seconds} seconds"
        )
    if report is not None and Path(report.get("input", {}).get("iq", "")).stem != point.run:
        raise ValueError(f"{point.run}: report IQ run id mismatch")
    packets = fine.get("packets", [])
    if not isinstance(packets, list) or not packets:
        raise ValueError(f"{point.run}: empty shared-sync candidate database")
    if any(row.get("node_id") is not None or row.get("sequence") is not None for row in packets):
        raise ValueError(f"{point.run}: fine-sync candidates are not anonymous")


def decode_point(point: DatasetPoint, detector: CoRaDetector) -> dict:
    fine_path = point.analysis_dir / "fine_sync" / f"{point.run}.json"
    report_path = point.analysis_dir / "reports" / f"{point.run}.json"
    fine = load_json(fine_path)
    report = load_json(report_path) if report_path.exists() else None
    validate_inputs(point, fine, report)
    if report is not None:
        manifest_path = Path(report["input"]["manifest"])
    else:
        source_iq = Path(fine["source_iq"])
        manifest_path = source_iq.parent / f"{source_iq.stem}.json"
    if not manifest_path.exists():
        raise ValueError(f"{point.run}: manifest not found at {manifest_path}")
    manifest = load_json(manifest_path)

    cfg = RealCollisionLoRaConfig(
        sf=point.sf,
        bw_hz=float(point.bandwidth_hz),
        sample_rate_hz=float(fine["sample_rate_hz"]),
        # All four requested PHYs have symbol durations below 16 ms.
        ldro=(2**point.sf) / float(point.bandwidth_hz) >= 0.016,
    )
    if (
        report is not None
        and int(cfg.payload_symbol_count) != int(report["config"]["payload_symbol_count"])
    ):
        raise ValueError(f"{point.run}: computed payload symbol count mismatch")

    capture = load_capture(
        Path(fine["source_iq"]),
        start_time_s=float(fine["window"]["analysis_start_s"]),
        max_duration_s=float(fine["window"]["duration_s"]),
    )
    samples = capture.samples.astype(np.complex64, copy=False)
    # Match the existing formal receiver's physical (pre-whitening) input.
    noise_samples = min(samples.shape[1], round(3.0 * cfg.sample_rate_hz))
    samples = samples - np.mean(samples[:, :noise_samples], axis=1, keepdims=True)

    bec = TnBBECDecoder(random_seed=0)
    aliases = identity_aliases(manifest)
    decoded_identities: set[tuple[int, int]] = set()
    successful_candidates: list[dict] = []
    statuses: Counter[str] = Counter()
    work_s = 0.0
    stage_s: Counter[str] = Counter()
    per_candidate_ms: list[float] = []
    candidate_mrc_parameters: list[dict] = []

    for candidate_id, estimate in enumerate(fine["packets"]):
        started_ns = time.perf_counter_ns()
        symbols = detector.detect(samples, estimate, cfg)
        candidate_mrc_parameters.append({
            "candidate_id": candidate_id,
            "channel_source": symbols.mrc_channel_source,
            "weights": [[w.real, w.imag] for w in symbols.mrc_weights],
        })
        phy = bec.decode(symbols.symbol_bins, cfg)
        identity = None
        app_status = "not_attempted"
        if phy.phy_crc_ok and len(phy.payload) == PAYLOAD_BITS // 8:
            try:
                app = decode_data_payload(phy.payload)
            except ValueError as exc:
                app_status = str(exc)
            else:
                merged_node = aliases.get(
                    (int(app.run_id), int(app.node_id)), int(app.node_id)
                )
                identity = (int(merged_node), int(app.sequence))
                decoded_identities.add(identity)
                app_status = "ok"
        elapsed_s = (time.perf_counter_ns() - started_ns) / 1e9
        work_s += elapsed_s
        per_candidate_ms.append(elapsed_s * 1000.0)
        statuses[phy.status if app_status in ("not_attempted", "ok") else app_status] += 1
        for stage, seconds in symbols.stage_seconds.items():
            stage_s[stage] += float(seconds)
        if identity is not None:
            successful_candidates.append(
                {
                    "candidate_id": candidate_id,
                    "node_id": identity[0],
                    "sequence": identity[1],
                    "source_payload_hex": phy.payload.hex(),
                    "bec_crc_attempts": phy.made_crc_attempts,
                    "bec_total_candidate_schedules": phy.total_candidate_schedules,
                    "bec_additionally_corrected_codewords": (
                        phy.additionally_corrected_codewords
                    ),
                    "decoder_elapsed_ms": elapsed_s * 1000.0,
                }
            )

    scheduled = manifest_expected_in_window(fine, manifest, point.window_seconds)
    detected = len(fine["packets"])
    denominator = min(scheduled, detected)
    successes = len(decoded_identities)
    if successes > denominator:
        raise ValueError(
            f"{point.run}: {successes} unique valid identities exceed denominator {denominator}"
        )
    prr = successes / denominator if denominator else None
    effective_duration_s = max(point.window_seconds, work_s)
    result = {
        **asdict(point),
        "analysis_dir": str(point.analysis_dir.resolve()),
        "method": "mrc_cora",
        "method_label": "MRC+CoRa",
        "merged": point.node_count > 15,
        "strict_window_s": point.window_seconds,
        "payload_bits": PAYLOAD_BITS,
        "manifest_expected_packet_count_in_analysis_window": scheduled,
        "detected_packet_count": detected,
        "decoded_success_packets": successes,
        "prr_denominator_packets": denominator,
        "prr": prr,
        "radio_window_tps_bps": successes * PAYLOAD_BITS / point.window_seconds,
        "decoder_work_s": work_s,
        "decoder_work_realtime_factor": work_s / point.window_seconds,
        "effective_tps_bps": successes * PAYLOAD_BITS / effective_duration_s,
        "metric_definition": {
            "prr": (
                "unique CRC-valid application payload identities / "
                "min(manifest-window expected packets, anonymous detected packets)"
            ),
            "tps": (
                "unique successful payload bits / max(strict radio window, summed "
                "serial post-shared-sync CoRa+TnB-BEC decoder work)"
            ),
            "shared_fine_sync_excluded_from_decoder_work": True,
        },
        "fine_sync": str(fine_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "source_iq": str(Path(fine["source_iq"]).resolve()),
        "posterior_grid": str(POSTERIOR.resolve()),
        "posterior_grid_shape": list(detector.posterior.shape),
        "status_counts": dict(sorted(statuses.items())),
        "detector_stage_s": dict(sorted(stage_s.items())),
        "candidate_decoder_elapsed_ms": per_candidate_ms,
        "candidate_mrc_parameters": candidate_mrc_parameters,
        "decoded_identities": [list(row) for row in sorted(decoded_identities)],
        "successful_candidates": successful_candidates,
    }
    return result


CSV_FIELDS = [
    "run", "scope", "setting", "sf", "bandwidth_hz", "node_count", "merged",
    "method", "method_label", "strict_window_s", "payload_bits",
    "manifest_expected_packet_count_in_analysis_window", "detected_packet_count",
    "decoded_success_packets", "prr_denominator_packets", "prr",
    "radio_window_tps_bps", "decoder_work_s", "decoder_work_realtime_factor",
    "effective_tps_bps",
]

INDOOR_AGGREGATE_FIELDS = [
    "figure", "duty_cycle", "bandwidth_hz", "setting", "simulated",
    "method", "method_label", "usable_rounds", "window_duration_s",
    "conditional_prr_mean", "conditional_prr_ci95", "scheduled_prr_mean",
    "scheduled_prr_ci95", "detection_rate_mean", "detection_rate_ci95",
    "radio_window_tps_mean", "radio_window_tps_ci95",
    "radio_window_goodput_kbps_mean", "radio_window_goodput_kbps_ci95",
    "effective_tps_mean", "effective_tps_ci95",
    "effective_goodput_kbps_mean", "effective_goodput_kbps_ci95",
    "decoder_work_s_mean", "decoder_work_s_ci95",
    "decoder_work_realtime_factor_mean", "decoder_work_realtime_factor_ci95",
    "complete_candidates_total", "decoded_successes_total",
]

OUTDOOR_FIG13_FIELDS = [
    "run", "sf", "bandwidth_hz", "node_count", "merged", "method",
    "method_label", "strict_window_s", "payload_bits",
    "manifest_expected_packet_count_in_analysis_window", "detected_packet_count",
    "decoded_success_packets", "prr_denominator_packets", "prr",
    "radio_window_tps_bps", "decoder_work_s", "decoder_work_realtime_factor",
    "effective_tps_bps",
]


def write_csv(path: Path, rows: list[dict], fields: list[str] = CSV_FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def publish(rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda row: (row["scope"], row["setting"], row["node_count"]))
    write_csv(RESULTS_ROOT / "mrc_cora_prr_tps.csv", rows)
    (RESULTS_ROOT / "mrc_cora_prr_tps.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    indoor_rows = [row for row in rows if row["scope"] == "indoor"]
    outdoor_rows = [row for row in rows if row["scope"] == "outdoor"]
    indoor_aggregate = [
        {
            "figure": "fig9_10",
            "duty_cycle": 0.25,
            "bandwidth_hz": row["bandwidth_hz"],
            "setting": row["node_count"],
            "simulated": row["merged"],
            "method": "mrc_cora",
            "method_label": "MRC+CoRa",
            "usable_rounds": 1,
            "window_duration_s": row["strict_window_s"],
            "conditional_prr_mean": row["prr"],
            "conditional_prr_ci95": "",
            "scheduled_prr_mean": row["prr"],
            "scheduled_prr_ci95": "",
            "detection_rate_mean": (
                row["detected_packet_count"]
                / row["manifest_expected_packet_count_in_analysis_window"]
            ),
            "detection_rate_ci95": "",
            "radio_window_tps_mean": row["radio_window_tps_bps"],
            "radio_window_tps_ci95": "",
            "radio_window_goodput_kbps_mean": row["radio_window_tps_bps"] / 1000.0,
            "radio_window_goodput_kbps_ci95": "",
            "effective_tps_mean": row["effective_tps_bps"],
            "effective_tps_ci95": "",
            "effective_goodput_kbps_mean": row["effective_tps_bps"] / 1000.0,
            "effective_goodput_kbps_ci95": "",
            "decoder_work_s_mean": row["decoder_work_s"],
            "decoder_work_s_ci95": "",
            "decoder_work_realtime_factor_mean": row["decoder_work_realtime_factor"],
            "decoder_work_realtime_factor_ci95": "",
            "complete_candidates_total": row["detected_packet_count"],
            "decoded_successes_total": row["decoded_success_packets"],
        }
        for row in indoor_rows
    ]
    write_csv(
        ROOT / "real_collision_experiment/analysis/fig9_10_12_5s/fig9_10_mrc_cora_prr_tps.csv",
        indoor_aggregate,
        INDOOR_AGGREGATE_FIELDS,
    )
    write_csv(
        ROOT / "real_collision_experiment/analysis/outdoor_fig13_5s/fig_13_mrc_cora_prr_tps.csv",
        outdoor_rows,
        OUTDOOR_FIG13_FIELDS,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", default=[], help="run id or setting")
    parser.add_argument("--force", action="store_true", help="ignore existing per-run result")
    args = parser.parse_args()
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    run_results = RESULTS_ROOT / "runs"
    run_results.mkdir(parents=True, exist_ok=True)
    detector = CoRaDetector(POSTERIOR)
    filters = set(args.only)
    points = [
        point for point in dataset_points()
        if not filters or point.run in filters or point.setting in filters
    ]
    for index, point in enumerate(points, 1):
        output = run_results / f"{point.run}.mrc_cora.json"
        if output.exists() and not args.force:
            result = load_json(output)
            print(
                f"CORA_SKIP {index}/{len(points)} {point.run} "
                f"PRR={result['prr']:.9f} TPS={result['effective_tps_bps']:.6f}",
                flush=True,
            )
            continue
        started = time.perf_counter()
        result = decode_point(point, detector)
        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(
            f"CORA_DONE {index}/{len(points)} {point.run} "
            f"success={result['decoded_success_packets']}/"
            f"{result['prr_denominator_packets']} PRR={result['prr']:.9f} "
            f"work={result['decoder_work_s']:.6f}s "
            f"TPS={result['effective_tps_bps']:.6f} "
            f"wall={time.perf_counter()-started:.3f}s",
            flush=True,
        )
    all_rows = [
        load_json(path)
        for path in sorted(run_results.glob("*.mrc_cora.json"))
        if load_json(path).get("run") in {point.run for point in dataset_points()}
    ]
    if len(all_rows) == len(dataset_points()):
        publish(all_rows)
        print(f"CORA_PUBLISHED rows={len(all_rows)}", flush=True)
    else:
        print(
            f"CORA_PARTIAL completed={len(all_rows)} expected={len(dataset_points())}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
