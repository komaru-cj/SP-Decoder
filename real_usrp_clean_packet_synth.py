"""Extract clean real USRP LoRa packets and synthesize dual-antenna collisions.

The synthesizer uses measured two-channel packet snippets from
real_usrp_outputs/pos01.npz ... pos10.npz.  It places packets with cumulative
8-10 LoRa-symbol random fractional offsets, preserving each snippet's measured
dual-antenna amplitude, phase, CFO, and waveform impairments.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from lora_mrc_sp_core import (
    LoRaConfig,
    add_fractional_waveform,
    noncoherent_preamble_score,
)


@dataclass
class ExtractedPacketMeta:
    source_file: str
    packet_index_in_file: int
    energy_start: int
    energy_end: int
    refined_start: int
    frame_samples: int
    preamble_score: float
    peak_bin: int
    cfo_bins: float
    median_peak_power: float
    frame_rms_ch0: float
    frame_rms_ch1: float
    noise_rms_ch0: float
    noise_rms_ch1: float
    snr_db_ch0: float
    snr_db_ch1: float
    saturation_fraction: float


def load_samples(path: Path) -> np.ndarray:
    z = np.load(path, allow_pickle=False)
    samples = z["samples"].astype(np.complex64)
    return samples - np.mean(samples, axis=1, keepdims=True).astype(np.complex64)


def detect_energy_segments(samples: np.ndarray, cfg: LoRaConfig) -> list[tuple[int, int]]:
    power = np.mean(np.abs(samples) ** 2, axis=0)
    block = max(1, int(round(0.001 * cfg.sample_rate_hz)))
    n_blocks = power.size // block
    block_power = power[: n_blocks * block].reshape(n_blocks, block).mean(axis=1)
    median = float(np.median(block_power))
    mad = float(np.median(np.abs(block_power - median)) + 1e-20)
    threshold = median + 8.0 * mad
    active = block_power > threshold
    raw: list[tuple[int, int]] = []
    i = 0
    while i < active.size:
        if not active[i]:
            i += 1
            continue
        j = i + 1
        while j < active.size and active[j]:
            j += 1
        if (j - i) * block >= 20_000:
            raw.append((max(0, i * block - 2 * block), min(samples.shape[1], j * block + 2 * block)))
        i = j

    merged: list[tuple[int, int]] = []
    for start, end in raw:
        if merged and start - merged[-1][1] < int(round(0.1 * cfg.sample_rate_hz)):
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def noise_power_outside_segments(samples: np.ndarray, segments: list[tuple[int, int]], cfg: LoRaConfig) -> np.ndarray:
    mask = np.ones(samples.shape[1], dtype=bool)
    guard = cfg.samples_per_symbol
    for start, end in segments:
        mask[max(0, start - guard) : min(samples.shape[1], end + guard)] = False
    if int(mask.sum()) < cfg.samples_per_symbol:
        return np.mean(np.abs(samples) ** 2, axis=1)
    return np.mean(np.abs(samples[:, mask]) ** 2, axis=1)


def refine_packet_start(samples: np.ndarray, segment_start: int, cfg: LoRaConfig) -> tuple[int, float, int, float, float]:
    lo = max(0, segment_start - 2 * cfg.samples_per_symbol)
    hi = min(samples.shape[1] - cfg.frame_samples, segment_start + 2 * cfg.samples_per_symbol)
    best = (segment_start, -1.0, 0, 0.0, 0.0)
    for step, radius in ((64, None), (8, 256), (1, 24)):
        if radius is None:
            starts = range(lo, hi + 1, step)
        else:
            center = best[0]
            starts = range(max(0, center - radius), min(samples.shape[1] - cfg.frame_samples, center + radius) + 1, step)
        for start in starts:
            score, peak_bin, cfo_bins, peak_power = noncoherent_preamble_score(samples, start, cfg)
            if score > best[1]:
                best = (start, score, peak_bin, cfo_bins, peak_power)
    return best


def extract_clean_packets(
    input_paths: list[Path],
    cfg: LoRaConfig,
    *,
    min_preamble_score: float = 250.0,
    min_duration_s: float = 0.390,
    max_duration_s: float = 0.440,
) -> tuple[np.ndarray, list[ExtractedPacketMeta]]:
    packets: list[np.ndarray] = []
    metas: list[ExtractedPacketMeta] = []
    for path in input_paths:
        samples = load_samples(path)
        segments = detect_energy_segments(samples, cfg)
        noise_power = noise_power_outside_segments(samples, segments, cfg)
        per_file_index = 0
        for energy_start, energy_end in segments:
            duration = (energy_end - energy_start) / cfg.sample_rate_hz
            touches_edge = energy_start == 0 or energy_end >= samples.shape[1]
            if touches_edge or duration < min_duration_s or duration > max_duration_s:
                continue
            refined_start, score, peak_bin, cfo_bins, peak_power = refine_packet_start(samples, energy_start, cfg)
            if score < min_preamble_score:
                continue
            if refined_start < 0 or refined_start + cfg.frame_samples > samples.shape[1]:
                continue
            snippet = samples[:, refined_start : refined_start + cfg.frame_samples].copy()
            sat = float(
                np.mean(
                    (np.abs(snippet.real) > 0.95)
                    | (np.abs(snippet.imag) > 0.95)
                )
            )
            frame_power = np.mean(np.abs(snippet) ** 2, axis=1)
            snr = 10.0 * np.log10(np.maximum(frame_power - noise_power, 1e-30) / np.maximum(noise_power, 1e-30))
            packets.append(snippet.astype(np.complex64))
            metas.append(
                ExtractedPacketMeta(
                    source_file=str(path),
                    packet_index_in_file=per_file_index,
                    energy_start=int(energy_start),
                    energy_end=int(energy_end),
                    refined_start=int(refined_start),
                    frame_samples=int(cfg.frame_samples),
                    preamble_score=float(score),
                    peak_bin=int(peak_bin),
                    cfo_bins=float(cfo_bins),
                    median_peak_power=float(peak_power),
                    frame_rms_ch0=float(math.sqrt(frame_power[0])),
                    frame_rms_ch1=float(math.sqrt(frame_power[1])),
                    noise_rms_ch0=float(math.sqrt(noise_power[0])),
                    noise_rms_ch1=float(math.sqrt(noise_power[1])),
                    snr_db_ch0=float(snr[0]),
                    snr_db_ch1=float(snr[1]),
                    saturation_fraction=sat,
                )
            )
            per_file_index += 1
    if not packets:
        return np.zeros((0, 2, cfg.frame_samples), dtype=np.complex64), []
    return np.stack(packets, axis=0), metas


def save_extracted(path: Path, packets: np.ndarray, metas: list[ExtractedPacketMeta], cfg: LoRaConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "source": "real_usrp_clean_packet_synth.extract_clean_packets",
        "packet_count": int(packets.shape[0]),
        "config": asdict(cfg),
        "packets": [asdict(meta) for meta in metas],
    }
    np.savez(path, packets=packets, metadata_json=np.array(json.dumps(metadata, indent=2)))


def load_extracted(path: Path) -> tuple[np.ndarray, dict]:
    z = np.load(path, allow_pickle=False)
    return z["packets"].astype(np.complex64), json.loads(str(z["metadata_json"]))


def synthesize_from_packets(
    packets: np.ndarray,
    metas: list[dict],
    cfg: LoRaConfig,
    *,
    seed: int = 1,
    packet_count: int | None = None,
    offset_symbols_range: tuple[float, float] = (8.0, 10.0),
    guard_symbols: float = 3.0,
    normalize_rms: bool = False,
) -> tuple[np.ndarray, dict]:
    if packets.ndim != 3 or packets.shape[1] != 2:
        raise ValueError("packets must have shape (P, 2, frame_samples)")
    rng = np.random.default_rng(seed)
    available = packets.shape[0]
    count = available if packet_count is None or packet_count <= 0 else int(packet_count)
    replace = count > available
    chosen = rng.choice(available, size=count, replace=replace)
    starts = [guard_symbols * cfg.samples_per_symbol + rng.random()]
    deltas = [0.0]
    for _ in range(1, count):
        delta_symbols = float(rng.uniform(offset_symbols_range[0], offset_symbols_range[1]))
        deltas.append(delta_symbols)
        starts.append(starts[-1] + delta_symbols * cfg.samples_per_symbol)
    total_len = int(math.ceil(starts[-1] + cfg.frame_samples + guard_symbols * cfg.samples_per_symbol))
    out = np.zeros((2, total_len), dtype=np.complex64)
    truth_packets: list[dict] = []
    for out_index, packet_index in enumerate(chosen):
        snippet = packets[int(packet_index)].copy()
        scale = 1.0
        if normalize_rms:
            rms = float(math.sqrt(np.mean(np.abs(snippet) ** 2)))
            if rms > 0:
                scale = 1.0 / rms
                snippet *= scale
        start = float(starts[out_index])
        for ch in range(2):
            add_fractional_waveform(out[ch], snippet[ch], start, 1.0 + 0.0j)
        truth_packets.append(
            {
                "output_packet_index": out_index,
                "source_packet_index": int(packet_index),
                "source_meta": metas[int(packet_index)],
                "start_sample": start,
                "delta_from_previous_symbols": float(deltas[out_index]),
                "scale": float(scale),
            }
        )
    metadata = {
        "source": "real_usrp_clean_packet_synth.synthesize_from_packets",
        "packet_count": count,
        "offset_symbols_range": list(offset_symbols_range),
        "offset_rule": "each packet starts after the previous packet by one random fractional-symbol offset drawn directly from the configured LoRa-symbol range",
        "seed": seed,
        "normalize_rms": normalize_rms,
        "config": asdict(cfg),
        "packets": truth_packets,
    }
    return out, metadata


def save_synthesized(path: Path, samples: np.ndarray, metadata: dict, cfg: LoRaConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        samples=samples.astype(np.complex64),
        sample_rate_hz=np.array(cfg.sample_rate_hz),
        center_freq_hz=np.array(487_700_000.0),
        metadata_json=np.array(json.dumps(metadata, indent=2)),
    )


def default_pos_paths() -> list[Path]:
    return [Path(f"real_usrp_outputs/pos{i:02d}.npz") for i in range(1, 11)]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    ext = sub.add_parser("extract", help="extract complete clean packets from pos01-pos10")
    ext.add_argument("--out", default="real_usrp_outputs/clean_pos_packets.npz")
    ext.add_argument("--inputs", nargs="*", default=None)
    ext.add_argument("--min-preamble-score", type=float, default=250.0)

    syn = sub.add_parser("synthesize", help="synthesize concurrent dual-antenna IQ from extracted packets")
    syn.add_argument("--packets", default="real_usrp_outputs/clean_pos_packets.npz")
    syn.add_argument("--out", default="real_usrp_outputs/synth_pos_clean_offset8_10.npz")
    syn.add_argument("--count", type=int, default=0, help="0 means use all extracted packets once")
    syn.add_argument("--seed", type=int, default=1)
    syn.add_argument("--min-offset-symbols", type=float, default=8.0)
    syn.add_argument("--max-offset-symbols", type=float, default=10.0)
    syn.add_argument("--normalize-rms", action="store_true")

    both = sub.add_parser("extract-and-synthesize", help="run extraction then synthesize")
    both.add_argument("--packet-out", default="real_usrp_outputs/clean_pos_packets.npz")
    both.add_argument("--synth-out", default="real_usrp_outputs/synth_pos_clean_offset8_10.npz")
    both.add_argument("--inputs", nargs="*", default=None)
    both.add_argument("--count", type=int, default=0)
    both.add_argument("--seed", type=int, default=1)
    both.add_argument("--min-offset-symbols", type=float, default=8.0)
    both.add_argument("--max-offset-symbols", type=float, default=10.0)
    both.add_argument("--min-preamble-score", type=float, default=250.0)
    both.add_argument("--normalize-rms", action="store_true")

    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    cfg = LoRaConfig()
    if args.cmd == "extract":
        inputs = [Path(p) for p in args.inputs] if args.inputs else default_pos_paths()
        packets, metas = extract_clean_packets(inputs, cfg, min_preamble_score=args.min_preamble_score)
        save_extracted(Path(args.out), packets, metas, cfg)
        print(f"extracted={packets.shape[0]} out={args.out}")
        for idx, meta in enumerate(metas):
            print(
                f"{idx}: {Path(meta.source_file).name} start={meta.refined_start} "
                f"score={meta.preamble_score:.1f} snr=({meta.snr_db_ch0:.1f},{meta.snr_db_ch1:.1f})dB"
            )
    elif args.cmd == "synthesize":
        packets, meta = load_extracted(Path(args.packets))
        samples, synth_meta = synthesize_from_packets(
            packets,
            meta["packets"],
            cfg,
            seed=args.seed,
            packet_count=args.count or None,
            offset_symbols_range=(args.min_offset_symbols, args.max_offset_symbols),
            normalize_rms=args.normalize_rms,
        )
        save_synthesized(Path(args.out), samples, synth_meta, cfg)
        print(f"synthesized={samples.shape} packets={synth_meta['packet_count']} out={args.out}")
    elif args.cmd == "extract-and-synthesize":
        inputs = [Path(p) for p in args.inputs] if args.inputs else default_pos_paths()
        packets, metas = extract_clean_packets(inputs, cfg, min_preamble_score=args.min_preamble_score)
        save_extracted(Path(args.packet_out), packets, metas, cfg)
        samples, synth_meta = synthesize_from_packets(
            packets,
            [asdict(meta) for meta in metas],
            cfg,
            seed=args.seed,
            packet_count=args.count or None,
            offset_symbols_range=(args.min_offset_symbols, args.max_offset_symbols),
            normalize_rms=args.normalize_rms,
        )
        save_synthesized(Path(args.synth_out), samples, synth_meta, cfg)
        print(f"extracted={packets.shape[0]} packet_out={args.packet_out}")
        print(f"synthesized={samples.shape} packets={synth_meta['packet_count']} synth_out={args.synth_out}")


if __name__ == "__main__":
    main()
