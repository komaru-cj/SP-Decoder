#!/usr/bin/env python3

import struct
import unittest

from usrp_run_controller import parse_experiment_tag
from protocol import (
    PHY_PROFILES,
    TRAFFIC_PROFILE_DUTY,
    TRAFFIC_LOADS,
    RunConfig,
    active_nodes_to_mask,
    build_data_payload,
    config_crc,
    crc16_ccitt,
    decode_data_payload,
    encode_config,
    encode_start,
    expected_tx_schedule_ms,
    firmware_mean_idle_gap_ms,
    lora_time_on_air_ms,
    recommended_receiver_sample_rate_hz,
)


class ProtocolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = RunConfig(
            run_id=0x20260719,
            active_mask=active_nodes_to_mask(list(range(1, 16))),
            num_active_nodes=15,
            phy_profile_id=5,
            traffic_profile_id=1,
            node_tx_power_dbm=2,
            duration_ms=20_000,
            warmup_ms=2_000,
            global_seed=0x12345678,
            payload_seed=0x89ABCDEF,
        )

    def test_config_frame(self) -> None:
        frame = encode_config(self.config)
        self.assertEqual(len(frame), 34)
        self.assertEqual(frame[:2], b"SP")
        self.assertEqual(config_crc(frame), crc16_ccitt(frame[:-2]))

    def test_active_population_must_match_active_mask(self) -> None:
        config = RunConfig(
            **{
                **self.config.__dict__,
                "active_mask": active_nodes_to_mask([1, 2, 3]),
                "num_active_nodes": 15,
                "traffic_profile_id": 5,
            }
        )
        with self.assertRaises(ValueError):
            encode_config(config)

    def test_extended_traffic_profile_ids_match_firmware_contract(self) -> None:
        self.assertEqual(
            TRAFFIC_LOADS,
            (
                0.25, 0.5, 1.0, 1.5, 2.0, 3.0,
                0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.35, 1.8, 2.25, 3.75,
                4.5, 6.0, 7.5, 1.4,
            ),
        )
        self.assertEqual(TRAFFIC_PROFILE_DUTY, {1: 0.25, 2: 0.5, 3: 0.75})
        self.assertEqual(PHY_PROFILES[5], {"sf": 10, "bandwidth_hz": 250_000})
        self.assertEqual(PHY_PROFILES[7], {"sf": 8, "bandwidth_hz": 500_000})
        self.assertEqual(PHY_PROFILES[8], {"sf": 10, "bandwidth_hz": 500_000})
        self.assertEqual(PHY_PROFILES[9], {"sf": 12, "bandwidth_hz": 500_000})
        self.assertEqual(recommended_receiver_sample_rate_hz(5), 750_000)
        self.assertEqual(recommended_receiver_sample_rate_hz(7), 1_000_000)

    def test_crc_standard_vector(self) -> None:
        self.assertEqual(crc16_ccitt(b"123456789"), 0x29B1)

    def test_start_frame(self) -> None:
        config_frame = encode_config(self.config)
        frame = encode_start(self.config.run_id, config_crc(config_frame), start_delay_ms=3670)
        self.assertEqual(len(frame), 18)
        self.assertEqual(struct.unpack_from("<I", frame, 6)[0], self.config.run_id)
        self.assertEqual(struct.unpack_from("<I", frame, 12)[0], 3670)
        self.assertEqual(struct.unpack_from("<H", frame, 16)[0], crc16_ccitt(frame[:-2]))

    def test_airtime(self) -> None:
        self.assertAlmostEqual(lora_time_on_air_ms(20), 370.688, places=3)
        self.assertAlmostEqual(
            lora_time_on_air_ms(20, sf=10, bandwidth_hz=250_000),
            185.344,
            places=3,
        )

    def test_data_payload(self) -> None:
        payload = build_data_payload(self.config, node_id=7, sequence=42)
        decoded = decode_data_payload(payload)
        self.assertEqual(len(payload), 20)
        self.assertEqual(decoded.node_id, 7)
        self.assertEqual(decoded.sequence, 42)
        self.assertEqual(decoded.run_id, self.config.run_id)

    def test_archived_profile_zero_payload_stays_version_one(self) -> None:
        legacy = RunConfig(
            **{
                **self.config.__dict__,
                "phy_profile_id": 0,
                "traffic_profile_id": 2,
            }
        )
        payload = build_data_payload(legacy, node_id=1, sequence=0)
        self.assertEqual(payload[2], 1)
        self.assertEqual(decode_data_payload(payload).run_id, legacy.run_id)

    def test_expected_schedule_is_deterministic(self) -> None:
        first = expected_tx_schedule_ms(self.config, node_id=7)
        second = expected_tx_schedule_ms(self.config, node_id=7)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertTrue(all(a < b for a, b in zip(first, first[1:])))
        self.assertEqual(firmware_mean_idle_gap_ms(self.config), 558)

    def test_experiment_tag(self) -> None:
        self.assertEqual(parse_experiment_tag("figure=fig9_10"), ("figure", "fig9_10"))
        with self.assertRaises(Exception):
            parse_experiment_tag("missing_separator")
        with self.assertRaises(Exception):
            parse_experiment_tag("bad key=value")


if __name__ == "__main__":
    unittest.main()
