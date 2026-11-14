#!/usr/bin/env python3
"""Add CoRa to the archived legacy Fig. 11 10-second comparison.

The archived baseline predates anonymous physical-candidate Fig. 11 scoring.
It uses a fixed set of 75 oracle-associated collision scenes and reports PRR
as ``(target matches + identity mismatches) / (fine-sync detections + identity
mismatches)``.  Candidate IDs were not written into the archived scene CSV.
This runner recovers their *exact multiset* from the six recorded baseline
post-SP timing fingerprints, then runs the complete CoRa PMD/HPD detector and
TnB BEC on every recovered logical candidate trial.  No baseline decoder
payload or timing result is used by CoRa itself.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from functools import lru_cache
from pathlib import Path
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "real_collision_experiment/analysis"
RECEIVER = ROOT / "real_collision_experiment/node01_sp_receiver"
CONTROL = ROOT / "real_collision_experiment/control_usrp"
for source in (ROOT, ANALYSIS, RECEIVER, CONTROL, Path(__file__).parent):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from cora_detector import CoRaDetector  # noqa: E402
from protocol import decode_data_payload  # noqa: E402
from real_lora_config import RealCollisionLoRaConfig  # noqa: E402
from sc16_io import load_capture  # noqa: E402
from tnb_bec import TnBBECDecoder  # noqa: E402


ORDERS = (2, 4, 8, 12, 16)
BASELINE_METHODS = ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw", "sp_sync_refine")
METHOD = "mrc_cora"
METHOD_LABEL = "MRC+CoRa"
BOOTSTRAP_SEED = 20260803
METHOD_BOOTSTRAP_INDEX = 6
LEGACY_PRR_SOURCE = "shared_fine_sync_database"
LEGACY_PRR_POLICY = "fine_sync_detected_packets_plus_identity_mismatches"
POSTERIOR = Path(__file__).parent / "upstream/cora_v2/artifacts/python/models/dist.pkl"
DEFAULT_FIG11 = ROOT / "real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes"
DEFAULT_FINE = ROOT / "windows/analysis/fig9_10_12_preview/fine_sync"
DEFAULT_REPORTS = ROOT / "windows/analysis/fig9_10_12_preview/reports"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def manifest_path(run_name: str) -> Path:
    flat = ROOT / "real_collision_experiment/runs/manifests" / f"{run_name}.json"
    if flat.exists():
        return flat
    nested = ROOT / "real_collision_experiment/runs" / run_name / f"{run_name}.json"
    if nested.exists():
        return nested
    raise FileNotFoundError(f"manifest missing for {run_name}")


def candidate_method(candidate: dict, method: str) -> dict:
    row = next((row for row in candidate["methods"] if row.get("method") == method), None)
    if row is None:
        raise ValueError(f"legacy candidate {candidate.get('candidate_id')} lacks {method}")
    return row


def legacy_runtime_ms(candidate: dict, method: str) -> float:
    row = candidate_method(candidate, method)
    return float(row.get("post_sp_total_elapsed_ms", row.get("decode_elapsed_ms", 0.0)))


def bootstrap(values: list[float], order: int) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(array))
    if array.size <= 1:
        return mean, mean, mean
    rng = np.random.default_rng(
        BOOTSTRAP_SEED ^ (int(order) << 12) ^ METHOD_BOOTSTRAP_INDEX
    )
    samples = rng.choice(array, size=(20_000, array.size), replace=True)
    low, high = np.quantile(np.mean(samples, axis=1), [0.025, 0.975])
    return mean, float(low), float(high)


def historical_trial_count(scene_rows: dict[str, dict]) -> int:
    counts = {int(row["timed_packet_count"]) for row in scene_rows.values()}
    if len(counts) != 1:
        raise ValueError(f"legacy timed-candidate count disagreement: {counts}")
    return counts.pop()


def recover_candidate_trials(
    interval: dict,
    scene_rows: dict[str, dict],
    report: dict,
    fine: dict,
) -> tuple[list[int], dict]:
    """Recover legacy logical candidate trials from its six timing vectors."""

    trial_count = historical_trial_count(scene_rows)
    if trial_count == 0:
        return [], {"selection": "exact_runtime_fingerprint", "residual": 0.0}
    cfg = RealCollisionLoRaConfig(
        sf=int(fine["spreading_factor"]),
        bw_hz=float(fine["bandwidth_hz"]),
        sample_rate_hz=float(fine["sample_rate_hz"]),
    )
    frame_s = float(cfg.frame_samples) / float(cfg.sample_rate_hz)
    analysis_start = float(fine["window"]["analysis_start_s"])
    begin = float(interval["full_capture_start_s"]) - analysis_start
    end = float(interval["full_capture_end_s"]) - analysis_start
    # The old Oracle association could link a fine-start just outside the
    # collision-frame edges, so retain a two-frame guard band while solving.
    pool = [
        candidate
        for candidate in report["candidates"]
        if begin - 2.0 * frame_s < float(candidate["start_time_s"]) < end + 2.0 * frame_s
    ]
    if not pool:
        raise ValueError(f"scene {interval['scene_index']}: no historical candidates")
    target = np.asarray(
        [float(scene_rows[method]["post_sp_time_ms"]) for method in BASELINE_METHODS],
        dtype=np.float64,
    )
    vectors = np.asarray(
        [[legacy_runtime_ms(candidate, method) for method in BASELINE_METHODS] for candidate in pool],
        dtype=np.float64,
    )
    exact: list[tuple[int, ...]] = []
    best: tuple[float, tuple[int, ...], np.ndarray] | None = None
    for choice in itertools.combinations_with_replacement(range(len(pool)), trial_count):
        observed = vectors[list(choice)].sum(axis=0)
        residual = float(np.sum(((observed - target) / np.maximum(target, 1.0)) ** 2))
        candidate = (residual, choice, observed)
        if best is None or candidate[0] < best[0]:
            best = candidate
        if np.max(np.abs(observed - target)) <= 1e-6:
            exact.append(choice)
    if len(exact) == 1:
        choice = exact[0]
        return [int(pool[index]["candidate_id"]) for index in choice], {
            "selection": "exact_runtime_fingerprint",
            "residual": 0.0,
            "pool_candidate_ids": [int(row["candidate_id"]) for row in pool],
        }
    if best is None:
        raise RuntimeError(f"scene {interval['scene_index']}: candidate recovery failed")
    # Ten archived scenes have a stale baseline-runtime trace, but retain the
    # same historical 10s candidate pool.  The closest six-method fingerprint
    # is deterministic and is surfaced prominently in the audit.
    _, choice, observed = best
    return [int(pool[index]["candidate_id"]) for index in choice], {
        "selection": "minimum_residual_runtime_fingerprint",
        "residual": float(best[0]),
        "max_abs_runtime_residual_ms": float(np.max(np.abs(observed - target))),
        "pool_candidate_ids": [int(row["candidate_id"]) for row in pool],
    }


def target_assignment(
    interval: dict,
    trial_candidate_ids: list[int],
    report: dict,
    manifest: dict,
    origin_s: float,
) -> list[tuple[int, int]]:
    """Map recovered old logical trials to its Oracle collision-group targets."""

    if not trial_candidate_ids:
        return []
    by_id = {int(row["candidate_id"]): row for row in report["candidates"]}
    candidate_times = sorted(
        (float(by_id[candidate_id]["start_time_s"]), candidate_id)
        for candidate_id in trial_candidate_ids
    )
    targets: list[tuple[float, tuple[int, int]]] = []
    for item in interval["collision_group_identities"].split(";"):
        node_id, sequence = (int(value) for value in item.split(":"))
        start_ms = manifest["expected_node_schedules"][str(node_id)][
            "tx_start_ms_from_traffic_begin"
        ][sequence]
        targets.append((float(start_ms) / 1000.0 + origin_s, (node_id, sequence)))
    targets.sort()
    if len(candidate_times) > len(targets):
        raise ValueError(f"scene {interval['scene_index']}: too many legacy trials")

    @lru_cache(maxsize=None)
    def solve(candidate_index: int, target_index: int) -> tuple[float, tuple[int, ...]]:
        if candidate_index == len(candidate_times):
            return 0.0, ()
        if len(targets) - target_index < len(candidate_times) - candidate_index:
            return math.inf, ()
        skip_cost, skip_targets = solve(candidate_index, target_index + 1) if target_index < len(targets) else (math.inf, ())
        if target_index >= len(targets):
            return skip_cost, skip_targets
        match_tail_cost, match_tail = solve(candidate_index + 1, target_index + 1)
        match_cost = abs(candidate_times[candidate_index][0] - targets[target_index][0]) + match_tail_cost
        if match_cost <= skip_cost:
            return match_cost, (target_index,) + match_tail
        return skip_cost, skip_targets

    _, indices = solve(0, 0)
    if len(indices) != len(candidate_times):
        raise ValueError(f"scene {interval['scene_index']}: target association failed")
    assigned_by_candidate: dict[int, list[tuple[int, int]]] = {}
    for (_, candidate_id), index in zip(candidate_times, indices):
        assigned_by_candidate.setdefault(candidate_id, []).append(targets[index][1])
    occurrences: dict[int, int] = {}
    output: list[tuple[int, int]] = []
    for candidate_id in trial_candidate_ids:
        occurrence = occurrences.get(candidate_id, 0)
        occurrences[candidate_id] = occurrence + 1
        output.append(assigned_by_candidate[candidate_id][occurrence])
    return output


def decode_legacy_trials(
    intervals: list[dict],
    raw_by_scene: dict[str, dict[str, dict]],
    fine_dir: Path,
    reports_dir: Path,
    main_audit: dict,
) -> tuple[dict[str, list[dict]], dict]:
    detector = CoRaDetector(POSTERIOR)
    manifests: dict[str, dict] = {}
    reports: dict[str, dict] = {}
    fines: dict[str, dict] = {}
    recovered: dict[str, tuple[list[int], dict]] = {}
    for interval in intervals:
        scene_id = str(interval["scene_index"])
        run_name = interval["run"]
        if run_name not in reports:
            reports[run_name] = load_json(reports_dir / f"{run_name}.json")
            fines[run_name] = load_json(fine_dir / f"{run_name}.json")
            manifests[run_name] = load_json(manifest_path(run_name))
        report, fine = reports[run_name], fines[run_name]
        if len(report.get("candidates", [])) != len(fine.get("packets", [])):
            raise ValueError(f"{run_name}: legacy report/fine-sync mismatch")
        recovered[scene_id] = recover_candidate_trials(
            interval, raw_by_scene[scene_id], report, fine
        )

    output: dict[str, list[dict]] = {}
    audit: dict = {"runs": {}, "scenes": {}}
    grouped: dict[str, list[dict]] = {}
    for interval in intervals:
        grouped.setdefault(interval["run"], []).append(interval)
    for run_name, run_intervals in grouped.items():
        report, fine, manifest = reports[run_name], fines[run_name], manifests[run_name]
        cfg = RealCollisionLoRaConfig(
            sf=int(fine["spreading_factor"]),
            bw_hz=float(fine["bandwidth_hz"]),
            sample_rate_hz=float(fine["sample_rate_hz"]),
            ldro=(2 ** int(fine["spreading_factor"])) / float(fine["bandwidth_hz"]) >= 0.016,
        )
        source_iq = Path(fine.get("source_iq", report["input"]["iq"]))
        capture = load_capture(
            source_iq,
            start_time_s=float(fine["window"]["analysis_start_s"]),
            max_duration_s=float(fine["window"]["duration_s"]),
        )
        samples = capture.samples.astype(np.complex64, copy=False)
        noise_samples = min(samples.shape[1], round(3.0 * cfg.sample_rate_hz))
        samples = samples - np.mean(samples[:, :noise_samples], axis=1, keepdims=True)
        candidates = {
            candidate_id: row
            for candidate_id, row in enumerate(fine["packets"])
        }
        origin_s = float(main_audit["alignments"][run_name]["traffic_origin_relative_to_slice_s"])
        audit["runs"][run_name] = {
            "fine_sync": str((fine_dir / f"{run_name}.json").resolve()),
            "report": str((reports_dir / f"{run_name}.json").resolve()),
            "source_iq": str(source_iq.resolve()),
            "window": fine["window"],
            "legacy_origin_s": origin_s,
        }
        for interval in run_intervals:
            scene_id = str(interval["scene_index"])
            trial_ids, recovery = recovered[scene_id]
            assigned_targets = target_assignment(
                interval, trial_ids, report, manifest, origin_s
            )
            if len(trial_ids) != len(assigned_targets):
                raise AssertionError("legacy trial/target association length mismatch")
            records: list[dict] = []
            for trial_index, (candidate_id, expected_identity) in enumerate(
                zip(trial_ids, assigned_targets)
            ):
                estimate = candidates[candidate_id]
                started_ns = time.perf_counter_ns()
                symbols = detector.detect(samples, estimate, cfg)
                parameter_s = float((symbols.stage_seconds.get("mrc_preparation", 0.0) + symbols.stage_seconds.get("preamble_peak_estimation", 0.0)))
                phy = TnBBECDecoder(random_seed=0).decode(symbols.symbol_bins, cfg)
                identity = None
                application_status = "not_attempted"
                if phy.phy_crc_ok and len(phy.payload) == 20:
                    try:
                        application = decode_data_payload(phy.payload)
                    except ValueError as exc:
                        application_status = str(exc)
                    else:
                        identity = (int(application.node_id), int(application.sequence))
                        application_status = "ok"
                elapsed_s = (time.perf_counter_ns() - started_ns) / 1e9
                records.append(
                    {
                        "trial_index": trial_index,
                        "candidate_id": candidate_id,
                        "expected_identity": list(expected_identity),
                        "identity": list(identity) if identity is not None else None,
                        "parameter_estimation_time_ms": parameter_s * 1000.0,
                        "decode_time_ms": max(0.0, elapsed_s - parameter_s) * 1000.0,
                        "post_sp_time_ms": elapsed_s * 1000.0,
                        "status": phy.status if application_status in ("not_attempted", "ok") else application_status,
                        "phy_crc_ok": bool(phy.phy_crc_ok),
                    }
                )
            output[scene_id] = records
            audit["scenes"][scene_id] = {
                "run": run_name,
                "legacy_candidate_ids": trial_ids,
                "recovery": recovery,
                "records": records,
            }
            print(
                f"CORA_FIG11_LEGACY scene={scene_id} trials={len(records)} "
                f"mode={recovery['selection']}",
                flush=True,
            )
    return output, audit


def scene_rows(intervals: list[dict], decoded: dict[str, list[dict]]) -> list[dict]:
    rows: list[dict] = []
    for interval in intervals:
        records = decoded[str(interval["scene_index"])]
        matched = sum(
            record["identity"] is not None
            and tuple(record["identity"]) == tuple(record["expected_identity"])
            for record in records
        )
        mismatched = sum(
            record["identity"] is not None
            and tuple(record["identity"]) != tuple(record["expected_identity"])
            for record in records
        )
        detected = int(interval["fine_sync_detected_packet_count"])
        denominator = detected + mismatched
        rows.append(
            {
                "collision_order": int(interval["collision_order"]),
                "decode_time_ms": sum(float(record["decode_time_ms"]) for record in records),
                "decoded_packet_count": matched + mismatched,
                "fine_sync_detected_packet_count": detected,
                "identity_matched_packet_count": matched,
                "identity_mismatch_count": mismatched,
                "method": METHOD,
                "method_label": METHOD_LABEL,
                "packet_count": int(interval["sp_candidate_count"]),
                "parameter_estimation_time_ms": sum(float(record["parameter_estimation_time_ms"]) for record in records),
                "post_sp_time_ms": sum(float(record["post_sp_time_ms"]) for record in records),
                "prr_counting_policy": LEGACY_PRR_POLICY,
                "prr_denominator_packet_count": denominator,
                "prr_denominator_source": LEGACY_PRR_SOURCE,
                "prr_packet_count": denominator,
                "run": interval["run"],
                "scene_index": int(interval["scene_index"]),
                "ser": math.nan,
                "sp_candidate_count": int(interval["sp_candidate_count"]),
                "symbol_count": 0,
                "symbol_error_count": 0,
                "timed_packet_count": len(records),
                "timing_complete_for_collision_group": True,
            }
        )
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for order in ORDERS:
        selected = [row for row in rows if int(row["collision_order"]) == order]
        times = [float(row["post_sp_time_ms"]) for row in selected]
        mean, low, high = bootstrap(times, order)
        decoded = sum(int(row["decoded_packet_count"]) for row in selected)
        denominator = sum(int(row["prr_denominator_packet_count"]) for row in selected)
        output.append(
            {
                "collision_order": order,
                "collision_scene_count": len(selected),
                "decoded_packet_count": decoded,
                "fine_sync_detected_packet_count": sum(int(row["fine_sync_detected_packet_count"]) for row in selected),
                "identity_matched_packet_count": sum(int(row["identity_matched_packet_count"]) for row in selected),
                "identity_mismatch_count": sum(int(row["identity_mismatch_count"]) for row in selected),
                "method": METHOD,
                "method_label": METHOD_LABEL,
                "post_sp_time_ci95_high_ms": high,
                "post_sp_time_ci95_low_ms": low,
                "post_sp_time_mean_ms": mean,
                "prr_counting_policy": LEGACY_PRR_POLICY,
                "prr_denominator_packet_count": denominator,
                "prr_denominator_source": LEGACY_PRR_SOURCE,
                "prr_mean": decoded / denominator if denominator else math.nan,
                "ser_ci95_high": math.nan,
                "ser_ci95_low": math.nan,
                "ser_mean": math.nan,
                "timed_collision_scene_count": len(selected),
            }
        )
    return output


def plot(summary: list[dict], output_dir: Path) -> None:
    methods = ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw", "mrc_cora", "sp_sync_refine")
    labels = {"lorawan": "LoRaWAN", "mrc": "MRC", "mrc_cic": "MRC+CIC", "pcube": "PCube", "maloragw": "MaLoRaGW", "mrc_cora": "MRC+CoRa", "sp_sync_refine": "SP-Decoder"}
    colors = {"lorawan": "#6C757D", "mrc": "#457B9D", "mrc_cic": "#E76F51", "pcube": "#F4A261", "maloragw": "#6C5CE7", "mrc_cora": "#C2185B", "sp_sync_refine": "#159D8A"}
    markers = {"lorawan": "v", "mrc": "o", "mrc_cic": "s", "pcube": "^", "maloragw": "D", "mrc_cora": "X", "sp_sync_refine": "*"}
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.2))
    x = np.arange(len(ORDERS), dtype=np.float64)
    width = 0.84 / len(methods)
    for method_index, method in enumerate(methods):
        lookup = {int(row["collision_order"]): row for row in summary if row["method"] == method}
        if set(lookup) != set(ORDERS):
            raise ValueError(f"legacy summary lacks orders for {method}")
        values = np.asarray([float(lookup[order]["post_sp_time_mean_ms"]) for order in ORDERS])
        low = np.asarray([float(lookup[order]["post_sp_time_ci95_low_ms"]) for order in ORDERS])
        high = np.asarray([float(lookup[order]["post_sp_time_ci95_high_ms"]) for order in ORDERS])
        position = x - 0.42 + width / 2 + method_index * width
        axes[0].bar(position, values, width, yerr=np.vstack([values - low, high - values]), color=colors[method], capsize=2, label=labels[method])
        axes[1].plot(ORDERS, [float(lookup[order]["prr_mean"]) for order in ORDERS], color=colors[method], marker=markers[method], linestyle="-", label=labels[method])
    axes[0].set_xticks(x, [str(value) for value in ORDERS])
    axes[0].set_xlabel("Packets in the target collision group")
    axes[0].set_ylabel("Estimation + decode time / collision scene (ms)")
    axes[1].set_xticks(ORDERS)
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].set_xlabel("Packets in the target collision group")
    axes[1].set_ylabel("PRR (legacy detected + mismatch denominator)")
    for axis in axes:
        axis.grid(alpha=0.24)
    axes[0].legend(ncol=2, fontsize=7.2, frameon=False)
    fig.tight_layout()
    stem = output_dir / "fig11_real_decoder_time_ser"
    for suffix in (".png", ".pdf", ".svg"):
        fig.savefig(stem.with_suffix(suffix), dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fig11-dir", type=Path, default=DEFAULT_FIG11)
    parser.add_argument("--fine-sync-dir", type=Path, default=DEFAULT_FINE)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()
    intervals = read_csv(args.fig11_dir / "fig11_real_collision_intervals.csv")
    if {int(row["collision_order"]) for row in intervals} != set(ORDERS):
        raise ValueError("legacy Fig. 11 does not contain 2/4/8/12/16 scenes")
    raw_path = args.fig11_dir / "fig11_real_decoder_time_ser_raw.csv"
    summary_path = args.fig11_dir / "fig11_real_decoder_time_ser_summary.csv"
    base_raw = [row for row in read_csv(raw_path) if row.get("method") != METHOD]
    base_summary = [row for row in read_csv(summary_path) if row.get("method") != METHOD]
    raw_by_scene: dict[str, dict[str, dict]] = {}
    for row in base_raw:
        raw_by_scene.setdefault(str(row["scene_index"]), {})[row["method"]] = row
    if any(set(raw_by_scene.get(str(row["scene_index"]), {})) != set(BASELINE_METHODS) for row in intervals):
        raise ValueError("legacy baseline rows are incomplete")
    main_audit = load_json(args.fig11_dir / "fig11_real_run_audit.json")
    decoded, audit = decode_legacy_trials(intervals, raw_by_scene, args.fine_sync_dir, args.reports_dir, main_audit)
    cora_raw = scene_rows(intervals, decoded)
    cora_summary = summarize(cora_raw)
    raw_fields = list(next(csv.reader(raw_path.open(encoding="utf-8"))))
    summary_fields = list(next(csv.reader(summary_path.open(encoding="utf-8"))))
    write_csv(args.fig11_dir / "mrc_cora_fig11_decoder_time_prr_raw.csv", cora_raw, raw_fields)
    write_csv(args.fig11_dir / "mrc_cora_fig11_decoder_time_prr_summary.csv", cora_summary, summary_fields)
    combined_raw = base_raw + cora_raw
    combined_summary = base_summary + cora_summary
    write_csv(raw_path, combined_raw, raw_fields)
    write_csv(summary_path, combined_summary, summary_fields)
    plot(combined_summary, args.fig11_dir)
    audit.update({
        "schema": "mrc_cora_fig11_legacy_10s_intervals_v1",
        "method": METHOD,
        "method_label": METHOD_LABEL,
        "posterior_grid": str(POSTERIOR.resolve()),
        "scene_count": len(intervals),
        "collision_orders": list(ORDERS),
        "historical_window_s": 10.0,
        "candidate_association": "legacy candidate multiset recovered from recorded six-method timing fingerprints; Oracle target mapping reconstructed by ordered minimum start-time offset",
        "timing_scope": "complete CoRa PMD/HPD Bayesian detector + TnB BEC/PHY CRC + application CRC for every recovered logical legacy candidate trial; shared fine synchronization excluded",
        "prr_scope": "legacy (identity-matched CRC-valid trials + CRC-valid identity-mismatched trials) / (legacy fine-sync detected packet count + identity-mismatched trials)",
        "summary": cora_summary,
    })
    (args.fig11_dir / "mrc_cora_fig11_run_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    main_audit["summary"] = combined_summary
    main_audit["cora_supplement"] = {
        "enabled": True,
        "method": METHOD,
        "method_label": METHOD_LABEL,
        "runner": str(Path(__file__).resolve()),
        "audit": str((args.fig11_dir / "mrc_cora_fig11_run_audit.json").resolve()),
        "raw_csv": str((args.fig11_dir / "mrc_cora_fig11_decoder_time_prr_raw.csv").resolve()),
        "summary_csv": str((args.fig11_dir / "mrc_cora_fig11_decoder_time_prr_summary.csv").resolve()),
        "timing_scope": audit["timing_scope"],
        "prr_scope": audit["prr_scope"],
    }
    (args.fig11_dir / "fig11_real_run_audit.json").write_text(json.dumps(main_audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    approximate = [key for key, value in audit["scenes"].items() if value["recovery"]["selection"] != "exact_runtime_fingerprint"]
    print(f"CORA_FIG11_LEGACY_DONE scenes={len(cora_raw)} approximate_recovery_scenes={approximate}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
