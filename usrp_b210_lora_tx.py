"""Transmit SX127x-compatible LoRa frames with a USRP B210.

Defaults match the current node profile:
487.7 MHz, SF10, BW125k, CR4/5, preamble 8, implicit header, payload CRC on,
sync word 0x12, normal IQ, 32 random payload bytes, one packet per second.

UHD TX gain is not calibrated dBm output power. Use --tx-gain and --amplitude
with external attenuation and a power meter/spectrum analyzer if you need an
actual 20 dBm conducted level.
"""

from __future__ import annotations

import argparse
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


WHITENING_SEQ = np.array(
    [
        0xFF, 0xFE, 0xFC, 0xF8, 0xF0, 0xE1, 0xC2, 0x85, 0x0B, 0x17, 0x2F, 0x5E, 0xBC, 0x78, 0xF1, 0xE3,
        0xC6, 0x8D, 0x1A, 0x34, 0x68, 0xD0, 0xA0, 0x40, 0x80, 0x01, 0x02, 0x04, 0x08, 0x11, 0x23, 0x47,
        0x8E, 0x1C, 0x38, 0x71, 0xE2, 0xC4, 0x89, 0x12, 0x25, 0x4B, 0x97, 0x2E, 0x5C, 0xB8, 0x70, 0xE0,
        0xC0, 0x81, 0x03, 0x06, 0x0C, 0x19, 0x32, 0x64, 0xC9, 0x92, 0x24, 0x49, 0x93, 0x26, 0x4D, 0x9B,
        0x37, 0x6E, 0xDC, 0xB9, 0x72, 0xE4, 0xC8, 0x90, 0x20, 0x41, 0x82, 0x05, 0x0A, 0x15, 0x2B, 0x56,
        0xAD, 0x5B, 0xB6, 0x6D, 0xDA, 0xB5, 0x6B, 0xD6, 0xAC, 0x59, 0xB2, 0x65, 0xCB, 0x96, 0x2C, 0x58,
        0xB0, 0x61, 0xC3, 0x87, 0x0F, 0x1F, 0x3E, 0x7D, 0xFB, 0xF6, 0xED, 0xDB, 0xB7, 0x6F, 0xDE, 0xBD,
        0x7A, 0xF5, 0xEB, 0xD7, 0xAE, 0x5D, 0xBA, 0x74, 0xE8, 0xD1, 0xA2, 0x44, 0x88, 0x10, 0x21, 0x43,
        0x86, 0x0D, 0x1B, 0x36, 0x6C, 0xD8, 0xB1, 0x63, 0xC7, 0x8F, 0x1E, 0x3C, 0x79, 0xF3, 0xE7, 0xCE,
        0x9C, 0x39, 0x73, 0xE6, 0xCC, 0x98, 0x31, 0x62, 0xC5, 0x8B, 0x16, 0x2D, 0x5A, 0xB4, 0x69, 0xD2,
        0xA4, 0x48, 0x91, 0x22, 0x45, 0x8A, 0x14, 0x29, 0x52, 0xA5, 0x4A, 0x95, 0x2A, 0x54, 0xA9, 0x53,
        0xA7, 0x4E, 0x9D, 0x3B, 0x77, 0xEE, 0xDD, 0xBB, 0x76, 0xEC, 0xD9, 0xB3, 0x67, 0xCF, 0x9E, 0x3D,
        0x7B, 0xF7, 0xEF, 0xDF, 0xBF, 0x7E, 0xFD, 0xFA, 0xF4, 0xE9, 0xD3, 0xA6, 0x4C, 0x99, 0x33, 0x66,
        0xCD, 0x9A, 0x35, 0x6A, 0xD4, 0xA8, 0x51, 0xA3, 0x46, 0x8C, 0x18, 0x30, 0x60, 0xC1, 0x83, 0x07,
        0x0E, 0x1D, 0x3A, 0x75, 0xEA, 0xD5, 0xAA, 0x55, 0xAB, 0x57, 0xAF, 0x5F, 0xBE, 0x7C, 0xF9, 0xF2,
        0xE5, 0xCA, 0x94, 0x28, 0x50, 0xA1, 0x42, 0x84, 0x09, 0x13, 0x27, 0x4F, 0x9F, 0x3F, 0x7F,
    ],
    dtype=np.uint8,
)


