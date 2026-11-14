"""LoRa explicit/implicit-header payload decoder for SP/MRC symbol decisions."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from usrp_b210_lora_tx import (
    WHITENING_SEQ,
    gray_demap,
    hamming_encode,
    int_to_bits,
    lora_payload_crc,
)


@dataclass(frozen=True)
class PhyPayloadDecode:
    header_nibbles: list[int]
    payload: bytes
    phy_crc_ok: bool
    corrected_codewords: int
    uncorrected_codewords: int
    status: str


def bits_to_int(bits: list[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming_distance(a: int, b: int) -> int:
    return int((int(a) ^ int(b)).bit_count())


@lru_cache(maxsize=16)
def gray_inverse_map(cfg) -> dict[int, int]:
    """Cache the PHY-profile map used by every bounded CRC repair trial."""
    return {int(gray_demap(sym, cfg)): int(sym) for sym in range(cfg.m)}


def deinterleave_block(symbols: list[int], *, sf: int, sf_app: int, cw_len: int, reduced: bool) -> list[int]:
    if len(symbols) != cw_len:
        raise ValueError("symbol block length must equal codeword bit length")
    rows = [int_to_bits(int(sym), sf) for sym in symbols]
    cw_bits = [[0] * cw_len for _ in range(sf_app)]
    for i, row in enumerate(rows):
        for j in range(sf_app):
            cw_idx = (i - j - 1) % sf_app
            cw_bits[cw_idx][i] = int(row[j])
        if reduced:
            parity = sum(row[:sf_app]) & 1
            _ = parity == int(row[sf_app])
    return [bits_to_int(bits) for bits in cw_bits]


def deinterleave_explicit(symbol_values: list[int], cfg) -> tuple[list[int], list[tuple[int, int]]]:
    header_symbols = int(cfg.explicit_header_symbol_count)
    header_cw: list[int] = []
    payload_cw: list[tuple[int, int]] = []
    if header_symbols or cfg.implicit_header:
        first_block = deinterleave_block(
            symbol_values[:8],
            sf=cfg.sf,
            sf_app=cfg.sf - 2,
            cw_len=8,
            reduced=True,
        )
        # SX127x explicit header contributes only five nibbles:
        # [payload_len_hi, payload_len_lo, (cr << 1) | crc, checksum_hi,
        # checksum_lo].  The first reduced interleaver block carries SF-2
        # codewords, so for SF10 the remaining three codewords are already the
        # first payload nibbles and must not be discarded.
        if cfg.implicit_header:
            payload_cw.extend((word, 4) for word in first_block)
        else:
            header_cw = first_block[:5]
            payload_cw.extend((word, 4) for word in first_block[5:])
    idx = 8
    while idx < len(symbol_values):
        block = symbol_values[idx : idx + cfg.cr + 4]
        if len(block) < cfg.cr + 4:
            break
        payload_cw.extend(
            (word, cfg.cr)
            for word in deinterleave_block(
                block,
                sf=cfg.sf,
                sf_app=cfg.sf,
                cw_len=cfg.cr + 4,
                reduced=False,
            )
        )
        idx += cfg.cr + 4
    return header_cw, payload_cw


def decode_hamming_word(word: int, cr_app: int) -> tuple[int, bool, bool]:
    best_nibble = 0
    best_dist = 99
    for nibble in range(16):
        encoded = hamming_encode(nibble, cr_app)
        dist = hamming_distance(int(word), int(encoded))
        if dist < best_dist:
            best_dist = dist
            best_nibble = nibble
    corrected = best_dist > 0
    uncorrected = best_dist > 1
    return best_nibble, corrected, uncorrected


def nibbles_to_bytes(nibbles: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(nibbles), 2):
        lo = int(nibbles[i]) & 0x0F
        hi = int(nibbles[i + 1]) & 0x0F if i + 1 < len(nibbles) else 0
        out.append(lo | (hi << 4))
    return bytes(out)


def decode_payload_from_symbol_bins(symbol_bins: list[int], cfg) -> PhyPayloadDecode:
    if len(symbol_bins) < cfg.payload_symbol_count:
        return PhyPayloadDecode([], b"", False, 0, 0, "not_enough_symbols")
    inv = gray_inverse_map(cfg)
    symbol_values = [inv.get(int(b) % cfg.m, 0) for b in symbol_bins[: cfg.payload_symbol_count]]
    header_cw, payload_cw = deinterleave_explicit(symbol_values, cfg)
    header_nibbles: list[int] = []
    payload_nibbles: list[int] = []
    corrected = 0
    uncorrected = 0
    for word in header_cw:
        nibble, corr, uncorr = decode_hamming_word(word, 4)
        header_nibbles.append(nibble)
        corrected += int(corr)
        uncorrected += int(uncorr)
    needed_nibbles = 2 * cfg.payload_len + (4 if cfg.crc_on else 0)
    for word, cr_app in payload_cw[:needed_nibbles]:
        nibble, corr, uncorr = decode_hamming_word(word, cr_app)
        payload_nibbles.append(nibble)
        corrected += int(corr)
        uncorrected += int(uncorr)
    if len(payload_nibbles) < needed_nibbles:
        return PhyPayloadDecode(header_nibbles, b"", False, corrected, uncorrected, "not_enough_codewords")
    whitened_payload = nibbles_to_bytes(payload_nibbles[: 2 * cfg.payload_len])
    payload = bytes(np.frombuffer(whitened_payload, dtype=np.uint8) ^ WHITENING_SEQ[: cfg.payload_len])
    crc_nibbles = payload_nibbles[2 * cfg.payload_len : 2 * cfg.payload_len + 4]
    decoded_crc = sum((int(n) & 0x0F) << shift for n, shift in zip(crc_nibbles, (0, 4, 8, 12)))
    expected_crc = lora_payload_crc(payload)
    phy_crc_ok = bool(decoded_crc == expected_crc and uncorrected == 0)
    status = "ok" if phy_crc_ok else "phy_crc_failed"
    return PhyPayloadDecode(header_nibbles, payload, phy_crc_ok, corrected, uncorrected, status)
