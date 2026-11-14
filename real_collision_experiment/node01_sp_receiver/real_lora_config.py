"""LoRa profile for the 15-node real-collision experiment."""

from __future__ import annotations

import math
from dataclasses import dataclass

from lora_mrc_sp_core import LoRaConfig


@dataclass(frozen=True)
class RealCollisionLoRaConfig(LoRaConfig):
    """Runtime-selected PHY used by STM32F103/SX1276 collision nodes."""

    sf: int = 10
    bw_hz: float = 125_000.0
    sample_rate_hz: float = 750_000.0
    cr: int = 1
    preamble_len: int = 8
    sync_word: int = 0x34
    payload_len: int = 20
    crc_on: bool = True
    implicit_header: bool = False
    ldro: bool = False

    @property
    def payload_symbol_count(self) -> int:
        ih = 1 if self.implicit_header else 0
        crc = 1 if self.crc_on else 0
        de = 1 if self.ldro else 0
        numerator = 8 * self.payload_len - 4 * self.sf + 28 + 16 * crc - 20 * ih
        denominator = 4 * (self.sf - 2 * de)
        return 8 + max(math.ceil(numerator / denominator) * (self.cr + 4), 0)

    @property
    def explicit_header_symbol_count(self) -> int:
        return 0 if self.implicit_header else 8

    @property
    def payload_data_symbol_count(self) -> int:
        return self.payload_symbol_count - self.explicit_header_symbol_count
