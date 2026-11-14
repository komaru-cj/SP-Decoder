"""Check coherent combining, synchronization, and full CIC/CoRa CRC closure."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "real_collision_experiment/node01_sp_receiver"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from compare.mrc_input import target_mrc_input
from compare.real_packet_decoders import PaperComparisonContext
from compare.CoRa.cora_detector import CoRaDetector
from compare.CoRa.tnb_bec import TnBBECDecoder
from lora_mrc_sp_core import compensate_symbol_window
from real_collision_experiment.node01_sp_receiver.real_lora_config import RealCollisionLoRaConfig
from real_collision_experiment.paper_experiments.simulate_sp_mechanisms import build_explicit_frame


class MRCBaselineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = RealCollisionLoRaConfig(sf=8, bw_hz=125000, sample_rate_hz=250000)
        self.payload = bytes(range(self.cfg.payload_len))
        frame, self.truth = build_explicit_frame(self.payload, self.cfg)
        other, _ = build_explicit_frame(bytes(reversed(self.payload)), self.cfg)
        # The competitor is stronger on each individual antenna, but exactly
        # orthogonal to the target's [1, j] spatial channel.
        channel = np.asarray([1, 1j])
        competitor = np.asarray([-1, 1j])
        self.samples = channel[:, None] * frame + 4 * competitor[:, None] * other
        self.estimate = {
            "start_sample": 0.0, "sto_samples": 0.0, "cfo_bins": 0.0,
            "channel": [[1, 0], [0, 1]],
            "shared_sp_mrc_channel": [[1, 0], [0, 1]],
        }

    def test_cic_combines_before_rssi_filter_and_recovers_payload(self):
        context = PaperComparisonContext(
            self.samples, [self.estimate], self.cfg, frontend_method="mrc_cic"
        )
        result = context.decode_cic(self.estimate)
        self.assertEqual(result["method"], "mrc_cic")
        self.assertEqual(result["symbol_bins"], self.truth)
        self.assertTrue(result["phy"]["phy_crc_ok"])
        self.assertEqual(result["phy"]["payload_hex"], self.payload.hex())

    def test_cora_preserves_bayesian_detector_and_tnb_crc_after_mrc(self):
        detector = CoRaDetector(ROOT / "compare/CoRa/upstream/cora_v2/artifacts/python/models/dist.pkl")
        symbols = detector.detect(self.samples, self.estimate, self.cfg)
        decoded = TnBBECDecoder().decode(symbols.symbol_bins, self.cfg)
        self.assertEqual(symbols.symbol_bins, self.truth)
        self.assertTrue(decoded.phy_crc_ok)
        self.assertEqual(decoded.payload, self.payload)
        self.assertGreater(symbols.stage_seconds["mrc_preparation"], 0)
        self.assertGreaterEqual(symbols.stage_seconds["total"], symbols.stage_seconds["mrc_preparation"])

    def test_cropped_mrc_preserves_fractional_start_sto_and_cfo(self):
        rng = np.random.default_rng(11)
        samples = rng.normal(size=(2, self.cfg.frame_samples + 600)) + 1j * rng.normal(size=(2, self.cfg.frame_samples + 600))
        estimate = {**self.estimate, "start_sample": 123.25, "sto_samples": .375, "cfo_bins": -2.125}
        combined, local, weights, _ = target_mrc_input(samples, estimate, self.cfg)
        relative = self.cfg.payload_start_symbols * self.cfg.samples_per_symbol
        direct = weights @ compensate_symbol_window(samples, estimate["start_sample"] + relative, estimate["cfo_bins"], self.cfg, sto_samples=estimate["sto_samples"])
        cropped = compensate_symbol_window(combined, local["start_sample"] + relative, estimate["cfo_bins"], self.cfg, sto_samples=estimate["sto_samples"])[0]
        np.testing.assert_allclose(cropped, direct, rtol=1e-5, atol=1e-5)

    def test_cora_default_mrc_works_without_supplied_channel(self):
        frame, _ = build_explicit_frame(self.payload, self.cfg)
        clean = np.asarray([.2, 1j])[:, None] * frame
        estimate = {k:v for k,v in self.estimate.items() if k != "shared_sp_mrc_channel"}
        detector = CoRaDetector(ROOT / "compare/CoRa/upstream/cora_v2/artifacts/python/models/dist.pkl")
        symbols = detector.detect(clean, estimate, self.cfg)
        self.assertEqual(symbols.symbol_bins, self.truth)
        decoded = TnBBECDecoder().decode(symbols.symbol_bins, self.cfg)
        self.assertTrue(decoded.phy_crc_ok)


if __name__ == "__main__":
    unittest.main()
