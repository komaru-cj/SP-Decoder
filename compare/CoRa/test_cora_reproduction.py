#!/usr/bin/env python3
"""Regression tests for the paper-faithful CoRa/TnB reproduction."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for source in (
    ROOT,
    ROOT / "real_collision_experiment/node01_sp_receiver",
    ROOT / "real_collision_experiment/control_usrp",
    Path(__file__).parent,
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from cora_detector import CoRaDetector  # noqa: E402
from lora_phy_decode import (  # noqa: E402
    decode_payload_from_symbol_bins,
    gray_inverse_map,
)
from real_lora_config import RealCollisionLoRaConfig  # noqa: E402
from tnb_bec import TnBBECDecoder  # noqa: E402
from usrp_b210_lora_tx import gray_demap  # noqa: E402


EXPECTED_PAYLOAD = "535002013121010f060000000201c2cdc12f119c"


def known_good_bins() -> tuple[list[int], RealCollisionLoRaConfig]:
    path = (
        ROOT
        / "real_collision_experiment/analysis/fig9_10_12_5s/reports/"
        "run_12012131.json"
    )
    report = json.loads(path.read_text(encoding="utf-8"))
    for candidate in report["candidates"]:
        for method in candidate.get("methods", []):
            if method.get("phy", {}).get("phy_crc_ok"):
                cfg = RealCollisionLoRaConfig(
                    sf=10, bw_hz=125_000.0, sample_rate_hz=750_000.0
                )
                return list(method["symbol_bins"]), cfg
    raise AssertionError("fixture report contains no CRC-valid symbols")


class CoRaReproductionTest(unittest.TestCase):
    def test_published_posterior_and_pmd_hpd_feature_shapes(self) -> None:
        detector = CoRaDetector(
            Path(__file__).parent
            / "upstream/cora_v2/artifacts/python/models/dist.pkl"
        )
        self.assertEqual(detector.posterior.shape, (200, 200))
        n = 256
        tone = np.exp(2j * np.pi * 17 * np.arange(n) / n)[None, :]
        hpd, pmd, magnitude = detector.calculate_features(tone, n)
        self.assertEqual(hpd.shape, (1, n))
        self.assertEqual(pmd.shape, (1, n))
        self.assertEqual(int(np.argmax(magnitude[0])), 17)
        self.assertAlmostEqual(float(pmd[0, 17]), 0.0, places=12)
        self.assertAlmostEqual(float(hpd[0, 17]), 0.0, places=12)

    def test_clean_tnb_bec_matches_existing_phy_payload(self) -> None:
        bins, cfg = known_good_bins()
        result = TnBBECDecoder().decode(bins, cfg)
        self.assertTrue(result.phy_crc_ok)
        self.assertEqual(result.payload.hex(), EXPECTED_PAYLOAD)
        self.assertEqual(result.header_nibbles, [1, 4, 3, 1, 7])

    def test_tnb_bec_repairs_cr1_column_error_standard_decoder_cannot(self) -> None:
        bins, cfg = known_good_bins()
        inverse = gray_inverse_map(cfg)
        corrupted = list(bins)
        # Flip one interleaved CR1 column in the first pure-payload block.
        corrupted[8] = gray_demap(int(inverse[bins[8]]) ^ 1, cfg)
        standard = decode_payload_from_symbol_bins(corrupted, cfg)
        bec = TnBBECDecoder().decode(corrupted, cfg)
        self.assertFalse(standard.phy_crc_ok)
        self.assertTrue(bec.phy_crc_ok)
        self.assertEqual(bec.payload.hex(), EXPECTED_PAYLOAD)
        self.assertGreater(bec.total_candidate_schedules, 1)


if __name__ == "__main__":
    unittest.main()
