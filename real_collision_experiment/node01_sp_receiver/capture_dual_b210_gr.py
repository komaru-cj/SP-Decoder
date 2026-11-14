#!/usr/bin/env python3
"""GNU Radio based dual-channel B210 capture for real collision experiments.

The low-level UHD Python receiver is useful for diagnostics, but on this VM it
can miss the two-channel real-time budget at higher rates. This capture path
keeps the hot streaming loop inside GNU Radio/C++ and only merges the two
channel files after capture completes.
"""

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
    if len(channels) != 2:
        raise argparse.ArgumentTypeError("this receiver expects exactly two channels, e.g. 0,1")
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
    parser.add_argument("--start-delay", type=float, default=1.0)
    parser.add_argument("--progress-interval", type=float, default=1.0)
    parser.add_argument("--stop-grace", type=float, default=5.0)
    parser.add_argument(
        "--max-wall-factor",
        type=float,
        default=1.25,
        help="Hard watchdog as a multiple of requested RF duration; allows sink drain but does not hide sustained UHD under-runs.",
    )
    parser.add_argument(
        "--stall-timeout",
        type=float,
        default=30.0,
        help="Abort only after neither channel file grows for this many seconds.",
    )
    parser.add_argument("--run-id", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--keep-channel-files", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace existing output/temp metadata files.")
    return parser


def channel_paths(out: Path) -> tuple[Path, Path]:
    return (
        out.with_suffix(out.suffix + ".ch0.tmp"),
        out.with_suffix(out.suffix + ".ch1.tmp"),
    )


def merge_channel_sc16(ch0_path: Path, ch1_path: Path, out_path: Path, block_samples: int = 1_000_000) -> int:
    samples_written = 0
    with ch0_path.open("rb") as f0, ch1_path.open("rb") as f1, out_path.open("wb") as out:
        while True:
            ch0 = np.fromfile(f0, dtype="<i2", count=2 * block_samples)
            ch1 = np.fromfile(f1, dtype="<i2", count=2 * block_samples)
            if ch0.size == 0 and ch1.size == 0:
                break
            usable_shorts = min(ch0.size, ch1.size)
            usable_shorts -= usable_shorts % 2
            if usable_shorts <= 0:
                break
            ch0_iq = ch0[:usable_shorts].reshape(-1, 2)
            ch1_iq = ch1[:usable_shorts].reshape(-1, 2)
            merged = np.empty((ch0_iq.shape[0], 2, 2), dtype="<i2")
            merged[:, 0, :] = ch0_iq
            merged[:, 1, :] = ch1_iq
            out.write(merged.tobytes())
            samples_written += ch0_iq.shape[0]
            if ch0.size != ch1.size:
                break
    return samples_written


def unique_partial_path(out: Path) -> Path:
    candidate = out.with_name(f"{out.stem}.partial{out.suffix}")
    index = 1
    while candidate.exists():
        candidate = out.with_name(f"{out.stem}.partial.{index}{out.suffix}")
        index += 1
    return candidate


