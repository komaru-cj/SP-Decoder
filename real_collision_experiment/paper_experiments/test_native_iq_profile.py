import unittest
from usrp_b210_lora_tx import payload_nibbles,hamming_codewords,interleave,gray_demap
from real_collision_experiment.paper_experiments import run_revision_abc as a
from real_collision_experiment.node01_sp_receiver.real_lora_config import RealCollisionLoRaConfig

class NativeProfileTests(unittest.TestCase):
    def test_implicit_first_reduced_block_carries_payload(self):
        cfg=RealCollisionLoRaConfig(sample_rate_hz=1000000,payload_len=32,implicit_header=True,sync_word=18)
        for payload in (bytes(range(32)),bytes([255]*32),bytes([0]*32)):
            bins=[gray_demap(v,cfg) for v in interleave(hamming_codewords(payload_nibbles(payload,cfg),cfg),cfg)]
            self.assertEqual(len(bins),38)
            result=a.decode_payload_from_symbol_bins(bins,cfg)
            self.assertTrue(result.phy_crc_ok)
            self.assertEqual(result.payload,payload)
            self.assertEqual(result.header_nibbles,[])

if __name__=='__main__':unittest.main()
