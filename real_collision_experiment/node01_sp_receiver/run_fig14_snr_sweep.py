#!/usr/bin/env python3
"""Build Fig.14 SNR-bin PRR data from Fig.13 SF8/BW250 real-IQ reports.

Every AWGN point keeps the exact anonymous physical-candidate set used by its
Fig.13 source report.  PRR remains the formal source-window metric:
unique decoded payload identities divided by min(planned, detected), while
the measured dual-RX noise covariance is raised.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from real_collision_experiment.analysis.formal_window import (  # noqa: E402
    FORMAL_ANALYSIS_DURATION_S,
)

EVALUATOR = ROOT / "real_collision_experiment" / "node01_sp_receiver" / "evaluate_awgn_prr_sweep.py"
SNR_TARGETS = (
    ("lt_m30", "<-30 dB", -35.0),
    ("m30_to_m10", "[-30,-10) dB", -20.0),
    ("m10_to_10", "[-10,10) dB", 0.0),
    ("ge_10", ">=10 dB", 15.0),
)
AWGN_SWEEP_SCHEMA = "real_iq_awgn_decoder_prr_sweep_v6"
SNR_BIN_SCHEMA = "fig14_outdoor_awgn_snr_bins_v7"
FINE_SYNC_SCHEMA = "fine_sync_anonymous_physical_v2"
SHARED_PRR_SOURCE = "min_manifest_window_expected_or_anonymous_detected_packets"
SHARED_PRR_POLICY = (
    "unique_crc_valid_payload_identities_over_"
    "min_manifest_window_expected_or_anonymous_detected_packets"
)
METHODS = ("sp_sync_refine", "mrc", "mrc_cic", "pcube", "maloragw")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snr_bin(value: float) -> tuple[str, str] | None:
    if not math.isfinite(value):
        return None
    if value < -30.0:
        return "lt_m30", "<-30 dB"
    if value < -10.0:
        return "m30_to_m10", "[-30,-10) dB"
    if value < 10.0:
        return "m10_to_10", "[-10,10) dB"
    return "ge_10", ">=10 dB"


def source_median_preamble_snr_db(
    report: dict,
    max_candidates: int,
    detected_candidate_count: int,
) -> float:
    config = report.get("config", {})
    frontend = report.get("frontend", {})
    sf = int(config.get("sf", 0))
    noise_sigma2_fft = float(frontend.get("noise_sigma2_fft", 0.0))
    if sf <= 0 or noise_sigma2_fft <= 0.0:
        raise ValueError("source report has no usable SF/noise_sigma2_fft")
    values = []
    for candidate in report.get("candidates", []):
        power = candidate.get("power_sp", candidate.get("power"))
        if power is None or float(power) <= 0.0:
            continue
        values.append(
            10.0
            * math.log10(
                (float(power) + 1e-30) / ((2**sf) * noise_sigma2_fft + 1e-30)
            )
        )
    if len(values) > max(1, max_candidates):
        raise ValueError(
            f"source report has D={len(values)} physical candidates, exceeding "
            f"--max-candidates={max_candidates}"
        )
    if len(values) != detected_candidate_count:
        raise ValueError(
            f"source report has {len(values)} candidate powers, expected D={detected_candidate_count}"
        )
    if not values:
        raise ValueError("source report has no candidate power_sp values")
    return float(np.median(values))


def anonymous_fine_sync_database_path(report_path: Path) -> Path:
    return report_path.parent.parent / "fine_sync" / f"{report_path.stem}.json"


def fine_sync_candidate_count(database_path: Path) -> int:
    database = load_json(database_path)
    packets = database.get("packets", [])
    if not isinstance(packets, list) or not packets:
        raise ValueError("fine-sync database has no physical candidates")
    if any(
        not isinstance(row, dict)
        or row.get("node_id") is not None
        or row.get("sequence") is not None
        for row in packets
    ):
        raise ValueError("fine-sync database is not anonymous")
    return len(packets)


def source_is_eligible(report_path: Path, report: dict) -> tuple[bool, str]:
    config = report.get("config", {})
    if int(config.get("sf", 0)) != 8 or abs(float(config.get("bw_hz", 0.0)) - 250_000.0) > 1.0:
        return False, "not SF8/BW250"
    strict = report.get("input", {}).get("strict_middle_business_window", {})
    if not isinstance(strict, dict) or not bool(strict.get("enabled")):
        return False, "missing strict middle-business window audit"
    if (
        abs(
            float(strict.get("analysis_duration_s", 0.0))
            - FORMAL_ANALYSIS_DURATION_S
        )
        > 1e-6
    ):
        return False, f"strict business window is not {FORMAL_ANALYSIS_DURATION_S:g} s"
    manifest_text = report.get("input", {}).get("manifest")
    if not manifest_text:
        return False, "missing source manifest path"
    manifest_path = Path(str(manifest_text))
    if not manifest_path.exists():
        return False, f"missing source manifest {manifest_path}"
    manifest = load_json(manifest_path)
    experiment = manifest.get("experiment", {})
    if str(experiment.get("figure")) != "fig13":
        return False, "manifest is not a Fig.13 run"
    if bool(experiment.get("simulated_merged", False)):
        return False, "merged Fig.13 run is excluded; Fig.14 uses a physical SF8 source"
    active_node_count = int(
        manifest.get("active_node_count", len(manifest.get("active_nodes", [])))
    )
    if active_node_count != 3:
        return False, "Fig.14 requires the physical Fig.13 N=3 source"
    database_path = anonymous_fine_sync_database_path(report_path)
    if not database_path.exists():
        return False, f"missing shared fine-sync database {database_path}"
    try:
        database = load_json(database_path)
        strict_start = float(strict["analysis_start_s_from_full_iq"])
        strict_duration = float(strict["analysis_duration_s"])
        window = database.get("window", {})
        detected_candidate_count = fine_sync_candidate_count(database_path)
        if database.get("schema") != FINE_SYNC_SCHEMA:
            return False, f"fine-sync schema is {database.get('schema')!r}, expected anonymous v2"
        discovery = database.get("candidate_discovery", {})
        if (
            discovery.get("scope") != "global_full_window"
            or discovery.get("manifest_schedule_exposed_to_detector") is not False
            or discovery.get("node_timing_calibration") is not False
            or discovery.get("planned_start_search_windows") is not False
            or discovery.get("score_truncation") is not False
        ):
            return False, "fine-sync database is not schedule-free global discovery"
        if database.get("run_id") != report_path.stem:
            return False, "fine-sync database run_id does not match source report"
        if (
            abs(float(window.get("analysis_start_s", math.nan)) - strict_start) > 1e-6
            or abs(float(window.get("duration_s", math.nan)) - strict_duration) > 1e-6
        ):
            return False, "fine-sync database window does not match strict source window"
        by_method = report.get("detection_and_decode", {}).get("by_method", {})
        for method in METHODS:
            values = by_method.get(method, {}) if isinstance(by_method, dict) else {}
            if values.get("execution_status") != "completed":
                return False, f"{method} was not formally completed"
            if values.get("prr_denominator_source") != SHARED_PRR_SOURCE:
                return False, f"{method} does not use min(planned, detected)"
            if values.get("prr_counting_policy") != SHARED_PRR_POLICY:
                return False, f"{method} has incompatible PRR policy"
            detected = int(values["complete_detected_packet_count"])
            decoded = int(values["decoded_success_count"])
            denominator = int(values["prr_denominator_packet_count"])
            planned = int(values["manifest_expected_packet_count_in_analysis_window"])
            reported_detected = int(values["prr_detected_physical_packet_count"])
            if (
                detected != detected_candidate_count
                or reported_detected != detected
                or decoded > min(planned, detected)
                or denominator != min(planned, detected)
                or not math.isfinite(float(values["prr"]))
                or abs(float(values["prr"]) - decoded / denominator) > 1e-9
            ):
                return False, f"{method} shared fine-sync PRR audit is inconsistent"
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return False, f"invalid shared fine-sync audit: {exc}"
    return True, "eligible"


def discover_reports(args: argparse.Namespace) -> list[Path]:
    explicit = [path.resolve() for path in args.report]
    if explicit:
        return explicit
    if args.reports is None:
        raise ValueError("pass --report at least once or provide --reports")
    return sorted(args.reports.glob("run_*.json"))


def evaluate_one(
    *,
    source_report: Path,
    fine_sync_database: Path,
    output: Path,
    rise_db: float,
    seed: int,
    args: argparse.Namespace,
) -> dict:
    if output.exists() and not args.overwrite:
        cached = load_json(output)
        if cached.get("schema") != AWGN_SWEEP_SCHEMA:
            raise ValueError(
                f"{output}: legacy AWGN cache uses {cached.get('schema')!r}; "
                "rerun with --overwrite to calculate shared-fine-sync PRR"
            )
        if (
            cached.get("source_target_policy") != "fine_sync_database"
            or cached.get("fine_sync_database") != str(fine_sync_database)
        ):
            raise ValueError(
                f"{output}: cache does not use this source's shared fine-sync database; "
                "rerun with --overwrite"
            )
        return cached
    command = [
        args.python_executable,
        str(EVALUATOR),
        "--report",
        str(source_report),
        "--out",
        str(output),
        "--noise-rise-db",
        f"{rise_db:.9f}",
        "--max-candidates",
        str(args.max_candidates),
        "--source-target-policy",
        "fine_sync_database",
        "--fine-sync-db",
        str(fine_sync_database),
        "--seed",
        str(seed),
        "--sp-sync-max-trials",
        str(args.sp_sync_max_trials),
    ]
    print("FIG14_AWGN_COMMAND", subprocess.list2cmdline(command), flush=True)
    if args.dry_run:
        return {}
    subprocess.run(command, cwd=ROOT, check=True)
    return load_json(output)


def aggregate(rows: list[dict]) -> list[dict]:
    totals: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not row.get("accepted", False):
            continue
        for method, values in row.get("by_method", {}).items():
            if values.get("prr_denominator_source") != SHARED_PRR_SOURCE:
                raise ValueError(f"{row.get('sweep_report')}: {method} does not use min(planned, detected)")
            if values.get("prr_counting_policy") != SHARED_PRR_POLICY:
                raise ValueError(f"{row.get('sweep_report')}: {method} has incompatible PRR policy")
            detected = int(values["detected_packet_count"])
            decoded = int(values["decoded_success_count"])
            denominator = int(values["prr_denominator_packet_count"])
            planned = int(values["manifest_expected_packet_count_in_analysis_window"])
            if (
                decoded > min(planned, detected)
                or denominator != min(planned, detected)
                or not math.isfinite(float(values["prr"]))
                or abs(float(values["prr"]) - decoded / denominator) > 1e-9
            ):
                raise ValueError(f"{row.get('sweep_report')}: {method} PRR audit is inconsistent")
            key = (row["measured_snr_bin_key"], method)
            item = totals.setdefault(
                key,
                {
                    "snr_bin_key": row["measured_snr_bin_key"],
                    "snr_bin_label": row["measured_snr_bin_label"],
                    "method": method,
                    "source_point_count": 0,
                    "manifest_expected_packet_count_in_analysis_window": 0,
                    "detected_packet_count": 0,
                    "decoded_success_count": 0,
                    "prr_denominator_packet_count": 0,
                    "measured_snr_db": [],
                },
            )
            item["source_point_count"] += 1
            item["manifest_expected_packet_count_in_analysis_window"] += planned
            item["detected_packet_count"] += int(values["detected_packet_count"])
            item["decoded_success_count"] += int(values["decoded_success_count"])
            item["measured_snr_db"].append(float(row["measured_median_snr_db"]))
    output = []
    for item in totals.values():
        planned = int(item["manifest_expected_packet_count_in_analysis_window"])
        detected = int(item["detected_packet_count"])
        denominator = min(planned, detected)
        successes = int(item.pop("decoded_success_count"))
        snrs = item.pop("measured_snr_db")
        output.append(
            {
                **item,
                "decoded_success_count": successes,
                "prr_denominator_packet_count": denominator,
                "conditional_prr": successes / denominator if denominator else None,
                "prr_denominator_source": SHARED_PRR_SOURCE,
                "prr_counting_policy": SHARED_PRR_POLICY,
                "median_measured_snr_db": float(np.median(snrs)) if snrs else None,
                "min_measured_snr_db": float(min(snrs)) if snrs else None,
                "max_measured_snr_db": float(max(snrs)) if snrs else None,
            }
        )
    return sorted(output, key=lambda row: (SNR_TARGETS.index(next(item for item in SNR_TARGETS if item[0] == row["snr_bin_key"])), row["method"]))


def achievable_target_snr_db(source_snr_db: float, target_key: str, target_center_db: float) -> float | None:
    """Keep the intended bin even when a source is below its nominal center."""

    if source_snr_db >= target_center_db:
        return target_center_db
    current = snr_bin(source_snr_db)
    if current is not None and current[0] == target_key:
        return source_snr_db
    return None


def run(args: argparse.Namespace) -> dict:
    source_paths = discover_reports(args)
    eligible: list[tuple[Path, Path, dict, float]] = []
    skipped: list[dict] = []
    for path in source_paths:
        try:
            report = load_json(path)
            valid, reason = source_is_eligible(path, report)
            if not valid:
                skipped.append({"source_report": str(path), "reason": reason})
                continue
            eligible.append(
                (
                    path,
                    anonymous_fine_sync_database_path(path),
                    report,
                    source_median_preamble_snr_db(
                        report,
                        args.max_candidates,
                        fine_sync_candidate_count(anonymous_fine_sync_database_path(path)),
                    ),
                )
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            skipped.append({"source_report": str(path), "reason": f"{type(exc).__name__}: {exc}"})
    if not eligible:
        raise ValueError(
            "no eligible physical Fig.13 SF8/BW250 N=3 "
            f"strict-{FORMAL_ANALYSIS_DURATION_S:g}-s source report"
        )

    point_rows: list[dict] = []
    for source_index, (source_path, fine_sync_database, source_report, source_snr_db) in enumerate(eligible):
        run_label = source_path.stem
        for target_index, (target_key, target_label, target_snr_db) in enumerate(SNR_TARGETS):
            effective_target_snr_db = achievable_target_snr_db(
                source_snr_db, target_key, target_snr_db
            )
            if effective_target_snr_db is None:
                skipped.append(
                    {
                        "source_report": str(source_path),
                        "target_snr_bin": target_label,
                        "reason": (
                            f"source median SNR {source_snr_db:.2f} dB is below the "
                            f"requested {target_label} bin; AWGN cannot increase SNR"
                        ),
                    }
                )
                continue
            rise_db = source_snr_db - effective_target_snr_db
            for seed_index, seed in enumerate(args.noise_seeds):
                output = args.out_dir / "sweeps" / f"{run_label}_{target_key}_seed{seed}.json"
                sweep = evaluate_one(
                    source_report=source_path,
                    fine_sync_database=fine_sync_database,
                    output=output,
                    rise_db=max(0.0, rise_db),
                    seed=int(seed),
                    args=args,
                )
                if args.dry_run:
                    continue
                points = sweep.get("sweep", [])
                if len(points) != 1:
                    raise ValueError(f"{output}: expected one AWGN point, found {len(points)}")
                point = points[0]
                measured_snr_db = float(point["median_estimated_preamble_snr_db"])
                measured_bin = snr_bin(measured_snr_db)
                if measured_bin is None:
                    raise ValueError(f"{output}: non-finite measured SNR")
                point_rows.append(
                    {
                        "source_report": str(source_path),
                        "fine_sync_database": str(fine_sync_database),
                        "source_run_id": source_report.get("run_id"),
                        "source_median_snr_db": source_snr_db,
                        "target_snr_bin_key": target_key,
                        "target_snr_bin_label": target_label,
                        "target_snr_center_db": target_snr_db,
                        "effective_target_snr_db": effective_target_snr_db,
                        "noise_floor_rise_db": max(0.0, rise_db),
                        "noise_seed": int(seed),
                        "sweep_report": str(output),
                        "measured_median_snr_db": measured_snr_db,
                        "measured_snr_bin_key": measured_bin[0],
                        "measured_snr_bin_label": measured_bin[1],
                        "accepted": measured_bin[0] == target_key,
                        "by_method": point["by_method"],
                    }
                )

    return {
        "schema": SNR_BIN_SCHEMA,
        "definition": {
            "measurement": (
                "anonymous-physical-candidate decoder PRR after covariance-matched AWGN "
                "addition: CRC-valid decoded candidates / detected candidates"
            ),
            "snr": (
                "median per-target preamble estimate: power_sp / "
                "(2^SF * total receiver noise variance), in dB"
            ),
            "source_slice": (
                "strict centered "
                f"{FORMAL_ANALYSIS_DURATION_S:g} s of the original 20 s business interval"
            ),
            "source_selection": "physical Fig.13 SF8/BW250 N=3 report only",
            "bin_policy": "a point is aggregated only when its measured median SNR is in its requested bin",
        },
        "targets": [
            {"key": key, "label": label, "center_db": center}
            for key, label, center in SNR_TARGETS
        ],
        "source_report_count": len(eligible),
        "noise_seeds": [int(seed) for seed in args.noise_seeds],
        "points": point_rows,
        "aggregate": aggregate(point_rows),
        "skipped": skipped,
    }


def parse_int_list(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=None, help="Directory containing strict Fig.13 reports")
    parser.add_argument("--report", type=Path, action="append", default=[], help="Explicit source report; may repeat")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--max-candidates", type=int, default=200)
    parser.add_argument("--sp-sync-max-trials", type=int, default=32)
    parser.add_argument("--noise-seeds", type=parse_int_list, default=(20260805,))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_candidates < 1 or args.sp_sync_max_trials < 1:
        raise SystemExit("--max-candidates and --sp-sync-max-trials must be positive")
    args.out_dir = args.out_dir.resolve()
    result = run(args)
    out = args.out_dir / "fig14_snr_bins.json"
    if not args.dry_run:
        save_json(out, result)
    accepted = sum(bool(row.get("accepted")) for row in result["points"])
    print(
        f"FIG14_SNR_SWEEP_DONE sources={result['source_report_count']} "
        f"accepted={accepted}/{len(result['points'])} out={out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
