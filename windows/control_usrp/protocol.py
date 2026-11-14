#!/usr/bin/env python3
"""Wire protocol shared by the control USRP and STM32 experiment nodes."""

from __future__ import annotations

import binascii
import math
import struct
from dataclasses import asdict, dataclass

MAGIC = b"SP"
LEGACY_VERSION = 1
VERSION = 2
FRAME_CONFIG = 1
FRAME_START = 2
CONFIG_FRAME_SIZE = 34
START_FRAME_SIZE = 18
DATA_PAYLOAD_SIZE = 20

PHY_PROFILE_LEGACY_SF10_BW125_CR45 = 0
PHY_PROFILES = {
    1: {"sf": 8, "bandwidth_hz": 125_000},
    2: {"sf": 10, "bandwidth_hz": 125_000},
    3: {"sf": 12, "bandwidth_hz": 125_000},
    4: {"sf": 8, "bandwidth_hz": 250_000},
    5: {"sf": 10, "bandwidth_hz": 250_000},
    6: {"sf": 12, "bandwidth_hz": 250_000},
    7: {"sf": 8, "bandwidth_hz": 500_000},
    8: {"sf": 10, "bandwidth_hz": 500_000},
    9: {"sf": 12, "bandwidth_hz": 500_000},
}
DEFAULT_PHY_PROFILE_ID = 5

# New firmware traffic profiles encode per-node duty directly.  The aggregate
# offered load is derived as G=N*d, so all N=1..15 work without a 45-entry
# aggregate-load table.
TRAFFIC_PROFILE_DUTY = {1: 0.25, 2: 0.50, 3: 0.75}
TRAFFIC_DUTY_CYCLES = tuple(TRAFFIC_PROFILE_DUTY.values())

# Kept only so archived profile-0 manifests can still be decoded and audited.
LEGACY_TRAFFIC_LOADS = (
    0.25,
    0.5,
    1.0,
    1.5,
    2.0,
    3.0,
    0.15,
    0.3,
    0.45,
    0.6,
    0.75,
    0.9,
    1.35,
    1.8,
    2.25,
    3.75,
    4.5,
    6.0,
    7.5,
    1.4,
)
TRAFFIC_LOADS = LEGACY_TRAFFIC_LOADS


def phy_profile(profile_id: int) -> dict[str, int]:
    try:
        return dict(PHY_PROFILES[int(profile_id)])
    except KeyError as exc:
        raise ValueError(f"unknown PHY profile ID {profile_id}") from exc


def recommended_receiver_sample_rate_hz(profile_id: int) -> int:
    """Return an integer-OSR capture rate for the selected data PHY."""
    bandwidth_hz = phy_profile(profile_id)["bandwidth_hz"]
    # BW125/BW250 retain the field-tested 750 ksample/s rate (OSR 6/3).
    # BW500 requires 1 Msample/s (OSR 2); 750 ksample/s gives unsupported OSR 1.5.
    return 1_000_000 if bandwidth_hz == 500_000 else 750_000


def traffic_profile_id_from_duty(duty_cycle: float) -> int:
    for profile_id, supported in TRAFFIC_PROFILE_DUTY.items():
        if math.isclose(float(duty_cycle), supported, rel_tol=0.0, abs_tol=1e-12):
            return profile_id
    raise ValueError("per-node duty cycle must be one of 0.25, 0.5, 0.75")


