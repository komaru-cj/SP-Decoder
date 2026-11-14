#!/usr/bin/env python3

import inspect
import unittest
from unittest.mock import patch

import numpy as np

from audit_fine_sync_database import audit
from build_fine_sync_database import (
    ANALYSIS_DURATION_S,
    ANONYMOUS_FINE_SYNC_SCHEMA,
    candidate_count_audit,
    certify_global_proposal,
    deduplicate_physical_candidates,
    discover_global_physical_candidates,
    plausible_for_timing_refinement,
    scheduled_packet_count_reference,
)


def candidate(
    start: float,
    cfo: float,
    channel: tuple[complex, complex],
    structure_score: float,
    *,
    discovery_pass: int = 0,
) -> dict:
    return {
        "start_sample": float(start),
        "sto_samples": 0.0,
        "cfo_bins": float(cfo),
        "continuous_cfo_bins": float(cfo),
        "channel": [[value.real, value.imag] for value in channel],
        "power": float(sum(abs(value) ** 2 for value in channel)),
        "confidence": 2_000.0,
        "preamble_ratio": 2_000.0,
        "sync_confidence": 128.0,
        "sfd_confidence": 256.0,
        "structure_score": float(structure_score),
        "structure_certified": True,
        "candidate_evidence": "strict_structural_certificate",
        "sfd_anchor_score": 1.0,
        "discovery_pass": int(discovery_pass),
    }


def valid_database(packets: list[dict]) -> dict:
    return {
        "schema": ANONYMOUS_FINE_SYNC_SCHEMA,
        "run_id": "synthetic",
        "sample_rate_hz": 1_000.0,
        "bandwidth_hz": 1_000.0,
        "spreading_factor": 4,
        "window": {"duration_s": ANALYSIS_DURATION_S},
        "candidate_discovery": {
            "scope": "global_full_window",
            "manifest_schedule_exposed_to_detector": False,
            "node_timing_calibration": False,
            "planned_start_search_windows": False,
            "score_truncation": False,
            "candidate_overflow_policy": "retain_excess_candidates_without_truncation",
            "candidate_admission_policy": "sfd_anchored_high_recall",
        },
        "scheduled_packet_count_reference": len(packets),
        "detected_physical_candidate_count": len(packets),
        "packets": packets,
    }


