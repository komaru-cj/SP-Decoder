from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECEIVER = Path(__file__).resolve().parent
CONTROL = ROOT / "real_collision_experiment" / "control_usrp"
for path in (ROOT, RECEIVER, CONTROL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sp_node01_receiver import (  # noqa: E402
    DECODER_METHODS,
    build_parser,
    detection_decode_statistics,
)


class DetectionDecodeStatisticsTests(unittest.TestCase):
    def test_formal_default_shares_sp_fine_sync(self) -> None:
        args = build_parser().parse_args(["--iq", "capture.sc16", "--out", "report.json"])
        self.assertEqual(args.comparison_frontend_scope, "common")
        self.assertTrue(args.comparison_paper_local_refinement)

    def test_paper_local_refinement_can_be_disabled_for_reproducibility(self) -> None:
        args = build_parser().parse_args(
            [
                "--iq",
                "capture.sc16",
                "--out",
                "report.json",
                "--no-comparison-paper-local-refinement",
            ]
        )
        self.assertFalse(args.comparison_paper_local_refinement)

    def test_skipped_comparison_decoders_are_null_not_zero(self) -> None:
        executed = set(DECODER_METHODS) - {"mrc_cic", "pcube", "maloragw"}
        stats = detection_decode_statistics(
            run_cfg=None,
            manifest={},
            active_nodes={1, 2},
            energy_diag={"events": [], "ranges": []},
            candidates=[
                {
                    "candidate_id": 0,
                    "start_sample": 100.0,
                    "methods": [],
                }
            ],
            complete_burst_threshold_s=0.1,
            business_duration_s=10.0,
            capture_sample_count=10_000,
            frame_sample_count=1_000,
            packet_alias_time_tolerance_samples=10.0,
            executed_methods=executed,
        )
        cic = stats["by_method"]["mrc_cic"]
        self.assertEqual(cic["execution_status"], "not_run")
        self.assertIsNone(cic["decoded_success_count"])
        self.assertIsNone(cic["prr"])

    def test_anonymous_fine_sync_prr_deduplicates_crc_valid_payload_identities(self) -> None:
        stats = detection_decode_statistics(
            run_cfg=None,
            manifest={},
            active_nodes={1, 2},
            energy_diag={"events": [], "ranges": []},
            candidates=[
                {
                    "candidate_id": 0,
                    "start_sample": 100.0,
                    "methods": [
                        {
                            "method": "sp",
                            "application": {
                                "app_crc_ok": True,
                                "decoded": {"node_id": 1, "sequence": 0},
                            },
                        }
                    ],
                },
                {
                    "candidate_id": 1,
                    "start_sample": 2_000.0,
                    "methods": [
                        {
                            "method": "sp",
                            "application": {
                                "app_crc_ok": True,
                                # The two candidates decode the same payload;
                                # PRR counts that payload only once.
                                "decoded": {"node_id": 1, "sequence": 0},
                            },
                        }
                    ],
                },
            ],
            complete_burst_threshold_s=0.1,
            business_duration_s=10.0,
            capture_sample_count=10_000,
            frame_sample_count=1_000,
            packet_alias_time_tolerance_samples=10.0,
            fine_sync_candidate_count=2,
            expected_sequences_by_node={1: [0, 1], 2: [0]},
        )

        sp = stats["by_method"]["sp"]
        self.assertEqual(sp["complete_detected_packet_count"], 2)
        self.assertEqual(sp["decoded_success_count"], 1)
        self.assertEqual(sp["prr_denominator_packet_count"], 2)
        self.assertEqual(
            sp["prr_denominator_source"],
            "min_manifest_window_expected_or_anonymous_detected_packets",
        )
        self.assertEqual(
            sp["prr_counting_policy"],
            "unique_crc_valid_payload_identities_over_"
            "min_manifest_window_expected_or_anonymous_detected_packets",
        )
        self.assertEqual(sp["manifest_expected_packet_count_in_analysis_window"], 3)
        self.assertEqual(sp["prr_detected_physical_packet_count"], 2)
        self.assertAlmostEqual(sp["prr"], 0.5)
        self.assertAlmostEqual(sp["decoded_success_tps"], 16.0)
        self.assertAlmostEqual(sp["payload_goodput_kbps"], 0.016)

    def test_anonymous_fine_sync_prr_uses_planned_count_when_detection_is_higher(self) -> None:
        candidates = [
            {
                "candidate_id": candidate_id,
                "start_sample": float(candidate_id * 2_000),
                "methods": [
                    {
                        "method": "sp",
                        "application": {
                            "app_crc_ok": True,
                            "decoded": {
                                "node_id": 1,
                                "sequence": min(candidate_id, 2),
                            },
                        },
                    }
                ],
            }
            for candidate_id in range(5)
        ]
        stats = detection_decode_statistics(
            run_cfg=None,
            manifest={},
            active_nodes={1},
            energy_diag={"events": [], "ranges": []},
            candidates=candidates,
            complete_burst_threshold_s=0.1,
            business_duration_s=5.0,
            capture_sample_count=20_000,
            frame_sample_count=1_000,
            packet_alias_time_tolerance_samples=10.0,
            fine_sync_candidate_count=5,
            expected_sequences_by_node={1: [0, 1, 2]},
        )

        sp = stats["by_method"]["sp"]
        self.assertEqual(sp["decoded_success_count"], 3)
        self.assertEqual(sp["manifest_expected_packet_count_in_analysis_window"], 3)
        self.assertEqual(sp["prr_detected_physical_packet_count"], 5)
        self.assertEqual(sp["prr_denominator_packet_count"], 3)
        self.assertAlmostEqual(sp["prr"], 1.0)

    def test_detected_packet_prr_credits_rejected_crc_valid_payload(self) -> None:
        stats = detection_decode_statistics(
            run_cfg=None,
            manifest={},
            active_nodes={1, 2},
            energy_diag={"events": [], "ranges": []},
            candidates=[
                {
                    "candidate_id": 0,
                    "start_sample": 100.0,
                    "methods": [
                        {
                            "method": "sp",
                            "application": {
                                "app_crc_ok": True,
                                "decoded": {"node_id": 1, "sequence": 0},
                            },
                        }
                    ],
                },
                {
                    "candidate_id": 1,
                    "start_sample": 2_000.0,
                    "methods": [
                        {
                            "method": "sp",
                            "application": {
                                "app_crc_ok": False,
                                "decoded": {"node_id": 3, "sequence": 0},
                            },
                        }
                    ],
                },
            ],
            complete_burst_threshold_s=0.1,
            business_duration_s=10.0,
            capture_sample_count=10_000,
            frame_sample_count=1_000,
            packet_alias_time_tolerance_samples=10.0,
        )

        sp = stats["by_method"]["sp"]
        self.assertEqual(sp["complete_detected_packet_count"], 2)
        self.assertEqual(sp["identity_matched_success_count"], 1)
        self.assertEqual(sp["identity_mismatch_count"], 1)
        self.assertEqual(sp["decoded_success_count"], 2)
        self.assertEqual(sp["prr_denominator_packet_count"], 3)
        self.assertAlmostEqual(sp["prr"], 2.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
