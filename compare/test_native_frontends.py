#!/usr/bin/env python3

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = ROOT / "real_collision_experiment/node01_sp_receiver"
for path in (ROOT, RECEIVER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from native_frontends import (
    projected_preamble_native_estimates,
    refine_paper_frontend_from_sp_fine,
    standard_native_estimates,
)


class NativeFrontendSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = SimpleNamespace(
            preamble_len=8,
            samples_per_symbol=16,
        )
        self.samples = np.zeros((2, 256), dtype=np.complex64)

    def test_pcube_uses_multiphase_physical_search_without_sp_residual(self) -> None:
        with patch("native_frontends.pcube_sp_estimates_real", return_value=[]) as detector:
            _, diagnostics = projected_preamble_native_estimates(
                self.samples,
                self.cfg,
                [(0, self.samples.shape[1])],
                method="pcube",
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                max_candidates=100,
                candidates_per_window=16,
                scan_phase_count=8,
            )
        kwargs = detector.call_args.kwargs
        self.assertEqual(kwargs["scan_phase_count"], 8)
        self.assertFalse(kwargs["use_spatial_residual_tracks"])
        self.assertFalse(kwargs["use_integer_alias_branch"])
        self.assertEqual(kwargs["stable_stream_mode"], "physical")
        self.assertTrue(diagnostics["shared_search_only_not_sp_payload_decoder"])

    def test_maloragw_keeps_pca_stream_mode(self) -> None:
        with patch("native_frontends.pcube_sp_estimates_real", return_value=[]) as detector:
            projected_preamble_native_estimates(
                self.samples,
                self.cfg,
                [(0, self.samples.shape[1])],
                method="maloragw",
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                max_candidates=100,
                candidates_per_window=16,
                scan_phase_count=8,
            )
        kwargs = detector.call_args.kwargs
        self.assertEqual(kwargs["scan_phase_count"], 8)
        self.assertFalse(kwargs["use_spatial_residual_tracks"])
        self.assertFalse(kwargs["use_integer_alias_branch"])
        self.assertEqual(kwargs["stable_stream_mode"], "pca")

    def test_lorawan_detector_is_strictly_single_channel_and_non_spatial(self) -> None:
        with patch("native_frontends.pcube_sp_estimates_real", return_value=[]) as detector:
            _, diagnostics = standard_native_estimates(
                self.samples,
                self.cfg,
                [(0, self.samples.shape[1])],
                method="lorawan",
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                max_candidates=100,
                candidates_per_window=16,
                scan_phase_count=8,
            )
        positional_samples = detector.call_args.args[0]
        kwargs = detector.call_args.kwargs
        self.assertEqual(positional_samples.shape[0], 1)
        self.assertEqual(kwargs["stable_stream_mode"], "physical")
        self.assertEqual(kwargs["stable_max_tracks"], 1)
        self.assertFalse(kwargs["use_spatial_residual_tracks"])
        self.assertFalse(kwargs["use_local_projection_tracks"])
        self.assertFalse(kwargs["use_integer_alias_branch"])
        self.assertFalse(diagnostics["sp_candidate_or_sync_reuse"])

    def test_mrc_detector_uses_own_two_channel_non_spatial_frontend(self) -> None:
        with patch("native_frontends.pcube_sp_estimates_real", return_value=[]) as detector:
            _, diagnostics = standard_native_estimates(
                self.samples,
                self.cfg,
                [(0, self.samples.shape[1])],
                method="mrc",
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                max_candidates=100,
                candidates_per_window=16,
                scan_phase_count=8,
            )
        positional_samples = detector.call_args.args[0]
        kwargs = detector.call_args.kwargs
        self.assertEqual(positional_samples.shape[0], 2)
        self.assertEqual(kwargs["stable_stream_mode"], "physical")
        self.assertEqual(kwargs["stable_max_tracks"], 1)
        self.assertFalse(kwargs["use_spatial_residual_tracks"])
        self.assertFalse(kwargs["use_integer_alias_branch"])
        self.assertEqual(diagnostics["physical_input_channels"], 2)

    def test_lorawan_and_mrc_keep_exact_shared_sp_fine_parameters(self) -> None:
        fine = {
            "start_sample": 100.0,
            "sto_samples": 0.25,
            "continuous_cfo_bins": 2.5,
            "cfo_bins_sp": 2.5,
            "channel": [[1.0, 0.0], [0.5, 0.0]],
            "shared_sp_physical_channel": [[1.0, 0.0], [0.5, 0.0]],
        }
        for method in ("lorawan", "mrc"):
            estimates, diagnostics = refine_paper_frontend_from_sp_fine(
                self.samples,
                self.cfg,
                [fine],
                method=method,
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                candidates_per_window=16,
            )
            self.assertEqual(estimates[0]["start_sample"], 100.0)
            self.assertEqual(estimates[0]["sto_samples"], 0.25)
            self.assertEqual(estimates[0]["cfo_bins_sp"], 2.5)
            self.assertFalse(estimates[0]["paper_method_refinement_applied"])
            self.assertFalse(
                estimates[0]["paper_method_parameter_estimation_applied"]
            )
            self.assertTrue(diagnostics["shared_sp_fine_sync_and_parameters"])

    def test_cic_refines_from_exact_sp_fine_seed_and_records_delta(self) -> None:
        fine = {
            "start_sample": 100.0,
            "sto_samples": 0.25,
            "continuous_cfo_bins": 2.5,
            "cfo_bins_sp": 2.5,
            "channel": [[1.0, 0.0], [0.5, 0.0]],
        }
        native = {
            "start_sample": 101.0,
            "sto_samples": 0.25,
            "continuous_cfo_bins": 3.0,
            "cfo_bins": 3.0,
            "channel": [[1.0, 0.0], [0.5, 0.0]],
            "confidence": 10.0,
        }
        with patch(
            "native_frontends.cic_native_estimates",
            return_value=([native], {"paper_frontend": "test_cic"}),
        ):
            estimates, diagnostics = refine_paper_frontend_from_sp_fine(
                self.samples,
                self.cfg,
                [fine],
                method="mrc_cic",
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                candidates_per_window=16,
            )
        self.assertTrue(estimates[0]["shared_sp_fine_sync_seed"])
        self.assertTrue(estimates[0]["paper_method_refinement_applied"])
        self.assertAlmostEqual(
            estimates[0]["paper_refinement_start_delta_samples"], 1.0
        )
        self.assertAlmostEqual(estimates[0]["paper_refinement_cfo_delta_bins"], 0.5)
        self.assertEqual(diagnostics["paper_refinement_success_count"], 1)
        self.assertEqual(diagnostics["paper_refinement_fallback_count"], 0)

    def test_paper_refinement_failure_falls_back_to_same_sp_candidate(self) -> None:
        fine = {
            "start_sample": 100.0,
            "sto_samples": 0.25,
            "continuous_cfo_bins": 2.5,
            "channel": [[1.0, 0.0], [0.5, 0.0]],
        }
        with patch(
            "native_frontends.cic_native_estimates",
            return_value=([], {"paper_frontend": "test_cic"}),
        ):
            estimates, diagnostics = refine_paper_frontend_from_sp_fine(
                self.samples,
                self.cfg,
                [fine],
                method="mrc_cic",
                threshold=3.0,
                cfo_min=-32.0,
                cfo_max=32.0,
                candidates_per_window=16,
            )
        self.assertEqual(len(estimates), 1)
        self.assertEqual(estimates[0]["start_sample"], 100.0)
        self.assertFalse(estimates[0]["paper_method_refinement_applied"])
        self.assertEqual(diagnostics["paper_refinement_fallback_count"], 1)


if __name__ == "__main__":
    unittest.main()
