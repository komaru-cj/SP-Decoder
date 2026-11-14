#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sp_detection_frontend import (
    phase_coherent_preamble_offset_branches,
    preamble_run_support_counts,
    sfd_pair_anchor_peak_indices,
    sfd_paired_peak_indices,
)


class SfdPairPrefilterTest(unittest.TestCase):
    def test_keeps_both_members_of_a_valid_sfd_pair(self) -> None:
        peaks = np.asarray([100, 1_104, 2_500], dtype=np.int64)

        paired = sfd_paired_peak_indices(
            peaks,
            n_symbol=1_000,
            tolerance_samples=8,
        )

        np.testing.assert_array_equal(paired, np.asarray([100, 1_104]))

    def test_rejects_isolated_downchirp_peaks(self) -> None:
        peaks = np.asarray([100, 900, 2_500], dtype=np.int64)

        paired = sfd_paired_peak_indices(
            peaks,
            n_symbol=1_000,
            tolerance_samples=8,
        )

        self.assertEqual(paired.size, 0)

    def test_keeps_overlapping_structural_pairs_without_ranking(self) -> None:
        peaks = np.asarray([100, 1_100, 2_100, 7_000], dtype=np.int64)

        paired = sfd_paired_peak_indices(
            peaks,
            n_symbol=1_000,
            tolerance_samples=2,
        )

        np.testing.assert_array_equal(paired, np.asarray([100, 1_100, 2_100]))

    def test_uses_only_the_first_sfd_downchirp_as_a_start_anchor(self) -> None:
        peaks = np.asarray([100, 1_104, 2_500], dtype=np.int64)

        anchors = sfd_pair_anchor_peak_indices(
            peaks,
            n_symbol=1_000,
            tolerance_samples=8,
        )

        np.testing.assert_array_equal(anchors, np.asarray([100]))

    def test_preamble_support_keeps_a_certified_head_without_scoring(self) -> None:
        support = preamble_run_support_counts(
            np.asarray([1_000, 2_002, 3_001], dtype=np.int64),
            np.asarray([7_000], dtype=np.int64),
            n_symbol=1_000,
            tolerance_samples=8,
            min_backtrack_symbols=3,
            max_backtrack_symbols=6,
        )

        np.testing.assert_array_equal(support, np.asarray([3]))

    def test_preamble_support_rejects_an_isolated_sfd_pair(self) -> None:
        support = preamble_run_support_counts(
            np.asarray([1_000, 3_900], dtype=np.int64),
            np.asarray([7_000], dtype=np.int64),
            n_symbol=1_000,
            tolerance_samples=8,
            min_backtrack_symbols=3,
            max_backtrack_symbols=6,
        )

        np.testing.assert_array_equal(support, np.asarray([1]))

    def test_phase_coherent_branches_keep_distinct_cfo_offsets(self) -> None:
        branches = phase_coherent_preamble_offset_branches(
            np.asarray([1_000, 1_020, 2_000, 2_020, 3_000, 3_020]),
            np.asarray([7_000], dtype=np.int64),
            n_symbol=1_000,
            phase_tolerance_samples=2,
            min_backtrack_symbols=3,
            max_backtrack_symbols=6,
            min_run_symbols=3,
        )

        self.assertEqual(branches, [[0, 20]])


if __name__ == "__main__":
    unittest.main()