def main() -> int:
    args = build_parser().parse_args()
    if (
        args.duration <= 0
        or args.rate <= 0
        or args.start_delay < 0
        or args.progress_interval <= 0
        or args.stop_grace < 0
        or args.max_wall_factor < 1.0
        or args.stall_timeout <= 0
    ):
        raise SystemExit(
            "duration/rate/progress-interval/stall-timeout must be positive; start-delay/stop-grace must be "
            "non-negative; max-wall-factor must be >= 1"
        )

    try:
        from gnuradio import blocks, gr, uhd
    except ImportError as exc:
        raise SystemExit("GNU Radio UHD Python bindings are required: python3 -c 'from gnuradio import uhd'") from exc

    args.out.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = args.out.with_suffix(args.out.suffix + ".json")
    ch_paths = channel_paths(args.out)
    target_samples = int(round(args.duration * args.rate))
    started_utc = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    fatal_error = ""
    recovery: dict = {}

    def file_samples(path: Path) -> int:
        try:
            return path.stat().st_size // 4
        except FileNotFoundError:
            return 0

    def write_metadata(status: str, samples_per_channel: int = 0, actual: dict | None = None) -> None:
        try:
            output_bytes = args.out.stat().st_size
        except FileNotFoundError:
            output_bytes = 0
        metadata = {
            "schema": "sp_decode_dual_b210_sc16_gnuradio_v1",
            "status": status,
            "run_id": args.run_id,
            "created_utc": started_utc.isoformat(),
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "host_elapsed_s": time.monotonic() - started_monotonic,
            "output_file": str(args.out.resolve()),
            "layout": "sample-major: ch0_I,ch0_Q,ch1_I,ch1_Q as little-endian int16",
            "dtype": "<i2",
            "channels": args.channels,
            "channel_temp_files": [str(path.resolve()) for path in ch_paths],
            "channel_temp_bytes": [path.stat().st_size if path.exists() else 0 for path in ch_paths],
            "samples_per_channel": samples_per_channel,
            "target_samples_per_channel": target_samples,
            "file_bytes": output_bytes,
            "requested": {
                "duration_s": args.duration,
                "sample_rate_hz": args.rate,
                "center_freq_hz": args.center_freq,
                "gain_db": args.gain,
                "bandwidth_hz": args.bandwidth,
                "antenna": args.antenna,
                "device_args": args.device_args,
                "start_delay_s": args.start_delay,
                "progress_interval_s": args.progress_interval,
                "stop_grace_s": args.stop_grace,
                "max_wall_factor": args.max_wall_factor,
                "stall_timeout_s": args.stall_timeout,
            },
            "actual": actual or {},
            "fatal_error": fatal_error,
            "recovery": recovery,
            "notes": args.notes,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    capture_artifacts = (args.out, metadata_path, *ch_paths)
    existing_artifacts = [path for path in capture_artifacts if path.exists()]
    if existing_artifacts and not args.overwrite:
        existing_text = ", ".join(str(path) for path in existing_artifacts)
        raise SystemExit(
            f"refusing to delete existing capture artifacts: {existing_text}; use a new --out or pass --overwrite explicitly"
        )
    for path in existing_artifacts:
        path.unlink()

    print(
        f"CAPTURE_ARMED_GR run=0x{args.run_id:08X} channels={args.channels} "
        f"rate={args.rate:.0f} duration={args.duration:.1f}s start_delay={args.start_delay:.3f}s "
        f"out={args.out}",
        flush=True,
    )
    write_metadata("armed")
    if args.start_delay:
        time.sleep(args.start_delay)

    tb = gr.top_block("dual_b210_sc16_capture")
    stream_args = uhd.stream_args("sc16", "sc16", channels=args.channels)
    src = uhd.usrp_source(args.device_args, stream_args)
    src.set_samp_rate(args.rate)
    for chan in args.channels:
        src.set_center_freq(args.center_freq, chan)
        src.set_gain(args.gain, chan)
        src.set_bandwidth(args.bandwidth, chan)
        if args.antenna:
            src.set_antenna(args.antenna, chan)

    actual = {
        "rate_hz": float(src.get_samp_rate()),
        "center_freq_hz": [float(src.get_center_freq(chan)) for chan in args.channels],
        "gain_db": [float(src.get_gain(chan)) for chan in args.channels],
        "bandwidth_hz": [float(src.get_bandwidth(chan)) for chan in args.channels],
    }

    item_size = gr.sizeof_short * 2
    for idx, path in enumerate(ch_paths):
        head = blocks.head(item_size, target_samples)
        sink = blocks.file_sink(item_size, str(path), False)
        tb.connect((src, idx), head, sink)

    write_metadata("running", actual=actual)
    tb.start()
    print(
        f"CAPTURE_STREAMING_GR run=0x{args.run_id:08X} "
        f"actual_rate={float(actual['rate_hz']):.0f} target_samples={target_samples}",
        flush=True,
    )
    try:
        capture_started = time.monotonic()
        stop_deadline = capture_started + args.duration * args.max_wall_factor + args.stop_grace
        next_progress = time.monotonic() + args.progress_interval
        last_growth_time = capture_started
        last_samples = 0
        stop_reason = ""
        rate_warning_emitted = False
        while True:
            samples = min(file_samples(ch_paths[0]), file_samples(ch_paths[1]))
            if samples >= target_samples:
                break
            now = time.monotonic()
            if samples > last_samples:
                last_samples = samples
                last_growth_time = now
            if now >= next_progress:
                file_rate = samples / max(now - capture_started, 1e-9)
                print(
                    f"CAPTURE_PROGRESS_GR samples={samples}/{target_samples} "
                    f"capture_elapsed={now - capture_started:.2f}s file_rate={file_rate:.0f}Sa/s",
                    flush=True,
                )
                if (
                    not rate_warning_emitted
                    and now - capture_started >= 10.0
                    and file_rate < 0.9 * float(actual["rate_hz"])
                ):
                    print(
                        f"CAPTURE_RATE_WARNING_GR file_rate={file_rate:.0f}Sa/s "
                        f"requested={float(actual['rate_hz']):.0f}Sa/s; stop concurrent CPU/disk jobs",
                        flush=True,
                    )
                    rate_warning_emitted = True
                write_metadata("running", samples_per_channel=samples, actual=actual)
                next_progress = now + args.progress_interval
            if now - last_growth_time >= args.stall_timeout:
                stop_reason = (
                    f"capture stalled: no channel file growth for {now - last_growth_time:.1f}s "
                    f"at {samples}/{target_samples} samples"
                )
                break
            if now >= stop_deadline:
                stop_reason = (
                    f"capture exceeded watchdog: wall={now - capture_started:.1f}s "
                    f"limit={args.duration * args.max_wall_factor + args.stop_grace:.1f}s"
                )
                break
            time.sleep(0.1)
        tb.stop()
        tb.wait()
    except BaseException as exc:
        fatal_error = f"{type(exc).__name__}: {exc}"
        write_metadata("exception", samples_per_channel=min(file_samples(ch_paths[0]), file_samples(ch_paths[1])), actual=actual)
        tb.stop()
        tb.wait()
        raise

    samples_after_stop = min(file_samples(ch_paths[0]), file_samples(ch_paths[1]))
    if samples_after_stop < target_samples:
        capture_elapsed = max(time.monotonic() - capture_started, 1e-9)
        fatal_error = (
            f"{stop_reason or 'capture stopped before target'}; expected {target_samples}, got {samples_after_stop}"
        )
        partial_path = unique_partial_path(args.out)
        partial_samples = merge_channel_sc16(ch_paths[0], ch_paths[1], partial_path)
        recovery.update(
            {
                "partial_output_file": str(partial_path.resolve()),
                "partial_samples_per_channel": int(partial_samples),
                "partial_file_bytes": int(partial_path.stat().st_size),
                "channel_temp_files_preserved": True,
                "effective_file_rate_sps": float(samples_after_stop) / capture_elapsed,
                "effective_rate_fraction": float(samples_after_stop) / capture_elapsed / max(float(actual["rate_hz"]), 1e-9),
            }
        )
        write_metadata("incomplete", samples_per_channel=samples_after_stop, actual=actual)
        print(
            f"CAPTURE_INCOMPLETE_GR samples={samples_after_stop}/{target_samples} "
            f"ch_bytes={[path.stat().st_size if path.exists() else 0 for path in ch_paths]} "
            f"partial={partial_path}",
            flush=True,
        )
        raise RuntimeError(fatal_error)

    write_metadata("merging", samples_per_channel=target_samples, actual=actual)
    merged_samples = merge_channel_sc16(ch_paths[0], ch_paths[1], args.out)
    if merged_samples != target_samples:
        fatal_error = f"merged sample count mismatch: expected {target_samples}, got {merged_samples}"
        write_metadata("invalid_merge", samples_per_channel=merged_samples, actual=actual)
        raise RuntimeError(fatal_error)
    if not args.keep_channel_files:
        for path in ch_paths:
            path.unlink(missing_ok=True)
    write_metadata("done", samples_per_channel=merged_samples, actual=actual)
    print(
        f"CAPTURE_DONE_GR samples={merged_samples} bytes={args.out.stat().st_size} metadata={metadata_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
