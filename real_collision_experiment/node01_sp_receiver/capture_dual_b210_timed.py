#!/usr/bin/env python3
"""Timed-start dual-channel B210 capture for real collision experiments."""

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
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=45.0)
    parser.add_argument("--center-freq", type=float, default=487_700_000.0)
    parser.add_argument("--rate", type=float, default=750_000.0)
    parser.add_argument("--gain", type=float, default=20.0)
    parser.add_argument("--bandwidth", type=float, default=500_000.0)
    parser.add_argument("--channels", type=parse_channels, default=parse_channels("0,1"))
    parser.add_argument("--antenna", default="RX2")
    parser.add_argument("--device-args", default="")
    parser.add_argument("--warmup", type=float, default=0.5)
    parser.add_argument("--start-delay", type=float, default=1.0)
    parser.add_argument("--progress-interval", type=float, default=1.0)
    parser.add_argument("--run-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--notes", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.duration <= 0 or args.rate <= 0 or args.warmup < 0 or args.start_delay <= 0 or args.progress_interval <= 0:
        raise SystemExit("duration/rate/start-delay/progress-interval must be positive and warmup must be non-negative")
    try:
        import uhd
    except ImportError as exc:
        raise SystemExit("UHD Python bindings are required: python3 -c 'import uhd'") from exc

    args.out.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = args.out.with_suffix(args.out.suffix + ".json")
    capture_temp_path = args.out.with_suffix(args.out.suffix + ".fc32.tmp")
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
    receive_buffer = np.zeros((channel_count, streamer.get_max_num_samps()), dtype=np.complex64)
    rx_metadata = uhd.types.RXMetadata()

    # Multi-channel B210 streamers must use a timed command; stream_now=True is
    # rejected by UHD because the two RX channels cannot be aligned otherwise.
    usrp.set_time_now(uhd.types.TimeSpec(0.0))
    start_time = uhd.types.TimeSpec(float(args.start_delay))
    stream_command = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
    stream_command.stream_now = False
    stream_command.time_spec = start_time

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
    fatal_error = ""

    def build_metadata(status: str) -> dict:
        elapsed_s = time.monotonic() - started_monotonic
        rms = np.sqrt(power_sum / max(received, 1))
        try:
            file_bytes = args.out.stat().st_size
        except FileNotFoundError:
            file_bytes = 0
        try:
            capture_temp_bytes = capture_temp_path.stat().st_size
        except FileNotFoundError:
            capture_temp_bytes = 0
        expected_bytes = received * channel_count * 2 * np.dtype("<i2").itemsize
        return {
            "schema": "sp_decode_dual_b210_sc16_timed_v2",
            "status": status,
            "run_id": args.run_id,
            "created_utc": started_utc.isoformat(),
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "host_elapsed_s": elapsed_s,
            "output_file": str(args.out.resolve()),
            "capture_temp_file": str(capture_temp_path.resolve()),
            "layout": "sample-major: ch0_I,ch0_Q,ch1_I,ch1_Q as little-endian int16",
            "capture_temp_layout": "sample-major: ch0,ch1 as little-endian complex64; converted offline to sc16 after a complete capture",
            "dtype": "<i2",
            "capture_temp_dtype": "<c8",
            "channels": args.channels,
            "samples_per_channel": received,
            "target_samples_per_channel": target_samples,
            "discarded_warmup_samples": discarded,
            "channel_count": channel_count,
            "file_bytes": file_bytes,
            "capture_temp_bytes": capture_temp_bytes,
            "expected_bytes_from_samples": expected_bytes,
            "requested": {
                "duration_s": args.duration,
                "sample_rate_hz": args.rate,
                "center_freq_hz": args.center_freq,
                "gain_db": args.gain,
                "bandwidth_hz": args.bandwidth,
                "antenna": args.antenna,
                "device_args": args.device_args,
                "warmup_s": args.warmup,
                "start_delay_s": args.start_delay,
                "progress_interval_s": args.progress_interval,
            },
            "actual": actual,
            "first_usrp_time_s": first_usrp_time_s,
            "overflow_count": overflow_count,
            "timeout_count": timeout_count,
            "fatal_error": fatal_error,
            "overflow_events": overflow_events,
            "peak_magnitude": peak_magnitude.tolist(),
            "rms_magnitude": rms.tolist(),
            "clipping_count": clipping_count.tolist(),
            "notes": args.notes,
        }

    def write_metadata(status: str) -> None:
        metadata_path.write_text(json.dumps(build_metadata(status), indent=2) + "\n", encoding="utf-8")

    print(
        f"CAPTURE_ARMED run=0x{args.run_id:08X} channels={args.channels} "
        f"rate={args.rate:.0f} duration={args.duration:.1f}s start_delay={args.start_delay:.3f}s "
        f"out={args.out}",
        flush=True,
    )
    write_metadata("armed")
    stream_started = False
    try:
        streamer.issue_stream_cmd(stream_command)
        stream_started = True
        next_progress_time = time.monotonic() + args.progress_interval
        with capture_temp_path.open("wb") as output_file:
            while received < target_samples:
                sample_count = streamer.recv(receive_buffer, rx_metadata, timeout=3.0)
                error_code = rx_metadata.error_code
                if error_code == uhd.types.RXMetadataErrorCode.overflow:
                    overflow_count += 1
                    overflow_events.append({"output_sample": received, "host_elapsed_s": time.monotonic() - started_monotonic})
                    if time.monotonic() >= next_progress_time:
                        write_metadata("running_overflow")
                        next_progress_time = time.monotonic() + args.progress_interval
                    continue
                if error_code == uhd.types.RXMetadataErrorCode.timeout:
                    timeout_count += 1
                    if time.monotonic() >= next_progress_time:
                        write_metadata("running_timeout")
                        next_progress_time = time.monotonic() + args.progress_interval
                    continue
                if error_code != uhd.types.RXMetadataErrorCode.none:
                    fatal_error = rx_metadata.strerror()
                    write_metadata("fatal")
                    break
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
                output_file.write(np.ascontiguousarray(chunk.T).tobytes())
                received += take
                now = time.monotonic()
                if now >= next_progress_time:
                    output_file.flush()
                    write_metadata("running")
                    rate = received / max(now - started_monotonic, 1e-9)
                    print(
                        f"CAPTURE_PROGRESS samples={received}/{target_samples} "
                        f"host_elapsed={now - started_monotonic:.2f}s write_rate={rate:.0f}Sa/s "
                        f"overflows={overflow_count} timeouts={timeout_count}",
                        flush=True,
                    )
                    next_progress_time = now + args.progress_interval
    except BaseException as exc:
        if not fatal_error:
            fatal_error = f"{type(exc).__name__}: {exc}"
        write_metadata("exception")
        raise
    finally:
        if stream_started:
            try:
                stop_command = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
                streamer.issue_stream_cmd(stop_command)
            except Exception:
                pass

    if not fatal_error and received >= target_samples:
        write_metadata("converting")
        block_samples = max(1, int(args.rate))
        with capture_temp_path.open("rb") as raw_file, args.out.open("wb") as sc16_file:
            while True:
                raw = np.fromfile(raw_file, dtype="<c8", count=block_samples * channel_count)
                if raw.size == 0:
                    break
                if raw.size % channel_count != 0:
                    fatal_error = f"capture temp size is not divisible by channel count: trailing complex64 count={raw.size}"
                    write_metadata("invalid_capture_temp")
                    raise RuntimeError(fatal_error)
                sample_major = raw.reshape(-1, channel_count)
                magnitudes = np.abs(sample_major)
                peak_magnitude = np.maximum(peak_magnitude, magnitudes.max(axis=0))
                power_sum += np.sum(magnitudes.astype(np.float64) ** 2, axis=0)
                clipping_count += np.sum(
                    (np.abs(sample_major.real) >= 0.999) | (np.abs(sample_major.imag) >= 0.999),
                    axis=0,
                ).astype(np.uint64)
                interleaved = np.empty((sample_major.shape[0], channel_count, 2), dtype="<i2")
                interleaved[:, :, 0] = np.rint(
                    np.clip(sample_major.real, -1.0, 32767.0 / 32768.0) * 32768.0
                ).astype(np.int16)
                interleaved[:, :, 1] = np.rint(
                    np.clip(sample_major.imag, -1.0, 32767.0 / 32768.0) * 32768.0
                ).astype(np.int16)
                sc16_file.write(interleaved.tobytes())
        capture_temp_path.unlink(missing_ok=True)

    write_metadata("done" if not fatal_error and received >= target_samples else "incomplete")
    if fatal_error or received < target_samples:
        temp_bytes = capture_temp_path.stat().st_size if capture_temp_path.exists() else 0
        print(
            f"CAPTURE_INCOMPLETE samples={received}/{target_samples} "
            f"temp_bytes={temp_bytes} overflows={overflow_count} timeouts={timeout_count}",
            flush=True,
        )
        if fatal_error:
            print(f"CAPTURE_INVALID fatal_error={fatal_error}", flush=True)
            raise RuntimeError(f"UHD RX error: {fatal_error}")
        raise RuntimeError(f"capture incomplete: samples={received}/{target_samples}")

    expected_bytes = received * channel_count * 2 * np.dtype("<i2").itemsize
    actual_bytes = args.out.stat().st_size
    if actual_bytes != expected_bytes:
        fatal_error = f"file size mismatch: expected {expected_bytes}, got {actual_bytes}"
        write_metadata("invalid_file_size")
        raise RuntimeError(f"file size mismatch: expected {expected_bytes}, got {actual_bytes}")
    print(f"CAPTURE_DONE samples={received} bytes={actual_bytes} overflows={overflow_count} timeouts={timeout_count}", flush=True)
    if fatal_error:
        print(f"CAPTURE_INVALID fatal_error={fatal_error}", flush=True)
    rms = np.sqrt(power_sum / max(received, 1))
    print(f"peak={peak_magnitude.tolist()} rms={rms.tolist()} clipping={clipping_count.tolist()}")
    print(f"metadata={metadata_path}")
    if fatal_error:
        raise RuntimeError(f"UHD RX error: {fatal_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
