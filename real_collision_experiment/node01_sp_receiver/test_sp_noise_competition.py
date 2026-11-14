from __future__ import annotations
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sp_noise_competition import noise_max_threshold, select_with_noise


class NoiseCompetitionTests(unittest.TestCase):
    def test_noise_max_threshold_controls_family_false_alarms(self):
        # Independent simulation checks the complete maximum, rather than
        # re-evaluating the analytic tail used by the implementation.
        rng = np.random.default_rng(945)
        x = rng.exponential(size=(20000, 64))
        y = rng.exponential(size=x.shape)
        for lam in (0., 4., 64.):
            threshold = noise_max_threshold(lam, 1., 64, .05)
            rate = np.mean(np.max(x - lam * y, axis=1) > threshold)
            self.assertLess(rate, .06)
            self.assertGreater(rate, .035)

    def test_noise_controls_runaway_pair_weight(self):
        # A<0<B: the old pair surrogate is strictly increasing at every lambda.
        power, reliability, sigma2 = 20000., .999, 1.
        row = dict(A_under=-50000., B_under=20000., C0=200000., C2=40000.)
        result = select_with_noise([row], [], power=power, reliability=reliability,
            noise_sigma2=sigma2, cap=900., noise_bin_count=1023)
        self.assertGreater(result['selected_lambda'], 4.)
        self.assertLess(result['selected_lambda'], 900.)
        self.assertTrue(any('noise_crossing' in source for item in result['candidate_points'] for source in item['sources']))
        self.assertTrue(math.isfinite(result['selected_objective']))

    def test_finite_candidates_cover_pair_noise_optimum(self):
        row = dict(A_under=-50000., B_under=20000., C0=200000., C2=40000.)
        power, reliability, sigma2, cap = 20000., .999, 1., 900.
        result = select_with_noise([row], [], power=power, reliability=reliability,
            noise_sigma2=sigma2, cap=cap, noise_bin_count=1023)
        grid = np.r_[0., np.geomspace(1e-5, cap, 20000)]
        pair = (row['A_under'] + grid * row['B_under']) / np.sqrt(row['C0'] + grid**2 * row['C2'])
        p, q = power * reliability, power * (1 - reliability)
        threshold = np.maximum(0., np.log(1023 / .05) - np.log1p(grid))
        noise = (p - grid * q + 1 - grid - threshold) / np.sqrt(1 + 2 * p + grid**2 * (1 + 2 * q))
        dense_best = float(np.max(np.minimum(pair, noise)))
        self.assertGreaterEqual(result['selected_objective'] + 1e-7, dense_best)

    def test_zero_cap_has_one_finite_candidate(self):
        row = dict(A_under=1., B_under=1., C0=1., C2=1.)
        result = select_with_noise([row], [], power=10., reliability=.9,
            noise_sigma2=1., cap=0., noise_bin_count=255)
        self.assertEqual(result['selected_lambda'], 0.)
        self.assertEqual(len(result['candidate_points']), 1)

    def test_more_noise_bins_raise_maximum_threshold(self):
        self.assertGreater(noise_max_threshold(4., 2., 1023),
                           noise_max_threshold(4., 2., 255))

    def test_power_units_do_not_change_selected_weight(self):
        row = dict(A_under=-50000., B_under=20000., C0=200000., C2=40000.)
        first = select_with_noise([row], [], power=20000., reliability=.999,
            noise_sigma2=1., cap=900., noise_bin_count=1023)
        factor = 1e-3
        scaled = {key: value * (factor**2 if key in ('C0', 'C2') else factor)
                  for key, value in row.items()}
        second = select_with_noise([scaled], [], power=20000. * factor,
            reliability=.999, noise_sigma2=factor, cap=900., noise_bin_count=1023)
        self.assertAlmostEqual(first['selected_lambda'], second['selected_lambda'], places=8)


if __name__ == '__main__':
    unittest.main()
