"""Capture two-channel LoRa IQ from a USRP B210.

The defaults match the current transmitter-facing capture profile:
487.7 MHz, SF=10, BW=125 kHz, Fs=1 MHz, OSR=8.

This script records complex baseband samples only. Offline detection,
stitching, and receiver comparison are handled by real_lora_stitch_decode.py.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from experiment_defaults import (
    DEFAULT_CAPTURE_SECONDS,
    DEFAULT_CENTER_FREQ_HZ,
    DEFAULT_CONFIG_NOTE,
    DEFAULT_RX_GAIN_DB,
    DEFAULT_SAMPLE_RATE_HZ,
    DEFAULT_USRP_RX_BW_HZ,
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


def parse_channels(text: str) -> list[int]:
    channels = [int(x.strip()) for x in text.split(",") if x.strip()]
    if not channels:
        raise argparse.ArgumentTypeError("at least one channel is required")
    return channels


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="Output .npz path")
    p.add_argument(
        "--center-freq",
        type=float,
        default=DEFAULT_CENTER_FREQ_HZ,
        help="RF center frequency in Hz; default is 487.7 MHz to match channel[7]",
    )
    p.add_argument("--rate", type=float, default=DEFAULT_SAMPLE_RATE_HZ, help="Sample rate in samples/s")
    p.add_argument("--duration", type=float, default=DEFAULT_CAPTURE_SECONDS, help="Capture duration in seconds")
    p.add_argument("--gain", type=float, default=DEFAULT_RX_GAIN_DB, help="RX gain in dB")
    p.add_argument("--bandwidth", type=float, default=DEFAULT_USRP_RX_BW_HZ, help="USRP analog RX bandwidth in Hz")
    p.add_argument("--channels", type=parse_channels, default=[0, 1], help="Comma-separated RX channels")
    p.add_argument("--antenna", default="", help="Optional antenna name to set on all channels")
    p.add_argument("--args", default="", help="UHD device args, for example serial=...")
    p.add_argument("--warmup", type=float, default=0.15, help="Seconds to discard after stream start")
    p.add_argument("--notes", default="", help="Free-form note stored in metadata")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    try:
        import uhd
    except ImportError as exc:
        raise SystemExit(
            "Could not import UHD Python bindings. Install UHD and verify "
            "`python -c \"import uhd\"` works before running capture."
        ) from exc

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    usrp = uhd.usrp.MultiUSRP(args.args)
    for ch in args.channels:
        usrp.set_rx_rate(args.rate, ch)
        usrp.set_rx_freq(uhd.types.TuneRequest(args.center_freq), ch)
        usrp.set_rx_gain(args.gain, ch)
        if args.bandwidth > 0:
            usrp.set_rx_bandwidth(args.bandwidth, ch)
        if args.antenna:
            usrp.set_rx_antenna(args.antenna, ch)

    stream_args = uhd.usrp.StreamArgs("fc32", "sc16")
    stream_args.channels = args.channels
    streamer = usrp.get_rx_stream(stream_args)
    max_samps = streamer.get_max_num_samps()
    recv_buffer = np.zeros((len(args.channels), max_samps), dtype=np.complex64)
    metadata = uhd.types.RXMetadata()

    warmup_samps = int(round(args.warmup * args.rate))
    target_samps = int(round(args.duration * args.rate))
    data = np.zeros((len(args.channels), target_samps), dtype=np.complex64)

    cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    cmd.stream_now = True
    streamer.issue_stream_cmd(cmd)

    got = 0
    discarded = 0
    overflows = 0
    start_time = time.time()
    try:
        while got < target_samps:
            num_rx = streamer.recv(recv_buffer, metadata, timeout=3.0)
            if metadata.error_code == uhd.types.RXMetadataErrorCode.overflow:
                overflows += 1
                continue
            if metadata.error_code != uhd.types.RXMetadataErrorCode.none:
                raise RuntimeError(f"UHD RX error: {metadata.strerror()}")
            if num_rx <= 0:
                continue

            chunk = recv_buffer[:, :num_rx]
            if discarded < warmup_samps:
                drop = min(num_rx, warmup_samps - discarded)
                discarded += drop
                chunk = chunk[:, drop:]
                if chunk.size == 0:
                    continue

            take = min(chunk.shape[1], target_samps - got)
            data[:, got : got + take] = chunk[:, :take]
            got += take
    finally:
        stop_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
        streamer.issue_stream_cmd(stop_cmd)

    meta = {
        "created_unix_s": time.time(),
        "elapsed_s": time.time() - start_time,
        "center_freq_hz": args.center_freq,
        "sample_rate_hz": args.rate,
        "duration_s": args.duration,
        "gain_db": args.gain,
        "bandwidth_hz": args.bandwidth,
        "channels": args.channels,
        "antenna": args.antenna,
        "uhd_args": args.args,
        "warmup_s": args.warmup,
        "overflows": overflows,
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
        samples=data,
        sample_rate_hz=np.array(args.rate),
        center_freq_hz=np.array(args.center_freq),
        metadata_json=np.array(json.dumps(meta, indent=2)),
    )
    print(f"Wrote {data.shape[1]} samples x {data.shape[0]} channels to {out_path}")
    if overflows:
        print(f"Warning: observed {overflows} UHD overflow events")


if __name__ == "__main__":
    main()
