#!/usr/bin/env python3
"""Small read-only diagnostics for failed single-node LoRa packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

RECEIVER_DIR = Path(__file__).resolve().parent / "node01_sp_receiver"
ROOT = Path(__file__).resolve().parent.parent
for module_dir in (RECEIVER_DIR, ROOT):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

from evaluate_sp_dechirp_real_pos import mrc_decode_bins
from lora_phy_decode import decode_payload_from_symbol_bins
from real_lora_config import RealCollisionLoRaConfig
from real_sp_frontend import detected_estimates_real
from sp_node01_receiver import decode_method
from sp_detection_frontend import preamble_channel_near_cfo, sfd_anchored_start_cfo_refine


def raw_capture(path: Path, channel_count: int = 2) -> np.memmap:
    raw = np.memmap(path, dtype="<i2", mode="r")
    return raw.reshape(-1, channel_count, 2)


def candidate_by_id(report: dict, candidate_id: int) -> dict:
    return next(c for c in report["candidates"] if int(c["candidate_id"]) == candidate_id)


def lora_config_from_report(config: dict) -> RealCollisionLoRaConfig:
    """Rebuild the exact runtime PHY recorded by ``sp_node01_receiver``."""
    sf = int(config["sf"])
    bandwidth_hz = float(config["bw_hz"])
    coding_rate = config.get("cr", 1)
    if isinstance(coding_rate, str) and "/" in coding_rate:
        numerator, denominator = (int(value) for value in coding_rate.split("/", 1))
        if numerator != 4 or denominator not in (5, 6, 7, 8):
            raise ValueError(f"unsupported LoRa coding rate {coding_rate!r}")
        coding_rate = denominator - 4
    return RealCollisionLoRaConfig(
        sf=sf,
        bw_hz=bandwidth_hz,
        sample_rate_hz=float(config["sample_rate_hz"]),
        cr=int(coding_rate),
        preamble_len=int(config.get("preamble_len", 8)),
        sync_word=int(config.get("sync_word", 0x34)),
        payload_len=int(config.get("payload_len", 20)),
        crc_on=bool(config.get("phy_crc", True)),
        implicit_header=not bool(config.get("explicit_header", True)),
        ldro=(2**sf) / bandwidth_hz >= 0.016,
    )


def packet_stats(
    raw: np.ndarray, start: float, sps: int, payload_start: float, count: int
) -> tuple[np.ndarray, np.ndarray]:
    powers = []
    clipping = []
    for q in range(count):
        begin = int(round(start + (payload_start + q) * sps))
        block = raw[begin : begin + sps].astype(np.float64)
        powers.append(np.mean(np.sum(block * block, axis=2), axis=0))
        clipping.append(np.sum(np.any(np.abs(block) >= 32760, axis=2), axis=0))
    return np.asarray(powers), np.asarray(clipping)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--candidate", type=int, action="append", default=[])
    parser.add_argument("--search-symbol-shifts", action="store_true")
    parser.add_argument("--current-decoder", action="store_true")
    parser.add_argument("--frontend-range", help="START_S:END_S")
    parser.add_argument("--frontend-limit", type=int, default=16)
    parser.add_argument("--frontend-cfo", type=float, default=96.0)
    parser.add_argument("--frontend-grid", action="store_true")
    parser.add_argument("--frontend-step", type=int, default=0)
    parser.add_argument("--energy-ratios", default="")
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    capture_path = Path(report["input"]["iq"])
    metadata = json.loads(Path(report["input"]["metadata"]).read_text(encoding="utf-8"))
    channel_count = int(metadata.get("channel_count", 2))
    raw = raw_capture(capture_path, channel_count)
    cfg = report["config"]
    local_cfg = lora_config_from_report(cfg)
    sps = int(round(local_cfg.samples_per_symbol))

    # Chunked whole-capture peak/clipping statistics; avoids a large temporary array.
    clip = np.zeros((channel_count,), dtype=np.int64)
    near_clip = np.zeros((channel_count,), dtype=np.int64)
    peak = np.zeros((channel_count,), dtype=np.int64)
    for begin in range(0, raw.shape[0], 1_000_000):
        block = np.abs(raw[begin : begin + 1_000_000].astype(np.int32))
        clip += np.sum(np.any(block >= 32760, axis=2), axis=0)
        near_clip += np.sum(np.any(block >= 30000, axis=2), axis=0)
        peak = np.maximum(peak, np.max(block, axis=(0, 2)))
    print(f"capture={capture_path} samples={raw.shape[0]} peak={peak.tolist()} near_clip={near_clip.tolist()} clip={clip.tolist()}")

    if args.energy_ratios:
        dc = np.asarray([complex(*v) for v in report["calibration"]["dc"]])[:, None]
        whitener = np.asarray(
            [[complex(*v) for v in row] for row in report["calibration"]["whitener"]]
        )
        block_samples = 10_000
        block_power = []
        for begin in range(0, raw.shape[0], 1_000_000):
            chunk = raw[begin : begin + 1_000_000].astype(np.float32)
            x = (chunk[:, :, 0] + 1j * chunk[:, :, 1]).T / 32768.0
            white = whitener @ (x - dc)
            usable = (white.shape[1] // block_samples) * block_samples
            block_power.extend(
                np.mean(np.abs(white[:, :usable].reshape(channel_count, -1, block_samples)) ** 2, axis=(0, 2))
            )
        block_power = np.asarray(block_power)
        median = float(np.median(block_power))
        counts = {}
        for ratio in (float(v) for v in args.energy_ratios.split(",")):
            active = block_power >= median * ratio
            counts[ratio] = int(np.count_nonzero(active & ~np.r_[False, active[:-1]]))
        print(f"energy_event_counts median={median} counts={counts}")

    if args.frontend_range:
        start_s, end_s = (float(v) for v in args.frontend_range.split(":", 1))
        first = int(round(start_s * float(cfg["sample_rate_hz"])))
        last = int(round(end_s * float(cfg["sample_rate_hz"])))
        raw_segment = raw[first:last].astype(np.float32)
        segment = (raw_segment[:, :, 0] + 1j * raw_segment[:, :, 1]).T / 32768.0
        dc = np.asarray([complex(*v) for v in report["calibration"]["dc"]])[:, None]
        whitener = np.asarray(
            [[complex(*v) for v in row] for row in report["calibration"]["whitener"]]
        )
        segment = (whitener @ (segment - dc)).astype(np.complex64)
        estimates, _ = detected_estimates_real(
            segment,
            local_cfg,
            max_candidates=100,
            raw_candidate_limit=int(args.frontend_limit),
            threshold=float(report["frontend"]["threshold"]),
            step_samples=int(args.frontend_step or report["frontend"]["step"]),
            min_sync_score=0.0,
            min_coherent_metric=0.0,
            cfo_min=-float(args.frontend_cfo),
            cfo_max=float(args.frontend_cfo),
            fast_single_node=True,
            fast_grid_refine=bool(args.frontend_grid),
        )
        print(
            "frontend_estimates="
            + str(
                [
                    (
                        round(start_s + float(e["start_sample"]) / float(cfg["sample_rate_hz"]), 6),
                        round(float(e["continuous_cfo_bins"]), 3),
                        round(float(e.get("sfd_confidence", 0.0)), 3),
                        bool(e.get("pcube_fast_refine_enabled", False)),
                    )
                    for e in estimates
                ]
            )
        )
        decoded_frontend = []
        for e in estimates:
            row = decode_method("mrc", segment, e, local_cfg)
            decoded_frontend.append(
                (
                    round(start_s + float(e["start_sample"]) / float(cfg["sample_rate_hz"]), 6),
                    row["phy"]["phy_crc_ok"],
                    row["phy"]["payload_hex"],
                    row["phy"]["header_nibbles"],
                    row["bin_drift_repair"],
                )
            )
        print("frontend_mrc=" + str(decoded_frontend))

    for candidate_id in args.candidate:
        c = candidate_by_id(report, candidate_id)
        powers, clipping = packet_stats(
            raw,
            float(c["start_sample"]),
            sps,
            float(cfg["payload_start_symbols"]),
            int(cfg["payload_symbol_count"]) + 8,
        )
        ref = np.median(powers[:24], axis=0)
        rel_db = 10.0 * np.log10(np.maximum(powers, 1.0) / np.maximum(ref, 1.0))
        print(
            f"candidate={candidate_id} t={c['start_time_s']:.6f}s cfo={c['continuous_cfo_bins']:.3f} "
            "q_power_db_vs_q0_23="
            + " ".join(f"{q}:{v[0]:+.1f}/{v[1]:+.1f}" for q, v in enumerate(rel_db))
        )
        print(
            f"candidate={candidate_id} clipped_samples_by_channel="
            + "/".join(str(int(v)) for v in np.sum(clipping, axis=0))
        )
        # Estimate actual RF burst extent from the unclipped channel.  This
        # distinguishes a decoder alignment error from a physically short TX.
        center = int(round(float(c["start_sample"])))
        extent_first = max(0, center - int(0.12 * float(cfg["sample_rate_hz"])))
        extent_last = min(raw.shape[0], center + int(0.55 * float(cfg["sample_rate_hz"])))
        extent = raw[extent_first:extent_last, min(1, channel_count - 1)].astype(np.float64)
        block_samples = 256
        extent = extent[: (extent.shape[0] // block_samples) * block_samples]
        extent_power = np.mean(np.sum(extent.reshape(-1, block_samples, 2) ** 2, axis=2), axis=1)
        noise_floor = float(np.percentile(extent_power, 10))
        signal_level = float(np.percentile(extent_power, 90))
        extent_threshold = np.sqrt(max(noise_floor, 1.0) * max(signal_level, 1.0))
        active = extent_power >= extent_threshold
        center_block = int((center - extent_first) // block_samples)
        left = min(max(center_block, 0), len(active) - 1)
        while left > 0 and active[left - 1]:
            left -= 1
        right = min(max(center_block, 0), len(active) - 1)
        while right + 1 < len(active) and active[right + 1]:
            right += 1
        burst_start = extent_first + left * block_samples
        burst_end = extent_first + (right + 1) * block_samples
        print(
            f"candidate={candidate_id} rf_burst_start_delta_symbols={(burst_start-center)/sps:+.3f} "
            f"duration_symbols={(burst_end-burst_start)/sps:.3f}"
        )
        if args.search_symbol_shifts or args.current_decoder:
            margin = 10 * sps
            first = max(0, int(round(float(c["start_sample"]))) - margin)
            last = min(
                raw.shape[0],
                int(round(float(c["start_sample"])))
                + int(round((float(cfg["payload_start_symbols"]) + int(cfg["payload_symbol_count"]) + 3) * sps)),
            )
            raw_segment = raw[first:last].astype(np.float32)
            segment = (raw_segment[:, :, 0] + 1j * raw_segment[:, :, 1]).T / 32768.0
            dc = np.asarray([complex(*v) for v in report["calibration"]["dc"]])[:, None]
            whitener = np.asarray(
                [[complex(*v) for v in row] for row in report["calibration"]["whitener"]]
            )
            segment = (whitener @ (segment - dc)).astype(np.complex64)
            local_start = float(c["start_sample"]) - first
            base_cfo = float(c["continuous_cfo_bins"])
            _, base_channel, _ = preamble_channel_near_cfo(segment, local_start, base_cfo, local_cfg)
            if args.current_decoder:
                local_est = dict(c)
                local_est.update(
                    {
                        "start_sample": local_start,
                        "continuous_cfo_bins": base_cfo,
                        "cfo_bins": float(c["cfo_bins"]),
                        "sto_samples": float(c.get("sto_samples", 0.0)),
                        "channel": [[float(v.real), float(v.imag)] for v in base_channel],
                        "channel_sp": [[float(v.real), float(v.imag)] for v in base_channel],
                        "lambda_sp": float(c.get("lambda_sp", 0.0)),
                    }
                )
                current = decode_method("mrc", segment, local_est, local_cfg)
                print(
                    f"candidate={candidate_id} current_mrc_crc={current['phy']['phy_crc_ok']} "
                    f"payload={current['phy']['payload_hex']} repair={current['bin_drift_repair']}"
                )
            if not args.search_symbol_shifts:
                continue
            sfd_start, sfd_cfo, _, sfd_metric, _, _ = sfd_anchored_start_cfo_refine(
                segment,
                local_start,
                local_cfg,
                symbol_radius=8,
                local_radius_bins=32,
            )
            _, sfd_channel, _ = preamble_channel_near_cfo(segment, sfd_start, sfd_cfo, local_cfg)
            sfd_bins, _ = mrc_decode_bins(segment, sfd_start, sfd_cfo, 0.0, sfd_channel, local_cfg)
            sfd_phy = decode_payload_from_symbol_bins(sfd_bins, local_cfg)
            print(
                f"candidate={candidate_id} wide_sfd_shift_symbols={(sfd_start-local_start)/sps:+.4f} "
                f"cfo={sfd_cfo:.3f} metric={sfd_metric:.3g} crc={sfd_phy.phy_crc_ok} "
                f"payload={sfd_phy.payload.hex()}"
            )
            passes = []
            for symbol_shift in range(-8, 9):
                trial_start = local_start + symbol_shift * sps
                for cfo_delta in np.arange(-2.0, 2.01, 0.5):
                    trial_cfo = base_cfo + float(cfo_delta)
                    _, channel, _ = preamble_channel_near_cfo(segment, trial_start, trial_cfo, local_cfg)
                    bins, _ = mrc_decode_bins(segment, trial_start, trial_cfo, 0.0, channel, local_cfg)
                    phy = decode_payload_from_symbol_bins(bins, local_cfg)
                    if phy.phy_crc_ok:
                        passes.append((symbol_shift, float(cfo_delta), phy.payload.hex()))
            print(f"candidate={candidate_id} integer_symbol_shift_crc_passes={passes}")


if __name__ == "__main__":
    main()
