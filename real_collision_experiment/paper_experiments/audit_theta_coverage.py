#!/usr/bin/env python3
"""Audit the original preamble theta against independent clean IQ directions.

This is a conditional direction-estimator experiment: start/CFO are supplied
from the source trace. It makes no detector or end-to-end PDR claim.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "real_collision_experiment" / "node01_sp_receiver"))

from evaluate_sp_dechirp_real_pos import channel_angle, robust_preamble_channel_sp  # noqa: E402
from lora_mrc_sp_core import LoRaConfig, fractional_read_2d, instantaneous_chirp, lora_symbol_fft  # noqa: E402
from real_usrp_clean_packet_synth import load_extracted  # noqa: E402
from real_collision_experiment.paper_experiments.generate_sp_v2_mechanism_figures import (  # noqa: E402
    estimate_fractional_cfo_from_preamble,
    synthesize_two_trace_packets,
)
from sp_detection_frontend import build_references  # noqa: E402


def whitener_for_source(source: str) -> np.ndarray:
    path = ROOT / source
    with np.load(path, allow_pickle=False) as data:
        noise = np.asarray(data["samples"][:, :8000], dtype=np.complex128)
    noise -= np.mean(noise, axis=1, keepdims=True)
    cov = noise @ noise.conj().T / noise.shape[1]
    eig, vec = np.linalg.eigh(cov)
    eig = np.maximum(eig.real, max(float(eig.max().real), 1e-20) * 1e-6)
    return vec @ np.diag(eig ** -0.5) @ vec.conj().T


def clean_multichirp_reference(packet: np.ndarray, cfg: LoRaConfig) -> tuple[np.ndarray, float]:
    """Use eight preamble and two sync chirps; split halves audit noise."""
    down = instantaneous_chirp(0, cfg, up=False)
    vectors = []
    for symbol in range(cfg.preamble_len + 2):
        start = symbol * cfg.samples_per_symbol
        window = fractional_read_2d(packet, start, cfg.samples_per_symbol)
        spectrum = np.vstack([lora_symbol_fft(ch * down, cfg) for ch in window])
        peak = int(np.argmax(np.sum(np.abs(spectrum) ** 2, axis=0)))
        value = spectrum[:, peak].astype(np.complex128)
        vectors.append(value / max(np.linalg.norm(value), 1e-30))
    vectors = np.asarray(vectors)
    anchor = vectors[0]
    aligned = vectors * np.exp(-1j * np.angle(vectors @ np.conj(anchor)))[:, None]
    center = np.mean(aligned, axis=0)
    for _ in range(3):
        aligned = vectors * np.exp(-1j * np.angle(vectors @ np.conj(center)))[:, None]
        angles = np.array([channel_angle(value, center) for value in aligned])
        weights = np.exp(-(angles / 0.25) ** 2)
        center = np.average(aligned, axis=0, weights=weights)
    half_a = np.mean(aligned[::2], axis=0)
    half_b = np.mean(aligned[1::2], axis=0)
    return center, math.degrees(channel_angle(half_a, half_b))


def observed_bin_separation(
    target: np.ndarray, interferer: np.ndarray, cfg: LoRaConfig,
    offset: float, cfo_shift: float, target_cfo: float,
) -> float:
    """Measure the two isolated peaks in a common target dechirp window."""
    down = instantaneous_chirp(0, cfg, up=False)
    target_fft = lora_symbol_fft(target[0, : cfg.samples_per_symbol] * down, cfg)
    # The shifted interferer is read at the target's first preamble window.
    from lora_mrc_sp_core import add_fractional_waveform
    isolated = np.zeros(cfg.samples_per_symbol * 3, dtype=np.complex64)
    n = np.arange(min(interferer.shape[1], isolated.size), dtype=np.float64)
    rotated = interferer[0, : n.size] * np.exp(1j * 2 * np.pi * cfo_shift * n / cfg.samples_per_symbol)
    add_fractional_waveform(isolated, rotated.astype(np.complex64), cfg.samples_per_symbol + offset * cfg.samples_per_symbol, 1 + 0j)
    segment = isolated[cfg.samples_per_symbol:2 * cfg.samples_per_symbol]
    other_fft = lora_symbol_fft(segment * down, cfg)
    a = int(np.argmax(abs(target_fft)))
    b = int(np.argmax(abs(other_fft)))
    return float(abs((a - b + cfg.m // 2) % cfg.m - cfg.m // 2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", type=Path, default=ROOT / "real_usrp_outputs/clean_pos_packets.npz")
    parser.add_argument("--out", type=Path, default=Path("analysis/theta_coverage_audit"))
    args = parser.parse_args()
    cfg = LoRaConfig()
    packets, metadata = load_extracted(args.clean)
    refs = build_references(args.clean, list(range(len(packets))), cfg)
    meta = metadata["packets"]
    whiteners = [whitener_for_source(row["source_file"]) for row in meta]
    continuous_cfo = [estimate_fractional_cfo_from_preamble(packet, refs[i].cfo_bins, cfg)
                      for i, packet in enumerate(packets)]
    rows = []
    for target_index, target_raw in enumerate(packets):
        w = whiteners[target_index]
        target = np.asarray(w @ target_raw, dtype=np.complex64)
        reference, ref_split = clean_multichirp_reference(target, cfg)
        for label, sir, offset, desired_sep in (
            ("clean", None, 0.0, None),
            ("near_aligned", 0.0, 0.0, 0.0),
            ("near_aligned_strong", -6.0, 0.0, 0.0),
            ("near_aligned_fractional", -6.0, 0.002, 0.0),
            ("separated_strong", -6.0, 0.0, 12.0),
        ):
            if sir is None:
                scene = target
                start = 0.0
                interferer_index = None
                shift = None
                measured_sep = None
            else:
                interferer_index = (target_index + 7) % len(packets)
                interferer = np.asarray(w @ packets[interferer_index], dtype=np.complex64)
                # Tune CFO after incorporating the actual sample timing offset.
                shift = continuous_cfo[target_index] - continuous_cfo[interferer_index] + desired_sep + offset * cfg.m
                scene, start, _ = synthesize_two_trace_packets(
                    target[:, :9 * cfg.samples_per_symbol],
                    interferer[:, :9 * cfg.samples_per_symbol], cfg,
                    offset_symbols=offset, sir_db=sir,
                    interferer_cfo_shift_bins=shift,
                    target_power=float(np.mean(abs(target) ** 2)),
                    interferer_power=float(np.mean(abs(interferer) ** 2)),
                )
                measured_sep = observed_bin_separation(target, interferer, cfg, offset, shift, continuous_cfo[target_index])
            estimate, rel = robust_preamble_channel_sp(scene, start, continuous_cfo[target_index], 0.0, cfg)
            error = math.degrees(channel_angle(estimate, reference))
            theta = math.degrees(rel.theta_total)
            rows.append({
                "target_index": target_index, "interferer_index": interferer_index,
                "condition": label, "sir_db": sir, "timing_offset_symbols": offset,
                "interferer_cfo_shift_bins": shift,
                "measured_dechirped_peak_gap_bins": measured_sep,
                "reference_split_half_deg": ref_split,
                "error_deg": error, "theta_deg": theta,
                "covered": int(error <= theta),
                "robust_hit_count": rel.robust_hit_count,
                "complete_preamble_windows": int(rel.robust_hit_count == cfg.preamble_len),
            })
        print(f"target {target_index + 1}/{len(packets)}", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "trials.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (args.out / "error_ecdf.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["condition", "error_deg", "cdf"])
        writer.writeheader()
        for label in dict.fromkeys(row["condition"] for row in rows):
            errors = sorted(row["error_deg"] for row in rows if row["condition"] == label)
            for rank, error in enumerate(errors, 1):
                writer.writerow({"condition": label, "error_deg": error, "cdf": rank / len(errors)})
    summary = {}
    for label in dict.fromkeys(row["condition"] for row in rows):
        subset = [row for row in rows if row["condition"] == label]
        errors = np.array([row["error_deg"] for row in subset])
        thetas = np.array([row["theta_deg"] for row in subset])
        summary[label] = {
            "count": len(subset), "complete_preamble_window_count": sum(row["complete_preamble_windows"] for row in subset),
            "coverage": float(np.mean([row["covered"] for row in subset])),
            "error_cdf_deg": {str(q): float(np.quantile(errors, q)) for q in (0.1, 0.5, 0.8, 0.9, 0.95)},
            "theta_median_deg": float(np.median(thetas)),
            "reference_split_half_median_deg": float(np.median([row["reference_split_half_deg"] for row in subset])),
            "reference_split_half_p90_deg": float(np.quantile([row["reference_split_half_deg"] for row in subset], 0.9)),
            "measured_gap_median_bins": float(np.median([row["measured_dechirped_peak_gap_bins"] for row in subset if row["measured_dechirped_peak_gap_bins"] is not None])) if label != "clean" else None,
            "measured_gap_max_bins": float(max(row["measured_dechirped_peak_gap_bins"] for row in subset)) if label != "clean" else None,
        }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
