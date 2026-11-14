import unittest
import numpy as np
from real_collision_experiment.paper_experiments.frame_integrity import check_frame_integrity
from real_collision_experiment.node01_sp_receiver.real_lora_config import RealCollisionLoRaConfig

class FrameIntegrityTests(unittest.TestCase):
    def test_preserves_phase_variation_but_flags_missing_final_symbol(self):
        c=RealCollisionLoRaConfig(sample_rate_hz=1000000,payload_len=32,implicit_header=True)
        phase=np.exp(1j*np.arange(c.frame_samples)*.03)
        p=np.vstack([phase,phase*np.exp(1j*.5*np.sin(np.arange(c.frame_samples)/1000))]).astype(np.complex64)
        self.assertTrue(check_frame_integrity(p,c,1e-4)['passed'])
        s=round((c.payload_start_symbols+c.payload_symbol_count-1)*c.samples_per_symbol)
        p[:,s:]=.01
        r=check_frame_integrity(p,c,1e-4)
        self.assertFalse(r['passed']);self.assertEqual(r['failed_symbol_positions'],[49.25])

    def test_checks_early_symbols_and_missing_samples_too(self):
        c=RealCollisionLoRaConfig(sample_rate_hz=1000000,payload_len=32,implicit_header=True)
        p=np.ones((2,c.frame_samples),dtype=np.complex64)
        p[:,c.samples_per_symbol:2*c.samples_per_symbol]=0
        self.assertFalse(check_frame_integrity(p,c,1e-4)['passed'])
        self.assertEqual(check_frame_integrity(p[:,:-1],c,1e-4)['reason'],'missing_samples')

if __name__=='__main__':unittest.main()
