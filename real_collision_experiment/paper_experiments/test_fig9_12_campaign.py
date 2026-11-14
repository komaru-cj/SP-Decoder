#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from plan_fig9_12_campaign import (
    DEFAULT_SCALE_DUTY_CYCLES,
    build_campaign,
    build_parser,
    powershell_text,
    run_config,
    validate_args,
    write_outputs,
)
from protocol import expected_tx_schedule_ms, firmware_mean_idle_gap_ms


class FigCampaignTest(unittest.TestCase):
    def args(self):
        args = build_parser().parse_args(["--out-dir", "/tmp/unused"])
        args.fig11_seed_search_count = 12
        return args

    def test_default_matrix_is_valid_and_unique(self) -> None:
        args = self.args()
        validate_args(args)
        runs = build_campaign(args)
        self.assertEqual(len(runs), 15)
        self.assertEqual(len({run.run_id for run in runs}), 15)
        self.assertEqual(sum(run.phase == "scale" for run in runs), 10)
        self.assertEqual(sum(run.phase == "runtime_source" for run in runs), 0)
        self.assertEqual(sum(run.phase == "proximity_calibration" for run in runs), 0)
        self.assertEqual(sum(run.phase == "proximity_collision" for run in runs), 5)
        scale_duties = {
            run.per_node_duty_cycle for run in runs if run.phase == "scale"
        }
        self.assertEqual(scale_duties, set(DEFAULT_SCALE_DUTY_CYCLES))
        fig12_duties = {
            run.per_node_duty_cycle
            for run in runs
            if run.phase == "proximity_collision"
        }
        self.assertEqual(fig12_duties, {0.75})
        for run in runs:
            self.assertEqual(run.node_tx_power_dbm, 16)
            self.assertEqual(run.firmware_active_node_count, len(run.active_nodes))
            run_config(run).validate()
            self.assertGreater(run.expected_tx_count, 0)
            self.assertGreater(run.recommended_capture_s, run.duration_s)

    def test_fixed_duty_has_fixed_per_node_rate(self) -> None:
        runs = [
            run
            for run in build_campaign(self.args())
            if run.phase == "scale"
            and run.per_node_duty_cycle == DEFAULT_SCALE_DUTY_CYCLES[0]
            and run.round_index == 1
        ]
        gaps = [
            firmware_mean_idle_gap_ms(run_config(run))
            for run in sorted(runs, key=lambda row: len(row.active_nodes))
        ]
        self.assertEqual(len(gaps), 5)
        self.assertEqual(len(set(gaps)), 1)

    def test_requested_one_round_high_duty_campaign(self) -> None:
        args = self.args()
        args.rounds = 1
        args.scale_duty_cycles = (0.5, 0.75)
        args.fig12_duty_cycle = 0.75
        args.fig12_rounds = 1
        validate_args(args)
        runs = build_campaign(args)
        scale = [run for run in runs if run.phase == "scale"]
        proximity = [run for run in runs if run.phase == "proximity_collision"]
        self.assertEqual(len(scale), 10)
        self.assertEqual(len(proximity), 5)
        self.assertEqual({run.per_node_duty_cycle for run in scale}, {0.5, 0.75})
        self.assertEqual({run.per_node_duty_cycle for run in proximity}, {0.75})
        self.assertEqual(
            {(len(run.active_nodes), run.per_node_duty_cycle) for run in scale},
            {(nodes, duty) for nodes in (3, 6, 9, 12, 15) for duty in (0.5, 0.75)},
        )

    def test_dual_bandwidth_scale_campaign_is_unique(self) -> None:
        args = self.args()
        args.scale_phy_profile_ids = (2, 5)
        args.scale_duty_cycles = (0.25,)
        args.fig12_rounds = 0
        args.run_id_revision = 3
        validate_args(args)
        runs = build_campaign(args)
        self.assertEqual(len(runs), 10)
        self.assertEqual(len({run.run_id for run in runs}), 10)
        self.assertEqual([run.phy_profile_id for run in runs], [2] * 5 + [5] * 5)
        self.assertEqual([run.spreading_factor for run in runs], [10] * 10)
        self.assertEqual(
            [run.bandwidth_hz for run in runs], [125_000] * 5 + [250_000] * 5
        )
        self.assertEqual([len(run.active_nodes) for run in runs], [15, 3, 6, 9, 12, 3, 6, 9, 12, 15])

    def test_scale_loads_grow_with_n_but_per_node_rate_stays_fixed(self) -> None:
        runs = [run for run in build_campaign(self.args()) if run.phase == "scale"]
        for duty in DEFAULT_SCALE_DUTY_CYCLES:
            round_one = sorted(
                (
                    run
                    for run in runs
                    if run.per_node_duty_cycle == duty and run.round_index == 1
                ),
                key=lambda run: len(run.active_nodes),
            )
            self.assertEqual(
                [run.offered_load for run in round_one],
                [round(nodes * duty, 12) for nodes in (3, 6, 9, 12, 15)],
            )
            self.assertEqual(
                len({firmware_mean_idle_gap_ms(run_config(run)) for run in round_one}),
                1,
            )

    def test_first_run_gives_every_node_an_early_gate_packet(self) -> None:
        first = build_campaign(self.args())[0]
        config = run_config(first)
        first_starts_s = {
            node: expected_tx_schedule_ms(config, node)[0] / 1000.0
            for node in first.active_nodes
        }
        self.assertEqual(set(first_starts_s), set(range(1, 16)))
        self.assertLess(max(first_starts_s.values()), 20.0)

    def test_outputs_include_real_and_dry_run_powershell(self) -> None:
        args = self.args()
        runs = build_campaign(args)
        with tempfile.TemporaryDirectory() as directory:
            args.out_dir = Path(directory)
            write_outputs(runs, args)
            real = (args.out_dir / "run_campaign.ps1").read_text(encoding="utf-8")
            dry = (args.out_dir / "dry_run_campaign.ps1").read_text(encoding="utf-8")
            self.assertIn("Read-Host", real)
            self.assertNotIn("--dry-run", real)
            self.assertIn("--dry-run", dry)
            self.assertNotIn("Read-Host", dry)
            self.assertTrue((args.out_dir / "campaign.json").exists())
            self.assertTrue((args.out_dir / "report_index_template.csv").exists())

    def test_powershell_contains_manifest_tags(self) -> None:
        args = self.args()
        run = build_campaign(args)[0]
        text = powershell_text([run], args, dry_run=True)
        self.assertIn("--experiment-tag 'figure=fig9_10'", text)
        self.assertNotIn("--traffic-reference-nodes", text)
        self.assertIn("--node-tx-power 16", text)
        self.assertIn("--phy-profile-id 5", text)
        self.assertIn("--per-node-duty-cycle 0.5", text)
        self.assertIn("ssh $Controller $RemoteCommand", text)


if __name__ == "__main__":
    unittest.main()