class FineSyncPhysicalCandidateTest(unittest.TestCase):
    def test_detector_api_cannot_receive_manifest_or_schedules(self) -> None:
        parameters = inspect.signature(discover_global_physical_candidates).parameters
        self.assertNotIn("manifest", parameters)
        self.assertNotIn("schedules", parameters)
        self.assertNotIn("planned_starts", parameters)

    def test_spatial_nulling_rescans_until_no_new_physical_candidate(self) -> None:
        first = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 20.0)
        second = candidate(2_000.0, 4.0, (0.0 + 0.0j, 1.0 + 0.0j), 18.0)
        third = candidate(3_000.0, 5.0, (1.0 + 0.0j, 1.0 + 0.0j), 16.0)
        scripted_rows = [
            [first],
            [dict(first, discovery_pass=1), second],
            [dict(second, discovery_pass=2), third],
            [dict(first, discovery_pass=3), dict(third, discovery_pass=3)],
        ]
        prior_counts: list[int] = []

        def fake_global_pass(
            _samples: np.ndarray,
            _cfg: object,
            *,
            cfo_limit: float,
            discovery_pass: int,
            prior_candidates: list[dict],
        ) -> tuple[list[dict], dict]:
            self.assertEqual(cfo_limit, 32.0)
            prior_counts.append(len(prior_candidates))
            return scripted_rows[discovery_pass], {"pass": discovery_pass}

        class SyntheticConfig:
            samples_per_symbol = 100

        with patch(
            "build_fine_sync_database.global_detection_pass",
            side_effect=fake_global_pass,
        ):
            physical, diagnostics = discover_global_physical_candidates(
                np.zeros((2, 8), dtype=np.complex64),
                SyntheticConfig(),
                cfo_limit=32.0,
            )

        self.assertEqual(prior_counts, [0, 1, 2, 3])
        self.assertEqual(len(physical), 3)
        self.assertEqual(
            [row["new_physical_candidate_count"] for row in diagnostics],
            [1, 1, 1, 0],
        )
        self.assertEqual(
            [row["cumulative_physical_candidate_count"] for row in diagnostics],
            [1, 2, 3, 3],
        )

    def test_spatial_nulling_accepts_recertification_consolidation(self) -> None:
        first = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 20.0)
        second = candidate(2_000.0, 4.0, (0.0 + 0.0j, 1.0 + 0.0j), 18.0)
        scripted_rows = [[first, second], [dict(first, discovery_pass=1)]]

        def fake_global_pass(
            _samples: np.ndarray,
            _cfg: object,
            *,
            cfo_limit: float,
            discovery_pass: int,
            prior_candidates: list[dict],
        ) -> tuple[list[dict], dict]:
            self.assertEqual(cfo_limit, 32.0)
            return scripted_rows[discovery_pass], {"pass": discovery_pass}

        class SyntheticConfig:
            samples_per_symbol = 100

        with patch(
            "build_fine_sync_database.global_detection_pass",
            side_effect=fake_global_pass,
        ), patch(
            "build_fine_sync_database.deduplicate_physical_candidates",
            side_effect=[[first, second], [first]],
        ):
            physical, diagnostics = discover_global_physical_candidates(
                np.zeros((2, 8), dtype=np.complex64),
                SyntheticConfig(),
                cfo_limit=32.0,
            )

        self.assertEqual(physical, [first])
        self.assertEqual(
            [row["new_physical_candidate_count"] for row in diagnostics],
            [2, 0],
        )
        self.assertEqual(
            [row["candidate_consolidation_count"] for row in diagnostics],
            [0, 1],
        )

    def test_auditor_accepts_global_anonymous_v2_database(self) -> None:
        database = valid_database(
            [candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 20.0)]
        )
        self.assertEqual(audit(database), [])

    def test_auditor_accepts_plausible_sfd_anchored_candidate(self) -> None:
        weak = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 1.0)
        weak.update(
            {
                "preamble_ratio": 1.0,
                "sync_confidence": 1.0,
                "sfd_confidence": 1.0,
                "structure_certified": False,
                "candidate_evidence": "plausible_preamble_sfd_anchor",
                "sfd_anchor_score": 0.5,
            }
        )
        self.assertEqual(audit(valid_database([weak])), [])

    def test_sfd_anchored_weak_candidate_is_retained(self) -> None:
        class SyntheticConfig:
            samples_per_symbol = 100
            frame_samples = 500

        weak_values = {
            "preamble_ratio": 1.0,
            "sync_confidence": 1.0,
            "sfd_confidence": 1.0,
            "frame_structure_score": 0.0,
        }
        with patch(
            "build_fine_sync_database.sfd_anchored_start_cfo_refine",
            return_value=(100.0, 3.0, 0.0, 0.5, 0.0, 0.0),
        ), patch(
            "build_fine_sync_database.certificate_values_at",
            return_value=(
                weak_values,
                np.asarray([1.0 + 0.0j, 0.2 + 0.1j]),
                3,
            ),
        ):
            row = certify_global_proposal(
                np.zeros((2, 1_000), dtype=np.complex64),
                SyntheticConfig(),
                candidate(100.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 1.0),
                cfo_limit=32.0,
                discovery_pass=0,
            )

        self.assertIsNotNone(row)
        assert row is not None
        self.assertFalse(row["structure_certified"])
        self.assertEqual(row["candidate_evidence"], "plausible_preamble_sfd_anchor")

    def test_exact_alias_keeps_only_best_structure_certificate(self) -> None:
        weak_alias = candidate(
            1_000.0,
            3.0,
            (1.0 + 0.0j, 0.2 + 0.1j),
            14.0,
            discovery_pass=0,
        )
        strong_alias = candidate(
            1_001.0,
            3.1,
            (2.0 + 0.0j, 0.4 + 0.2j),
            22.0,
            discovery_pass=1,
        )

        physical = deduplicate_physical_candidates(
            [weak_alias, strong_alias],
            n_symbol=100,
        )

        self.assertEqual(len(physical), 1)
        self.assertEqual(physical[0]["structure_score"], 22.0)
        self.assertEqual(physical[0]["alias_support_count"], 2)
        self.assertEqual(physical[0]["alias_discovery_passes"], [0, 1])

    def test_close_weak_packet_with_different_cfo_is_never_discarded(self) -> None:
        strong = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 40.0)
        weak = candidate(1_002.0, 4.2, (1.0 + 0.0j, 0.2 + 0.1j), 13.1)

        physical = deduplicate_physical_candidates([strong, weak], n_symbol=100)

        self.assertEqual(len(physical), 2)
        self.assertEqual(sorted(row["structure_score"] for row in physical), [13.1, 40.0])

    def test_close_weak_packet_with_different_channel_is_never_discarded(self) -> None:
        strong = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 40.0)
        weak = candidate(1_002.0, 3.1, (0.0 + 0.0j, 1.0 + 0.0j), 13.1)

        physical = deduplicate_physical_candidates([strong, weak], n_symbol=100)

        self.assertEqual(len(physical), 2)

    def test_close_weak_packet_with_distinct_start_is_never_discarded(self) -> None:
        strong = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 40.0)
        weak = candidate(1_010.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 13.1)

        physical = deduplicate_physical_candidates([strong, weak], n_symbol=100)

        self.assertEqual(len(physical), 2)

    def test_close_weak_packet_with_small_distinct_cfo_is_never_discarded(self) -> None:
        strong = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 40.0)
        weak = candidate(1_001.0, 3.3, (1.0 + 0.0j, 0.2 + 0.1j), 13.1)

        physical = deduplicate_physical_candidates([strong, weak], n_symbol=100)

        self.assertEqual(len(physical), 2)

    def test_integer_cfo_alias_merges_only_when_spatially_indistinguishable(self) -> None:
        first = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.2 + 0.1j), 20.0)
        branch_alias = candidate(1_001.0, 4.0, (2.0 + 0.0j, 0.4 + 0.2j), 22.0)
        weak_separable = candidate(1_001.0, 4.0, (0.0 + 0.0j, 1.0 + 0.0j), 14.0)

        physical = deduplicate_physical_candidates(
            [first, branch_alias, weak_separable],
            n_symbol=100,
        )

        self.assertEqual(len(physical), 2)
        self.assertEqual(
            sorted(row["structure_score"] for row in physical),
            [14.0, 22.0],
        )

    def test_scalar_upper_bound_ignores_packet_timestamps(self) -> None:
        manifest = {
            "config": {"duration_ms": 20_000},
            "expected_node_schedules": {
                "1": {"tx_count": 79, "tx_start_ms_from_traffic_begin": [1]},
                "2": {"tx_count": 84, "tx_start_ms_from_traffic_begin": [19_999]},
            },
        }

        self.assertEqual(
            scheduled_packet_count_reference(manifest, duration_s=ANALYSIS_DURATION_S),
            163,
        )
        manifest["expected_node_schedules"]["1"]["tx_start_ms_from_traffic_begin"] = [9_999]
        self.assertEqual(
            scheduled_packet_count_reference(manifest, duration_s=ANALYSIS_DURATION_S),
            163,
        )

    def test_complete_link_does_not_chain_distinct_tracks(self) -> None:
        first = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 20.0)
        middle = candidate(1_004.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 19.0)
        last = candidate(1_008.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 18.0)

        physical = deduplicate_physical_candidates(
            [first, middle, last],
            n_symbol=100,
        )

        self.assertEqual(len(physical), 2)

    def test_candidate_count_can_exceed_scheduled_reference(self) -> None:
        rows = [
            candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 40.0),
            candidate(2_000.0, 4.0, (0.0 + 0.0j, 1.0 + 0.0j), 13.1),
        ]
        audit_row = candidate_count_audit(rows, 1, run_name="synthetic")
        self.assertEqual(len(rows), 2)
        self.assertEqual(audit_row["excess_candidate_count"], 1)
        self.assertEqual(audit_row["detected_minus_scheduled_reference"], 1)

    def test_timing_grid_requires_independent_local_iq_evidence(self) -> None:
        plausible = {
            "preamble_ratio": 8.0,
            "sync_confidence": 2.0,
            "sfd_confidence": 2.0,
        }
        self.assertTrue(plausible_for_timing_refinement(plausible))
        for field in plausible:
            rejected = dict(plausible)
            rejected[field] = 0.0
            self.assertFalse(plausible_for_timing_refinement(rejected))

    def test_auditor_rejects_any_identity_or_timing_prior_field(self) -> None:
        row = candidate(1_000.0, 3.0, (1.0 + 0.0j, 0.0 + 0.0j), 20.0)
        row["node_id"] = 7
        row["planned_start_sample"] = 900.0

        errors = audit(valid_database([row]))

        self.assertTrue(any("forbidden prior fields" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