def crc16_ccitt(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


@dataclass(frozen=True)
class RunConfig:
    run_id: int
    active_mask: int
    num_active_nodes: int
    phy_profile_id: int
    traffic_profile_id: int
    node_tx_power_dbm: int
    duration_ms: int
    warmup_ms: int
    global_seed: int
    payload_seed: int
    flags: int = 0

    def validate(self) -> None:
        if not 0 <= self.run_id <= 0xFFFFFFFF:
            raise ValueError("run_id must fit uint32")
        if not 0 < self.active_mask <= 0x7FFF:
            raise ValueError("active_mask must select node IDs 1..15")
        if not 1 <= self.num_active_nodes <= 15:
            raise ValueError("num_active_nodes must be in the range 1..15")
        if self.active_mask.bit_count() != self.num_active_nodes:
            raise ValueError("num_active_nodes does not match active_mask")
        if self.phy_profile_id == PHY_PROFILE_LEGACY_SF10_BW125_CR45:
            if not 0 <= self.traffic_profile_id < len(LEGACY_TRAFFIC_LOADS):
                raise ValueError("unknown legacy traffic profile")
        else:
            phy_profile(self.phy_profile_id)
            if self.traffic_profile_id not in TRAFFIC_PROFILE_DUTY:
                raise ValueError("new PHY profiles require duty profile ID 1, 2, or 3")
        if not -4 <= self.node_tx_power_dbm <= 20:
            raise ValueError("node TX power must be between -4 and 20 dBm")
        if not 1_000 <= self.duration_ms <= 3_600_000:
            raise ValueError("duration must be between 1 s and 1 h")
        if not 0 <= self.warmup_ms <= 60_000:
            raise ValueError("warmup must be between 0 and 60 s")
        if self.offered_load >= self.num_active_nodes:
            raise ValueError("offered load G must be smaller than active node count")

    @property
    def offered_load(self) -> float:
        return self.per_node_duty_cycle * self.num_active_nodes

    @property
    def per_node_duty_cycle(self) -> float:
        if self.phy_profile_id == PHY_PROFILE_LEGACY_SF10_BW125_CR45:
            return LEGACY_TRAFFIC_LOADS[self.traffic_profile_id] / self.num_active_nodes
        return TRAFFIC_PROFILE_DUTY[self.traffic_profile_id]

    @property
    def phy(self) -> dict[str, int]:
        if self.phy_profile_id == PHY_PROFILE_LEGACY_SF10_BW125_CR45:
            return {"sf": 10, "bandwidth_hz": 125_000}
        return phy_profile(self.phy_profile_id)

    def to_dict(self) -> dict[str, int | float]:
        result = asdict(self)
        result["offered_load"] = self.offered_load
        result["per_node_duty_cycle"] = self.per_node_duty_cycle
        result.update(self.phy)
        return result


@dataclass(frozen=True)
class DataPayload:
    node_id: int
    run_id: int
    sequence: int
    phy_profile_id: int
    traffic_profile_id: int
    prbs_word: int
    application_crc: int


def encode_config(config: RunConfig) -> bytes:
    config.validate()
    prefix = struct.pack(
        "<2sBBBBIHBBBbIIII",
        MAGIC,
        VERSION,
        FRAME_CONFIG,
        CONFIG_FRAME_SIZE,
        config.flags,
        config.run_id,
        config.active_mask,
        config.num_active_nodes,
        config.phy_profile_id,
        config.traffic_profile_id,
        config.node_tx_power_dbm,
        config.duration_ms,
        config.warmup_ms,
        config.global_seed,
        config.payload_seed,
    )
    assert len(prefix) == CONFIG_FRAME_SIZE - 2
    return prefix + struct.pack("<H", crc16_ccitt(prefix))


def encode_start(
    run_id: int,
    config_crc: int,
    start_delay_ms: int = 0,
    flags: int = 1,
) -> bytes:
    if not 0 <= run_id <= 0xFFFFFFFF:
        raise ValueError("run_id must fit uint32")
    if not 0 <= config_crc <= 0xFFFF:
        raise ValueError("config_crc must fit uint16")
    if not 0 <= start_delay_ms <= 60_000:
        raise ValueError("START delay must be between 0 and 60 s")
    prefix = struct.pack(
        "<2sBBBBIHI",
        MAGIC,
        VERSION,
        FRAME_START,
        START_FRAME_SIZE,
        flags,
        run_id,
        config_crc,
        start_delay_ms,
    )
    assert len(prefix) == START_FRAME_SIZE - 2
    return prefix + struct.pack("<H", crc16_ccitt(prefix))


def config_crc(config_frame: bytes) -> int:
    if len(config_frame) != CONFIG_FRAME_SIZE:
        raise ValueError("invalid CONFIG frame length")
    return struct.unpack_from("<H", config_frame, CONFIG_FRAME_SIZE - 2)[0]


def active_nodes_to_mask(node_ids: list[int]) -> int:
    if not node_ids:
        raise ValueError("at least one active node is required")
    mask = 0
    for node_id in sorted(set(node_ids)):
        if not 1 <= node_id <= 15:
            raise ValueError("node IDs must be in the range 1..15")
        mask |= 1 << (node_id - 1)
    return mask


def xorshift32(value: int) -> int:
    value &= 0xFFFFFFFF
    if value == 0:
        value = 0x6D2B79F5
    value ^= (value << 13) & 0xFFFFFFFF
    value ^= value >> 17
    value ^= (value << 5) & 0xFFFFFFFF
    return value & 0xFFFFFFFF


def build_data_payload(config: RunConfig, node_id: int, sequence: int) -> bytes:
    prbs_state = (
        config.payload_seed
        ^ config.run_id
        ^ ((node_id * 0x9E3779B9) & 0xFFFFFFFF)
        ^ sequence
    )
    payload_version = (
        LEGACY_VERSION
        if config.phy_profile_id == PHY_PROFILE_LEGACY_SF10_BW125_CR45
        else VERSION
    )
    prefix = struct.pack(
        "<2sBBIIBBI",
        MAGIC,
        payload_version,
        node_id,
        config.run_id,
        sequence,
        config.phy_profile_id,
        config.traffic_profile_id,
        xorshift32(prbs_state),
    )
    assert len(prefix) == DATA_PAYLOAD_SIZE - 2
    return prefix + struct.pack("<H", crc16_ccitt(prefix))


def decode_data_payload(payload: bytes) -> DataPayload:
    if len(payload) != DATA_PAYLOAD_SIZE:
        raise ValueError(f"data payload must be {DATA_PAYLOAD_SIZE} bytes")
    magic, version, node_id, run_id, sequence, phy_id, traffic_id, prbs, crc = (
        struct.unpack("<2sBBIIBBIH", payload)
    )
    if magic != MAGIC or version not in (LEGACY_VERSION, VERSION):
        raise ValueError("payload magic/version mismatch")
    if crc16_ccitt(payload[:-2]) != crc:
        raise ValueError("application CRC16 mismatch")
    return DataPayload(node_id, run_id, sequence, phy_id, traffic_id, prbs, crc)


def lora_time_on_air_ms(
    payload_bytes: int,
    sf: int = 10,
    bandwidth_hz: int = 125_000,
    coding_rate: int = 1,
    preamble_symbols: int = 8,
    explicit_header: bool = True,
    phy_crc: bool = True,
) -> float:
    symbol_s = (2**sf) / bandwidth_hz
    low_data_rate_optimize = 1 if symbol_s >= 0.016 else 0
    implicit_header = 0 if explicit_header else 1
    crc = 1 if phy_crc else 0
    numerator = 8 * payload_bytes - 4 * sf + 28 + 16 * crc - 20 * implicit_header
    denominator = 4 * (sf - 2 * low_data_rate_optimize)
    payload_symbols = 8 + max(
        math.ceil(numerator / denominator) * (coding_rate + 4), 0
    )
    return (preamble_symbols + 4.25 + payload_symbols) * symbol_s * 1000.0


def mean_idle_gap_ms(config: RunConfig) -> float:
    toa_ms = lora_time_on_air_ms(DATA_PAYLOAD_SIZE, **config.phy)
    return toa_ms * (1.0 / config.per_node_duty_cycle - 1.0)


def firmware_time_on_air_ms(config: RunConfig | None = None) -> int:
    phy = config.phy if config is not None else {"sf": 10, "bandwidth_hz": 125_000}
    return math.ceil(lora_time_on_air_ms(DATA_PAYLOAD_SIZE, **phy))


def firmware_mean_idle_gap_ms(config: RunConfig) -> int:
    duty_milli = round(config.per_node_duty_cycle * 1000)
    numerator = 1000 - duty_milli
    return max(1, firmware_time_on_air_ms(config) * numerator // duty_milli)


def _firmware_negative_log_q16(uniform_value: int) -> int:
    uniform_value &= 0xFFFFFFFF
    if uniform_value == 0:
        uniform_value = 1
    normalized = uniform_value
    exponent = 0
    while normalized & 0x80000000 == 0:
        normalized = (normalized << 1) & 0xFFFFFFFF
        exponent += 1
    y_q16 = 65536 - (normalized >> 16)
    term_q16 = y_q16
    sum_q16 = term_q16
    for divisor in range(2, 9):
        term_q16 = (term_q16 * y_q16) >> 16
        sum_q16 += term_q16 // divisor
    return sum_q16 + exponent * 45426


def firmware_exponential_gap_ms(mean_gap_ms: int, state: int) -> tuple[int, int]:
    state = xorshift32(state)
    gap_ms = mean_gap_ms * _firmware_negative_log_q16(state) >> 16
    gap_ms = min(gap_ms, mean_gap_ms * 8)
    return max(1, gap_ms), state


def expected_tx_schedule_ms(config: RunConfig, node_id: int) -> list[int]:
    """Reproduce ideal firmware TX starts relative to TRAFFIC_BEGIN."""
    if not 1 <= node_id <= 15:
        raise ValueError("node_id must be in the range 1..15")
    state = (
        config.global_seed
        ^ config.payload_seed
        ^ config.run_id
        ^ ((node_id * 0x9E3779B9) & 0xFFFFFFFF)
    ) & 0xFFFFFFFF
    if state == 0:
        state = 1
    toa_ms = firmware_time_on_air_ms(config)
    mean_gap_ms = firmware_mean_idle_gap_ms(config)
    mean_period_ms = toa_ms + mean_gap_ms
    state = xorshift32(state)
    next_start_ms = state % (mean_period_ms + 1)
    starts: list[int] = []
    while next_start_ms < config.duration_ms:
        starts.append(next_start_ms)
        gap_ms, state = firmware_exponential_gap_ms(mean_gap_ms, state)
        next_start_ms += toa_ms + gap_ms
    return starts
