#!/usr/bin/env python3

import unittest

from build_fig11_real_run_intervals import aggregate


class Fig11PrrTest(unittest.TestCase):
    def test_prr_uses_minimum_of_planned_and_anonymous_detected_packets(self) -> None:
        rows = [
            {
                "collision_order": 4,
                "method": "lorawan",
                "ser": 0.5,
                "decoded_packet_count": 2,
                "planned_packet_count": 4,
                "fine_sync_detected_packet_count": 2,
                "prr_denominator_packet_count": 2,
                "post_sp_time_ms": 1.0,
            },
            {
                "collision_order": 4,
                "method": "lorawan",
                "ser": 0.75,
                "decoded_packet_count": 1,
                "planned_packet_count": 4,
                "fine_sync_detected_packet_count": 4,
                "prr_denominator_packet_count": 4,
                "post_sp_time_ms": 2.0,
            },
        ]

        [summary] = aggregate(rows, (4,), seed=1)

        self.assertEqual(summary["decoded_packet_count"], 3)
        self.assertEqual(summary["fine_sync_detected_packet_count"], 6)
        self.assertEqual(summary["manifest_expected_packet_count_in_collision_scenes"], 8)
        self.assertEqual(summary["prr_denominator_packet_count"], 6)
        self.assertAlmostEqual(summary["prr_mean"], 3.0 / 6.0)
        self.assertEqual(
            summary["prr_denominator_source"],
            "min_manifest_collision_scene_expected_or_anonymous_detected_packets",
        )

    def test_prr_uses_only_fine_sync_packets_from_a_planned_scene(self) -> None:
        rows = [
            {
                "collision_order": 8,
                "method": "sp_sync_refine",
                "ser": 0.25,
                "decoded_packet_count": 3,
                "planned_packet_count": 8,
                "fine_sync_detected_packet_count": 3,
                "prr_denominator_packet_count": 3,
                "post_sp_time_ms": 4.0,
            }
        ]

        [summary] = aggregate(rows, (8,), seed=1)

        self.assertEqual(summary["fine_sync_detected_packet_count"], 3)
        self.assertEqual(summary["decoded_packet_count"], 3)
        self.assertEqual(summary["prr_denominator_packet_count"], 3)
        self.assertAlmostEqual(summary["prr_mean"], 1.0)


if __name__ == "__main__":
    unittest.main()
