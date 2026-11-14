"""Invariants for measured-channel explicit-waveform experiments."""
import unittest
import numpy as np

from real_collision_experiment.paper_experiments.run_revision_abc import (
    assign_tracks, default_cfg, evaluate, source_bank, specifications, synthesize,
)


class RevisionABCTests(unittest.TestCase):
    def test_controlled_single_packet_closes_all_six_receiver_crcs(self):
        spec = dict(family="pilot", k=1, snr_db=10., seed=17)
        result, _ = evaluate(spec, source_bank(), default_cfg())
        for method, row in result["targets"][0]["methods"].items():
            with self.subTest(method=method):
                self.assertTrue(row["delivered"])
                self.assertEqual(row["ser"], 0.)

    def test_synthesis_retains_measured_channel_ratio_and_cfo(self):
        bank = source_bank()
        cfg = default_cfg()
        spec = dict(family="B_angle", k=2, snr_db=0., sir_db=0., angle_low=0., angle_high=2., seed=18)
        _, truth, noise = synthesize(spec, bank, cfg)
        self.assertEqual(noise, 1.)
        self.assertNotEqual(truth[0]["position"], truth[1]["position"])
        for packet in truth:
            original = bank[packet["source_index"]]
            h = np.array([complex(*x) for x in packet["channel"]])
            ref = np.array([complex(*x) for x in original["channel_ri"]])
            self.assertAlmostEqual(abs(np.vdot(h, ref)) / np.linalg.norm(h), 1.)
            self.assertEqual(packet["cfo_bins"], original["cfo_bins"])

    def test_coincident_starts_match_by_cfo_and_css_timing_alias(self):
        cfg = default_cfg()
        truth = [dict(start_sample=100., cfo_bins=-12.366), dict(start_sample=100., cfo_bins=-21.045)]
        estimates = [dict(start_sample=106., cfo_bins=-11.), dict(start_sample=100., cfo_bins=-21.)]
        self.assertEqual(assign_tracks(estimates, truth, cfg), {0: 0, 1: 1})

    def test_snr_sir_grid_reuses_pair_seed_without_changing_source_pool(self):
        specs = specifications("B", 1, -20., 17)
        selected = [s for s in specs if s["family"] == "B_grid" and s["angle_low"] == 0.]
        self.assertEqual(len({s["seed"] for s in selected}), 1)
        self.assertEqual(len(selected), 24)

    def test_channel_assisted_scoring_does_not_count_two_aliases_as_two_packets(self):
        from real_collision_experiment.paper_experiments.render_revision_abc import rescore_C_truth_channels
        truth = [dict(start_sample=100.,cfo_bins=-20.,channel=h) for h in ([[1.,0.],[0.,0.]],[[0.,0.],[1.,0.]])]
        estimates = [dict(start_sample=100.,cfo_bins=-20.,channel_sp=h,confidence=confidence,lambda_sp=0.,lambda_cap_sp=4.,theta_total=.1) for h,confidence in (([[1.,0.],[0.,0.]],1.),([[1.,0.],[.01,0.]],2.))]
        targets = [dict(target_index=i,track_established=True,methods={"sp":{"delivered":i==0}}) for i in range(2)]
        job = dict(spec={"family":"C"},calibration={"whitener":[[[1.,0.],[0.,0.]],[[0.,0.],[1.,0.]]]},truth=truth,candidate_estimates=estimates,targets=targets)
        scored = rescore_C_truth_channels(job)
        self.assertEqual([r["track_established"] for r in scored["targets"]],[True,False])
        self.assertEqual(scored["targets"][0]["matched_candidate"],1)
        self.assertEqual([r["methods"] for r in scored["targets"]],[r["methods"] for r in targets])


if __name__ == "__main__":
    unittest.main()