@dataclass(frozen=True)
class LoRaTxConfig:
    sf: int = 10
    bw_hz: float = 125_000.0
    sample_rate_hz: float = 1_000_000.0
    cr: int = 1
    preamble_len: int = 8
    sync_word: int = 0x12
    payload_len: int = 32
    crc_on: bool = True
    implicit_header: bool = True
    ldro: bool = False

    @property
    def m(self) -> int:
        return 1 << self.sf

    @property
    def osr(self) -> int:
        ratio = self.sample_rate_hz / self.bw_hz
        rounded = int(round(ratio))
        if abs(ratio - rounded) > 1e-9:
            raise ValueError("sample_rate_hz must be an integer multiple of bw_hz")
        return rounded

    @property
    def samples_per_symbol(self) -> int:
        return self.m * self.osr


def int_to_bits(value: int, n_bits: int) -> list[int]:
    return [int((value >> i) & 1) for i in range(n_bits - 1, -1, -1)]


def bits_to_int(bits: list[int]) -> int:
    out = 0
    for bit in bits:
        out = (out << 1) | int(bit)
    return out


def crc16_step(crc: int, byte: int) -> int:
    for _ in range(8):
        if ((crc & 0x8000) >> 8) ^ (byte & 0x80):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF
        else:
            crc = (crc << 1) & 0xFFFF
        byte = (byte << 1) & 0xFF
    return crc


def lora_payload_crc(payload: bytes) -> int:
    if len(payload) < 2:
        raise ValueError("LoRa payload CRC in this profile requires at least two payload bytes")
    crc = 0
    for byte in payload[:-2]:
        crc = crc16_step(crc, byte)
    return crc ^ payload[-1] ^ (payload[-2] << 8)


def payload_nibbles(payload: bytes, cfg: LoRaTxConfig) -> list[int]:
    if len(payload) > len(WHITENING_SEQ):
        raise ValueError("payload is longer than the whitening table")
    whitened = np.frombuffer(payload, dtype=np.uint8) ^ WHITENING_SEQ[: len(payload)]
    nibbles: list[int] = []
    for byte in whitened:
        nibbles.append(int(byte & 0x0F))
        nibbles.append(int(byte >> 4))
    if cfg.crc_on:
        crc = lora_payload_crc(payload)
        nibbles.extend([(crc >> shift) & 0x0F for shift in (0, 4, 8, 12)])
    return nibbles


def hamming_encode(nibble: int, cr_app: int) -> int:
    d = int_to_bits(nibble & 0x0F, 4)
    if cr_app == 1:
        p4 = d[0] ^ d[1] ^ d[2] ^ d[3]
        return (d[3] << 4) | (d[2] << 3) | (d[1] << 2) | (d[0] << 1) | p4
    p0 = d[3] ^ d[2] ^ d[1]
    p1 = d[2] ^ d[1] ^ d[0]
    p2 = d[3] ^ d[2] ^ d[0]
    p3 = d[3] ^ d[1] ^ d[0]
    encoded = (d[3] << 7) | (d[2] << 6) | (d[1] << 5) | (d[0] << 4) | (p0 << 3) | (p1 << 2) | (p2 << 1) | p3
    return encoded >> (4 - cr_app)


def hamming_codewords(nibbles: list[int], cfg: LoRaTxConfig) -> list[int]:
    out: list[int] = []
    for idx, nibble in enumerate(nibbles):
        cr_app = 4 if idx < cfg.sf - 2 else cfg.cr
        out.append(hamming_encode(nibble, cr_app))
    return out


