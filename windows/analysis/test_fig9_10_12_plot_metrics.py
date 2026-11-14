#!/usr/bin/env python3

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from plot_fig9_10_12_from_reports import collect


class Fig912PlotMetricsTest(unittest.TestCase):
    def write_fixture(
        self,
        directory: Path,
        *,
        denominator_source: str,
        detected_count: int = 3,
        decoded_count: int = 3,
        reported_prr: float = 1.0,
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
                "1": {"tx_start_ms_from_traffic_begin": [6000, 8000, 10000]},
                "2": {"tx_start_ms_from_traffic_begin": [7000, 9000]},
            },
        }
        report = {
            "input": {
                "analysis_slice": {
                    "start_time_s": 27.5,
                    "requested_duration_s": 5.0,
                },
                "strict_middle_business_window": {
                    "enabled": True,
                    "traffic_start_s_from_full_iq": 20.0,
                    "analysis_start_s_from_full_iq": 27.5,
                    "analysis_duration_s": 5.0,
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
                        "prr_denominator_packet_count": min(3, detected_count),
                        "prr": reported_prr,
                        "manifest_expected_packet_count_in_analysis_window": 3,
                        "prr_detected_physical_packet_count": detected_count,
                        "prr_denominator_source": denominator_source,
                        "prr_counting_policy": (
                            "unique_crc_valid_payload_identities_over_"
                            "min_manifest_window_expected_or_anonymous_detected_packets"
                        ),
                    }
                }
            },
        }
        (manifests / f"{run_name}.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (reports / f"{run_name}.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        return argparse.Namespace(runs=runs, reports=reports, window_duration_s=5.0)

    def test_fig12_uses_min_planned_or_detected_prr_and_five_second_goodput(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = self.write_fixture(
                Path(temporary),
                denominator_source=(
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
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
        self.assertAlmostEqual(row["window_tps"], 96.0)
        self.assertAlmostEqual(row["payload_goodput_kbps"], 0.096)

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
                detected_count=5,
                decoded_count=3,
            )
            rows, notes = collect(args)

        self.assertFalse(any("inconsistent" in note for note in notes))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prr_denominator_packets"], 3)
        self.assertAlmostEqual(rows[0]["conditional_prr"], 1.0)


if __name__ == "__main__":
    unittest.main()
