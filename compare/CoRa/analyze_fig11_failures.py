#!/usr/bin/env python3
"""Evidence-backed failure analysis for CoRa on the fixed Fig. 11 scenes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RECEIVER = ROOT / "real_collision_experiment/node01_sp_receiver"
CONTROL = ROOT / "real_collision_experiment/control_usrp"
PAPER_EXPERIMENTS = ROOT / "real_collision_experiment/paper_experiments"
for source in (ROOT, RECEIVER, CONTROL, PAPER_EXPERIMENTS, Path(__file__).parent):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from compare.mrc_input import target_mrc_input
from cora_detector import CoRaDetector, FEATURE_MAX, GRID_BINS  # noqa: E402
from lora_mrc_sp_core import (  # noqa: E402
    compensate_symbol_window,
    instantaneous_chirp,
    lora_symbol_fft,
)
from lora_phy_decode import (  # noqa: E402
    decode_hamming_word,
    decode_payload_from_symbol_bins,
    deinterleave_explicit,
    gray_inverse_map,
)
from real_lora_config import RealCollisionLoRaConfig  # noqa: E402
from sc16_io import load_capture  # noqa: E402
from simulate_sp_mechanisms import (  # noqa: E402
    encode_explicit_payload,
    payload_nibbles,
)
from tnb_bec import TnBBECDecoder  # noqa: E402


FIG11 = ROOT / "real_collision_experiment/analysis/fig11_real_run_intervals"
FINE = ROOT / "real_collision_experiment/analysis/fig9_10_12_5s/fine_sync"
REPORTS = ROOT / "real_collision_experiment/analysis/fig9_10_12_5s/reports"
POSTERIOR = Path(__file__).parent / "upstream/cora_v2/artifacts/python/models/dist.pkl"
ORDERS = (2, 4, 8, 12, 16)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def truth_payload(candidate: dict) -> bytes | None:
    payloads: set[str] = set()
    for method in candidate.get("methods", []):
        application = method.get("application", {})
        payload_hex = method.get("phy", {}).get("payload_hex")
        if (
            application.get("app_crc_ok")
            and application.get("manifest_payload_match") is not False
            and isinstance(payload_hex, str)
            and len(payload_hex) == 40
        ):
            payloads.add(payload_hex)
    if len(payloads) != 1:
        return None
    return bytes.fromhex(next(iter(payloads)))


def percentile(values: list[float], q: float) -> float | None:
    return float(np.quantile(values, q)) if values else None


def summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": float(np.mean(values)) if values else None,
        "median": percentile(values, 0.5),
        "p10": percentile(values, 0.1),
        "p90": percentile(values, 0.9),
    }


def preamble_magnitudes(
    detector: CoRaDetector,
    samples: np.ndarray,
    estimate: dict,
    cfg: RealCollisionLoRaConfig,
) -> list[float]:
    start, cfo = detector._effective_sync(estimate)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    output: list[float] = []
    for index in range(cfg.preamble_len):
        symbol_start = start + index * cfg.samples_per_symbol
        if symbol_start < 0 or symbol_start + cfg.samples_per_symbol > samples.shape[1]:
            continue
        compensated = compensate_symbol_window(
            samples[:1], symbol_start, cfo, cfg, sto_samples=0.0
        )[0]
        output.append(float(abs(lora_symbol_fft(compensated * downchirp, cfg)[0])))
    return output


def truth_feature_metrics(
    detector: CoRaDetector,
    samples: np.ndarray,
    estimate: dict,
    cfg: RealCollisionLoRaConfig,
    expected_peak: float,
    truth_bins: list[int],
) -> dict | None:
    start, cfo = detector._effective_sync(estimate)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    relatives = (
        float(cfg.payload_start_symbols)
        - 1.0
        + np.arange(cfg.payload_symbol_count + 1, dtype=np.float64)
    )
    chips = []
    for relative in relatives:
        symbol_start = start + float(relative) * cfg.samples_per_symbol
        if symbol_start < 0 or symbol_start + cfg.samples_per_symbol > samples.shape[1]:
            return None
        chips.append(
            detector._dechirped_chips(
                samples,
                symbol_start=symbol_start,
                cfo_bins=cfo,
                cfg=cfg,
                downchirp=downchirp,
            )
        )
    hpd, pmd, _ = detector.calculate_features(
        np.asarray(chips), expected_peak
    )
    h_index = np.floor(np.minimum(hpd, FEATURE_MAX) * GRID_BINS).astype(np.int64)
    p_index = np.floor(np.minimum(pmd, FEATURE_MAX) * GRID_BINS).astype(np.int64)
    complete = detector.posterior[h_index, p_index]
    bayes = complete[1:] * (1.0 - complete[:-1])
    truth = np.asarray(truth_bins, dtype=np.int64)
    row = np.arange(truth.size)
    truth_score = bayes[row, truth]
    selected = np.argmax(bayes, axis=1)
    selected_score = bayes[row, selected]
    ranks = 1 + np.sum(bayes > truth_score[:, None], axis=1)
    return {
        "truth_rank1_fraction": float(np.mean(ranks == 1)),
        "truth_rank_median": float(np.median(ranks)),
        "truth_rank_p90": float(np.quantile(ranks, 0.9)),
        "truth_bayes_score_median": float(np.median(truth_score)),
        "winner_to_truth_score_ratio_median": float(
            np.median(selected_score / np.maximum(truth_score, 1e-30))
        ),
        "truth_hpd_median": float(np.median(hpd[1:][row, truth])),
        "winner_hpd_median": float(np.median(hpd[1:][row, selected])),
        "truth_pmd_median": float(np.median(pmd[1:][row, truth])),
        "winner_pmd_median": float(np.median(pmd[1:][row, selected])),
    }


def pre_bec_nibble_errors(
    symbol_bins: list[int], payload: bytes, cfg: RealCollisionLoRaConfig
) -> dict:
    """Compare meaningful deinterleaved nibbles before TnB BEC.

    This avoids treating unused tail/interleaver padding bits as symbol errors.
    """

    truth = [1, 4, 3, 1, 7] + payload_nibbles(payload, cfg)
    inverse = gray_inverse_map(cfg)
    values = [inverse.get(int(value) % cfg.m, 0) for value in symbol_bins]
    header_words, payload_words = deinterleave_explicit(values, cfg)
    observed: list[int] = []
    for word in header_words[:5]:
        observed.append(decode_hamming_word(int(word), 4)[0])
    for word, cr_app in payload_words[: len(truth) - 5]:
        observed.append(decode_hamming_word(int(word), int(cr_app))[0])
    if len(observed) < len(truth):
        observed.extend([-1] * (len(truth) - len(observed)))
    errors = np.asarray(observed[: len(truth)]) != np.asarray(truth)
    return {
        "pre_bec_nibble_error_count": int(np.count_nonzero(errors)),
        "pre_bec_nibble_error_rate": float(np.mean(errors)),
        "pre_bec_header_nibble_error_count": int(np.count_nonzero(errors[:5])),
        "pre_bec_payload_nibble_error_count": int(np.count_nonzero(errors[5:])),
    }


def main() -> int:
    global FIG11, FINE, REPORTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fig11-dir", type=Path, default=FIG11)
    parser.add_argument("--fine-sync-dir", type=Path, default=FINE)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    args = parser.parse_args()
    FIG11 = args.fig11_dir
    FINE = args.fine_sync_dir
    REPORTS = args.reports_dir
    intervals = read_csv(FIG11 / "fig11_real_collision_intervals.csv")
    runs = sorted({row["run"] for row in intervals})
    detector = CoRaDetector(POSTERIOR)
    records: list[dict] = []
    by_run: dict[str, list[dict]] = {}
    for run_name in runs:
        fine = load_json(FINE / f"{run_name}.json")
        report = load_json(REPORTS / f"{run_name}.json")
        cfg = RealCollisionLoRaConfig(
            sf=int(fine["spreading_factor"]),
            bw_hz=float(fine["bandwidth_hz"]),
            sample_rate_hz=float(fine["sample_rate_hz"]),
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
        run_records: list[dict] = []
        for candidate_id, (estimate, report_candidate) in enumerate(
            zip(fine["packets"], report["candidates"])
        ):
            detected = detector.detect(samples, estimate, cfg)
            phy = bec.decode(detected.symbol_bins, cfg)
            payload = truth_payload(report_candidate)
            truth_bins = encode_explicit_payload(payload, cfg) if payload else None
            combined, local, _, _ = target_mrc_input(samples, estimate, cfg)
            magnitudes = preamble_magnitudes(detector, combined, local, cfg)
            preamble_cv = (
                float(np.std(magnitudes) / max(np.mean(magnitudes), 1e-30))
                if len(magnitudes) == cfg.preamble_len
                else None
            )
            record = {
                "run": run_name,
                "candidate_id": candidate_id,
                "start_time_s": float(report_candidate["start_time_s"]),
                "status": phy.status,
                "truth_available": truth_bins is not None,
                "mean_bayes_margin": detected.mean_bayes_margin,
                "min_bayes_margin": detected.min_bayes_margin,
                "expected_peak_magnitude": detected.expected_peak_magnitude,
                "preamble_peak_cv": preamble_cv,
                "tnb_crc_attempts": int(phy.made_crc_attempts),
                "tnb_candidate_schedules": int(phy.total_candidate_schedules),
                "tnb_additionally_corrected_codewords": int(
                    phy.additionally_corrected_codewords
                ),
            }
            if truth_bins is not None and detected.symbol_bins:
                errors = np.asarray(detected.symbol_bins) != np.asarray(truth_bins)
                standard = decode_payload_from_symbol_bins(detected.symbol_bins, cfg)
                record.update(
                    {
                        "symbol_error_count": int(np.count_nonzero(errors)),
                        "symbol_error_rate": float(np.mean(errors)),
                        "header_symbol_error_count": int(np.count_nonzero(errors[:8])),
                        "payload_symbol_error_count": int(np.count_nonzero(errors[8:])),
                        "standard_phy_crc_ok": bool(standard.phy_crc_ok),
                        "tnb_only_recovery": bool(
                            phy.phy_crc_ok and not standard.phy_crc_ok
                        ),
                    }
                )
                record.update(
                    pre_bec_nibble_errors(detected.symbol_bins, payload, cfg)
                )
                features = truth_feature_metrics(
                    detector,
                    combined,
                    local,
                    cfg,
                    detected.expected_peak_magnitude,
                    truth_bins,
                )
                if features is not None:
                    record.update(features)
            run_records.append(record)
            records.append(record)
        by_run[run_name] = run_records
        print(f"CORA_FIG11_ANALYZE {run_name} candidates={len(run_records)}", flush=True)

    status = Counter(row["status"] for row in records)
    known = [row for row in records if row["truth_available"]]
    known_complete = [row for row in known if "symbol_error_rate" in row]
    success = [row for row in known_complete if row["status"] == "ok"]
    failure = [row for row in known_complete if row["status"] != "ok"]

    scene_status: dict[int, Counter] = defaultdict(Counter)
    scene_candidate_count: Counter = Counter()
    scene_truth_count: Counter = Counter()
    for interval in intervals:
        order = int(interval["collision_order"])
        run_name = interval["run"]
        fine = load_json(FINE / f"{run_name}.json")
        cfg = RealCollisionLoRaConfig(
            sf=int(fine["spreading_factor"]),
            bw_hz=float(fine["bandwidth_hz"]),
            sample_rate_hz=float(fine["sample_rate_hz"]),
        )
        frame_s = cfg.frame_samples / cfg.sample_rate_hz
        analysis_start = float(fine["window"]["analysis_start_s"])
        begin = float(interval["full_capture_start_s"]) - analysis_start
        end = float(interval["full_capture_end_s"]) - analysis_start
        selected = [
            row for row in by_run[run_name]
            if row["start_time_s"] < end and row["start_time_s"] + frame_s > begin
        ]
        scene_candidate_count[order] += len(selected)
        scene_truth_count[order] += sum(row["truth_available"] for row in selected)
        scene_status[order].update(row["status"] for row in selected)

    def field_summary(rows: list[dict], field: str) -> dict:
        return summary(
            [float(row[field]) for row in rows if row.get(field) is not None]
        )

    output = {
        "schema": "mrc_cora_fig11_failure_analysis_v1",
        "candidate_count": len(records),
        "truth_available_candidate_count": len(known),
        "status_counts": dict(status),
        "status_fractions": {
            key: value / len(records) for key, value in sorted(status.items())
        },
        "header_pass_candidate_count": (
            len(records) - status["header_bec_failed"] - status["not_enough_symbols"]
        ),
        "truth_conditioned": {
            "candidate_count": len(known_complete),
            "success_count": len(success),
            "failure_count": len(failure),
            "symbol_error_rate": field_summary(known_complete, "symbol_error_rate"),
            "pre_bec_nibble_error_rate": field_summary(
                known_complete, "pre_bec_nibble_error_rate"
            ),
            "pre_bec_nibble_error_count": field_summary(
                known_complete, "pre_bec_nibble_error_count"
            ),
            "header_symbol_error_count": field_summary(
                known_complete, "header_symbol_error_count"
            ),
            "truth_rank1_fraction": field_summary(
                known_complete, "truth_rank1_fraction"
            ),
            "truth_rank_median": field_summary(known_complete, "truth_rank_median"),
            "winner_to_truth_score_ratio_median": field_summary(
                known_complete, "winner_to_truth_score_ratio_median"
            ),
            "truth_hpd_median": field_summary(known_complete, "truth_hpd_median"),
            "winner_hpd_median": field_summary(known_complete, "winner_hpd_median"),
            "truth_pmd_median": field_summary(known_complete, "truth_pmd_median"),
            "winner_pmd_median": field_summary(known_complete, "winner_pmd_median"),
            "preamble_peak_cv": field_summary(known_complete, "preamble_peak_cv"),
            "tnb_only_recovery_count": sum(
                bool(row.get("tnb_only_recovery")) for row in known_complete
            ),
            "success": {
                "symbol_error_rate": field_summary(success, "symbol_error_rate"),
                "pre_bec_nibble_error_rate": field_summary(
                    success, "pre_bec_nibble_error_rate"
                ),
                "pre_bec_nibble_error_count": field_summary(
                    success, "pre_bec_nibble_error_count"
                ),
                "header_symbol_error_count": field_summary(
                    success, "header_symbol_error_count"
                ),
                "truth_rank1_fraction": field_summary(
                    success, "truth_rank1_fraction"
                ),
                "truth_rank_median": field_summary(success, "truth_rank_median"),
                "winner_to_truth_score_ratio_median": field_summary(
                    success, "winner_to_truth_score_ratio_median"
                ),
                "truth_hpd_median": field_summary(success, "truth_hpd_median"),
                "winner_hpd_median": field_summary(success, "winner_hpd_median"),
                "truth_pmd_median": field_summary(success, "truth_pmd_median"),
                "winner_pmd_median": field_summary(success, "winner_pmd_median"),
                "preamble_peak_cv": field_summary(success, "preamble_peak_cv"),
                "mean_bayes_margin": field_summary(success, "mean_bayes_margin"),
            },
            "failure": {
                "symbol_error_rate": field_summary(failure, "symbol_error_rate"),
                "pre_bec_nibble_error_rate": field_summary(
                    failure, "pre_bec_nibble_error_rate"
                ),
                "pre_bec_nibble_error_count": field_summary(
                    failure, "pre_bec_nibble_error_count"
                ),
                "header_symbol_error_count": field_summary(
                    failure, "header_symbol_error_count"
                ),
                "truth_rank1_fraction": field_summary(
                    failure, "truth_rank1_fraction"
                ),
                "truth_rank_median": field_summary(failure, "truth_rank_median"),
                "winner_to_truth_score_ratio_median": field_summary(
                    failure, "winner_to_truth_score_ratio_median"
                ),
                "truth_hpd_median": field_summary(failure, "truth_hpd_median"),
                "winner_hpd_median": field_summary(failure, "winner_hpd_median"),
                "truth_pmd_median": field_summary(failure, "truth_pmd_median"),
                "winner_pmd_median": field_summary(failure, "winner_pmd_median"),
                "preamble_peak_cv": field_summary(failure, "preamble_peak_cv"),
                "mean_bayes_margin": field_summary(failure, "mean_bayes_margin"),
            },
        },
        "scene_weighted_by_collision_order": {
            str(order): {
                "candidate_attempt_count": scene_candidate_count[order],
                "truth_available_attempt_count": scene_truth_count[order],
                "status_counts": dict(scene_status[order]),
                "status_fractions": {
                    key: value / scene_candidate_count[order]
                    for key, value in sorted(scene_status[order].items())
                },
            }
            for order in ORDERS
        },
        "model_domain": {
            "published_training_fft_bins": 256,
            "fig11_fft_bins": 1024,
            "published_training_max_interferers": 2,
            "fig11_collision_orders": list(ORDERS),
            "source": "upstream/cora_v2/artifacts/python/models/gen_dist.py",
        },
        "records": records,
    }
    output_path = FIG11 / "mrc_cora_fig11_failure_analysis.json"
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"CORA_FIG11_ANALYSIS_DONE out={output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
