#!/usr/bin/env python3

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from formal_window import FORMAL_ANALYSIS_DURATION_S
from plot_fig9_10_12_from_reports import (
    aggregate,
    collect,
    method_decoder_work_s,
    plot_metric,
)


class Fig912PlotMetricsTest(unittest.TestCase):
    def write_fixture(
        self,
        directory: Path,
        *,
        denominator_source: str,
        detected_count: int = 3,
        decoded_count: int = 3,
        reported_prr: float = 1.0,
        decoder_work_ms: tuple[float, ...] | None = None,
    ) -> argparse.Namespace:
        runs = directory / "runs"
        reports = directory / "reports"
        manifests = runs / "manifests"
        manifests.mkdir(parents=True)
        reports.mkdir()
        run_name = "run_0203c111"
        manifest = {
            "experiment": {
                "figure": "fig12",
                "round": "1",
                "per_node_duty_cycle": "0.75",
                "node_separation_label": "2cm",
                "node_separation_m": "0.02",
            },
            "config": {"run_id": 0x0203C111},
            "active_node_count": 2,
            "radio": {"bandwidth_hz": 250000},
            "traffic": {
                "packet_airtime_ms": 185.344,
                "data_payload_bytes": 20,
            },
            "expected_node_schedules": {
                "1": {"tx_start_ms_from_traffic_begin": [8000, 10000, 12000]},
                "2": {"tx_start_ms_from_traffic_begin": [9000, 11000]},
            },
        }
        timing_values = (
            decoder_work_ms
            if decoder_work_ms is not None
            else (100.0,) * detected_count
        )
        report = {
            "input": {
                "analysis_slice": {
                    "start_time_s": 27.5,
                    "requested_duration_s": FORMAL_ANALYSIS_DURATION_S,
                },
                "strict_middle_business_window": {
                    "enabled": True,
                    "traffic_start_s_from_full_iq": 20.0,
                    "analysis_start_s_from_full_iq": 27.5,
                    "analysis_duration_s": FORMAL_ANALYSIS_DURATION_S,
                },
                "fine_sync_database": {
                    "schema": "fine_sync_anonymous_physical_v2",
                    "candidate_discovery": {
                        "scope": "global_full_window",
                        "manifest_schedule_exposed_to_detector": False,
                        "node_timing_calibration": False,
                        "planned_start_search_windows": False,
                        "score_truncation": False,
                    },
                },
            },
            "detection_and_decode": {
                "by_method": {
                    "lorawan": {
                        "complete_detected_packet_count": detected_count,
                        "decoded_success_count": decoded_count,
                        "prr_denominator_packet_count": min(5, detected_count),
                        "prr": reported_prr,
                        "manifest_expected_packet_count_in_analysis_window": 5,
                        "prr_detected_physical_packet_count": detected_count,
                        "prr_denominator_source": denominator_source,
                        "prr_counting_policy": (
                            "unique_crc_valid_payload_identities_over_"
                            "min_manifest_window_expected_or_anonymous_detected_packets"
                        ),
                    }
                }
            },
            "candidates": [
                {
                    "methods": [
                        {
                            "method": "lorawan",
                            "post_sp_total_elapsed_ms": elapsed_ms,
                        }
                    ]
                }
                for elapsed_ms in timing_values
            ],
        }
        (manifests / f"{run_name}.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (reports / f"{run_name}.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        return argparse.Namespace(
            runs=runs,
            reports=reports,
            window_duration_s=FORMAL_ANALYSIS_DURATION_S,
        )

    def test_fig12_tps_uses_total_decoder_latency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary),
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                decoder_work_ms=(200.0, 300.0, 500.0),
            )
            rows, notes = collect(args)

        self.assertFalse(any("stale PRR semantics" in note for note in notes))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["complete_candidates"], 3)
        self.assertEqual(row["decoded_successes"], 3)
        self.assertEqual(row["prr_denominator_packets"], 3)
        self.assertAlmostEqual(row["conditional_prr"], 1.0)
        self.assertEqual(row["detected_in_slice"], 3)
        self.assertAlmostEqual(row["radio_window_tps"], 480.0)
        self.assertAlmostEqual(row["radio_window_goodput_kbps"], 0.48)
        self.assertEqual(row["decoder_work_s"], 1.0)
        self.assertAlmostEqual(row["effective_tps"], 480.0)

    def test_effective_tps_uses_decoder_latency_even_when_faster_than_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary),
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                decoder_work_ms=(200.0, 300.0, 400.0),
            )
            rows, notes = collect(args)

        self.assertFalse(any("inconsistent" in note for note in notes))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertAlmostEqual(row["decoder_work_s"], 0.9)
        self.assertAlmostEqual(row["decoder_work_realtime_factor"], 0.18)
        self.assertAlmostEqual(row["effective_tps"], 3 * 160 / 0.9)
        self.assertAlmostEqual(row["effective_goodput_kbps"], 3 * 160 / 900.0)

    def test_sp_decoder_work_does_not_double_count_batch_lambda_configuration(self) -> None:
        report = {
            "candidates": [
                {
                    "methods": [
                        {
                            "method": "sp_sync_refine",
                            "post_sp_total_elapsed_ms": 100.0,
                        }
                    ]
                },
                {
                    "methods": [
                        {
                            "method": "sp_sync_refine",
                            "post_sp_total_elapsed_ms": 200.0,
                        }
                    ]
                },
            ],
            "decoder": {"sp_lambda_configuration": {"batch_elapsed_ms": 700.0}},
        }

        self.assertAlmostEqual(method_decoder_work_s(report, "sp_sync_refine"), 0.3)

    def test_fig12_rejects_legacy_conditional_prr_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary), denominator_source="complete_detected_packets"
            )
            rows, notes = collect(args)

        self.assertEqual(rows, [])
        self.assertTrue(any("stale PRR semantics" in note for note in notes))

    def test_fig12_rejects_an_inconsistent_min_denominator_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary),
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                reported_prr=0.5,
            )
            rows, notes = collect(args)

        self.assertEqual(rows, [])
        self.assertTrue(any("inconsistent min(planned, detected) PRR" in note for note in notes))

    def test_fig12_uses_detected_count_when_planned_exceeds_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary),
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                detected_count=2,
                decoded_count=2,
            )
            rows, notes = collect(args)

        self.assertFalse(any("inconsistent" in note for note in notes))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prr_denominator_packets"], 2)
        self.assertAlmostEqual(rows[0]["conditional_prr"], 1.0)

    def test_fig12_uses_planned_count_when_detected_exceeds_planned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary),
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                detected_count=7,
                decoded_count=5,
            )
            rows, notes = collect(args)

        self.assertFalse(any("inconsistent" in note for note in notes))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prr_denominator_packets"], 5)
        self.assertAlmostEqual(rows[0]["conditional_prr"], 1.0)

    def test_aggregate_preserves_window_duration_for_plotting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            args = self.write_fixture(
                directory,
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
            )
            rows, _ = collect(args)
            aggregate_rows = aggregate(rows)
            self.assertEqual(
                aggregate_rows[0]["window_duration_s"], FORMAL_ANALYSIS_DURATION_S
            )

            output_stem = directory / "fig12_preview"
            plot_metric(
                aggregate_rows,
                figure="fig12",
                metric="conditional_prr_mean",
                ci_metric="conditional_prr_ci95",
                ylabel="PRR",
                output_stem=output_stem,
            )
            self.assertTrue(output_stem.with_suffix(".png").exists())


if __name__ == "__main__":
    unittest.main()
