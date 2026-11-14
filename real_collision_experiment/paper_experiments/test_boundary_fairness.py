"""Signal parity and counting invariants for the collision-boundary experiment."""
import unittest
from unittest.mock import patch
import numpy as np
from real_collision_experiment.paper_experiments import run_boundary_fairness as b
from lora_mrc_sp_core import LoRaConfig


class BoundaryTests(unittest.TestCase):
    def test_zero_observed_difference_keeps_gain_and_loss_uncertainty(self):
        from real_collision_experiment.paper_experiments.render_boundary_fairness import paired_ci
        mean,lower,upper=paired_ci(np.zeros(128))
        self.assertEqual(mean,0.)
        self.assertLess(lower,0.)
        self.assertGreater(upper,0.)
        mean,lower,upper=paired_ci(np.ones(128))
        self.assertEqual(mean,1.)
        self.assertGreater(lower,0.)
        self.assertLess(lower,1.)
        self.assertEqual(upper,1.)

    def test_certified_candidates_are_not_merged_as_blind_aliases(self):
        from real_collision_experiment.paper_experiments.replay_boundary_certified_candidates import CertifiedContext
        cfg=LoRaConfig(sf=7,sample_rate_hz=125000)
        samples=np.zeros((2,cfg.frame_samples+500),np.complex64)
        es=[dict(start_sample=s,cfo_bins=0.,channel=[[0.,0.],[0.,0.]]) for s in (100.,103.)]
        with patch('compare.real_packet_decoders._preamble_measurements',return_value=(np.array([1.,0.],complex),0.,1.)):
            ctx=CertifiedContext(samples,es,cfg,frontend_method='pcube')
        self.assertEqual(len(ctx.blind_alias_groups),1)
        self.assertEqual(len(ctx._physical_groups),2)
        self.assertEqual(ctx._physical_group_representatives,[0,1])

    def test_certified_adapter_preserves_unmerged_candidate_order(self):
        from real_collision_experiment.paper_experiments.replay_boundary_certified_candidates import CertifiedContext
        cfg=LoRaConfig(sf=7,sample_rate_hz=125000)
        samples=np.zeros((2,cfg.frame_samples+500),np.complex64)
        es=[dict(start_sample=s,cfo_bins=0.,channel=[[0.,0.],[0.,0.]]) for s in (300.,100.)]
        with patch('compare.real_packet_decoders._preamble_measurements',return_value=(np.array([1.,0.],complex),0.,1.)):
            normal=b.PaperComparisonContext(samples,es,cfg,frontend_method='pcube')
            certified=CertifiedContext(samples,es,cfg,frontend_method='pcube')
        self.assertEqual(normal._physical_groups,certified._physical_groups)
        self.assertEqual(normal._physical_group_by_index,certified._physical_group_by_index)
        self.assertEqual(normal._physical_group_representatives,certified._physical_group_representatives)

    def test_cached_integer_and_fractional_windows_match_receiver(self):
        cfg=LoRaConfig(sf=7,sample_rate_hz=125000)
        rng=np.random.default_rng(8)
        samples=(rng.normal(size=(2,cfg.frame_samples+300))+1j*rng.normal(size=(2,cfg.frame_samples+300))).astype(np.complex64)
        for start in (11.,11.125):
            est=dict(start_sample=start,cfo_bins=-2.135,channel=[[0,0],[0,0]])
            cache=b.IntegerPayloadCache()
            for index in (0,1,2):
                actual=cache.mixed_for(samples,est,cfg,index)
                expected=b._physical_mixed(samples,est,cfg,index)
                np.testing.assert_array_equal(actual,expected)
                np.testing.assert_array_equal(cache.mixed_for(samples,est,cfg,index),expected)

    def test_exact_interval_contains_only_positive_margins(self):
        # True bin zero: -2 + 2*lambda > 0 and 4-lambda > 0.
        p=np.array([[4.,6.,0.]])
        q=np.array([[1.,3.,0.]])
        result=b.exact_interval(p,q,[0],10.)
        self.assertTrue(result['nonempty'])
        self.assertEqual(result['lower'],1.)
        self.assertEqual(result['upper'],4.)
        for lam in (1.1,2.,3.9):self.assertEqual(int(np.argmax(p-lam*q)),0)

    def test_empty_symbol_interval_does_not_claim_crc_failure(self):
        result=b.exact_interval(np.array([[1.,2.]]),np.array([[1.,1.]]),[0],4.)
        self.assertFalse(result['nonempty'])

    def test_overlap_counts_only_target_payload(self):
        cfg=LoRaConfig()
        both=b.overlap_summary([0,0],cfg,0)
        self.assertEqual(both['mean_concurrency'],2.)
        self.assertEqual(both['peak_concurrency'],2)
        apart=b.overlap_summary([0,2*cfg.frame_samples],cfg,0)
        self.assertEqual(apart['mean_concurrency'],1.)
        self.assertEqual(apart['overlapping_indices'],[])


if __name__=='__main__':unittest.main()
