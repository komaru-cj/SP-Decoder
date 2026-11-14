#!/usr/bin/env python3

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIVER = ROOT / "real_collision_experiment" / "node01_sp_receiver"
if str(RECEIVER) not in sys.path:
    sys.path.insert(0, str(RECEIVER))

from build_outdoor_fig13_fig14_fig15_database import collect_fig14, plot_fig14
from run_fig14_snr_sweep import snr_bin


class Fig14SnrBinsTest(unittest.TestCase):
    def test_snr_bin_boundaries(self) -> None:
        self.assertEqual(snr_bin(-30.1)[0], "lt_m30")
        self.assertEqual(snr_bin(-30.0)[0], "m30_to_m10")
        self.assertEqual(snr_bin(-10.0)[0], "m10_to_10")
        self.assertEqual(snr_bin(10.0)[0], "ge_10")

    def test_v7_rows_are_ordered_and_rendered_as_bars(self) -> None:
        bins = (
            ("lt_m30", "<-30 dB"),
            ("m30_to_m10", "[-30,-10) dB"),
            ("m10_to_10", "[-10,10) dB"),
            ("ge_10", ">=10 dB"),
        )
        aggregate = [
            {
                "snr_bin_key": key,
                "snr_bin_label": label,
                "method": "mrc",
                "source_point_count": 1,
                "manifest_expected_packet_count_in_analysis_window": 3,
                "detected_packet_count": 3,
                "decoded_success_count": 2,
                "prr_denominator_packet_count": 3,
                "conditional_prr": 2.0 / 3.0,
                "prr_denominator_source": (
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                "prr_counting_policy": (
                    "unique_crc_valid_payload_identities_over_"
                    "min_manifest_window_expected_or_anonymous_detected_packets"
                ),
                "median_measured_snr_db": 0.0,
            }
            for key, label in bins
        ]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report = directory / "fig14_snr_bins.json"
            report.write_text(
                json.dumps(
                    {"schema": "fig14_outdoor_awgn_snr_bins_v7", "aggregate": aggregate}
                ),
                encoding="utf-8",
            )
            rows = collect_fig14(report, [])
            self.assertEqual([row["snr_bin_order"] for row in rows], [0, 1, 2, 3])
            plot_fig14(rows, directory / "fig14_prr_by_snr")
            self.assertTrue((directory / "fig14_prr_by_snr.png").exists())
            self.assertTrue((directory / "fig14_prr_by_snr.pdf").exists())


if __name__ == "__main__":
    unittest.main()
