#!/usr/bin/env python3
"""Decoder PRR sweep after adding calibrated AWGN to real IQ.

This is a mechanism/stress experiment, not an end-to-end detector experiment.
It reuses certified shared fine-sync targets from a prior receiver report,
raises the measured physical receiver-noise covariance by controlled dB steps,
and runs the five Fig.14 decoders with standard FEC/application CRC closure.

Formal Fig.14 mode reads the same anonymous physical-candidate database used
by Fig.9/10.  Its certified physical candidates are D, while the source
report carries the formal-window manifest planned count P.  PRR is
``unique CRC-valid payload identities / min(P, D)`` even though the IQ has
been perturbed after the original fine synchronization.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTROL_DIR = ROOT / "real_collision_experiment" / "control_usrp"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from compare.real_packet_decoders import (
    PaperComparisonContext,
    PhysicalEvidencePayloadCache,
)
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda
from real_collision_experiment.node01_sp_receiver.real_lora_config import (
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import load_capture
from real_collision_experiment.node01_sp_receiver.sp_node01_receiver import (
    SharedPhysicalDecodeCache,
    decode_method,
    decode_sp_stages,
    physical_evidence_key,
    validate_payload,
)


METHODS = ("sp_sync_refine", "mrc", "mrc_cic", "pcube", "maloragw")
SCHEMA = "real_iq_awgn_decoder_prr_sweep_v6"
FINE_SYNC_SCHEMA = "fine_sync_anonymous_physical_v2"
SHARED_PRR_SOURCE = "min_manifest_window_expected_or_anonymous_detected_packets"
SHARED_PRR_POLICY = (
    "unique_crc_valid_payload_identities_over_"
    "min_manifest_window_expected_or_anonymous_detected_packets"
)


def _complex_vector(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(float(real), float(imag)) for real, imag in values])


def _complex_matrix(values: list[list[list[float]]]) -> np.ndarray:
    return np.asarray(
        [
            [complex(float(value[0]), float(value[1])) for value in row]
            for row in values
        ],
        dtype=np.complex128,
    )


def _sync_refined_estimate(candidate: dict, *, offset: int) -> dict:
    sync = next(
        row
        for row in candidate.get("methods", [])
        if row.get("method") == "sp_sync_refine"
    )
    estimate = {
        key: value
        for key, value in candidate.items()
        if key not in {"candidate_id", "methods", "start_time_s"}
    }
    estimate["packet_index"] = int(candidate.get("candidate_id", 0))
    estimate["start_sample"] = (
        float(candidate["start_sample"])
        + float(candidate.get("sto_samples_sp", candidate.get("sto_samples", 0.0)))
        + float(sync.get("sync_refine_start_delta_samples", 0.0))
        - int(offset)
    )
    estimate["sto_samples"] = 0.0
    estimate["sto_samples_sp"] = 0.0
    estimate["continuous_cfo_bins"] = float(
        sync.get(
            "used_cfo_bins",
            candidate.get("continuous_cfo_bins", candidate["cfo_bins"]),
        )
    )
    estimate["cfo_bins"] = float(estimate["continuous_cfo_bins"])
    estimate["cfo_bins_sp"] = float(estimate["continuous_cfo_bins"])
    channel = candidate.get("channel_sp", candidate.get("channel"))
    if channel is None:
        channel = [[1.0, 0.0], [0.0, 0.0]]
    estimate["channel"] = channel
    estimate["channel_sp"] = channel
    return estimate


def _noise_basis(covariance: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(np.asarray(covariance, dtype=np.complex128))
    floor = max(float(np.max(values).real), 1e-18) * 1e-9
    return vectors @ np.diag(np.sqrt(np.maximum(values.real, floor)))


def _added_noise(
    basis: np.ndarray,
    sample_count: int,
    variance_multiplier: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if variance_multiplier <= 0.0:
        return np.zeros((basis.shape[0], sample_count), dtype=np.complex64)
    standard = (
        rng.standard_normal((basis.shape[1], sample_count))
        + 1j * rng.standard_normal((basis.shape[1], sample_count))
    ) / math.sqrt(2.0)
    return (math.sqrt(variance_multiplier) * (basis @ standard)).astype(np.complex64)


def _method_outcome(
    method_row: dict,
    run_id: int | None,
    active_nodes: set[int],
    *,
    target: tuple[int, int] | None = None,
    identity_aliases: dict[tuple[int, int], int] | None = None,
) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    """Return M and U identities for one target/candidate decode.

    ``validate_payload`` checks the embedded application CRC before returning
    a payload.  In formal fine-sync mode an otherwise valid payload with the
    wrong run/node identity is U, rather than being discarded by the normal
    run/node acceptance filter.
    """

    payload = bytes.fromhex(method_row["phy"]["payload_hex"])
    decoded, accepted, _ = validate_payload(payload, run_id=run_id, active_nodes=active_nodes)
    if decoded is None:
        return None, None
    source_identity = int(decoded.run_id), int(decoded.node_id)
    identity = (
        int((identity_aliases or {}).get(source_identity, int(decoded.node_id))),
        int(decoded.sequence),
    )
    if target is not None:
        return (identity, None) if identity == target else (None, identity)
    return (identity, None) if accepted else (None, identity)


def _anonymous_decoded_identity(
    method_row: dict,
    run_id: int | None,
    active_nodes: set[int],
) -> tuple[int, int] | None:
    """Return an application-CRC-valid payload identity without target binding."""

    payload = bytes.fromhex(method_row["phy"]["payload_hex"])
    decoded, _accepted, _ = validate_payload(
        payload, run_id=run_id, active_nodes=active_nodes
    )
    if decoded is None:
        return None
    return int(decoded.node_id), int(decoded.sequence)


def _strict_window(report: dict) -> tuple[float, float]:
    strict = report.get("input", {}).get("strict_middle_business_window", {})
    if not isinstance(strict, dict) or not bool(strict.get("enabled")):
        raise ValueError("source report has no strict middle-business-window audit")
    start_s = float(strict["analysis_start_s_from_full_iq"])
    duration_s = float(strict["analysis_duration_s"])
    if abs(duration_s - 5.0) > 1e-6:
        raise ValueError(f"source report strict window is {duration_s:g} s, expected 5 s")
    slice_row = report.get("input", {}).get("analysis_slice", {})
    if not isinstance(slice_row, dict):
        raise ValueError("source report has no analysis_slice")
    if abs(float(slice_row.get("start_time_s", math.nan)) - start_s) > 1e-6:
        raise ValueError("source report analysis_slice start does not match strict window")
    if abs(float(slice_row.get("requested_duration_s", math.nan)) - duration_s) > 1e-6:
        raise ValueError("source report analysis_slice duration does not match strict window")
    return start_s, duration_s


def _validate_source_shared_prr(report: dict, target_count: int) -> int:
    by_method = report.get("detection_and_decode", {}).get("by_method", {})
    if not isinstance(by_method, dict):
        raise ValueError("source report has no decoder PRR audit")
    expected_counts: set[int] = set()
    for method in METHODS:
        row = by_method.get(method)
        if not isinstance(row, dict) or row.get("execution_status") != "completed":
            raise ValueError(f"source report did not formally run {method}")
        if row.get("prr_denominator_source") != SHARED_PRR_SOURCE:
            raise ValueError(f"source report {method} does not use min(planned, detected)")
        if row.get("prr_counting_policy") != SHARED_PRR_POLICY:
            raise ValueError(f"source report {method} has incompatible PRR policy")
        detected = int(row["complete_detected_packet_count"])
        decoded = int(row["decoded_success_count"])
        denominator = int(row["prr_denominator_packet_count"])
        planned = int(row["manifest_expected_packet_count_in_analysis_window"])
        reported_detected = int(row["prr_detected_physical_packet_count"])
        expected_counts.add(planned)
        if (
            detected != target_count
            or reported_detected != detected
            or decoded > min(planned, detected)
            or denominator != min(planned, detected)
            or not math.isfinite(float(row["prr"]))
            or abs(float(row["prr"]) - decoded / denominator) > 1e-9
        ):
            raise ValueError(f"source report {method} shared fine-sync PRR audit is inconsistent")
    if len(expected_counts) != 1:
        raise ValueError("source report methods disagree on planned five-second count")
    return next(iter(expected_counts))


def _fine_sync_target_candidates(
    source_report: dict,
    database_path: Path,
    report_path: Path,
) -> tuple[list[dict], dict, int]:
    """Match every anonymous database candidate to its source report row."""

    if not database_path.exists():
        raise ValueError(f"missing shared fine-sync database {database_path}")
    database = json.loads(database_path.read_text(encoding="utf-8"))
    if database.get("schema") != FINE_SYNC_SCHEMA:
        raise ValueError(
            f"fine-sync database must be {FINE_SYNC_SCHEMA}; got {database.get('schema')!r}"
        )
    discovery = database.get("candidate_discovery", {})
    if (
        discovery.get("scope") != "global_full_window"
        or discovery.get("manifest_schedule_exposed_to_detector") is not False
        or discovery.get("node_timing_calibration") is not False
        or discovery.get("planned_start_search_windows") is not False
        or discovery.get("score_truncation") is not False
    ):
        raise ValueError("fine-sync database is not a schedule-free global discovery")
    run_name = report_path.stem
    if database.get("run_id") != run_name:
        raise ValueError("fine-sync database run_id does not match source report name")
    analysis_start_s, duration_s = _strict_window(source_report)
    window = database.get("window", {})
    if (
        abs(float(window.get("analysis_start_s", math.nan)) - analysis_start_s) > 1e-6
        or abs(float(window.get("duration_s", math.nan)) - duration_s) > 1e-6
    ):
        raise ValueError("fine-sync database window does not match source report")
    database_candidates = database.get("packets", [])
    if not isinstance(database_candidates, list) or not database_candidates:
        raise ValueError("fine-sync database contains no physical candidates")
    if any(
        not isinstance(row, dict)
        or row.get("node_id") is not None
        or row.get("sequence") is not None
        for row in database_candidates
    ):
        raise ValueError("fine-sync database is not anonymous")
    manifest_expected_packet_count = _validate_source_shared_prr(
        source_report, len(database_candidates)
    )
    candidates = sorted(
        (row for row in source_report.get("candidates", []) if isinstance(row, dict)),
        key=lambda row: int(row.get("candidate_id", -1)),
    )
    if len(candidates) != len(database_candidates):
        raise ValueError(
            "source report candidate count does not equal the anonymous database "
            f"({len(candidates)} != {len(database_candidates)})"
        )
    if [int(row.get("candidate_id", -1)) for row in candidates] != list(range(len(candidates))):
        raise ValueError("source report anonymous candidate IDs are not contiguous")
    return candidates, database, manifest_expected_packet_count


def _renamed(result: dict, method: str, **extra: object) -> dict:
    row = dict(result)
    row["method"] = method
    row.update(extra)
    return row


def _phy_crc_ok(row: dict) -> bool:
    return bool(row.get("phy", {}).get("phy_crc_ok", False))


def _fixed_frontend_sp_stages(
    samples: np.ndarray,
    estimate: dict,
    cfg: RealCollisionLoRaConfig,
) -> list[dict]:
    """Decode SP stages without any low-SNR sync/channel re-estimation."""

    fixed = dict(estimate)
    fixed["sto_samples"] = 0.0
    fixed["sto_samples_sp"] = 0.0
    fixed["_sp_disable_cfo_trials"] = True
    fixed["_sp_disable_repair"] = True
    fixed["_disable_lambda_endpoint_retry"] = True
    sync_raw = decode_method("sp", samples, fixed, cfg)
    sync_refine = _renamed(
        sync_raw,
        "sp_sync_refine",
        decoder_stage="fixed_high_snr_sync_refine",
        synchronization_trials=0,
        sync_refine_applied=False,
        sync_refine_crc_closed=_phy_crc_ok(sync_raw),
        sync_refine_start_delta_samples=0.0,
        sync_refine_cfo_delta_bins=0.0,
        front_end_estimate_source="source_report_high_snr",
        risk_lambda_fixed=True,
    )

    sync_refine["repair_result"] = None
    return [sync_refine]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Existing complete receiver report")
    parser.add_argument(
        "--fine-sync-db",
        type=Path,
        default=None,
        help=(
            "Anonymous fine_sync physical-candidate database for formal Fig.14 "
            "PRR. Its candidates are D and must match the strict source-report window."
        ),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--noise-rise-db",
        type=float,
        nargs="+",
        default=[0.0, 3.0, 6.0, 9.0, 12.0],
        help="Total receiver-noise-floor increase relative to the measured capture noise.",
    )
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument(
        "--source-target-policy",
        choices=("all", "crc_closed_any_method", "fine_sync_database"),
        default="all",
        help=(
            "Select source-report candidates before AWGN. 'all' preserves the "
            "legacy behavior; 'crc_closed_any_method' retains only candidates with "
            "a valid application-CRC identity from at least one source decoder; "
            "'fine_sync_database' uses --fine-sync-db and is required for formal Fig.14."
        ),
    )
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--sp-gamma", type=float, default=0.05)
    parser.add_argument("--sp-lambda-max", type=float, default=4.0)
    parser.add_argument("--sp-sync-max-trials", type=int, default=32)
    parser.add_argument(
        "--fixed-front-end-estimates",
        action="store_true",
        help=(
            "Use high-SNR packet start/CFO/channel/lambda estimates from the source "
            "report for every noise point; do not run low-SNR sync refine or channel "
            "re-estimation."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_report = json.loads(args.report.read_text(encoding="utf-8"))
    active_nodes = {int(value) for value in source_report.get("active_nodes", [])}
    run_id = source_report.get("run_id")
    candidates = list(source_report.get("candidates", []))
    fine_sync_database: dict | None = None
    manifest_expected_packet_count: int | None = None
    if args.source_target_policy == "fine_sync_database":
        if args.fine_sync_db is None:
            raise ValueError("--source-target-policy fine_sync_database requires --fine-sync-db")
        candidates, fine_sync_database, manifest_expected_packet_count = _fine_sync_target_candidates(
            source_report, args.fine_sync_db, args.report
        )
        if len(candidates) > max(1, int(args.max_candidates)):
            raise ValueError(
                f"fine-sync database contains D={len(candidates)} candidates, exceeding "
                f"--max-candidates={args.max_candidates}; increase the limit rather than "
                "silently changing D"
            )
    else:
        if args.fine_sync_db is not None:
            raise ValueError("--fine-sync-db requires --source-target-policy fine_sync_database")
    if args.source_target_policy == "crc_closed_any_method":
        candidates = [
            candidate
            for candidate in candidates
            if any(
                _method_outcome(method_row, run_id, active_nodes)[0] is not None
                for method_row in candidate.get("methods", [])
                if isinstance(method_row, dict)
            )
        ]
    if args.source_target_policy != "fine_sync_database":
        candidates = candidates[: max(1, int(args.max_candidates))]
    if not candidates:
        raise ValueError("report contains no candidates")

    input_row = source_report["input"]
    iq = Path(input_row["iq"])
    metadata = Path(input_row["metadata"])
    analysis_slice = input_row.get("analysis_slice", {})
    if analysis_slice is None:
        analysis_slice = {}
    if not isinstance(analysis_slice, dict):
        raise ValueError("source report input.analysis_slice must be an object when present")
    capture_start_s = float(analysis_slice.get("start_time_s", 0.0))
    capture_duration_s = analysis_slice.get("requested_duration_s")
    if capture_duration_s is not None:
        capture_duration_s = float(capture_duration_s)
    capture = load_capture(
        iq,
        metadata,
        start_time_s=capture_start_s,
        max_duration_s=capture_duration_s,
    )
    rate = float(source_report["config"]["sample_rate_hz"])
    cfg = RealCollisionLoRaConfig(sample_rate_hz=rate)

    guard = 2 * cfg.samples_per_symbol
    begin = max(0, int(math.floor(min(float(row["start_sample"]) for row in candidates))) - guard)
    end = min(
        capture.samples.shape[1],
        int(math.ceil(max(float(row["start_sample"]) for row in candidates) + cfg.frame_samples))
        + guard,
    )
    calibration = source_report["calibration"]
    dc = _complex_vector(calibration["dc"]).astype(np.complex64)
    covariance = _complex_matrix(calibration["noise_covariance"])
    whitener = _complex_matrix(calibration["whitener"])
    original_noise_sigma2_time = float(calibration["noise_sigma2_time"])
    physical = np.asarray(capture.samples[:, begin:end] - dc[:, None], dtype=np.complex64)
    del capture

    base_estimates = [_sync_refined_estimate(row, offset=begin) for row in candidates]
    fixed_estimates = None
    if args.fixed_front_end_estimates:
        source_white = np.asarray(whitener @ physical, dtype=np.complex64)
        fixed_estimates = attach_sp_reliability_and_lambda(
            source_white,
            base_estimates,
            cfg,
            noise_sigma2=max(cfg.m * original_noise_sigma2_time, 1e-12),
            gamma=float(args.sp_gamma),
            max_lambda=float(args.sp_lambda_max),
        )
    noise_basis = _noise_basis(covariance)
    rng = np.random.default_rng(int(args.seed))
    sweep_rows: list[dict] = []

    for noise_rise_db in args.noise_rise_db:
        total_multiplier = 10.0 ** (float(noise_rise_db) / 10.0)
        added = _added_noise(
            noise_basis,
            physical.shape[1],
            max(0.0, total_multiplier - 1.0),
            rng,
        )
        noisy_physical = np.asarray(physical + added, dtype=np.complex64)
        noisy_white = np.asarray(whitener @ noisy_physical, dtype=np.complex64)
        noise_sigma2_fft = max(
            cfg.m * original_noise_sigma2_time * total_multiplier,
            1e-12,
        )
        if fixed_estimates is not None:
            estimates = [dict(row) for row in fixed_estimates]
        else:
            estimates = attach_sp_reliability_and_lambda(
                noisy_white,
                base_estimates,
                cfg,
                noise_sigma2=noise_sigma2_fft,
                gamma=float(args.sp_gamma),
                max_lambda=float(args.sp_lambda_max),
            )
        for candidate_index, estimate in enumerate(estimates):
            estimate["_anonymous_physical_candidate_id"] = int(candidate_index)
            estimate["_physical_evidence_key"] = physical_evidence_key(
                estimate, candidate_index
            )
        shared_sp_cache = SharedPhysicalDecodeCache()
        comparison_payload_cache = PhysicalEvidencePayloadCache()
        comparison = PaperComparisonContext(
            noisy_physical,
            estimates,
            cfg,
            payload_spectrum_cache=comparison_payload_cache,
        )
        decoded_success_identities = {method: set() for method in METHODS}
        theta_total: list[float] = []
        lambda_values: list[float] = []
        estimated_snr_db: list[float] = []

        for candidate_index, estimate in enumerate(estimates):
            if args.fixed_front_end_estimates:
                stages = _fixed_frontend_sp_stages(noisy_white, estimate, cfg)
            else:
                stages = decode_sp_stages(
                    noisy_white,
                    estimate,
                    cfg,
                    max_sync_trials=int(args.sp_sync_max_trials),
                    shared_cache=shared_sp_cache,
                    physical_key=tuple(estimate["_physical_evidence_key"]),
                )
            sync = next(row for row in stages if row["method"] == "sp_sync_refine")
            refined = dict(estimate)
            refined["_comparison_candidate_index"] = int(candidate_index)
            refined["start_sample"] = float(estimate["start_sample"]) + float(
                sync.get("sync_refine_start_delta_samples", 0.0)
            )
            refined["sto_samples"] = 0.0
            refined["sto_samples_sp"] = 0.0
            refined["continuous_cfo_bins"] = float(sync["used_cfo_bins"])
            refined["cfo_bins_sp"] = float(sync["used_cfo_bins"])
            mrc = decode_method("mrc", noisy_white, refined, cfg)
            paper_rows = comparison.decode_all(refined)
            method_rows = [mrc, *stages, *paper_rows]
            for method in METHODS:
                row = next(item for item in method_rows if item["method"] == method)
                identity = _anonymous_decoded_identity(row, run_id, active_nodes)
                if identity is not None:
                    decoded_success_identities[method].add(identity)

            theta_total.append(float(estimate.get("theta_total", math.nan)))
            lambda_values.append(float(estimate.get("lambda_sp", 0.0)))
            signal_power = float(estimate.get("power_sp", 0.0))
            # ``power_sp`` is the squared M-point coherent preamble FFT vector,
            # whereas ``noise_sigma2_fft`` is the noise power in one FFT bin.
            # Remove the M-fold coherent processing gain to report an input
            # per-chip SNR estimate rather than an inflated post-FFT SNR.
            estimated_snr_db.append(
                10.0
                * math.log10(
                    (signal_power + 1e-30) / (cfg.m * noise_sigma2_fft + 1e-30)
                )
            )
            print(
                f"AWGN_DECODE_CANDIDATE rise_db={float(noise_rise_db):g} "
                f"candidate={candidate_index + 1}/{len(estimates)} "
                f"sp_cache=h{shared_sp_cache.sp_payload_hits}"
                f"/m{shared_sp_cache.sp_payload_misses} "
                f"payload_fft=h{comparison_payload_cache.spectrum_hits}"
                f"/m{comparison_payload_cache.spectrum_misses}",
                flush=True,
            )

        detected_packet_count = len(estimates)
        prr_denominator_packet_count = (
            min(manifest_expected_packet_count, detected_packet_count)
            if manifest_expected_packet_count is not None
            else detected_packet_count
        )
        method_rows = {
            method: {
                "detected_packet_count": detected_packet_count,
                "decoded_success_count": len(decoded_success_identities[method]),
                "manifest_expected_packet_count_in_analysis_window": (
                    manifest_expected_packet_count
                ),
                "prr_denominator_packet_count": prr_denominator_packet_count,
                "prr": (
                    float(len(decoded_success_identities[method]))
                    / prr_denominator_packet_count
                    if prr_denominator_packet_count
                    else None
                ),
                "prr_denominator_source": (
                    SHARED_PRR_SOURCE
                    if args.source_target_policy == "fine_sync_database"
                    else "source_report_candidates"
                ),
                "prr_counting_policy": (
                    SHARED_PRR_POLICY
                    if args.source_target_policy == "fine_sync_database"
                    else "unique_crc_valid_payload_identities_over_detected_packets"
                ),
            }
            for method in METHODS
        }
        sweep_row = {
            "noise_floor_rise_db": float(noise_rise_db),
            "total_noise_variance_multiplier": float(total_multiplier),
            "median_estimated_preamble_snr_db": float(np.nanmedian(estimated_snr_db)),
            "p10_estimated_preamble_snr_db": float(np.nanpercentile(estimated_snr_db, 10)),
            "p90_estimated_preamble_snr_db": float(np.nanpercentile(estimated_snr_db, 90)),
            "median_theta_total_rad": float(np.nanmedian(theta_total)),
            "median_lambda_sp": float(np.nanmedian(lambda_values)),
            "shared_physical_work_cache": {
                "sp_sync": shared_sp_cache.audit(),
                "comparison_payload": comparison_payload_cache.audit(),
            },
            "sp_repair": None,
            "by_method": method_rows,
        }
        sweep_rows.append(sweep_row)
        print(json.dumps(sweep_row, ensure_ascii=False), flush=True)

    output = {
        "schema": SCHEMA,
        "definition": (
            "Decoder stress test on fixed anonymous physical candidates. In formal "
            "fine-sync mode D is the anonymous candidate count and PRR is unique "
            "CRC-valid payload identities / min(source five-second planned count, D). "
            "It is not an end-to-end detector rerun. Added "
            "noise follows the measured two-channel physical noise covariance."
        ),
        "source_report": str(args.report),
        "input_iq": str(iq),
        "source_analysis_slice": {
            "start_time_s": capture_start_s,
            "requested_duration_s": capture_duration_s,
            "candidate_coordinates": "relative_to_source_analysis_slice",
        },
        "candidate_count": len(base_estimates),
        "candidate_ids": [int(row.get("candidate_id", index)) for index, row in enumerate(candidates)],
        "fine_sync_database": str(args.fine_sync_db) if args.fine_sync_db else None,
        "fine_sync_database_schema": fine_sync_database.get("schema") if fine_sync_database else None,
        "fine_sync_candidate_count": len(base_estimates),
        "manifest_expected_packet_count_in_analysis_window": (
            manifest_expected_packet_count
        ),
        "source_target_policy": args.source_target_policy,
        "segment": {"start_sample": begin, "end_sample": end},
        "random_seed": int(args.seed),
        "front_end_estimate_mode": (
            "fixed_high_snr_source_report"
            if args.fixed_front_end_estimates
            else "source_targets_per_noise_reliability_lambda_bounded_sync_refine"
        ),
        "sweep": sweep_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
