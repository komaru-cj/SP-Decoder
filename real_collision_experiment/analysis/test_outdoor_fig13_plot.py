#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from build_outdoor_fig13_fig14_fig15_database import (
    method_decoder_work_s,
    plot_fig13,
)


class OutdoorFig13PlotTest(unittest.TestCase):
    def test_renders_separate_sf8_and_sf10_prr_tps_figures(self) -> None:
        rows = [
            {
                "sf": spreading_factor,
                "node_count": node_count,
                "method": "sp_sync_refine",
                "prr": 0.5,
                "effective_tps_bps": 100.0,
            }
            for spreading_factor in (8, 10)
            for node_count in (3, 6)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            plot_fig13(rows, output_dir)
            for stem in (
                "fig13_sf8_prr",
                "fig13_sf10_prr",
                "fig13_sf8_tps",
                "fig13_sf10_tps",
            ):
                self.assertTrue((output_dir / f"{stem}.png").exists())
                self.assertTrue((output_dir / f"{stem}.pdf").exists())

    def test_sp_decoder_work_does_not_double_count_batch_timing(self) -> None:
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

        self.assertAlmostEqual(
            method_decoder_work_s(report, "sp_sync_refine", "run_test", 2), 0.3
        )


if __name__ == "__main__":
    unittest.main()
