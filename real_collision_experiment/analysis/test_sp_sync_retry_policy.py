#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


RECEIVER_DIR = Path(__file__).resolve().parents[1] / "node01_sp_receiver"
if str(RECEIVER_DIR) not in sys.path:
    sys.path.insert(0, str(RECEIVER_DIR))

from sp_node01_receiver import sp_sync_retry_gate  # noqa: E402


class SpSyncRetryPolicyTest(unittest.TestCase):
    def test_strict_header_preserves_full_trial_budget(self) -> None:
        passed, policy, budget, reason = sp_sync_retry_gate(
            {"preamble_ratio": 12.0, "sync_confidence": 12.0, "sfd_confidence": 12.0},
            {"phy": {"header_nibbles": [1, 4, 3, 1, 7]}},
            retry_policy="strict_header",
            max_sync_trials=32,
            relaxed_max_trials=8,
        )

        self.assertTrue(passed)
        self.assertEqual(policy, "strict_header")
        self.assertEqual(budget, 32)
        self.assertIsNone(reason)

    def test_relaxed_structure_retries_plausible_header_miss_with_short_budget(self) -> None:
        estimate = {"preamble_ratio": 12.0, "sync_confidence": 3.0, "sfd_confidence": 3.0}
        result = {"phy": {"header_nibbles": [8, 2, 0, 7, 6]}}

        strict = sp_sync_retry_gate(
            estimate,
            result,
            retry_policy="strict_header",
            max_sync_trials=32,
            relaxed_max_trials=8,
        )
        relaxed = sp_sync_retry_gate(
            estimate,
            result,
            retry_policy="relaxed_structure",
            max_sync_trials=32,
            relaxed_max_trials=8,
        )

        self.assertEqual(strict, (False, None, 1, "missing_explicit_header_or_structure_certificate"))
        self.assertEqual(relaxed, (True, "relaxed_structure", 8, None))

    def test_relaxed_structure_rejects_weak_preamble_sfd_evidence(self) -> None:
        self.assertEqual(
            sp_sync_retry_gate(
                {"preamble_ratio": 12.0, "sync_confidence": 2.9, "sfd_confidence": 5.0},
                {"phy": {"header_nibbles": [8, 2, 0, 7, 6]}},
                retry_policy="relaxed_structure",
                max_sync_trials=32,
                relaxed_max_trials=8,
            ),
            (False, None, 1, "missing_relaxed_preamble_sfd_support"),
        )


if __name__ == "__main__":
    unittest.main()