def interleave(codewords: list[int], cfg: LoRaTxConfig) -> list[int]:
    symbols: list[int] = []
    cw_cnt = 0
    while cw_cnt < len(codewords):
        reduced = (cw_cnt == 0) or cfg.ldro
        sf_app = cfg.sf - 2 if reduced else cfg.sf
        cw_len = 4 + (4 if cw_cnt < cfg.sf - 2 else cfg.cr)
        block = codewords[cw_cnt : cw_cnt + sf_app]
        block += [0] * (sf_app - len(block))
        cw_bits = [int_to_bits(cw, cw_len) for cw in block]
        for i in range(cw_len):
            row = [0] * cfg.sf
            for j in range(sf_app):
                row[j] = cw_bits[(i - j - 1) % sf_app][i]
            if reduced:
                row[sf_app] = sum(row[:sf_app]) & 1
            symbols.append(bits_to_int(row))
        cw_cnt += sf_app
    return symbols


def gray_demap(symbol: int, cfg: LoRaTxConfig) -> int:
    out = int(symbol)
    shift = 1
    while shift < 32:
        out ^= out >> shift
        shift <<= 1
    return (out + 1) % cfg.m


def instantaneous_chirp(symbol: int, cfg: LoRaTxConfig, up: bool = True) -> np.ndarray:
    if not up:
        return np.conj(instantaneous_chirp(symbol, cfg, up=True))
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    symbol = int(symbol) % cfg.m
    phase = (
        math.pi * n * n / (cfg.m * cfg.osr * cfg.osr)
        - math.pi * n / cfg.osr
        + 2.0 * math.pi * symbol * n / (cfg.m * cfg.osr)
    )
    fold = (cfg.m - symbol) * cfg.osr
    if symbol and fold < cfg.samples_per_symbol:
        phase[int(fold) :] -= 2.0 * math.pi * n[int(fold) :] / cfg.osr
    return np.exp(1j * phase).astype(np.complex64)


