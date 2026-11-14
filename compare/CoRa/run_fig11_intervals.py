#!/usr/bin/env python3
"""Add CoRa latency/PRR to the existing real-run Fig. 11 intervals.

The scene list is treated as immutable input.  Each CoRa packet attempt uses
the same anonymous, schedule-free fine-sync candidate used by the existing
methods.  Native discovery is therefore outside the timed scope; expected
preamble peak estimation, CoRa PMD/HPD Bayesian symbol decisions, TnB BEC,
PHY CRC, and application CRC are all inside it.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
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


METHOD = "mrc_cora"
METHOD_LABEL = "MRC+CoRa"
ORDERS = (2, 4, 8, 12, 16)
BOOTSTRAP_SEED = 20260803
METHOD_BOOTSTRAP_INDEX = 6  # CoRa follows the six existing Fig. 11 methods.
PRR_DENOMINATOR_SOURCE = (
    "min_manifest_collision_scene_expected_or_anonymous_detected_packets"
)
PRR_COUNTING_POLICY = (
    "unique_crc_valid_manifest_collision_group_payload_identities_over_"
    "min_manifest_collision_scene_expected_or_anonymous_detected_packets"
)
FIG11_DIR = ROOT / "real_collision_experiment/analysis/fig11_real_run_intervals"
FINE_SYNC_DIR = ROOT / "real_collision_experiment/analysis/fig9_10_12_5s/fine_sync"
REPORTS_DIR = ROOT / "real_collision_experiment/analysis/fig9_10_12_5s/reports"
POSTERIOR = (
    Path(__file__).parent / "upstream/cora_v2/artifacts/python/models/dist.pkl"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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


def decode_runs(intervals: list[dict]) -> tuple[dict[str, list[dict]], dict]:
    detector = CoRaDetector(POSTERIOR)
    decoded_by_run: dict[str, list[dict]] = {}
    audit: dict = {"runs": {}}
    for run_name in sorted({row["run"] for row in intervals}):
        fine_path = FINE_SYNC_DIR / f"{run_name}.json"
        report_path = REPORTS_DIR / f"{run_name}.json"
        fine = load_json(fine_path)
        report = load_json(report_path)
        packets = fine.get("packets", [])
        report_candidates = report.get("candidates", [])
        if fine.get("schema") != "fine_sync_anonymous_physical_v2":
            raise ValueError(f"{run_name}: incompatible fine-sync schema")
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
                raise ValueError(f"{run_name}: shared-sync audit mismatch for {key}")
        if len(packets) != len(report_candidates):
            raise ValueError(f"{run_name}: fine-sync/report candidate count mismatch")
        sf = int(fine["spreading_factor"])
        bandwidth_hz = int(fine["bandwidth_hz"])
        if sf != 10 or bandwidth_hz != 250_000:
            raise ValueError(f"{run_name}: Fig. 11 PHY mismatch")
        cfg = RealCollisionLoRaConfig(
            sf=sf,
            bw_hz=float(bandwidth_hz),
            sample_rate_hz=float(fine["sample_rate_hz"]),
            ldro=(2**sf) / float(bandwidth_hz) >= 0.016,
        )
        capture = load_capture(
            Path(fine["source_iq"]),
            start_time_s=float(fine["window"]["analysis_start_s"]),
            max_duration_s=float(fine["window"]["duration_s"]),
        )
        samples = capture.samples.astype(np.complex64, copy=False)
        noise_samples = min(samples.shape[1], round(3.0 * cfg.sample_rate_hz))
        samples = samples - np.mean(samples[:, :noise_samples], axis=1, keepdims=True)
        bec = TnBBECDecoder(random_seed=0)
        decoded: list[dict] = []
        status_counts: dict[str, int] = {}
        for candidate_id, (estimate, report_candidate) in enumerate(
            zip(packets, report_candidates)
        ):
            if abs(float(estimate["start_sample"]) - float(report_candidate["start_sample"])) > 1e-6:
                raise ValueError(f"{run_name}: candidate {candidate_id} ordering mismatch")
            started_ns = time.perf_counter_ns()
            symbols = detector.detect(samples, estimate, cfg)
            parameter_s = float(
                (symbols.stage_seconds.get("mrc_preparation", 0.0) + symbols.stage_seconds.get("preamble_peak_estimation", 0.0))
            )
            phy = bec.decode(symbols.symbol_bins, cfg)
            identity = None
            application_status = "not_attempted"
            if phy.phy_crc_ok and len(phy.payload) == 20:
                try:
                    application = decode_data_payload(phy.payload)
                except ValueError as exc:
                    application_status = str(exc)
                else:
                    # This deliberately matches build_fig11_real_run_intervals.py:
                    # the CRC-valid payload's embedded identity is counted as-is.
                    identity = (int(application.node_id), int(application.sequence))
                    application_status = "ok"
            elapsed_s = (time.perf_counter_ns() - started_ns) / 1e9
            decode_s = max(0.0, elapsed_s - parameter_s)
            status = (
                phy.status
                if application_status in ("not_attempted", "ok")
                else application_status
            )
            status_counts[status] = status_counts.get(status, 0) + 1
            decoded.append(
                {
                    "candidate_id": candidate_id,
                    "start_sample": float(estimate["start_sample"]),
                    "start_time_s": float(report_candidate["start_time_s"]),
                    "parameter_estimation_time_ms": parameter_s * 1000.0,
                    "decode_time_ms": decode_s * 1000.0,
                    "post_sp_time_ms": elapsed_s * 1000.0,
                    "identity": list(identity) if identity is not None else None,
                    "phy_crc_ok": bool(phy.phy_crc_ok),
                    "status": status,
                    "bec_crc_attempts": int(phy.made_crc_attempts),
                    "mrc_channel_source": symbols.mrc_channel_source,
                    "mrc_weights": [[w.real, w.imag] for w in symbols.mrc_weights],
                    "bec_total_candidate_schedules": int(
                        phy.total_candidate_schedules
                    ),
                    "bec_additionally_corrected_codewords": int(
                        phy.additionally_corrected_codewords
                    ),
                }
            )
        decoded_by_run[run_name] = decoded
        audit["runs"][run_name] = {
            "fine_sync": str(fine_path.resolve()),
            "report": str(report_path.resolve()),
            "source_iq": str(Path(fine["source_iq"]).resolve()),
            "candidate_count": len(decoded),
            "crc_valid_candidate_count": sum(
                row["identity"] is not None for row in decoded
            ),
            "status_counts": status_counts,
            "decoder_work_s": sum(row["post_sp_time_ms"] for row in decoded)
            / 1000.0,
        }
        print(
            f"CORA_FIG11_RUN {run_name} candidates={len(decoded)} "
            f"valid={audit['runs'][run_name]['crc_valid_candidate_count']} "
            f"work={audit['runs'][run_name]['decoder_work_s']:.6f}s",
            flush=True,
        )
    return decoded_by_run, audit


def scene_rows(
    intervals: list[dict], decoded_by_run: dict[str, list[dict]]
) -> list[dict]:
    rows: list[dict] = []
    for interval in intervals:
        run_name = interval["run"]
        fine = load_json(FINE_SYNC_DIR / f"{run_name}.json")
        cfg = RealCollisionLoRaConfig(
            sf=int(fine["spreading_factor"]),
            bw_hz=float(fine["bandwidth_hz"]),
            sample_rate_hz=float(fine["sample_rate_hz"]),
        )
        frame_s = float(cfg.frame_samples) / float(cfg.sample_rate_hz)
        analysis_start_s = float(fine["window"]["analysis_start_s"])
        begin_s = float(interval["full_capture_start_s"]) - analysis_start_s
        end_s = float(interval["full_capture_end_s"]) - analysis_start_s
        selected = [
            candidate
            for candidate in decoded_by_run[run_name]
            if candidate["start_time_s"] < end_s
            and candidate["start_time_s"] + frame_s > begin_s
        ]
        expected_detected = int(interval["fine_sync_detected_packet_count"])
        if len(selected) != expected_detected:
            raise ValueError(
                f"scene {interval['scene_index']}: candidate count "
                f"{len(selected)} != {expected_detected}"
            )
        planned_identities = {
            tuple(int(value) for value in item.split(":"))
            for item in interval["collision_group_identities"].split(";")
            if item
        }
        identities = {
            tuple(int(value) for value in candidate["identity"])
            for candidate in selected
            if candidate["identity"] is not None
            and tuple(int(value) for value in candidate["identity"])
            in planned_identities
        }
        denominator = min(int(interval["planned_packet_count"]), len(selected))
        if len(identities) > denominator:
            raise ValueError(
                f"scene {interval['scene_index']}: decoded identities exceed denominator"
            )
        parameter_ms = sum(
            float(candidate["parameter_estimation_time_ms"])
            for candidate in selected
        )
        decode_ms = sum(float(candidate["decode_time_ms"]) for candidate in selected)
        total_ms = sum(float(candidate["post_sp_time_ms"]) for candidate in selected)
        rows.append(
            {
                "collision_order": int(interval["collision_order"]),
                "decode_time_ms": decode_ms,
                "decoded_packet_count": len(identities),
                "fine_sync_detected_packet_count": len(selected),
                "method": METHOD,
                "method_label": METHOD_LABEL,
                "packet_count": len(selected),
                "parameter_estimation_time_ms": parameter_ms,
                "planned_packet_count": int(interval["planned_packet_count"]),
                "post_sp_time_ms": total_ms,
                "prr_counting_policy": PRR_COUNTING_POLICY,
                "prr_denominator_packet_count": denominator,
                "prr_denominator_source": PRR_DENOMINATOR_SOURCE,
                "prr_packet_count": denominator,
                "run": run_name,
                "scene_index": int(interval["scene_index"]),
                "ser": math.nan,
                "sp_candidate_count": len(selected),
                "symbol_count": 0,
                "symbol_error_count": 0,
                "timed_packet_count": len(selected),
                "timing_complete_for_collision_group": True,
            }
        )
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for order in ORDERS:
        selected = [row for row in rows if int(row["collision_order"]) == order]
        if not selected:
            raise ValueError(f"no CoRa scenes for collision order {order}")
        times = [float(row["post_sp_time_ms"]) for row in selected]
        mean, low, high = bootstrap(times, order)
        decoded = sum(int(row["decoded_packet_count"]) for row in selected)
        denominator = sum(
            int(row["prr_denominator_packet_count"]) for row in selected
        )
        output.append(
            {
                "collision_order": order,
                "collision_scene_count": len(selected),
                "decoded_packet_count": decoded,
                "fine_sync_detected_packet_count": sum(
                    int(row["fine_sync_detected_packet_count"]) for row in selected
                ),
                "manifest_expected_packet_count_in_collision_scenes": sum(
                    int(row["planned_packet_count"]) for row in selected
                ),
                "method": METHOD,
                "method_label": METHOD_LABEL,
                "post_sp_time_ci95_high_ms": high,
                "post_sp_time_ci95_low_ms": low,
                "post_sp_time_mean_ms": mean,
                "prr_counting_policy": PRR_COUNTING_POLICY,
                "prr_denominator_packet_count": denominator,
                "prr_denominator_source": PRR_DENOMINATOR_SOURCE,
                "prr_mean": decoded / denominator,
                "ser_ci95_high": math.nan,
                "ser_ci95_low": math.nan,
                "ser_mean": math.nan,
                "timed_collision_scene_count": len(selected),
            }
        )
    return output


def plot(summary: list[dict]) -> None:
    methods = (
        "lorawan", "mrc", "mrc_cic", "pcube", "maloragw", "mrc_cora",
        "sp_sync_refine",
    )
    labels = {
        "lorawan": "LoRaWAN", "mrc": "MRC", "mrc_cic": "MRC+CIC",
        "pcube": "PCube", "maloragw": "MaLoRaGW", "mrc_cora": "MRC+CoRa",
        "sp_sync_refine": "SP-Decoder",
    }
    colors = {
        "lorawan": "#6C757D", "mrc": "#457B9D", "mrc_cic": "#E76F51",
        "pcube": "#F4A261", "maloragw": "#6C5CE7", "mrc_cora": "#C2185B",
        "sp_sync_refine": "#159D8A",
    }
    markers = {
        "lorawan": "v", "mrc": "o", "mrc_cic": "s", "pcube": "^",
        "maloragw": "D", "mrc_cora": "X", "sp_sync_refine": "*",
    }
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.2))
    x = np.arange(len(ORDERS), dtype=np.float64)
    width = 0.84 / len(methods)
    for method_index, method in enumerate(methods):
        lookup = {
            int(row["collision_order"]): row
            for row in summary
            if row["method"] == method
        }
        if set(lookup) != set(ORDERS):
            raise ValueError(f"summary lacks all orders for {method}")
        values = np.asarray(
            [float(lookup[order]["post_sp_time_mean_ms"]) for order in ORDERS]
        )
        low = np.asarray(
            [float(lookup[order]["post_sp_time_ci95_low_ms"]) for order in ORDERS]
        )
        high = np.asarray(
            [float(lookup[order]["post_sp_time_ci95_high_ms"]) for order in ORDERS]
        )
        position = x - 0.42 + width / 2 + method_index * width
        axes[0].bar(
            position,
            values,
            width,
            yerr=np.vstack([values - low, high - values]),
            color=colors[method],
            capsize=2,
            label=labels[method],
        )
        axes[1].plot(
            ORDERS,
            [float(lookup[order]["prr_mean"]) for order in ORDERS],
            color=colors[method],
            marker=markers[method],
            linestyle="-",
            label=labels[method],
        )
    axes[0].set_xticks(x, [str(value) for value in ORDERS])
    axes[0].set_xlabel("Packets in the target collision group")
    axes[0].set_ylabel("Estimation + decode time / collision scene (ms)")
    axes[1].set_xticks(ORDERS)
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].set_xlabel("Packets in the target collision group")
    axes[1].set_ylabel("PRR (unique decoded / min(planned, detected))")
    for axis in axes:
        axis.grid(alpha=0.24)
    axes[0].legend(ncol=2, fontsize=7.2, frameon=False)
    fig.tight_layout()
    stem = FIG11_DIR / "fig11_real_decoder_time_ser"
    for suffix in (".png", ".pdf", ".svg"):
        fig.savefig(stem.with_suffix(suffix), dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    global FIG11_DIR, FINE_SYNC_DIR, REPORTS_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fig11-dir", type=Path, default=FIG11_DIR)
    parser.add_argument("--fine-sync-dir", type=Path, default=FINE_SYNC_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args()
    FIG11_DIR = args.fig11_dir
    FINE_SYNC_DIR = args.fine_sync_dir
    REPORTS_DIR = args.reports_dir
    intervals_path = FIG11_DIR / "fig11_real_collision_intervals.csv"
    raw_path = FIG11_DIR / "fig11_real_decoder_time_ser_raw.csv"
    summary_path = FIG11_DIR / "fig11_real_decoder_time_ser_summary.csv"
    intervals = read_csv(intervals_path)
    interval_orders = {int(row["collision_order"]) for row in intervals}
    if not intervals or interval_orders != set(ORDERS):
        raise ValueError(
            "Fig. 11 scene table must contain exactly collision orders "
            f"{list(ORDERS)}; got {sorted(interval_orders)} across {len(intervals)} scenes"
        )
    decoded_by_run, audit = decode_runs(intervals)
    cora_raw = scene_rows(intervals, decoded_by_run)
    cora_summary = summarize(cora_raw)

    raw_fields = list(next(csv.reader(raw_path.open(encoding="utf-8"))))
    summary_fields = list(next(csv.reader(summary_path.open(encoding="utf-8"))))
    base_raw = [row for row in read_csv(raw_path) if row.get("method") != METHOD]
    base_summary = [
        row for row in read_csv(summary_path) if row.get("method") != METHOD
    ]
    combined_raw = base_raw + cora_raw
    combined_summary = base_summary + cora_summary
    write_csv(
        FIG11_DIR / "mrc_cora_fig11_decoder_time_prr_raw.csv", cora_raw, raw_fields
    )
    write_csv(
        FIG11_DIR / "mrc_cora_fig11_decoder_time_prr_summary.csv",
        cora_summary,
        summary_fields,
    )
    write_csv(raw_path, combined_raw, raw_fields)
    write_csv(summary_path, combined_summary, summary_fields)
    plot(combined_summary)

    audit.update(
        {
            "schema": "mrc_cora_fig11_real_intervals_v1",
            "method": METHOD,
            "method_label": METHOD_LABEL,
            "posterior_grid": str(POSTERIOR.resolve()),
            "posterior_grid_shape": [200, 200],
            "scene_source": str(intervals_path.resolve()),
            "scene_count": len(intervals),
            "collision_orders": list(ORDERS),
            "timing_scope": (
                "sum per scene over every anonymous fine-sync candidate: expected "
                "preamble peak estimation + CoRa dechirp/PMD/HPD/Bayesian decision + "
                "TnB BEC/PHY CRC + application CRC; shared fine synchronization excluded"
            ),
            "prr_scope": (
                "pooled unique CRC-valid embedded payload identities belonging to the "
                "manifest collision group / sum of "
                "min(scene manifest planned packets, scene anonymous detected candidates)"
            ),
            "raw_rows": len(cora_raw),
            "summary": cora_summary,
        }
    )
    (FIG11_DIR / "mrc_cora_fig11_run_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    main_audit_path = FIG11_DIR / "fig11_real_run_audit.json"
    main_audit = load_json(main_audit_path)
    main_audit["summary"] = combined_summary
    main_audit["cora_supplement"] = {
        "enabled": True,
        "method": METHOD,
        "method_label": METHOD_LABEL,
        "runner": str(Path(__file__).resolve()),
        "audit": str((FIG11_DIR / "mrc_cora_fig11_run_audit.json").resolve()),
        "raw_csv": str(
            (FIG11_DIR / "mrc_cora_fig11_decoder_time_prr_raw.csv").resolve()
        ),
        "summary_csv": str(
            (FIG11_DIR / "mrc_cora_fig11_decoder_time_prr_summary.csv").resolve()
        ),
        "timing_scope": audit["timing_scope"],
        "prr_scope": audit["prr_scope"],
    }
    main_audit_path.write_text(
        json.dumps(main_audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"CORA_FIG11_DONE scenes={len(cora_raw)} out={FIG11_DIR}", flush=True
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
