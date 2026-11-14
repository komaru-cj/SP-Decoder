from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RECEIVER = Path(__file__).resolve().parent
for path in (ROOT, RECEIVER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from evaluate_sp_dechirp_real_pos import (  # noqa: E402
    SPPacketReliability,
    attach_sp_reliability_and_lambda,
)
from sp_node01_receiver import build_parser, configure_sp_lambda_batch  # noqa: E402


class _Config:
    m = 1024
    preamble_len = 8
    payload_start_symbols = 12.25
    payload_symbol_count = 33
    samples_per_symbol = 100.0


def _estimate(start_sample: float) -> dict:
    return {
        "start_sample": start_sample,
        "sto_samples": 0.0,
        "cfo_bins": 0.0,
        "continuous_cfo_bins": 0.0,
        "channel": [[1.0, 0.0], [0.0, 1.0]],
    }


class SpLambdaConfigurationTests(unittest.TestCase):
    def test_receiver_defaults_to_the_confirmed_upgraded_sp(self):
        parser = build_parser()
        self.assertEqual(parser.get_default('sp_lambda_policy'), 'pair_and_noise_reference_guard_v2')
        self.assertIn('pair_only_legacy', parser._option_string_actions['--sp-lambda-policy'].choices)

    def _robust_channel(self, _samples, start, *_args):
        # The two targets are orthogonal, high-confidence preamble directions.
        channel = (
            np.asarray([10.0 + 0.0j, 0.0 + 0.0j])
            if start < 100.0
            else np.asarray([0.0 + 0.0j, 10.0 + 0.0j])
        )
        return channel, SPPacketReliability(
            theta_obs=0.01,
            theta_drift=0.0,
            theta_total=0.01,
            L=0.99,
            power=100.0,
            noise_sigma2=1.0,
            robust_hit_count=8,
        )

    @patch("evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp")
    def test_payload_overlap_builds_nonzero_lambda_candidates(self, robust_channel) -> None:
        robust_channel.side_effect = self._robust_channel
        configured = attach_sp_reliability_and_lambda(
            np.zeros((2, 1), dtype=np.complex64),
            [_estimate(0.0), _estimate(100.0)],
            _Config(),
            noise_sigma2=1.0,
            gamma=0.05,
            max_lambda=4.0,
            noise_competition=True,
        )

        for row in configured:
            self.assertEqual(row["overlapping_interferer_count_sp"], 1)
            self.assertGreater(row["lambda_cap_sp"], 0.0)
            self.assertGreater(len(row["lambda_candidate_points_sp"]), 1)
            self.assertTrue(any(item["lambda"] > 0 for item in row["lambda_candidate_points_sp"]))
            # Orthogonal equal-power users can be noise-limited already: the
            # new objective may correctly choose MRC despite an overlap edge.
            expected = ("noise_constrained_risk_maximizer" if row["lambda_sp"] > 0
                        else "mrc_is_noise_constrained_risk_maximizer")
            self.assertEqual(row["lambda_selection_reason_sp"], expected)
            self.assertEqual(row["lambda_policy_sp"], "pair_and_noise_max_v1")

    @patch("evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp")
    def test_experimental_policy_is_opt_in_and_legacy_cap_is_preserved(self, robust_channel):
        robust_channel.side_effect = self._robust_channel
        configured = attach_sp_reliability_and_lambda(
            np.zeros((2, 1), dtype=np.complex64),
            [_estimate(0.0), _estimate(100.0)], _Config(),
            noise_sigma2=1., gamma=.05,
        )
        for row in configured:
            self.assertEqual(row['lambda_policy_sp'], 'pair_only_legacy')
            self.assertEqual(row['lambda_cap_sp'], 4.)
            self.assertGreater(row['lambda_sp'], 0.)

    @patch("evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp")
    def test_two_packet_gate_keeps_multiuser_legacy_weights(self, robust_channel):
        robust_channel.side_effect = self._robust_channel
        rows = [_estimate(0.), _estimate(100.), _estimate(200.)]
        kwargs = dict(noise_sigma2=1., gamma=.05)
        legacy = attach_sp_reliability_and_lambda(np.zeros((2, 1)), rows, _Config(), **kwargs)
        gated = attach_sp_reliability_and_lambda(np.zeros((2, 1)), rows, _Config(),
            noise_competition=True, noise_two_packet_only=True, max_lambda=1024., **kwargs)
        for old, new in zip(legacy, gated):
            self.assertEqual(old['lambda_sp'], new['lambda_sp'])
            self.assertEqual(new['lambda_cap_sp'], 4.)
            self.assertEqual(new['lambda_gate_policy_sp'], 'pair_and_noise_two_packet_v1')
            self.assertEqual(new['lambda_policy_sp'], 'pair_only_legacy')

    @patch('evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp')
    def test_explicit_multiuser_cap10_and_old_candidates_are_supported(self, robust_channel):
        robust_channel.side_effect=self._robust_channel
        rows=[_estimate(0.),_estimate(100.),_estimate(200.)]
        result=attach_sp_reliability_and_lambda(np.zeros((2,1)),rows,_Config(),
            noise_sigma2=1.,gamma=.05,reference_guard=True,physical_samples=np.zeros((2,1)),
            whitener=np.eye(2),multiuser_lambda_cap=10.)
        for row in result:
            self.assertEqual(row['lambda_cap_sp'],10.)
            self.assertEqual(row['lambda_global_max_sp'],10.)
            self.assertLessEqual(row['lambda_sp'],10.)
            self.assertEqual(row['lambda_guard_reason_sp'],'retain_bounded_multiuser_branch')
            candidates=[p['lambda'] for p in row['lambda_candidate_points_sp']]
            for value in (0.,1.,2.,3.,4.,10.):self.assertIn(value,candidates)

    @patch('evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp')
    def test_multiuser_fixed_cap_can_be_removed_without_removing_reliability_bound(self, robust_channel):
        robust_channel.side_effect=self._robust_channel
        rows=[_estimate(0.),_estimate(100.),_estimate(200.)]
        kwargs=dict(noise_sigma2=1.,gamma=.05,reference_guard=True,
            physical_samples=np.zeros((2,1)),whitener=np.eye(2))
        bounded=attach_sp_reliability_and_lambda(np.zeros((2,1)),rows,_Config(),**kwargs)
        expanded=attach_sp_reliability_and_lambda(np.zeros((2,1)),rows,_Config(),
            remove_multiuser_lambda_cap=True,**kwargs)
        for a,b in zip(bounded,expanded):
            self.assertEqual(a['lambda_cap_sp'],4.)
            self.assertAlmostEqual(b['lambda_cap_sp'],(.99-.05)/(1-.99))
            self.assertLessEqual(b['lambda_sp'],b['lambda_cap_sp'])
            self.assertTrue(b['lambda_fixed_global_cap_removed_sp'])
            self.assertIsNone(b['lambda_global_max_sp'])
            self.assertEqual(b['lambda_guard_reason_sp'],'retain_reliability_limited_multiuser_branch')
            candidates=[p['lambda'] for p in b['lambda_candidate_points_sp']]
            for old_value in (0.,1.,2.,3.,4.):self.assertIn(old_value,candidates)
            self.assertTrue(any(v>4. for v in candidates))

    @patch("evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp")
    def test_two_packet_gate_uses_the_same_adaptive_noise_selector(self, robust_channel):
        robust_channel.side_effect = self._robust_channel
        rows = [_estimate(0.), _estimate(100.)]
        kwargs = dict(noise_sigma2=1., gamma=.05, noise_competition=True)
        full = attach_sp_reliability_and_lambda(np.zeros((2, 1)), rows, _Config(), **kwargs)
        gated = attach_sp_reliability_and_lambda(np.zeros((2, 1)), rows, _Config(),
            noise_two_packet_only=True, **kwargs)
        for old, new in zip(full, gated):
            self.assertEqual(old['lambda_sp'], new['lambda_sp'])
            self.assertGreater(new['lambda_cap_sp'], 4.)
            self.assertEqual(new['lambda_gate_reason_sp'], 'one_overlapping_competitor')

    @patch("evaluate_sp_dechirp_real_pos.robust_preamble_channel_sp")
    def test_isolated_target_falls_back_to_mrc(self, robust_channel) -> None:
        robust_channel.side_effect = self._robust_channel
        configured = attach_sp_reliability_and_lambda(
            np.zeros((2, 1), dtype=np.complex64),
            [_estimate(0.0), _estimate(10_000.0)],
            _Config(),
            noise_sigma2=1.0,
            gamma=0.05,
            max_lambda=4.0,
            noise_competition=True,
        )

        for row in configured:
            self.assertEqual(row["overlapping_interferer_count_sp"], 0)
            self.assertEqual(row["lambda_sp"], 0.0)
            self.assertEqual(
                row["lambda_selection_reason_sp"],
                "no_payload_overlapping_competitor",
            )

    @patch("sp_node01_receiver.attach_sp_reliability_and_lambda")
    def test_receiver_configures_the_full_target_batch_once(self, attach) -> None:
        rows = [_estimate(0.0), _estimate(100.0)]
        configured = [
            {
                **row,
                "sto_samples_sp": 0.0,
                "overlapping_interferer_count_sp": 1,
                "lambda_sp": 1.0,
                "lambda_selection_reason_sp": "risk_maximizer",
            }
            for row in rows
        ]
        attach.return_value = configured

        result, audit = configure_sp_lambda_batch(
            np.zeros((2, 1), dtype=np.complex64),
            rows,
            _Config(),
            noise_sigma2=1.0,
            gamma=0.05,
            max_lambda=4.0,
        )

        self.assertEqual(result, configured)
        self.assertEqual(attach.call_count, 1)
        self.assertEqual(attach.call_args.args[1], rows)
        self.assertEqual(audit["payload_overlap_edge_count"], 1)
        self.assertEqual(audit["targets_with_positive_lambda"], 2)


if __name__ == "__main__":
    unittest.main()