def build_frame(payload: bytes, cfg: LoRaTxConfig) -> tuple[np.ndarray, list[int]]:
    encoded = hamming_codewords(payload_nibbles(payload, cfg), cfg)
    interleaved = interleave(encoded, cfg)
    mod_symbols = [gray_demap(sym, cfg) for sym in interleaved]

    parts: list[np.ndarray] = []
    up0 = instantaneous_chirp(0, cfg, up=True)
    down0 = instantaneous_chirp(0, cfg, up=False)
    parts.extend([up0] * cfg.preamble_len)
    parts.append(instantaneous_chirp(((cfg.sync_word & 0xF0) >> 4) << 3, cfg, up=True))
    parts.append(instantaneous_chirp((cfg.sync_word & 0x0F) << 3, cfg, up=True))
    parts.extend([down0, down0])
    parts.append(down0[: cfg.samples_per_symbol // 4])
    parts.extend(instantaneous_chirp(sym, cfg, up=True) for sym in mod_symbols)
    return np.concatenate(parts).astype(np.complex64), mod_symbols


def make_payload(args: argparse.Namespace, cfg: LoRaTxConfig) -> bytes:
    if args.payload_hex:
        payload = bytes.fromhex(args.payload_hex)
        if len(payload) != cfg.payload_len:
            raise ValueError(f"--payload-hex must contain exactly {cfg.payload_len} bytes")
        return payload
    return os.urandom(cfg.payload_len)


def send_with_uhd(args: argparse.Namespace, cfg: LoRaTxConfig) -> None:
    try:
        import uhd
    except ImportError as exc:
        raise SystemExit("Could not import UHD Python bindings. Verify `python3 -c 'import uhd'`.") from exc

    usrp = uhd.usrp.MultiUSRP(args.args)
    usrp.set_tx_rate(cfg.sample_rate_hz, args.channel)
    usrp.set_tx_freq(uhd.types.TuneRequest(args.center_freq), args.channel)
    usrp.set_tx_gain(args.tx_gain, args.channel)
    if args.bandwidth > 0:
        usrp.set_tx_bandwidth(args.bandwidth, args.channel)
    if args.antenna:
        usrp.set_tx_antenna(args.antenna, args.channel)

    stream_args = uhd.usrp.StreamArgs("fc32", "sc16")
    stream_args.channels = [args.channel]
    streamer = usrp.get_tx_stream(stream_args)
    metadata = uhd.types.TXMetadata()
    metadata.start_of_burst = True
    metadata.end_of_burst = False
    metadata.has_time_spec = False

    max_samps = streamer.get_max_num_samps()
    gap_len = max(0, int(round(args.interval * cfg.sample_rate_hz)))
    sent = 0
    try:
        while args.count <= 0 or sent < args.count:
            payload = make_payload(args, cfg)
            frame, symbols = build_frame(payload, cfg)
            if args.dump_iq:
                dump_path = Path(args.dump_iq)
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(dump_path, samples=frame, payload=np.frombuffer(payload, dtype=np.uint8), symbols=np.asarray(symbols, dtype=np.uint16))
            tx = args.amplitude * frame
            if gap_len > tx.size:
                tx = np.concatenate([tx, np.zeros(gap_len - tx.size, dtype=np.complex64)])
            for off in range(0, tx.size, max_samps):
                streamer.send(tx[off : off + max_samps], metadata)
                metadata.start_of_burst = False
            sent += 1
            print(f"sent={sent} payload={payload.hex()} symbols={len(symbols)} samples={frame.size}")
            if gap_len <= tx.size and args.interval > 0:
                time.sleep(args.interval)
    finally:
        metadata.end_of_burst = True
        streamer.send(np.zeros(1, dtype=np.complex64), metadata)


def dry_run(args: argparse.Namespace, cfg: LoRaTxConfig) -> None:
    payload = make_payload(args, cfg)
    frame, symbols = build_frame(payload, cfg)
    if args.dump_iq:
        dump_path = Path(args.dump_iq)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            dump_path,
            samples=(args.amplitude * frame).astype(np.complex64),
            payload=np.frombuffer(payload, dtype=np.uint8),
            symbols=np.asarray(symbols, dtype=np.uint16),
            sample_rate_hz=np.array(cfg.sample_rate_hz),
            center_freq_hz=np.array(args.center_freq),
        )
        print(f"wrote {dump_path}")
    print(f"payload={payload.hex()}")
    print(f"payload_symbols={len(symbols)}")
    print(f"samples={frame.size}")
    print(f"duration_s={frame.size / cfg.sample_rate_hz:.6f}")
    print(f"max_abs_after_amplitude={float(np.max(np.abs(args.amplitude * frame))):.6f}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--center-freq", type=float, default=487_700_000.0)
    parser.add_argument("--rate", type=float, default=1_000_000.0)
    parser.add_argument("--bandwidth", type=float, default=250_000.0, help="USRP analog TX bandwidth in Hz")
    parser.add_argument("--bw-hz", type=float, default=125_000.0, help="LoRa signal bandwidth in Hz")
    parser.add_argument("--sf", type=int, default=10)
    parser.add_argument("--cr", type=int, default=1, help="LoRa coding rate index: 1 means 4/5")
    parser.add_argument("--preamble", type=int, default=8)
    parser.add_argument("--sync-word", type=lambda x: int(x, 0), default=0x12)
    parser.add_argument("--payload-len", type=int, default=32)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--count", type=int, default=0, help="Number of packets; 0 means run until Ctrl-C")
    parser.add_argument("--payload-hex", default="", help="Optional fixed payload as 32 bytes of hex")
    parser.add_argument("--amplitude", type=float, default=0.35)
    parser.add_argument("--tx-gain", type=float, default=60.0)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--antenna", default="", help="Optional UHD antenna name, for example TX/RX")
    parser.add_argument("--args", default="", help="UHD device args, for example serial=...")
    parser.add_argument("--dump-iq", default="", help="Optional .npz path for the last generated baseband frame")
    parser.add_argument("--dry-run", action="store_true", help="Generate one frame and exit without opening the USRP")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    cfg = LoRaTxConfig(
        sf=args.sf,
        bw_hz=args.bw_hz,
        sample_rate_hz=args.rate,
        cr=args.cr,
        preamble_len=args.preamble,
        sync_word=args.sync_word,
        payload_len=args.payload_len,
    )
    if args.dry_run:
        dry_run(args, cfg)
    else:
        send_with_uhd(args, cfg)


if __name__ == "__main__":
    main()
