#!/usr/bin/env python3
"""Stream synchronized two-channel B210 IQ to an interleaved sc16 file."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def parse_channels(value: str) -> list[int]:
    channels = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not channels:
        raise argparse.ArgumentTypeError("at least one channel is required")
    if len(set(channels)) != len(channels):
        raise argparse.ArgumentTypeError("channel IDs must be unique")
    return channels


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Output .sc16 file")
    parser.add_argument("--duration", type=float, default=45.0)
    parser.add_argument("--center-freq", type=float, default=487_700_000.0)
    parser.add_argument("--rate", type=float, default=750_000.0)
    parser.add_argument("--gain", type=float, default=15.0)
    parser.add_argument("--bandwidth", type=float, default=500_000.0)
    parser.add_argument("--channels", type=parse_channels, default=parse_channels("0,1"))
    parser.add_argument("--antenna", default="RX2")
    parser.add_argument("--device-args", default="")
    parser.add_argument("--warmup", type=float, default=0.5)
    parser.add_argument("--run-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--notes", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.duration <= 0 or args.rate <= 0 or args.warmup < 0:
        raise SystemExit("duration/rate must be positive and warmup must be non-negative")

    try:
        import uhd
    except ImportError as exc:
        raise SystemExit("UHD Python bindings are required: python3 -c 'import uhd'") from exc

    args.out.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = args.out.with_suffix(args.out.suffix + ".json")
    channel_count = len(args.channels)
    target_samples = round(args.duration * args.rate)
    warmup_samples = round(args.warmup * args.rate)

    usrp = uhd.usrp.MultiUSRP(args.device_args)
    actual = {"rate_hz": [], "center_freq_hz": [], "gain_db": [], "bandwidth_hz": []}
    for channel in args.channels:
        usrp.set_rx_rate(args.rate, channel)
        usrp.set_rx_freq(uhd.types.TuneRequest(args.center_freq), channel)
        usrp.set_rx_gain(args.gain, channel)
        usrp.set_rx_bandwidth(args.bandwidth, channel)
        if args.antenna:
            usrp.set_rx_antenna(args.antenna, channel)
        actual["rate_hz"].append(usrp.get_rx_rate(channel))
        actual["center_freq_hz"].append(usrp.get_rx_freq(channel))
        actual["gain_db"].append(usrp.get_rx_gain(channel))
        actual["bandwidth_hz"].append(usrp.get_rx_bandwidth(channel))

    stream_args = uhd.usrp.StreamArgs("fc32", "sc16")
    stream_args.channels = args.channels
    streamer = usrp.get_rx_stream(stream_args)
    receive_buffer = np.zeros(
        (channel_count, streamer.get_max_num_samps()), dtype=np.complex64
    )
    rx_metadata = uhd.types.RXMetadata()

    stream_command = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    stream_command.stream_now = True

    received = 0
    discarded = 0
    overflow_count = 0
    timeout_count = 0
    clipping_count = np.zeros(channel_count, dtype=np.uint64)
    peak_magnitude = np.zeros(channel_count, dtype=np.float64)
    power_sum = np.zeros(channel_count, dtype=np.float64)
    first_usrp_time_s = None
    overflow_events: list[dict[str, int | float]] = []
    started_utc = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()

    print(
        f"CAPTURE_ARMED run=0x{args.run_id:08X} channels={args.channels} "
        f"rate={args.rate:.0f} duration={args.duration:.1f}s out={args.out}"
    )
    streamer.issue_stream_cmd(stream_command)

    try:
        with args.out.open("wb") as output_file:
            while received < target_samples:
                sample_count = streamer.recv(receive_buffer, rx_metadata, timeout=3.0)
                error_code = rx_metadata.error_code
                if error_code == uhd.types.RXMetadataErrorCode.overflow:
                    overflow_count += 1
                    overflow_events.append(
                        {
                            "output_sample": received,
                            "host_elapsed_s": time.monotonic() - started_monotonic,
                        }
                    )
                    continue
                if error_code == uhd.types.RXMetadataErrorCode.timeout:
                    timeout_count += 1
                    continue
                if error_code != uhd.types.RXMetadataErrorCode.none:
                    raise RuntimeError(f"UHD RX error: {rx_metadata.strerror()}")
                if sample_count <= 0:
                    continue
                if first_usrp_time_s is None and rx_metadata.has_time_spec:
                    first_usrp_time_s = rx_metadata.time_spec.get_real_secs()

                chunk = receive_buffer[:, :sample_count]
                if discarded < warmup_samples:
                    drop = min(sample_count, warmup_samples - discarded)
                    discarded += drop
                    chunk = chunk[:, drop:]
                    if chunk.shape[1] == 0:
                        continue

                take = min(chunk.shape[1], target_samples - received)
                chunk = chunk[:, :take]
                magnitudes = np.abs(chunk)
                peak_magnitude = np.maximum(peak_magnitude, magnitudes.max(axis=1))
                power_sum += np.sum(magnitudes.astype(np.float64) ** 2, axis=1)
                clipping_count += np.sum(
                    (np.abs(chunk.real) >= 0.999) | (np.abs(chunk.imag) >= 0.999), axis=1
                ).astype(np.uint64)

                interleaved = np.empty((take, channel_count, 2), dtype="<i2")
                interleaved[:, :, 0] = np.rint(
                    np.clip(chunk.real.T, -1.0, 32767.0 / 32768.0) * 32768.0
                ).astype(np.int16)
                interleaved[:, :, 1] = np.rint(
                    np.clip(chunk.imag.T, -1.0, 32767.0 / 32768.0) * 32768.0
                ).astype(np.int16)
                output_file.write(interleaved.tobytes())
                received += take

                if received % round(5 * args.rate) < take:
                    print(f"CAPTURE_PROGRESS samples={received}/{target_samples}")
    finally:
        stop_command = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
        streamer.issue_stream_cmd(stop_command)

    elapsed_s = time.monotonic() - started_monotonic
    rms = np.sqrt(power_sum / max(received, 1))
    metadata = {
        "schema": "sp_decode_dual_b210_sc16_v1",
        "run_id": args.run_id,
        "created_utc": started_utc.isoformat(),
        "host_elapsed_s": elapsed_s,
        "output_file": str(args.out.resolve()),
        "layout": "sample-major: ch0_I,ch0_Q,ch1_I,ch1_Q as little-endian int16",
        "dtype": "<i2",
        "channels": args.channels,
        "samples_per_channel": received,
        "channel_count": channel_count,
        "requested": {
            "duration_s": args.duration,
            "sample_rate_hz": args.rate,
            "center_freq_hz": args.center_freq,
            "gain_db": args.gain,
            "bandwidth_hz": args.bandwidth,
            "antenna": args.antenna,
            "device_args": args.device_args,
            "warmup_s": args.warmup,
        },
        "actual": actual,
        "first_usrp_time_s": first_usrp_time_s,
        "overflow_count": overflow_count,
        "timeout_count": timeout_count,
        "overflow_events": overflow_events,
        "peak_magnitude": peak_magnitude.tolist(),
        "rms_magnitude": rms.tolist(),
        "clipping_count": clipping_count.tolist(),
        "notes": args.notes,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    expected_bytes = received * channel_count * 2 * np.dtype("<i2").itemsize
    actual_bytes = args.out.stat().st_size
    if actual_bytes != expected_bytes:
        raise RuntimeError(f"file size mismatch: expected {expected_bytes}, got {actual_bytes}")

    print(
        f"CAPTURE_DONE samples={received} bytes={actual_bytes} "
        f"overflows={overflow_count} timeouts={timeout_count}"
    )
    print(f"peak={peak_magnitude.tolist()} rms={rms.tolist()} clipping={clipping_count.tolist()}")
    print(f"metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
