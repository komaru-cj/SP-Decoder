from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as hm
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda
from sp_reference_guard import GUARDED_PAIR_POLICY,decision_channel
abc=hm.abc


class ReferenceGuardTests(unittest.TestCase):
    def test_physical_mrc_fallback_matches_every_symbol_with_nonunit_whitener(self):
        spec=dict(family='B_grid',k=2,snr_db=-20.,sir_db=20.,angle_low=10.,angle_high=60.,seed=3188008350)
        cfg=abc.default_cfg()
        physical,truth,_=abc.synthesize(spec,abc.source_bank(),cfg)
        physical=physical.astype(np.complex64)
        W=np.array([[2.,.4+.2j],[.1,.6]],dtype=np.complex128)
        white=(W@physical).astype(np.complex64)
        es=[dict(start_sample=t['start_sample'],cfo_bins=t['cfo_bins'],sto_samples=0.,channel=[[0.,0.],[0.,0.]]) for t in truth]
        guarded=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=1024.,gamma=.05,
            reference_guard=True,physical_samples=physical,whitener=W)
        e=guarded[0]
        self.assertEqual(e['lambda_sp'],0.)
        self.assertTrue(e['sp_mrc_fallback'])
        baseline=abc.PaperComparisonContext(physical,es,cfg,frontend_method='mrc').decode_mrc(es[0])
        self.assertEqual(abc.projected_decisions(white,e,cfg)[0],baseline['symbol_bins'])
        stages=abc.decode_sp_stages(white,e,cfg,max_sync_trials=1)
        self.assertEqual(next(r for r in stages if r['method']=='sp_core')['symbol_bins'],baseline['symbol_bins'])
        # The decision vector is deliberately distinct from the whitened
        # signal direction; this catches accidental coordinate mixing.
        self.assertFalse(np.allclose(decision_channel(e),e['channel_sp']))

    def test_negative_unsafe_pair_proposal_is_disabled(self):
        spec=next(s for s in hm.specs_for('C1_angle_sir') if s['angle_low']==0 and s['sir_db']==0 and s['repeat']==5)
        cfg=abc.default_cfg();samples,truth,_=abc.synthesize(spec,abc.source_bank(),cfg)
        physical,white,es,sigma,W,_=abc.controlled_inputs(samples,truth,cfg)
        old=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=sigma,gamma=.05,
            noise_competition=True,noise_two_packet_only=True)
        self.assertGreater(old[0]['lambda_sp'],100.)
        new=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=sigma,gamma=.05,
            reference_guard=True,physical_samples=physical,whitener=W)
        self.assertEqual(new[0]['lambda_sp'],0.)
        self.assertEqual(new[0]['lambda_guard_reason_sp'],'reference_cones_not_separated')
        self.assertEqual(new[0]['lambda_policy_sp'],GUARDED_PAIR_POLICY)

    def test_multiuser_channel_lambda_and_payload_are_identical(self):
        spec=dict(family='A3_density_delay',k=4,gap_symbols=.1,snr_db=0.,seed=719,jitter_kind='absolute_0p1')
        cfg=abc.default_cfg();samples,truth,_,_=hm.a3_synthesize(spec,abc.source_bank(),cfg)
        physical,white,es,sigma,W,_=abc.controlled_inputs(samples,truth,cfg)
        old=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=sigma,gamma=.05,
            noise_competition=True,noise_two_packet_only=True)
        new=attach_sp_reliability_and_lambda(white,es,cfg,noise_sigma2=sigma,gamma=.05,
            reference_guard=True,physical_samples=physical,whitener=W)
        for before,after in zip(old,new):
            self.assertEqual(before['channel_sp'],after['channel_sp'])
            self.assertEqual(before['lambda_sp'],after['lambda_sp'])
            self.assertEqual(abc.projected_decisions(white,before,cfg)[0],abc.projected_decisions(white,after,cfg)[0])

    def test_missing_physical_coordinate_mapping_fails_explicitly(self):
        cfg=abc.default_cfg()
        with self.assertRaisesRegex(ValueError,'physical samples'):
            attach_sp_reliability_and_lambda(np.zeros((2,1)),[],cfg,noise_sigma2=1.,gamma=.05,reference_guard=True)

if __name__=='__main__':unittest.main()
