import unittest
import numpy as np
from compare.PCube.soft_grouping import group_packet


def packet(phases,amplitudes):
    rng=np.random.default_rng(945)
    spectra=[]
    for p,a in zip(phases,amplitudes):
        f=(rng.normal(size=(2,128))+1j*rng.normal(size=(2,128))) / np.sqrt(2)
        for b,phi,amp in zip((17,71),p,a):
            f[0,b]=amp*np.exp(1j*phi)
            f[1,b]=amp
        spectra.append(f)
    return spectra,[np.array([17,71]) for _ in spectra]


class SoftPDoAGroupingTests(unittest.TestCase):
    def test_conservative_extension_recovers_outside_peak_without_reordering_admitted_peaks(self):
        f,c=packet([[.53,0.]]*38,[[10.,2.]]*38)
        bins,_,_=group_packet(f,c,[0.],[100.],0,8,preserve_accepted=True)
        self.assertEqual(bins,[17]*38)
        f,c=packet([[.25,0.]]*38,[[9.,10.]]*38)
        bins,_,_=group_packet(f,c,[.3,0.],[100.,100.],0,8,preserve_accepted=True)
        self.assertEqual(bins,[71]*38)

    def test_resolved_phase_groups_recover_weaker_target(self):
        f,c=packet([[0.,2.]]*20,[[10.,40.]]*20)
        for target_only in (False,True):
            with self.subTest(target_only=target_only):
                refs,powers=([0.],[100.]) if target_only else ([0.,2.],[100.,1600.])
                bins,_,_=group_packet(f,c,refs,powers,0,8,target_only=target_only)
                self.assertEqual(bins,[17]*20)

    def test_phase_wrap_and_common_reference_rotation(self):
        f,c=packet([[3.12,-1.]]*20,[[10.,20.]]*20)
        rotated=[x*np.array([[np.exp(.7j)],[1.]]) for x in f]
        for target_only in (False,True):
            with self.subTest(target_only=target_only):
                refs,powers=([-3.13],[100.]) if target_only else ([-3.13,-1.],[100.,400.])
                a=group_packet(f,c,refs,powers,0,8,target_only=target_only)[0]
                b=group_packet(rotated,c,np.asarray(refs)+.7,powers,0,8,target_only=target_only)[0]
                self.assertEqual(a,[17]*20)
                self.assertEqual(a,b)

    def test_no_discontinuity_at_legacy_half_radian_boundary(self):
        for target_only in (False,True):
            with self.subTest(target_only=target_only):
                outputs=[]
                for phi in (.4999,.5001):
                    f,c=packet([[phi,0.]]*38,[[10.,2.]]*38)
                    outputs.append(group_packet(f,c,[0.],[100.],0,8,target_only=target_only)[0])
                self.assertEqual(outputs[0],outputs[1])
                self.assertEqual(outputs[0],[17]*38)


if __name__=='__main__':unittest.main()
