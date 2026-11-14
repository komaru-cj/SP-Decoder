import unittest
import numpy as np
from real_collision_experiment.paper_experiments import run_resubmission_heatmaps as h


class ResubmissionHeatmapTests(unittest.TestCase):
    def test_angle_grid_pairs_payloads_and_sources_across_sir(self):
        specs=h.specs_for('C1_angle_sir',1)
        chosen=[s for s in specs if s['angle_low']==2.]
        self.assertEqual(len(chosen),4)
        self.assertEqual(len({s['seed'] for s in chosen}),1)
        truth=[]
        for s in chosen:
            _,t,_=h.abc.synthesize(s,h.abc.source_bank(),h.abc.default_cfg())
            truth.append(t)
        for t in truth[1:]:
            for a,b in zip(truth[0],t):
                self.assertEqual(a['source_index'],b['source_index'])
                self.assertEqual(a['payload_hex'],b['payload_hex'])
                self.assertEqual(a['start_sample'],b['start_sample'])

    def test_a3_nested_packets_and_three_decimal_gap_audit(self):
        bank,cfg=h.abc.source_bank(),h.abc.default_cfg()
        common=dict(family='A3_density_delay',gap_symbols=.1,snr_db=0.,seed=719,
                    jitter_kind='absolute_0p005')
        _,small,_,timing=h.a3_synthesize(dict(common,k=4),bank,cfg)
        _,large,_,_=h.a3_synthesize(dict(common,k=10),bank,cfg)
        for a,b in zip(small,large):
            self.assertEqual(a,b)
        gaps=np.asarray(timing['planned_signed_adjacent_gaps'])
        self.assertTrue(np.all(abs(gaps-.1)<=.005+1e-12))
        np.testing.assert_allclose(gaps*1000,np.round(gaps*1000),atol=1e-10)
        actual=np.asarray(timing['actual_signed_adjacent_gaps'])
        self.assertTrue(np.all(abs(actual-gaps)<=1/cfg.samples_per_symbol))

    def test_a3_requires_explicit_jitter_units(self):
        with self.assertRaises(ValueError):h.specs_for('A3_density_delay',1)

    def test_absolute_tenth_symbol_jitter_keeps_negative_increments(self):
        s=dict(family='A3_density_delay',k=10,gap_symbols=.05,snr_db=0.,seed=719,
               jitter_kind='absolute_0p1')
        _,truth,_,timing=h.a3_synthesize(s,h.abc.source_bank(),h.abc.default_cfg())
        gaps=np.asarray(timing['planned_signed_adjacent_gaps'])
        self.assertTrue(np.all(abs(gaps-.05)<=.1+1e-12))
        self.assertTrue(np.any(gaps<0))
        self.assertEqual(timing['negative_start_increment_count'],np.count_nonzero(gaps<0))
        cfg=h.abc.default_cfg()
        starts=np.array([t['start_sample'] for t in truth])
        self.assertEqual(float(starts.min()),3*cfg.samples_per_symbol)
        np.testing.assert_allclose(np.diff(starts)/cfg.samples_per_symbol,gaps,
                                   atol=1/cfg.samples_per_symbol,rtol=0)

    def test_cached_snr_grid_is_current_sp_with_four_requested_methods(self):
        s=h.specs_for('C1_snr_sir',1)[0]
        j=h.cached_grid(s)
        self.assertEqual(j['sp_policy'],h.TWO_PACKET_POLICY)
        self.assertEqual(set(j['targets'][0]['methods']),set(h.METHODS))
        self.assertTrue(j['provenance']['current_weight_reproduced'])

    def test_a3_uses_the_bounded_branch_of_the_current_sp(self):
        s=dict(family='A3_density_delay',k=4,gap_symbols=.1,snr_db=0.,seed=719,
               jitter_kind='absolute_0p005')
        j=h.fresh_job(s)
        self.assertEqual(len(j['targets']),4)
        for e in j['candidate_estimates']:
            self.assertEqual(e['lambda_gate_policy_sp'],h.TWO_PACKET_POLICY)
            self.assertEqual(e['overlapping_interferer_count_sp'],3)
            self.assertLessEqual(e['lambda_cap_sp'],4.)


if __name__=='__main__':unittest.main()
