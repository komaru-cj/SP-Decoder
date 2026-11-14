"""Convert GNU Radio raw complex64 channel files into the experiment .npz format."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from experiment_defaults import (
    DEFAULT_CENTER_FREQ_HZ,
    DEFAULT_CONFIG_NOTE,
    DEFAULT_SAMPLE_RATE_HZ,
    LORA_BW_HZ,
    LORA_CODING_RATE,
    LORA_CRC,
    LORA_HEADER_MODE,
    LORA_PAYLOAD_BYTES,
    LORA_PAYLOAD_START_SYMBOLS,
    LORA_PAYLOAD_SYMBOLS,
    LORA_PREAMBLE_SYMBOLS,
    LORA_SF,
    LORA_SYNC_WORD,
    LORA_TX_INTERVAL_S,
    LORA_TX_POWER_DBM,
)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ch0", required=True, help="GNU Radio raw gr_complex file for RX channel 0")
    p.add_argument("--ch1", required=True, help="GNU Radio raw gr_complex file for RX channel 1")
    p.add_argument("--out", required=True, help="Output .npz file")
    p.add_argument("--rate", type=float, default=DEFAULT_SAMPLE_RATE_HZ, help="Sample rate in samples/s")
    p.add_argument(
        "--center-freq",
        type=float,
        default=DEFAULT_CENTER_FREQ_HZ,
        help="RF center frequency in Hz; default is 487.7 MHz to match channel[7]",
    )
    p.add_argument("--skip", type=int, default=0, help="Samples to skip from the beginning of each channel")
    p.add_argument("--max-samples", type=int, default=0, help="Maximum samples to keep; 0 keeps all")
    p.add_argument("--dc-block", action="store_true", help="Subtract per-channel mean before saving")
    p.add_argument("--notes", default="", help="Free-form note stored in metadata")
    return p


def read_complex64(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(path)
    data = np.fromfile(path, dtype=np.complex64)
    if data.size == 0:
        raise ValueError(f"{path} is empty")
    return data


def main() -> None:
    args = build_arg_parser().parse_args()
    ch0_path = Path(args.ch0)
    ch1_path = Path(args.ch1)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ch0 = read_complex64(ch0_path)
    ch1 = read_complex64(ch1_path)
    n = min(ch0.size, ch1.size)
    if args.skip:
        if args.skip >= n:
            raise ValueError("--skip is longer than the shortest input file")
        ch0 = ch0[args.skip:n]
        ch1 = ch1[args.skip:n]
    else:
        ch0 = ch0[:n]
        ch1 = ch1[:n]

    if args.max_samples > 0:
        ch0 = ch0[: args.max_samples]
        ch1 = ch1[: args.max_samples]

    samples = np.vstack([ch0, ch1]).astype(np.complex64, copy=False)
    if args.dc_block:
        samples = samples - np.mean(samples, axis=1, keepdims=True).astype(np.complex64)

    meta = {
        "created_unix_s": time.time(),
        "source": "gnuradio raw gr_complex file sinks",
        "ch0_file": str(ch0_path),
        "ch1_file": str(ch1_path),
        "sample_rate_hz": args.rate,
        "center_freq_hz": args.center_freq,
        "skip_samples": args.skip,
        "saved_samples": int(samples.shape[1]),
        "dc_block": bool(args.dc_block),
        "notes": args.notes,
        "recommended_experiment_profile": DEFAULT_CONFIG_NOTE,
        "expected_lora_node": {
            "sf": LORA_SF,
            "bw_hz": LORA_BW_HZ,
            "coding_rate": LORA_CODING_RATE,
            "preamble_symbols": LORA_PREAMBLE_SYMBOLS,
            "crc": LORA_CRC,
            "header_mode": LORA_HEADER_MODE,
            "payload_bytes": LORA_PAYLOAD_BYTES,
            "payload_symbols": LORA_PAYLOAD_SYMBOLS,
            "payload_start_symbols": LORA_PAYLOAD_START_SYMBOLS,
            "tx_interval_s": LORA_TX_INTERVAL_S,
            "tx_power_dbm": LORA_TX_POWER_DBM,
            "sync_word": f"0x{LORA_SYNC_WORD:02x}",
        },
    }
    np.savez(
        out_path,
        samples=samples,
        sample_rate_hz=np.array(args.rate),
        center_freq_hz=np.array(args.center_freq),
        metadata_json=np.array(json.dumps(meta, indent=2)),
    )
    print(f"Wrote {samples.shape[1]} samples x 2 channels to {out_path}")


if __name__ == "__main__":
    main()
