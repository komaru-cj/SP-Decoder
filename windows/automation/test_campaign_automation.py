#!/usr/bin/env python3

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from campaign_common import load_campaign
from controller_campaign_client import controller_command
from offline_controller_campaign import offline_controller_command
from offline_receiver_campaign import build_parser as build_offline_rx_parser
from offline_receiver_campaign import required_capture_bytes
from offline_schedule import build_schedule
from receiver_campaign_server import (
    capture_command,
    decoder_command,
    formal_candidate_budgets,
    recover_middle_window_partial_capture,
    validate_capture,
)


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = (
    ROOT
    / "real_collision_experiment/paper_experiments/generated/fig9_10_fig12_phy5_d05_d075_r1_20s/campaign.json"
)
FIG9_D025_DUAL_BW_CAMPAIGN = (
    ROOT
    / "real_collision_experiment/paper_experiments/generated/fig9_10_sf10_bw125_bw250_d025_r3_20s/campaign.json"
)
FIG13_FIG15_OUTDOOR_CAMPAIGN = (
    ROOT
    / "real_collision_experiment/paper_experiments/generated/fig13_fig15_outdoor_sf8_sf10_sf12_bw250_d025_r6_20s/campaign.json"
)


class CampaignAutomationTest(unittest.TestCase):
    def test_outdoor_fig15_uses_node02_baseline_and_75_percent_duty(self) -> None:
        _, runs, _ = load_campaign(
            FIG13_FIG15_OUTDOOR_CAMPAIGN, start_sequence=16, end_sequence=29
        )
        distances = [20.0, 40.0, 60.0, 80.0, 100.0, 150.0, 200.0]
        self.assertEqual(len(runs), 14)
        self.assertEqual(
            [run["tags"]["node_b_distance_m"] for run in runs],
            [f"{distance:g}" for distance in distances for _ in range(2)],
        )
        self.assertEqual(
            [run["tags"]["mode"] for run in runs],
            [mode for _ in distances for mode in ("ab_simultaneous", "b_only")],
        )
        self.assertEqual(
            [run["active_nodes"] for run in runs],
            [nodes for _ in distances for nodes in ([1, 2], [2])],
        )
        self.assertEqual([run["per_node_duty_cycle"] for run in runs], [0.75] * 14)
        self.assertEqual(
            [run["offered_load"] for run in runs],
            [load for _ in distances for load in (1.5, 0.75)],
        )

        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(
                python_executable="python",
                repo_root=ROOT,
                manifest_dir=Path(directory),
                control_tx_gain=60.0,
                pre_config_delay_s=5.0,
            )
            simultaneous = " ".join(offline_controller_command(args, runs[0]))
            b_only = " ".join(offline_controller_command(args, runs[1]))
        self.assertIn("--active-nodes 1,2", simultaneous)
        self.assertIn("--active-nodes 2", b_only)
        self.assertIn("--per-node-duty-cycle 0.75", simultaneous)
        self.assertIn("--per-node-duty-cycle 0.75", b_only)

    def test_offline_capture_guard_is_applied_once(self) -> None:
        _, runs, _ = load_campaign(
            FIG13_FIG15_OUTDOOR_CAMPAIGN, start_sequence=1, end_sequence=1
        )
        args = argparse.Namespace(
            python_executable="python3",
            repo_root=ROOT,
            runs_root=ROOT / "real_collision_experiment/runs_outdoor",
            sample_rate=750_000.0,
            rx_gain=20.0,
            capture_guard_s=5.0,
            campaign_id="fig13_fig15_outdoor_sf8_sf10_sf12_bw250_d025_r6_20s",
        )
        command, _ = capture_command(args, runs[0])
        self.assertEqual(command[command.index("--duration") + 1], "55")

        final_bytes, merge_extra = required_capture_bytes(
            runs, sample_rate=750_000.0, capture_guard_s=5.0
        )
        expected_bytes = round(55.0 * 750_000.0 * 8)
        self.assertEqual(final_bytes, expected_bytes)
        self.assertEqual(merge_extra, expected_bytes)

    def test_fig9_d025_dual_bandwidth_campaign_and_entry_scripts_are_aligned(self) -> None:
        _, runs, _ = load_campaign(
            FIG9_D025_DUAL_BW_CAMPAIGN, start_sequence=1, end_sequence=10
        )
        self.assertEqual([run["sequence"] for run in runs], list(range(1, 11)))
        self.assertEqual(
            [len(run["active_nodes"]) for run in runs],
            [15, 3, 6, 9, 12, 3, 6, 9, 12, 15],
        )
        self.assertEqual(
            [run["per_node_duty_cycle"] for run in runs], [0.25] * 10
        )
        self.assertEqual([run["phy_profile_id"] for run in runs], [2] * 5 + [5] * 5)
        self.assertEqual([run["bandwidth_hz"] for run in runs], [125_000] * 5 + [250_000] * 5)
        self.assertEqual(runs[0]["run_id_hex"], "0x0F012131")

        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(
                python_executable="python",
                repo_root=ROOT,
                manifest_dir=Path(directory),
                control_tx_gain=60.0,
                pre_config_delay_s=5.0,
            )
            rendered = " ".join(offline_controller_command(args, runs[0]))
        self.assertIn("--phy-profile-id 2", rendered)
        self.assertIn("--per-node-duty-cycle 0.25", rendered)
        self.assertIn("--node-tx-power 16", rendered)
        self.assertIn("--usrp-tx-gain 60", rendered)

        expected_campaign_fragment = "fig9_10_sf10_bw125_bw250_d025_r3_20s"
        for relative in (
            "start_offline_rx_preflight.sh",
            "start_offline_rx_fig9_10.sh",
            "start_offline_control_preflight.ps1",
            "start_offline_control_fig9_10.ps1",
        ):
            text = (ROOT / "real_collision_experiment/automation" / relative).read_text(
                encoding="utf-8"
            )
            self.assertIn(expected_campaign_fragment, text)
        rx_fig9 = (
            ROOT / "real_collision_experiment/automation/start_offline_rx_fig9_10.sh"
        ).read_text(encoding="utf-8")
        control_fig9 = (
            ROOT
            / "real_collision_experiment/automation/start_offline_control_fig9_10.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("--end-sequence 10", rx_fig9)
        self.assertIn("--end-sequence 10", control_fig9)
        self.assertIn("--slot-s 100", rx_fig9)
        self.assertIn("--slot-s 100", control_fig9)

    def test_one_time_gate_skips_control_and_warmup(self) -> None:
        args = build_offline_rx_parser().parse_args(["--campaign", str(CAMPAIGN)])
        self.assertIsNone(args.gate_capture_start_seconds)
        self.assertEqual(args.gate_capture_seconds, 3.0)

    def test_partial_capture_is_usable_when_target_middle_three_seconds_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iq = root / "run.sc16"
            partial = root / "run.partial.sc16"
            metadata_path = iq.with_suffix(iq.suffix + ".json")
            rate = 10.0
            target = 100
            available = 80
            partial.write_bytes(b"\0" * (available * 8))
            metadata_path.write_text(
                json.dumps(
                    {
                        "status": "incomplete",
                        "target_samples_per_channel": target,
                        "samples_per_channel": available,
                        "channel_temp_files": [],
                        "requested": {"sample_rate_hz": rate},
                        "actual": {"rate_hz": rate},
                        "fatal_error": "test stall",
                        "recovery": {
                            "partial_output_file": str(partial),
                            "partial_samples_per_channel": available,
                        },
                    }
                ),
                encoding="utf-8",
            )
            recovered = recover_middle_window_partial_capture(
                iq, child_return_code=1, required_middle_window_s=3.0
            )
            self.assertIsNotNone(recovered)
            self.assertEqual(validate_capture(iq)["status"], "usable_partial")
            self.assertEqual(iq.stat().st_size, available * 8)

    def test_campaign_range_and_digest(self) -> None:
        _, runs, digest = load_campaign(CAMPAIGN, start_sequence=1, end_sequence=3)
        self.assertEqual([run["sequence"] for run in runs], [1, 2, 3])
        self.assertEqual(runs[0]["run_id_hex"], "0x0F023211")
        self.assertEqual(len(digest), 64)
        _, same_runs, same_digest = load_campaign(
            CAMPAIGN, start_sequence=1, end_sequence=3
        )
        self.assertEqual(runs, same_runs)
        self.assertEqual(digest, same_digest)

    def test_controller_command_has_frozen_parameters_and_no_serial(self) -> None:
        _, runs, _ = load_campaign(CAMPAIGN, start_sequence=1, end_sequence=1)
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(
                python_executable="python",
                repo_root=ROOT,
                manifest_dir=Path(directory),
                control_tx_gain=60.0,
            )
            command = controller_command(args, runs[0])
        rendered = " ".join(command)
        self.assertIn("--run-id 0x0F023211", rendered)
        self.assertIn("--active-nodes 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15", rendered)
        self.assertIn("--phy-profile-id 5", rendered)
        self.assertIn("--per-node-duty-cycle 0.5", rendered)
        self.assertNotIn("--traffic-reference-nodes", rendered)
        self.assertIn("--node-tx-power 16", rendered)
        self.assertIn("--usrp-tx-gain 60", rendered)
        self.assertNotIn("--device-args", command)
        self.assertNotIn("serial=", rendered)

    def test_receiver_commands_have_no_device_selector(self) -> None:
        _, runs, _ = load_campaign(CAMPAIGN, start_sequence=1, end_sequence=1)
        args = argparse.Namespace(
            python_executable="python3",
            repo_root=ROOT,
            runs_root=ROOT / "real_collision_experiment/runs",
            sample_rate=750_000.0,
            rx_gain=20.0,
            campaign_id="fig9_10_fig12_phy5_d05_d075_r1_20s",
        )
        capture, iq_path = capture_command(args, runs[0])
        decode, report = decoder_command(args, runs[0], iq_path)
        self.assertNotIn("--device-args", capture)
        self.assertIn("--duration", capture)
        self.assertIn("50", capture)
        self.assertEqual(capture[capture.index("--rate") + 1], "750000")
        self.assertEqual(capture[capture.index("--bandwidth") + 1], "500000")
        self.assertEqual(capture[capture.index("--gain") + 1], "20")
        self.assertIn("--run-id", decode)
        self.assertIn("--energy-min-ratio", decode)
        self.assertEqual(decode[decode.index("--energy-min-ratio") + 1], "3")
        self.assertIn("--comparison-frontend-scope", decode)
        self.assertEqual(
            decode[decode.index("--comparison-frontend-scope") + 1], "common"
        )
        self.assertEqual(
            decode[decode.index("--max-candidates") + 1],
            str(3 * int(runs[0]["expected_tx_count"])),
        )
        self.assertEqual(
            decode[decode.index("--frontend-candidates-per-window") + 1], "256"
        )
        self.assertTrue(str(report).endswith("six_methods_gate.json"))

        bw500_run = {**runs[0], "phy_profile_id": 7, "bandwidth_hz": 500_000}
        bw500_capture, _ = capture_command(args, bw500_run)
        self.assertEqual(bw500_capture[bw500_capture.index("--rate") + 1], "1e+06")
        self.assertEqual(bw500_capture[bw500_capture.index("--bandwidth") + 1], "1e+06")

    def test_formal_candidate_budgets_scale_with_load_and_node_count(self) -> None:
        self.assertEqual(
            formal_candidate_budgets(
                {"active_nodes": [9, 12, 13, 14], "expected_tx_count": 108}
            ),
            (800, 256),
        )
        self.assertEqual(
            formal_candidate_budgets(
                {"active_nodes": list(range(1, 16)), "expected_tx_count": 1213}
            ),
            (3639, 256),
        )

    def test_offline_schedule_has_fixed_slots_and_position_breaks(self) -> None:
        _, runs, _ = load_campaign(CAMPAIGN, start_sequence=2, end_sequence=15)
        schedule = build_schedule(runs, slot_s=70.0, position_pause_s=20.0)
        offsets = {int(item.run["sequence"]): item.start_offset_s for item in schedule}
        self.assertEqual(offsets[2], 0.0)
        self.assertEqual(offsets[3], 70.0)
        self.assertEqual(offsets[11], 9 * 70.0 + 20.0)
        self.assertEqual(offsets[12] - offsets[11], 70.0 + 20.0)
        self.assertEqual(
            [item.run["sequence"] for item in schedule if item.position_pause_before_s],
            [11, 12, 13, 14, 15],
        )

        _, fig12_runs, _ = load_campaign(CAMPAIGN, start_sequence=11, end_sequence=15)
        fig12_schedule = build_schedule(
            fig12_runs, slot_s=70.0, position_pause_s=20.0
        )
        self.assertEqual(fig12_schedule[0].start_offset_s, 0.0)
        self.assertEqual(
            [item.run["sequence"] for item in fig12_schedule if item.position_pause_before_s],
            [12, 13, 14, 15],
        )

    def test_offline_controller_shortens_only_initial_control_delay(self) -> None:
        _, runs, _ = load_campaign(CAMPAIGN, start_sequence=1, end_sequence=1)
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(
                python_executable="python",
                repo_root=ROOT,
                manifest_dir=Path(directory),
                control_tx_gain=60.0,
                pre_config_delay_s=5.0,
            )
            command = offline_controller_command(args, runs[0])
        rendered = " ".join(command)
        self.assertIn("--pre-config-delay-s 5", rendered)
        self.assertIn("--config-repeat 5", rendered)
        self.assertIn("--start-repeat 5", rendered)
        self.assertIn("--start-interval-s 0.6", rendered)
        self.assertIn("--start-arm-delay-s 4", rendered)
        self.assertIn("--usrp-tx-gain 60", rendered)
        self.assertNotIn("--device-args", command)

    def test_full_campaign_storage_estimate(self) -> None:
        _, runs, _ = load_campaign(CAMPAIGN, start_sequence=1, end_sequence=15)
        final_bytes, merge_extra = required_capture_bytes(
            runs, sample_rate=750_000.0, capture_guard_s=5.0
        )
        self.assertGreater(final_bytes, 4.6 * 1024**3)
        self.assertLess(final_bytes, 4.7 * 1024**3)
        self.assertGreater(merge_extra, 300 * 1024**2)


if __name__ == "__main__":
    unittest.main()
