#!/usr/bin/env python3

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from decode_fig9_10_12_middle5s import (
    estimate_traffic_start_from_control_energy,
    middle_business_window,
    validate_fine_sync_database,
)
from formal_window import FORMAL_ANALYSIS_DURATION_S


class BusinessMiddleWindowTest(unittest.TestCase):
    def test_middle_window_is_centered_on_business_not_capture(self) -> None:
        self.assertEqual(
            middle_business_window(19.0, 20.0, FORMAL_ANALYSIS_DURATION_S),
            (26.5, FORMAL_ANALYSIS_DURATION_S),
        )
        with self.assertRaises(ValueError):
            middle_business_window(19.0, 4.0, FORMAL_ANALYSIS_DURATION_S)

    def test_control_event_energy_alignment_rejects_continuous_data_region(self) -> None:
        rate = 1_000
        duration_s = 40
        samples = rate * duration_s
        rng = np.random.default_rng(20260803)
        raw = rng.integers(-4, 5, size=(samples, 4), dtype=np.int16)
        first_rf_s = 5.0
        event_offsets = [0.0, 1.0, 2.0, 3.0, 4.0, 8.0, 8.6, 9.2, 9.8, 10.4]
        event_durations = [0.50] * 5 + [0.35] * 5
        for offset, event_duration in zip(event_offsets, event_durations):
            start = int((first_rf_s + offset) * rate)
            end = int((first_rf_s + offset + event_duration) * rate)
            raw[start:end] += rng.integers(-700, 701, size=(end - start, 4), dtype=np.int16)
        # The later node-business region is stronger and nearly continuous;
        # alignment must still choose the event-versus-gap control template.
        data_start = int(19.0 * rate)
        raw[data_start:] += rng.integers(
            -2_000, 2_001, size=(samples - data_start, 4), dtype=np.int16
        )

        base = datetime(2026, 8, 3, tzinfo=timezone.utc)
        events = []
        for index, offset in enumerate(event_offsets):
            events.append(
                {
                    "type": "CONFIG_ENQUEUED" if index < 5 else "START_ENQUEUED",
                    "utc": (base + timedelta(seconds=offset)).isoformat(),
                }
            )
        manifest = {
            "events": events,
            "expected_traffic_begin_utc": (base + timedelta(seconds=14)).isoformat(),
            "config": {"duration_ms": 20_000},
            "control": {"start_airtime_s": 0.35},
        }
        metadata = {
            "samples_per_channel": samples,
            "actual": {"rate_hz": rate},
            "updated_utc": "synthetic",
        }
        with tempfile.TemporaryDirectory() as directory:
            iq = Path(directory) / "run.sc16"
            raw.tofile(iq)
            traffic_start, audit = estimate_traffic_start_from_control_energy(
                iq,
                metadata,
                manifest,
                analysis_duration_s=FORMAL_ANALYSIS_DURATION_S,
            )
        self.assertAlmostEqual(traffic_start, 19.0, delta=0.06)
        self.assertGreater(audit["best_log_contrast_score"], 1.6)

    def test_fine_sync_database_must_match_the_formal_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "run_0203c111.json"
            database.write_text(
                json.dumps(
                    {
                        "schema": "fine_sync_anonymous_physical_v2",
                        "run_id": "run_0203c111",
                        "window": {
                            "analysis_start_s": 24.0,
                            "duration_s": FORMAL_ANALYSIS_DURATION_S,
                        },
                        "candidate_discovery": {
                            "scope": "global_full_window",
                            "manifest_schedule_exposed_to_detector": False,
                            "node_timing_calibration": False,
                            "planned_start_search_windows": False,
                            "score_truncation": False,
                            "candidate_overflow_policy": "fail_closed_without_truncation",
                        },
                        "packets": [{"start_sample": 1.0}],
                    }
                ),
                encoding="utf-8",
            )
            validate_fine_sync_database(
                database,
                run_name="run_0203c111",
                analysis_start_s=24.0,
                duration_s=FORMAL_ANALYSIS_DURATION_S,
            )
            with self.assertRaisesRegex(ValueError, "does not match decode window"):
                validate_fine_sync_database(
                    database,
                    run_name="run_0203c111",
                    analysis_start_s=24.0,
                    duration_s=FORMAL_ANALYSIS_DURATION_S - 1.0,
                )

    def test_formal_decoder_rejects_stale_v1_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "run_0203c111.json"
            database.write_text(
                json.dumps(
                    {
                        "schema": "fine_sync_anonymous_physical_v1",
                        "run_id": "run_0203c111",
                        "window": {
                            "analysis_start_s": 24.0,
                            "duration_s": FORMAL_ANALYSIS_DURATION_S,
                        },
                        "packets": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "global anonymous v2"):
                validate_fine_sync_database(
                    database,
                    run_name="run_0203c111",
                    analysis_start_s=24.0,
                    duration_s=FORMAL_ANALYSIS_DURATION_S,
                )


if __name__ == "__main__":
    unittest.main()
