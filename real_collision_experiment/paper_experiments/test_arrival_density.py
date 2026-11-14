import unittest
import numpy as np
from real_collision_experiment.paper_experiments.arrival_density import scaled_starts


class ArrivalDensityTests(unittest.TestCase):
    def test_rescaling_preserves_negative_increments_and_label_order(self):
        original=np.array([.1,.18,.13,.2])
        for density in (10/3,5.,10.,20.):
            starts,meta=scaled_starts(original,density,8192)
            self.assertEqual(np.argsort(starts).tolist(),[0,2,1,3])
            self.assertLess(np.diff(starts)[1],0)
            self.assertEqual(starts.min(),3*8192)
            self.assertLessEqual(abs(np.ptp(starts)/8192-3/density),.5/8192)
            relative=(starts-starts.min())/np.ptp(starts)
            np.testing.assert_allclose(relative,[0.,.8,.3,1.],atol=1/np.ptp(starts))
            self.assertFalse(meta['absolute_jitter_preserved'])

    def test_density_grid_controls_span_for_every_collision_order(self):
        for k in (4,6,8,10):
            offsets=np.cumsum(np.r_[0.,np.random.default_rng(k).uniform(.01,.2,k-1)])
            for density in (10/3,5.,10.,20.):
                starts,meta=scaled_starts(offsets,density,8192)
                self.assertEqual(np.ptp(starts),round((k-1)/density*8192))
                self.assertLess(abs(meta['actual_density']/density-1.),.0003)


if __name__=='__main__':unittest.main()
