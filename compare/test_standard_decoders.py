#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = ROOT / "real_collision_experiment/node01_sp_receiver"
for path in (ROOT, RECEIVER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import real_packet_decoders
from real_packet_decoders import PaperComparisonContext, PhysicalEvidencePayloadCache


def return_bins(method, bins, margins, diagnostics):
    return {"method": method, "symbol_bins": list(bins), "diagnostics": diagnostics}


class StrictStandardDecoderTests(unittest.TestCase):
    @patch.object(real_packet_decoders, '_result', side_effect=return_bins)
    @patch.object(real_packet_decoders, '_local_peaks', return_value=np.asarray([17,71]))
    @patch.object(real_packet_decoders, '_physical_spectra')
    def test_default_pcube_v3_recovers_peak_rejected_by_legacy(self, spectra, peaks, result):
        context = PaperComparisonContext.__new__(PaperComparisonContext)
        context.physical_samples = np.zeros((2,128),dtype=np.complex64)
        context.estimates = [dict(start_sample=0.)]
        context.cfg = SimpleNamespace(payload_symbol_count=38,preamble_len=8,frame_samples=128)
        context._physical_group_representatives = [0]
        context._physical_group_by_index = [0]
        context._pdoas = [0.]
        context._channels = [np.ones(2,dtype=complex)]
        rng = np.random.default_rng(945)
        f = (rng.normal(size=(2,128))+1j*rng.normal(size=(2,128)))/np.sqrt(2)
        f[:,17] = [10*np.exp(.53j),10]
        f[:,71] = [2,2]
        spectra.return_value = f
        default = context.decode_pcube(context.estimates[0])
        legacy = context.decode_pcube(context.estimates[0],grouping_policy='legacy_fixed_gate')
        self.assertEqual(default['symbol_bins'],[17]*38)
        self.assertEqual(legacy['symbol_bins'],[71]*38)
        self.assertEqual(default['diagnostics']['grouping']['policy'],real_packet_decoders.DEFAULT_PCUBE_POLICY)

    def test_standalone_pcube_delegates_without_scoring_truth(self):
        from unittest.mock import Mock
        from compare.PCube.evaluate_pcube import decode_pcube
        context=Mock()
        context.decode_pcube.return_value={'symbol_bins':[17]}
        estimate={'start_sample':0.}
        result=decode_pcube(None,object(),estimate,object(),None,context=context)
        self.assertEqual(result,[17])
        context.decode_pcube.assert_called_once_with(estimate)

    def setUp(self) -> None:
        self.context = PaperComparisonContext.__new__(PaperComparisonContext)
        self.context.physical_samples = np.zeros((2, 64), dtype=np.complex64)
        self.context.estimates = [{"start_sample": 0.0}]
        self.context.cfg = SimpleNamespace(payload_symbol_count=1)
        self.context._channels = [np.asarray([1.0 + 0.0j, 1.0 + 0.0j])]

    @patch.object(real_packet_decoders, "_result", side_effect=return_bins)
    @patch.object(real_packet_decoders, "_physical_spectra")
    def test_lorawan_uses_only_ch0_top_one(self, spectra, _result) -> None:
        spectra.return_value = np.asarray([[1.0, 2.0, 9.0, 3.0]], dtype=np.complex128)
        decoded = self.context.decode_lorawan(self.context.estimates[0])
        self.assertEqual(decoded["symbol_bins"], [2])
        self.assertEqual(spectra.call_args.args[0].shape[0], 1)
        self.assertEqual(decoded["diagnostics"]["cfo_retry_count"], 0)

    @patch.object(real_packet_decoders, "_result", side_effect=return_bins)
    @patch.object(real_packet_decoders, "_physical_spectra")
    def test_mrc_fixed_weights_then_top_one(self, spectra, _result) -> None:
        # Bin 0 is strongest on either antenna separately but cancels under
        # the independently estimated [1, 1] channel.  Fixed MRC must choose
        # coherent bin 1.
        spectra.return_value = np.asarray(
            [[10.0, 6.0, 0.0, 0.0], [-10.0, 6.0, 0.0, 0.0]],
            dtype=np.complex128,
        )
        decoded = self.context.decode_mrc(self.context.estimates[0])
        self.assertEqual(decoded["symbol_bins"], [1])
        self.assertEqual(decoded["diagnostics"]["cfo_retry_count"], 0)
        self.assertFalse(decoded["diagnostics"]["symbol_repair"])

    @patch.object(real_packet_decoders, "_preamble_measurements")
    def test_mrc_context_uses_shared_sp_channel_without_reestimating(self, measure) -> None:
        estimate = {
            "start_sample": 0.0,
            "shared_sp_mrc_channel": [[1.0, 0.0], [0.25, -0.5]],
        }
        context = PaperComparisonContext(
            np.zeros((2, 64), dtype=np.complex64),
            [estimate],
            SimpleNamespace(),
            frontend_method="mrc",
        )
        measure.assert_not_called()
        np.testing.assert_allclose(
            context._channels[0],
            np.asarray([1.0 + 0.0j, 0.25 - 0.5j]),
        )

    @patch.object(real_packet_decoders, "_preamble_measurements")
    def test_pcube_reuses_its_matched_local_refinement_channel(self, measure) -> None:
        estimate = {
            "start_sample": 0.0,
            "channel": [[1.0, 0.0], [0.25, -0.5]],
            "paper_method_refinement_applied": True,
        }
        context = PaperComparisonContext(
            np.zeros((2, 64), dtype=np.complex64),
            [estimate],
            SimpleNamespace(),
            frontend_method="pcube",
        )
        measure.assert_not_called()
        self.assertEqual(
            context.cache_audit()[
                "reused_method_native_local_refinement_preamble_channels"
            ],
            1,
        )

    @patch.object(real_packet_decoders, "_result", side_effect=return_bins)
    @patch.object(real_packet_decoders, "_local_peaks")
    @patch.object(real_packet_decoders, "_physical_spectra")
    def test_legacy_pcube_gate_retained_for_ablation(self, spectra, peaks, _result) -> None:
        context = PaperComparisonContext.__new__(PaperComparisonContext)
        context.physical_samples = np.zeros((2, 64), dtype=np.complex64)
        context.estimates = [{"start_sample": 0.0}]
        context.cfg = SimpleNamespace(payload_symbol_count=1)
        context._pdoas = [0.0]
        spectrum = np.zeros((2, 64), dtype=np.complex128)
        # Bin 15 has slightly larger rotated-I evidence but a clearly wrong
        # PDoA; bin 39 belongs to the target cluster.
        spectrum[0, 15] = 100.0
        spectrum[1, 15] = 100.0 * np.exp(-1j * 1.0)
        spectrum[0, 39] = 90.0
        spectrum[1, 39] = 90.0
        spectra.return_value = spectrum
        peaks.return_value = np.asarray([15, 39], dtype=np.int64)
        decoded = context.decode_pcube(context.estimates[0],grouping_policy='legacy_fixed_gate')
        self.assertEqual(decoded["symbol_bins"], [39])

    @patch.object(real_packet_decoders, "lora_symbol_fft")
    @patch.object(real_packet_decoders, "_physical_mixed")
    def test_payload_cache_requires_same_physical_evidence(self, mixed, fft) -> None:
        cfg = SimpleNamespace(
            payload_start_symbols=0,
            samples_per_symbol=4,
            m=4,
        )
        samples = np.zeros((2, 16), dtype=np.complex64)
        mixed.return_value = np.ones((2, 4), dtype=np.complex64)
        fft.return_value = np.ones(4, dtype=np.complex64)
        cache = PhysicalEvidencePayloadCache()
        first = {
            "_physical_evidence_key": ("anonymous", 1),
            "start_sample": 0.0,
            "cfo_bins": 0.0,
            "channel": [[1.0, 0.0], [0.0, 1.0]],
        }
        same_physical_copy = dict(first)
        other_candidate = {**first, "_physical_evidence_key": ("anonymous", 2)}

        cache.spectra_for(samples, first, cfg, 0)
        cache.spectra_for(samples, same_physical_copy, cfg, 0)
        cache.spectra_for(samples, other_candidate, cfg, 0)

        self.assertEqual(fft.call_count, 4)
        self.assertEqual(cache.spectrum_hits, 1)
        self.assertEqual(cache.spectrum_misses, 2)


if __name__ == "__main__":
    unittest.main()
