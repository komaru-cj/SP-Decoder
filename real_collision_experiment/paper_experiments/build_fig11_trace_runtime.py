#!/usr/bin/env python3
"""Build Fig. 11 runtime and SER with a shared SP fine-synchronization boundary.

SP supplies every method with the same candidate identity and final fine
start/CFO/STO.  No comparison method re-synchronizes the packet.  LoRaWAN uses
physical Ch0 directly; MRC, CIC, PCube, and MaLoRaGW perform only the parameter
estimation required by their receiver and then decode the payload.  Oracle
packet starts, CFOs, channels, and source identities remain evaluation-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_fig11_matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[2]
RECEIVER_DIR = ROOT / "real_collision_experiment" / "node01_sp_receiver"
for path in (ROOT, RECEIVER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from compare.native_frontends import (  # noqa: E402
    cic_native_estimates,
    detect_native_frontends,
    projected_preamble_native_estimates,
)
from compare.real_packet_decoders import PaperComparisonContext  # noqa: E402
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda  # noqa: E402
from real_collision_experiment.paper_experiments.simulate_sp_mechanisms import (  # noqa: E402
    build_explicit_frame,
)
from lora_mrc_sp_core import (  # noqa: E402
    add_fractional_waveform,
    decode_packet_branch,
    estimate_preamble_ml_cfo_channel,
    fixed_mrc_branch_parameters,
)
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import (  # noqa: E402
    dc_remove_and_whiten,
)
from real_collision_experiment.node01_sp_receiver.sp_node01_receiver import (  # noqa: E402
    decode_method,
    decode_sp_stages,
    supplement_sp_estimates_with_continuous_sfd,
)
from real_sp_frontend import detected_estimates_real  # noqa: E402
from real_usrp_clean_packet_synth import load_extracted  # noqa: E402
from sp_detection_frontend import (  # noqa: E402
    ReferencePacket,
    preamble_channel_near_cfo,
    sfd_anchored_start_cfo_refine,
)


METHODS = ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw", "sp_sync_refine")
METHOD_LABELS = {
    "lorawan": "LoRaWAN",
    "mrc": "MRC",
    "mrc_cic": "MRC+CIC",
    "pcube": "PCube",
    "maloragw": "MaLoRaGW",
    "sp_sync_refine": "SP-Decoder",
}
METHOD_COLORS = {
    "lorawan": "#3B82B8",
    "mrc": "#6C757D",
    "mrc_cic": "#E76F51",
    "pcube": "#F4A261",
    "maloragw": "#6C5CE7",
    "sp_sync_refine": "#159D8A",
}
METHOD_MARKERS = {
    "lorawan": "v",
    "mrc": "o",
    "mrc_cic": "s",
    "pcube": "^",
    "maloragw": "D",
    "sp_sync_refine": "*",
}


def parse_orders(text: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in text.split(",") if item.strip())
    if not values or any(value < 2 for value in values):
        raise argparse.ArgumentTypeError("collision counts must all be at least 2")
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def bootstrap_mean(
    values: list[float], rng: np.random.Generator, repetitions: int = 20_000
) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(array))
    if array.size == 1:
        return mean, mean, mean
    sampled = rng.choice(array, size=(repetitions, array.size), replace=True)
    means = np.mean(sampled, axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return mean, float(low), float(high)


def source_noise_power(meta: dict, scale: float) -> float:
    powers = [
        float(meta.get("noise_rms_ch0", 0.0)) ** 2,
        float(meta.get("noise_rms_ch1", 0.0)) ** 2,
    ]
    return float(np.mean(powers)) * float(scale) ** 2


def resample_packet_bank(
    packets: np.ndarray, source_rate_hz: float, target_rate_hz: float
) -> np.ndarray:
    """Band-limited resampling while preserving packet-start time zero."""

    if abs(float(source_rate_hz) - float(target_rate_hz)) < 1e-9:
        return np.asarray(packets, dtype=np.complex64)
    ratio = Fraction(float(target_rate_hz) / float(source_rate_hz)).limit_denominator(64)
    expected = int(round(packets.shape[-1] * float(target_rate_hz) / float(source_rate_hz)))
    output = np.empty((packets.shape[0], packets.shape[1], expected), dtype=np.complex64)
    for packet_index in range(packets.shape[0]):
        converted = resample_poly(
            np.asarray(packets[packet_index], dtype=np.complex128),
            ratio.numerator,
            ratio.denominator,
            axis=-1,
        )
        if converted.shape[-1] < expected:
            raise RuntimeError("resampler returned fewer samples than the target frame")
        output[packet_index] = converted[..., :expected].astype(np.complex64)
    return output


def build_in_memory_references(
    packets: np.ndarray,
    packet_meta: list[dict],
    cfg: RealCollisionLoRaConfig,
) -> dict[int, ReferencePacket]:
    """Build symbol truth from the exact rate-converted waveforms under test."""

    references: dict[int, ReferencePacket] = {}
    for source_index, packet in enumerate(packets):
        meta = packet_meta[source_index]
        center = int(meta.get("peak_bin", 0))
        cfo = float(meta.get("cfo_bins", 0.0))
        ml = estimate_preamble_ml_cfo_channel(
            packet,
            0.0,
            cfg,
            center_bin=center,
            bin_radius=8,
            fine_cfo_grid=17,
        )
        decoded = decode_packet_branch(
            packet,
            int(source_index),
            0.0,
            cfo,
            fixed_mrc_branch_parameters(ml.channel),
            cfg,
        )
        references[source_index] = ReferencePacket(
            source_index=int(source_index),
            cfo_bins=cfo,
            sto_samples=0.0,
            channel=[
                [float(np.real(value)), float(np.imag(value))]
                for value in ml.channel
            ],
            symbol_bins=[int(item.symbol_bin) for item in decoded.decisions],
        )
    return references


def build_trace_channel_known_phy_bank(
    measured_packets: np.ndarray,
    packet_meta: list[dict],
    cfg: RealCollisionLoRaConfig,
    *,
    payload_seed: int,
) -> tuple[np.ndarray, dict[int, ReferencePacket]]:
    """Generate standards-compliant frames over measured dual-channel directions.

    The legacy clean-position traces do not carry transmitter symbol truth and
    their recorded implicit-header Sync/CRC profile is incompatible with the
    current receiver.  They are therefore used only to measure h and CFO.  A
    known explicit-header/CRC-valid PHY frame supplies auditable synchronization
    landmarks and symbol truth without replacing the measured spatial channel.
    """

    payload_rng = np.random.default_rng(int(payload_seed))
    bank = np.zeros(
        (len(measured_packets), 2, int(cfg.frame_samples)), dtype=np.complex64
    )
    references: dict[int, ReferencePacket] = {}
    time_index = np.arange(int(cfg.frame_samples), dtype=np.float64)
    for source_index, measured in enumerate(measured_packets):
        meta = packet_meta[source_index]
        center = int(meta.get("peak_bin", 0))
        coarse_cfo = float(meta.get("cfo_bins", 0.0))
        ml = estimate_preamble_ml_cfo_channel(
            measured,
            0.0,
            cfg,
            center_bin=center,
            bin_radius=8,
            fine_cfo_grid=17,
        )
        h = np.asarray(ml.channel, dtype=np.complex128)
        h /= math.sqrt(float(np.vdot(h, h).real)) + 1e-30
        payload = payload_rng.integers(
            0, 256, size=int(cfg.payload_len), dtype=np.uint8
        ).tobytes()
        frame, symbol_bins = build_explicit_frame(payload, cfg)
        carrier = np.exp(
            1j
            * 2.0
            * math.pi
            * coarse_cfo
            * time_index
            / float(cfg.samples_per_symbol)
        )
        bank[source_index] = (
            h[:, None] * frame[None, :] * carrier[None, :]
        ).astype(np.complex64)
        references[source_index] = ReferencePacket(
            source_index=int(source_index),
            cfo_bins=float(coarse_cfo),
            sto_samples=0.0,
            channel=[
                [float(np.real(value)), float(np.imag(value))] for value in h
            ],
            symbol_bins=[int(value) for value in symbol_bins],
        )
    return bank, references


def select_channel_packets(
    packet_meta: list[dict],
    count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Select measured packets for one collision scene.

    The first pass uses at most one packet per RF position.  If the requested
    order exceeds the number of measured positions, extra entries are drawn
    from unused repetitions and the scene is marked in the CSV/audit by its
    reduced distinct-position count.  Selection never inspects decoder output.
    """

    groups: dict[str, list[int]] = defaultdict(list)
    for source_index, meta in enumerate(packet_meta):
        source_file = str(meta.get("source_file", f"source_{source_index}"))
        position_key = Path(source_file).name
        groups[position_key].append(int(source_index))
    keys = sorted(groups)
    distinct_count = min(int(count), len(keys))
    chosen_keys = list(rng.choice(keys, size=distinct_count, replace=False))
    chosen = [int(rng.choice(groups[str(key)])) for key in chosen_keys]
    if len(chosen) < int(count):
        used = set(chosen)
        extra_pool = [
            int(index)
            for key in keys
            for index in groups[key]
            if int(index) not in used
        ]
        if len(extra_pool) < int(count) - len(chosen):
            raise ValueError(
                f"requested {count} packets, only {len(packet_meta)} clean packets are available"
            )
        chosen.extend(
            int(value)
            for value in rng.choice(
                extra_pool, size=int(count) - len(chosen), replace=False
            )
        )
    return np.asarray(chosen, dtype=np.int64)


def selected_position_keys(packet_meta: list[dict], selected: np.ndarray) -> list[str]:
    keys: list[str] = []
    for source_index in selected:
        meta = packet_meta[int(source_index)]
        keys.append(Path(str(meta.get("source_file", f"source_{source_index}"))).name)
    return keys


def build_scene(
    packets: np.ndarray,
    packet_meta: list[dict],
    cfg: RealCollisionLoRaConfig,
    selected: np.ndarray,
    rng: np.random.Generator,
    *,
    min_offset_symbols: float,
    max_offset_symbols: float,
    min_fractional_chirp_offset: float,
    stagger_high_order_preambles: bool = True,
    uniform_stagger_spacing_symbols: float = 4.25,
) -> tuple[np.ndarray, list[dict], list[float], float]:
    """Construct one equal-RMS collision and evaluation-only truth table."""

    if bool(stagger_high_order_preambles):
        # Apply the same construction to 2/4/6/8 packets.  Adjacent starts are
        # approximately 4.25 chirps apart: preambles overlap by at most about
        # two packets, while payload windows still collide substantially.  A
        # bounded jitter and an ADC-sample-domain guard ensure no pair differs
        # by an exact integer number of chirps.
        count = len(selected)
        target_span = min(
            2.0 * float(max_offset_symbols),
            float(uniform_stagger_spacing_symbols) * max(0, count - 1),
            float(cfg.frame_symbols) - 1.0,
        )
        if abs(target_span - round(target_span)) < 1e-9:
            target_span -= max(0.125, 2.0 * float(min_fractional_chirp_offset))
        alignment_guard_samples = max(8, int(round(0.015 * cfg.samples_per_symbol)))
        for _attempt in range(10_000):
            positions = np.linspace(0.0, target_span, num=count, dtype=np.float64)
            if count > 2:
                positions[1:-1] += rng.uniform(-0.10, 0.10, size=count - 2)
            positions.sort()
            centered = positions - 0.5 * (positions[0] + positions[-1])
            sample_offsets = np.rint(
                centered * float(cfg.samples_per_symbol)
            ).astype(np.int64)
            pairwise_non_aligned = True
            for left in range(count):
                for right in range(left + 1, count):
                    delta = abs(int(sample_offsets[right] - sample_offsets[left]))
                    remainder = delta % int(cfg.samples_per_symbol)
                    circular = min(remainder, int(cfg.samples_per_symbol) - remainder)
                    if circular < alignment_guard_samples:
                        pairwise_non_aligned = False
                        break
                if not pairwise_non_aligned:
                    break
            if pairwise_non_aligned:
                break
        else:
            raise RuntimeError("could not construct pairwise non-aligned staggered starts")
        offsets_array = sample_offsets.astype(np.float64) / float(
            cfg.samples_per_symbol
        )
        offsets = [float(value) for value in rng.permutation(offsets_array)]
    else:
        offsets = [0.0]
        for _ in range(1, len(selected)):
            for _attempt in range(10_000):
                magnitude = float(rng.uniform(min_offset_symbols, max_offset_symbols))
                fractional = abs(magnitude - round(magnitude))
                distance_to_integer = min(fractional, 1.0 - fractional)
                if distance_to_integer >= float(min_fractional_chirp_offset):
                    break
            else:
                raise RuntimeError("could not draw a non-aligned fractional chirp offset")
            offsets.append(magnitude if bool(rng.integers(0, 2)) else -magnitude)
    guard_symbols = max_offset_symbols + 1.0
    # Trace-driven collision means shifting already sampled IQ by an integer
    # number of ADC samples.  The offsets remain non-integer in chirp units;
    # applying a second fractional linear interpolation to measured IQ creates
    # an artificial timing/filter impairment that was absent in the capture.
    starts = [
        float(
            int(
                round(
                    (guard_symbols + float(offset))
                    * cfg.samples_per_symbol
                )
            )
        )
        for offset in offsets
    ]
    total_samples = int(
        math.ceil(
            max(starts)
            + cfg.frame_samples
            + guard_symbols * cfg.samples_per_symbol
        )
    )
    scene = np.zeros((2, total_samples), dtype=np.complex64)
    truth_packets: list[dict] = []
    noise_time_power = 0.0
    for scene_index, (source_index, start) in enumerate(zip(selected, starts)):
        packet = packets[int(source_index)]
        rms = math.sqrt(float(np.mean(np.abs(packet) ** 2)))
        scale = 1.0 / max(rms, 1e-12)
        for channel in range(2):
            add_fractional_waveform(
                scene[channel], packet[channel], float(start), complex(scale)
            )
        truth_packets.append(
            {
                "packet_index": int(scene_index),
                "source_packet_index": int(source_index),
                "start_sample": float(start),
            }
        )
        noise_time_power += source_noise_power(packet_meta[int(source_index)], scale)
    return scene, truth_packets, offsets, noise_time_power


def maximum_preamble_overlap(offsets: list[float], preamble_symbols: float) -> int:
    events: list[tuple[float, int]] = []
    for offset in offsets:
        events.append((float(offset), 1))
        events.append((float(offset) + float(preamble_symbols), -1))
    active = 0
    maximum = 0
    # End events precede start events at an exact boundary.
    for _, delta in sorted(events, key=lambda row: (row[0], row[1])):
        active += int(delta)
        maximum = max(maximum, active)
    return int(maximum)


def complete_estimates(
    estimates: list[dict], sample_count: int, cfg: RealCollisionLoRaConfig
) -> list[dict]:
    return [
        estimate
        for estimate in estimates
        if float(estimate["start_sample"]) >= 0.0
        and float(estimate["start_sample"])
        + float(estimate.get("sto_samples", 0.0))
        + float(cfg.frame_samples)
        <= float(sample_count)
    ]


def current_sp_frontend(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    max_candidates: int,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    scan_phase_count: int,
) -> list[dict]:
    estimates, _ = detected_estimates_real(
        samples,
        cfg,
        max_candidates=max_candidates,
        raw_candidate_limit=max_candidates,
        threshold=threshold,
        step_samples=int(cfg.samples_per_symbol),
        scan_phase_count=int(scan_phase_count),
        min_sync_score=0.0,
        min_coherent_metric=0.0,
        cfo_min=cfo_min,
        cfo_max=cfo_max,
        min_sfd_score=10.0,
        min_refined_sync_score=500.0,
        use_local_projection_tracks=False,
        use_spatial_residual_tracks=True,
        fast_single_node=True,
        fast_grid_refine=False,
    )
    return complete_estimates(estimates, samples.shape[1], cfg)


def native_frontend(
    method: str,
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    max_candidates: int,
    candidates_per_window: int,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
) -> tuple[list[dict], dict]:
    scan_ranges = [(0, int(samples.shape[1]))]
    if method == "mrc_cic":
        estimates, diagnostics = cic_native_estimates(
            samples,
            cfg,
            scan_ranges,
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            max_candidates=max_candidates,
        )
    else:
        estimates, diagnostics = projected_preamble_native_estimates(
            samples,
            cfg,
            scan_ranges,
            method=method,
            threshold=threshold,
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            max_candidates=max_candidates,
            candidates_per_window=candidates_per_window,
        )
    return complete_estimates(estimates, samples.shape[1], cfg), diagnostics


def prepare_receiver_inputs(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    max_candidates: int,
    candidates_per_window: int,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    sp_scan_phase_count: int,
) -> dict:
    """Run SP detection/fine sync and freeze that sync for every receiver.

    This stage is excluded from Fig. 11 latency but its outputs are the only
    estimates supplied to the payload decoders and therefore fully determine
    the SER figure.
    """

    raw = np.asarray(samples, dtype=np.complex64)
    white, _, sigma2_time, calibration = dc_remove_and_whiten(
        raw,
        noise_samples=max(128, int(round(0.75 * cfg.samples_per_symbol))),
    )
    dc = np.asarray(
        [complex(float(value[0]), float(value[1])) for value in calibration["dc"]],
        dtype=np.complex64,
    )
    physical = np.asarray(raw - dc[:, None], dtype=np.complex64)
    noise_sigma2_fft = max(float(cfg.m) * float(sigma2_time), 1e-12)
    current = current_sp_frontend(
        white,
        cfg,
        max_candidates=max_candidates,
        threshold=threshold,
        cfo_min=cfo_min,
        cfo_max=cfo_max,
        scan_phase_count=sp_scan_phase_count,
    )
    # Use the same continuous-SFD supplement as the formal real-capture
    # receiver so Fig. 11 no longer carries a private acquisition path.
    sp_estimates, sfd_supplement_diagnostics = (
        supplement_sp_estimates_with_continuous_sfd(
            physical,
            white,
            cfg,
            current,
            [(0, int(physical.shape[1]))],
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            max_candidates=max_candidates,
        )
    )
    estimation_policy = {
        "lorawan": "none; physical Ch0 top-1 payload decisions",
        "mrc": "own physical-pair preamble channel estimate at fixed SP sync",
        "mrc_cic": "fixed target MRC and combined preamble RSSI/fractional-frequency features",
        "pcube": "own target-preamble PDoA estimate at fixed SP sync",
        "maloragw": "own preamble channel matrix and peak features at fixed SP sync",
    }
    shared_estimates: dict[str, list[dict]] = {}
    native_diagnostics: dict[str, dict] = {}
    for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw"):
        method_rows: list[dict] = []
        for candidate_index, estimate in enumerate(sp_estimates):
            row = dict(estimate)
            row["_comparison_candidate_index"] = int(candidate_index)
            row["shared_sp_fine_sync"] = True
            row["shared_sp_fine_sync_seed"] = True
            row["paper_method_refinement_applied"] = False
            row["paper_method_parameter_estimation_applied"] = bool(
                method != "lorawan"
            )
            method_rows.append(row)
        shared_estimates[method] = method_rows
        native_diagnostics[method] = {
            "paper_frontend": "shared SP candidate and final fine start/CFO/STO",
            "shared_sp_candidate_identity": True,
            "shared_sp_fine_start_cfo_sto": True,
            "method_specific_resynchronization": False,
            "method_parameter_estimation": estimation_policy[method],
            "candidate_count": int(len(method_rows)),
        }
    native_diagnostics["sp_detection"] = {
        "paper_frontend": (
            "interleaved preamble tracks plus continuous SFD-pair supplement"
        ),
        "preamble_candidate_count": int(len(current)),
        "sfd_supplement_raw_count": int(
            sfd_supplement_diagnostics["sfd_raw_candidate_count"]
        ),
        "final_candidate_count": int(len(sp_estimates)),
        "sfd_supplement_diagnostics": sfd_supplement_diagnostics,
    }
    estimates = {
        method: complete_estimates(
            [dict(item) for item in shared_estimates.get(method, [])],
            physical.shape[1],
            cfg,
        )
        for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw")
    }
    estimates["sp_sync_refine"] = sp_estimates
    return {
        "white": white,
        "physical": physical,
        "estimates": estimates,
        "sp_detection_estimates": [dict(item) for item in sp_estimates],
        "native_diagnostics": native_diagnostics,
        "frontend_names": {
            "sp_sync_refine": (
                "interleaved_preamble_tracks_plus_continuous_sfd_pair_supplement"
            ),
            **{
                method: str(
                    native_diagnostics.get(method, {}).get(
                        "paper_frontend", f"{method}_native_frontend"
                    )
                )
                for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw")
            },
        },
        "noise_sigma2_fft": noise_sigma2_fft,
        "threshold": float(threshold),
        "cfo_min": float(cfo_min),
        "cfo_max": float(cfo_max),
        "candidates_per_window": int(candidates_per_window),
        "sp_scan_phase_count": int(sp_scan_phase_count),
    }


def replay_sp_refinement_from_coarse(
    samples: np.ndarray,
    coarse_source_estimates: list[dict],
    cfg: RealCollisionLoRaConfig,
    *,
    cfo_min: float,
    cfo_max: float,
    coarse_phase_count: int,
) -> list[dict]:
    """Replay SP fine start/CFO/channel estimation from quantized coarse starts.

    This is used for Fig. 11 timing only.  It starts from the same coarse packet
    positions exposed after SP detection and does not inspect payload symbols,
    CRC, source identity, or evaluation truth.
    """

    symbol_samples = int(cfg.samples_per_symbol)
    phase_count = max(1, int(coarse_phase_count))
    phase_spacing = float(symbol_samples) / float(phase_count)
    refined: list[dict] = []
    for seed_index, fine in enumerate(coarse_source_estimates):
        aligned = float(fine["start_sample"]) + float(fine.get("sto_samples", 0.0))
        coarse = round(aligned / phase_spacing) * phase_spacing
        try:
            sfd_start, sfd_cfo, cto_samples, sfd_score, _, _ = (
                sfd_anchored_start_cfo_refine(
                    samples,
                    float(coarse),
                    cfg,
                    symbol_radius=0,
                    local_radius_bins=int(max(96.0, abs(cfo_min), abs(cfo_max))),
                    coarse_up_bin=float(fine.get("cfo_bins", 0.0)),
                    physical_cfo_min=float(cfo_min),
                    physical_cfo_max=float(cfo_max),
                    max_start_correction_samples=0.75 * phase_spacing,
                )
            )
            cfo = float(min(max(float(sfd_cfo), float(cfo_min)), float(cfo_max)))
            channel_score, channel, peak_bin = preamble_channel_near_cfo(
                samples, float(sfd_start), cfo, cfg, radius_bins=2
            )
            start_floor = float(math.floor(float(sfd_start)))
            row = dict(fine)
            row.update(
                {
                    "start_sample": start_floor,
                    "sto_samples": float(sfd_start) - start_floor,
                    "cfo_bins": cfo,
                    "continuous_cfo_bins": cfo,
                    "cto_samples": float(cto_samples),
                    "channel": [
                        [float(np.real(value)), float(np.imag(value))]
                        for value in channel
                    ],
                    "power": float(np.vdot(channel, channel).real),
                    "confidence": float(max(channel_score, sfd_score)),
                    "peak_bin": int(peak_bin),
                    "sp_coarse_seed_index": int(seed_index),
                    "sp_coarse_start_sample": float(coarse),
                    "frontend_candidate_stage": "timed_sp_coarse_to_fine_replay",
                }
            )
        except Exception:
            row = dict(fine)
            row["sp_refinement_replay_failed"] = True
            row["sp_coarse_seed_index"] = int(seed_index)
            row["sp_coarse_start_sample"] = float(coarse)
        refined.append(row)
    return complete_estimates(refined, samples.shape[1], cfg)


def timed_estimates_for_method(
    method: str,
    prepared: dict,
    cfg: RealCollisionLoRaConfig,
) -> tuple[list[dict], np.ndarray]:
    if method == "lorawan":
        return [dict(item) for item in prepared["estimates"][method]], prepared[
            "physical"
        ]
    if method in {"mrc", "mrc_cic", "pcube", "maloragw"}:
        return [dict(item) for item in prepared["estimates"][method]], prepared[
            "physical"
        ]
    if method == "sp_sync_refine":
        estimates = replay_sp_refinement_from_coarse(
            prepared["white"],
            prepared["sp_detection_estimates"],
            cfg,
            cfo_min=float(prepared["cfo_min"]),
            cfo_max=float(prepared["cfo_max"]),
            coarse_phase_count=int(prepared["sp_scan_phase_count"]),
        )
        return estimates, prepared["white"]
    raise ValueError(f"unknown method: {method}")


def payload_decode_pass(
    method: str,
    prepared: dict,
    cfg: RealCollisionLoRaConfig,
    *,
    sp_sync_max_trials: int,
    collect_ser: bool,
) -> tuple[list[dict], list[float]]:
    """Decode candidates and time post-SP-coarse processing."""

    decoded: list[dict] = []
    elapsed_ms: list[float] = []

    if method in {"lorawan", "mrc_cic", "pcube", "maloragw"}:
        started_ns = time.perf_counter_ns()
        estimates, samples = timed_estimates_for_method(method, prepared, cfg)
        for candidate_index, estimate in enumerate(estimates):
            estimate["_comparison_candidate_index"] = int(candidate_index)
        context = PaperComparisonContext(
            samples,
            estimates,
            cfg,
            frontend_method=method,
        )
        decoder = {
            "lorawan": context.decode_lorawan,
            "mrc_cic": context.decode_cic,
            "pcube": context.decode_pcube,
            "maloragw": context.decode_maloragw,
        }[method]
        results: list[dict] = []
        for estimate in estimates:
            result = decoder(estimate)
            results.append(result)
            if collect_ser:
                decoded.append({"estimate": estimate, "result": result})
        total_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
        if estimates:
            elapsed_ms = [total_ms / len(estimates)] * len(estimates)
        return decoded, elapsed_ms

    if method == "mrc":
        estimates, samples = timed_estimates_for_method(method, prepared, cfg)
        started_ns = time.perf_counter_ns()
        for candidate_index, estimate in enumerate(estimates):
            estimate["_comparison_candidate_index"] = int(candidate_index)
        context = PaperComparisonContext(samples, estimates, cfg, frontend_method="mrc")
        for estimate in estimates:
            result = context.decode_mrc(estimate)
            if collect_ser:
                decoded.append({"estimate": estimate, "result": result})
        total_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
        if estimates:
            elapsed_ms = [total_ms / len(estimates)] * len(estimates)
        return decoded, elapsed_ms

    started_ns = time.perf_counter_ns()
    estimates, samples = timed_estimates_for_method(method, prepared, cfg)
    configured_estimates = attach_sp_reliability_and_lambda(
        samples,
        [dict(item) for item in estimates],
        cfg,
        noise_sigma2=float(prepared["noise_sigma2_fft"]),
        gamma=0.05,
        max_lambda=None,
    )
    for estimate in configured_estimates:
        core_estimate = dict(estimate)
        core_estimate["_sp_disable_cfo_trials"] = True
        core_estimate["_sp_disable_repair"] = True
        core_estimate["_disable_lambda_endpoint_retry"] = True
        decode_method("sp", samples, core_estimate, cfg)
    total_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
    if configured_estimates:
        elapsed_ms = [total_ms / len(configured_estimates)] * len(configured_estimates)
    if collect_ser:
        ser_configured_estimates = attach_sp_reliability_and_lambda(
            samples,
            [dict(item) for item in prepared["estimates"][method]],
            cfg,
            noise_sigma2=float(prepared["noise_sigma2_fft"]),
            gamma=0.05,
            max_lambda=None,
        )
        for estimate in ser_configured_estimates:
            stages = decode_sp_stages(
                samples,
                estimate,
                cfg,
                max_sync_trials=sp_sync_max_trials,
            )
            result = next(
                row for row in stages if row["method"] == "sp_sync_refine"
            )
            decoded.append({"estimate": estimate, "result": result})
    return decoded, elapsed_ms


def decode_prepared_for_ser(
    method: str,
    prepared: dict,
    cfg: RealCollisionLoRaConfig,
    *,
    sp_sync_max_trials: int,
) -> list[dict]:
    """Decode from already prepared synchronization estimates for SER only."""

    estimates = [dict(item) for item in prepared["estimates"][method]]
    samples = prepared["white"] if method == "sp_sync_refine" else prepared["physical"]
    decoded: list[dict] = []
    if method in {"lorawan", "mrc_cic", "pcube", "maloragw"}:
        for candidate_index, estimate in enumerate(estimates):
            estimate["_comparison_candidate_index"] = int(candidate_index)
        context = PaperComparisonContext(
            samples,
            estimates,
            cfg,
            frontend_method=method,
        )
        decoder = {
            "lorawan": context.decode_lorawan,
            "mrc_cic": context.decode_cic,
            "pcube": context.decode_pcube,
            "maloragw": context.decode_maloragw,
        }[method]
        for estimate in estimates:
            decoded.append({"estimate": estimate, "result": decoder(estimate)})
        return decoded
    if method == "mrc":
        for candidate_index, estimate in enumerate(estimates):
            estimate["_comparison_candidate_index"] = int(candidate_index)
        context = PaperComparisonContext(samples, estimates, cfg, frontend_method="mrc")
        for estimate in estimates:
            decoded.append(
                {"estimate": estimate, "result": context.decode_mrc(estimate)}
            )
        return decoded

    configured_estimates = attach_sp_reliability_and_lambda(
        samples,
        estimates,
        cfg,
        noise_sigma2=float(prepared["noise_sigma2_fft"]),
        gamma=0.05,
        max_lambda=None,
    )
    for estimate in configured_estimates:
        stages = decode_sp_stages(
            samples,
            estimate,
            cfg,
            max_sync_trials=sp_sync_max_trials,
        )
        result = next(row for row in stages if row["method"] == "sp_sync_refine")
        decoded.append({"estimate": estimate, "result": result})
    return decoded


def aligned_start(estimate: dict) -> float:
    return float(estimate["start_sample"]) + float(
        estimate.get("sto_samples_sp", estimate.get("sto_samples", 0.0))
    )


def match_detections_for_evaluation(
    truth_packets: list[dict],
    decoded: list[dict],
    *,
    tolerance_samples: float,
) -> list[dict | None]:
    """One-to-one matching used only after every decoder has finished."""

    pairs: list[tuple[float, int, int]] = []
    for truth_index, truth in enumerate(truth_packets):
        for detected_index, row in enumerate(decoded):
            error = abs(
                aligned_start(row["estimate"]) - float(truth["start_sample"])
            )
            if error <= float(tolerance_samples):
                pairs.append((float(error), truth_index, detected_index))
    matched: list[dict | None] = [None] * len(truth_packets)
    used_truth: set[int] = set()
    used_detected: set[int] = set()
    for _, truth_index, detected_index in sorted(pairs):
        if truth_index in used_truth or detected_index in used_detected:
            continue
        matched[truth_index] = decoded[detected_index]
        used_truth.add(truth_index)
        used_detected.add(detected_index)
    return matched


def strict_ser(decoded_bins: list[int], truth_bins: list[int]) -> float:
    if not truth_bins:
        return 1.0
    errors = 0
    for index, truth_bin in enumerate(truth_bins):
        if index >= len(decoded_bins) or int(decoded_bins[index]) != int(truth_bin):
            errors += 1
    return float(errors) / float(len(truth_bins))


def evaluate_receiver_output(
    receiver: dict,
    truth_packets: list[dict],
    references: dict,
    cfg: RealCollisionLoRaConfig,
) -> tuple[float, list[dict]]:
    matched = match_detections_for_evaluation(
        truth_packets,
        receiver["decoded"],
        tolerance_samples=0.25 * float(cfg.samples_per_symbol),
    )
    rows: list[dict] = []
    for truth, detected in zip(truth_packets, matched):
        reference = references[int(truth["source_packet_index"])]
        if detected is None:
            ser = 1.0
            detected_start = None
            detected_cfo = None
            status = "frontend_miss"
        else:
            result = detected["result"]
            ser = strict_ser(
                [int(value) for value in result.get("symbol_bins", [])],
                [int(value) for value in reference.symbol_bins],
            )
            estimate = detected["estimate"]
            detected_start = aligned_start(estimate)
            detected_cfo = float(
                estimate.get(
                    "cfo_bins_sp",
                    estimate.get("continuous_cfo_bins", estimate["cfo_bins"]),
                )
            )
            status = "decoded"
        rows.append(
            {
                "truth_packet_index": int(truth["packet_index"]),
                "source_packet_index": int(truth["source_packet_index"]),
                "truth_start_sample_evaluation_only": float(truth["start_sample"]),
                "detected_start_sample": detected_start,
                "detected_cfo_bins": detected_cfo,
                "status": status,
                "ser": float(ser),
            }
        )
    return float(np.mean([row["ser"] for row in rows])), rows


def aggregate_rows(
    timing_rows: list[dict], ser_scene_rows: list[dict], rng: np.random.Generator
) -> list[dict]:
    timing_repeats: dict[tuple[int, str, int], list[float]] = defaultdict(list)
    for row in timing_rows:
        value = row.get("payload_decode_time_per_detected_packet_ms")
        if value not in (None, ""):
            timing_repeats[
                (
                    int(row["collision_order"]),
                    str(row["method"]),
                    int(row["scene_index"]),
                )
            ].append(float(value))
    timing_cells: dict[tuple[int, str], list[float]] = defaultdict(list)
    for (order, method, _), values in timing_repeats.items():
        # Repetitions quantify timing jitter; independently constructed scenes
        # are the statistical units used by the bootstrap confidence interval.
        timing_cells[(order, method)].append(float(np.median(values)))
    ser_cells: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in ser_scene_rows:
        ser_cells[(int(row["collision_order"]), str(row["method"]))].append(row)

    output: list[dict] = []
    for order, method in sorted(ser_cells):
        scenes = ser_cells[(order, method)]
        times = timing_cells.get((order, method), [])
        sers = [float(row["scene_ser"]) for row in scenes]
        detection_rates = [float(row["matched_detection_rate"]) for row in scenes]
        conditional_sers = [
            float(row["conditional_ser_detected_packets"])
            for row in scenes
            if row.get("conditional_ser_detected_packets") not in (None, "")
        ]
        if times:
            time_mean, time_low, time_high = bootstrap_mean(times, rng)
            time_median = float(np.median(times))
        else:
            time_mean = time_low = time_high = time_median = float("nan")
        ser_mean, ser_low, ser_high = bootstrap_mean(sers, rng)
        output.append(
            {
                "collision_order": int(order),
                "method": method,
                "method_label": METHOD_LABELS[method],
                "scene_count": len(scenes),
                "timed_scene_count": len(times),
                "payload_decode_time_mean_ms": time_mean,
                "payload_decode_time_ci95_low_ms": time_low,
                "payload_decode_time_ci95_high_ms": time_high,
                "payload_decode_time_median_ms": time_median,
                "ser_mean": ser_mean,
                "ser_ci95_low": ser_low,
                "ser_ci95_high": ser_high,
                "matched_detection_rate_mean": float(np.mean(detection_rates)),
                "conditional_ser_detected_packets_mean": (
                    float(np.mean(conditional_sers))
                    if conditional_sers
                    else float("nan")
                ),
                "mean_detected_packet_count": float(
                    np.mean([float(row["detected_count"]) for row in scenes])
                ),
            }
        )
    return output


def plot_runtime(
    rows: list[dict], out_prefix: Path, *, runtime_orders: tuple[int, ...] | None = None
) -> None:
    allowed = set(int(value) for value in runtime_orders) if runtime_orders else None
    orders = sorted(
        {
            int(row["collision_order"])
            for row in rows
            if (allowed is None or int(row["collision_order"]) in allowed)
        }
    )
    x = np.arange(len(orders), dtype=np.float64)
    width = 0.84 / len(METHODS)
    fig, axis = plt.subplots(figsize=(7.5, 4.2))
    for method_index, method in enumerate(METHODS):
        selected = {
            int(row["collision_order"]): row
            for row in rows
            if row["method"] == method
        }
        values = np.asarray(
            [float(selected[order]["payload_decode_time_mean_ms"]) for order in orders]
        )
        low = np.asarray(
            [float(selected[order]["payload_decode_time_ci95_low_ms"]) for order in orders]
        )
        high = np.asarray(
            [float(selected[order]["payload_decode_time_ci95_high_ms"]) for order in orders]
        )
        positions = x - 0.42 + width / 2.0 + method_index * width
        axis.bar(
            positions,
            values,
            width=width,
            color=METHOD_COLORS[method],
            yerr=np.vstack([values - low, high - values]),
            capsize=2.2,
            label=METHOD_LABELS[method],
        )
    axis.set_xticks(x, [str(order) for order in orders])
    axis.set_xlabel("Number of colliding packets")
    axis.set_ylabel("Post-SP-fine estimation + decode time / packet (ms)")
    axis.set_title("Shared SP fine synchronization excluded")
    axis.grid(axis="y", alpha=0.24)
    axis.legend(ncol=3, fontsize=7.6, frameon=False)
    fig.tight_layout()
    for suffix in (".pdf", ".png", ".svg"):
        fig.savefig(out_prefix.with_suffix(suffix), dpi=240, bbox_inches="tight")
    plt.close(fig)


def plot_ser(rows: list[dict], out_prefix: Path) -> None:
    orders = sorted({int(row["collision_order"]) for row in rows})
    fig, axis = plt.subplots(figsize=(7.2, 4.1))
    for method in METHODS:
        selected = {
            int(row["collision_order"]): row
            for row in rows
            if row["method"] == method
        }
        values = np.asarray([float(selected[order]["ser_mean"]) for order in orders])
        low = np.asarray([float(selected[order]["ser_ci95_low"]) for order in orders])
        high = np.asarray([float(selected[order]["ser_ci95_high"]) for order in orders])
        axis.errorbar(
            orders,
            values,
            yerr=np.vstack([values - low, high - values]),
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            markersize=6.0 if method != "sp_sync_refine" else 8.0,
            linewidth=2.0,
            capsize=2.5,
            label=METHOD_LABELS[method],
        )
    axis.set_xticks(orders)
    axis.set_ylim(-0.03, 1.03)
    axis.set_xlabel("Number of colliding packets")
    axis.set_ylabel("SER (parameter-refinement failures count as 1)")
    axis.set_title("Shared SP detection; no oracle payload information")
    axis.grid(alpha=0.24)
    axis.legend(ncol=3, fontsize=7.6, frameon=False)
    fig.tight_layout()
    for suffix in (".pdf", ".png", ".svg"):
        fig.savefig(out_prefix.with_suffix(suffix), dpi=240, bbox_inches="tight")
    plt.close(fig)


def plot_combined(
    rows: list[dict], out_prefix: Path, *, runtime_orders: tuple[int, ...] | None = None
) -> None:
    orders = sorted({int(row["collision_order"]) for row in rows})
    runtime_allowed = (
        set(int(value) for value in runtime_orders)
        if runtime_orders
        else set(orders)
    )
    runtime_plot_orders = [order for order in orders if order in runtime_allowed]
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.0))
    x = np.arange(len(runtime_plot_orders), dtype=np.float64)
    width = 0.84 / len(METHODS)
    for method_index, method in enumerate(METHODS):
        selected = {
            int(row["collision_order"]): row
            for row in rows
            if row["method"] == method
        }
        times = np.asarray(
            [
                float(selected[order]["payload_decode_time_mean_ms"])
                for order in runtime_plot_orders
            ]
        )
        positions = x - 0.42 + width / 2.0 + method_index * width
        axes[0].bar(
            positions,
            times,
            width=width,
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
        )
        sers = [float(selected[order]["ser_mean"]) for order in orders]
        axes[1].plot(
            orders,
            sers,
            color=METHOD_COLORS[method],
            marker=METHOD_MARKERS[method],
            linewidth=2.0,
            markersize=5.5 if method != "sp_sync_refine" else 7.5,
            label=METHOD_LABELS[method],
        )
    axes[0].set_xticks(x, [str(order) for order in runtime_plot_orders])
    axes[0].set_xlabel("Number of colliding packets")
    axes[0].set_ylabel("Post-SP-fine time / detected packet (ms)")
    axes[0].set_title("(a) Runtime after shared SP fine sync", fontweight="bold")
    axes[1].set_xticks(orders)
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].set_xlabel("Number of colliding packets")
    axes[1].set_ylabel("SER (refinement failures = 1)")
    axes[1].set_title("(b) Shared-detection symbol errors", fontweight="bold")
    for axis in axes:
        axis.grid(axis="y", alpha=0.24)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, frameon=False)
    fig.suptitle(
        "Runtime includes method estimation and decode after shared SP fine synchronization",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0.10, 1, 0.94))
    for suffix in (".pdf", ".png", ".svg"):
        fig.savefig(out_prefix.with_suffix(suffix), dpi=240, bbox_inches="tight")
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean-packets",
        type=Path,
        default=ROOT / "real_usrp_outputs/clean_pos_packets.npz",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "real_usrp_outputs/fig11_trace_runtime",
    )
    parser.add_argument(
        "--collision-orders", type=parse_orders, default=(2, 4, 6, 8, 10)
    )
    parser.add_argument(
        "--runtime-orders",
        type=parse_orders,
        default=(2, 4, 6, 8, 10),
        help="collision orders shown in Fig. 11(a); SER still uses --collision-orders",
    )
    parser.add_argument("--scenes-per-order", type=int, default=4)
    parser.add_argument("--timing-repeats", type=int, default=3)
    parser.add_argument(
        "--trace-driven-known-phy",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "use measured dual-channel directions/CFO with explicit-header, "
            "CRC-valid PHY frames whose transmitted symbols are known"
        ),
    )
    parser.add_argument(
        "--payload-seed",
        type=int,
        default=20260802,
        help="deterministic payload seed for the auditable trace-channel frame bank",
    )
    parser.add_argument(
        "--scene-snr-db",
        type=float,
        default=30.0,
        help="per-packet time-domain SNR after equal-RMS normalization",
    )
    parser.add_argument(
        "--evaluation-rate-hz",
        type=float,
        default=500_000.0,
        help="rate used by every receiver after band-limited conversion of the measured IQ",
    )
    parser.add_argument("--min-offset-symbols", type=float, default=5.0)
    parser.add_argument(
        "--max-offset-symbols",
        type=float,
        default=15.0,
        help=(
            "maximum signed asynchronous offset; 15 symbols preserves a long "
            "payload collision while avoiding an artificial all-preambles-aligned case"
        ),
    )
    parser.add_argument(
        "--min-fractional-chirp-offset",
        type=float,
        default=0.2,
        help="minimum distance from an integer-symbol offset; prevents near-aligned chirp windows",
    )
    parser.add_argument(
        "--stagger-high-order-preambles",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "for every collision order, distribute starts approximately uniformly "
            "inside one-frame overlap while avoiding pairwise chirp alignment"
        ),
    )
    parser.add_argument(
        "--uniform-stagger-spacing-symbols",
        type=float,
        default=4.25,
        help="target adjacent start spacing for the constrained Fig. 11 scenes",
    )
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--cfo-min", type=float, default=-32.0)
    parser.add_argument("--cfo-max", type=float, default=32.0)
    parser.add_argument("--candidates-per-window", type=int, default=16)
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument("--sp-sync-max-trials", type=int, default=32)
    parser.add_argument(
        "--sp-scan-phase-count",
        type=int,
        default=8,
        help=(
            "interleaved phases of the one-symbol SP preamble scan; 8 covers "
            "the chirp period at 1/8-symbol spacing before local start/CFO refinement"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260801)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.scenes_per_order < 1 or args.timing_repeats < 1:
        raise SystemExit("scene and timing-repeat counts must be positive")
    if args.sp_scan_phase_count < 1:
        raise SystemExit("--sp-scan-phase-count must be positive")
    if not 0.0 <= args.min_fractional_chirp_offset < 0.5:
        raise SystemExit("--min-fractional-chirp-offset must be in [0, 0.5)")
    if not 0.0 < args.min_offset_symbols <= args.max_offset_symbols:
        raise SystemExit("offset range must satisfy 0 < min <= max")
    if args.uniform_stagger_spacing_symbols <= 0.0:
        raise SystemExit("--uniform-stagger-spacing-symbols must be positive")
    if not set(int(value) for value in args.runtime_orders).issubset(
        set(int(value) for value in args.collision_orders)
    ):
        raise SystemExit("--runtime-orders must be a subset of --collision-orders")
    args.clean_packets = args.clean_packets.resolve()
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    packets, metadata = load_extracted(args.clean_packets)
    source_cfg = metadata.get("config", {})
    source_rate_hz = float(source_cfg.get("sample_rate_hz", 1_000_000.0))
    if args.trace_driven_known_phy:
        # Current experiment PHY.  The formal encoder self-check is defined
        # for this explicit-header 20-byte profile.
        cfg = RealCollisionLoRaConfig(
            sf=int(source_cfg.get("sf", 10)),
            bw_hz=float(source_cfg.get("bw_hz", 125_000.0)),
            sample_rate_hz=float(args.evaluation_rate_hz),
            cr=1,
            preamble_len=8,
            sync_word=0x34,
            payload_len=20,
            crc_on=True,
            implicit_header=False,
            ldro=False,
        )
    else:
        cfg = RealCollisionLoRaConfig(
            sf=int(source_cfg.get("sf", 10)),
            bw_hz=float(source_cfg.get("bw_hz", 125_000.0)),
            sample_rate_hz=float(args.evaluation_rate_hz),
            cr=int(source_cfg.get("cr", 1)),
            preamble_len=int(source_cfg.get("preamble_len", 8)),
            sync_word=int(source_cfg.get("sync_word", 0x12)),
            payload_len=int(source_cfg.get("payload_len", 32)),
            crc_on=bool(source_cfg.get("crc_on", True)),
            implicit_header=bool(source_cfg.get("implicit_header", True)),
            ldro=bool(source_cfg.get("ldro", False)),
        )
    packet_meta = list(metadata.get("packets", []))
    available_positions = {
        Path(str(item.get("source_file", f"source_{index}"))).name
        for index, item in enumerate(packet_meta)
    }
    if max(args.collision_orders) > len(packet_meta):
        raise SystemExit(
            "collision count exceeds available clean packet repetitions"
        )
    measured_packets = resample_packet_bank(
        packets, source_rate_hz, cfg.sample_rate_hz
    )
    if args.trace_driven_known_phy:
        packets, references = build_trace_channel_known_phy_bank(
            measured_packets,
            packet_meta,
            cfg,
            payload_seed=args.payload_seed,
        )
    else:
        packets = measured_packets
        if packets.shape[-1] != int(cfg.frame_samples):
            raise RuntimeError(
                f"rate-converted packet length {packets.shape[-1]} != "
                f"cfg.frame_samples {cfg.frame_samples}"
            )
        references = build_in_memory_references(packets, packet_meta, cfg)
    rng = np.random.default_rng(args.seed)
    timing_rows: list[dict] = []
    ser_scene_rows: list[dict] = []
    packet_ser_rows: list[dict] = []
    frontend_names: dict[str, set[str]] = defaultdict(set)
    runtime_order_set = set(int(value) for value in args.runtime_orders)

    for order in args.collision_orders:
        for scene_index in range(1, args.scenes_per_order + 1):
            selected = select_channel_packets(packet_meta, order, rng)
            position_keys = selected_position_keys(packet_meta, selected)
            distinct_position_count = len(set(position_keys))
            scene, truth_packets, offsets, _ = build_scene(
                packets,
                packet_meta,
                cfg,
                selected,
                rng,
                min_offset_symbols=args.min_offset_symbols,
                max_offset_symbols=args.max_offset_symbols,
                min_fractional_chirp_offset=args.min_fractional_chirp_offset,
                stagger_high_order_preambles=args.stagger_high_order_preambles,
                uniform_stagger_spacing_symbols=args.uniform_stagger_spacing_symbols,
            )
            max_preamble_overlap = maximum_preamble_overlap(
                offsets, float(cfg.preamble_len)
            )
            # All methods receive the same noise realization.  Each component
            # packet was normalized to unit RMS before addition, so this is a
            # directly auditable per-packet time-domain SNR definition.
            scene_noise_rng = np.random.default_rng(
                int(args.seed)
                ^ (int(order) << 20)
                ^ (int(scene_index) * 0x45D9F3B)
            )
            noise_power = 10.0 ** (-float(args.scene_snr_db) / 10.0)
            scene_noise = (
                scene_noise_rng.normal(size=scene.shape)
                + 1j * scene_noise_rng.normal(size=scene.shape)
            ) * math.sqrt(noise_power / 2.0)
            scene = (scene + scene_noise.astype(np.complex64)).astype(np.complex64)
            prepared = prepare_receiver_inputs(
                scene,
                cfg,
                max_candidates=max(args.max_candidates, 3 * order),
                candidates_per_window=max(args.candidates_per_window, 2 * order),
                threshold=args.threshold,
                cfo_min=args.cfo_min,
                cfo_max=args.cfo_max,
                sp_scan_phase_count=args.sp_scan_phase_count,
            )
            method_order = list(METHODS)
            rng.shuffle(method_order)
            for method in method_order:
                frontend_names[method].add(prepared["frontend_names"][method])
                repeat_count = (
                    int(args.timing_repeats)
                    if int(order) in runtime_order_set
                    else 1
                )
                for repeat in range(1, repeat_count + 1):
                    if int(order) in runtime_order_set:
                        decoded, per_candidate_times = payload_decode_pass(
                            method,
                            prepared,
                            cfg,
                            sp_sync_max_trials=args.sp_sync_max_trials,
                            collect_ser=repeat == 1,
                        )
                    else:
                        decoded = decode_prepared_for_ser(
                            method,
                            prepared,
                            cfg,
                            sp_sync_max_trials=args.sp_sync_max_trials,
                        )
                        per_candidate_times = []
                    detected_count = (
                        len(decoded)
                        if repeat == 1
                        else len(prepared["estimates"][method])
                    )
                    timing_rows.append(
                        {
                            "collision_order": int(order),
                            "scene_index": int(scene_index),
                            "timing_repeat": int(repeat),
                            "method": method,
                            "method_label": METHOD_LABELS[method],
                            "payload_decode_time_total_ms": (
                                float(np.sum(per_candidate_times))
                                if per_candidate_times
                                else None
                            ),
                            "payload_decode_time_per_detected_packet_ms": (
                                float(np.mean(per_candidate_times))
                                if per_candidate_times
                                else None
                            ),
                            "detected_count": int(detected_count),
                            "truth_packet_count": int(order),
                            "source_indices": ",".join(str(int(value)) for value in selected),
                            "source_position_keys": ",".join(position_keys),
                            "distinct_source_position_count": int(
                                distinct_position_count
                            ),
                            "reuses_measured_position": bool(
                                distinct_position_count < int(order)
                            ),
                            "offset_symbols": ",".join(f"{value:.6f}" for value in offsets),
                            "maximum_simultaneous_preambles": int(
                                max_preamble_overlap
                            ),
                            "timing_scope": "post_shared_sp_fine_sync_method_estimation_and_decoder",
                            "oracle_start_cfo_channel_supplied": False,
                            "included_in_runtime_plot": bool(
                                int(order) in runtime_order_set
                            ),
                        }
                    )
                    if repeat == 1:
                        receiver = {
                            "decoded": decoded,
                            "detected_count": detected_count,
                        }
                        scene_ser, per_packet = evaluate_receiver_output(
                            receiver, truth_packets, references, cfg
                        )
                        matched_rows = [
                            row for row in per_packet if row["status"] == "decoded"
                        ]
                        ser_scene_rows.append(
                            {
                                "collision_order": int(order),
                                "scene_index": int(scene_index),
                                "method": method,
                                "method_label": METHOD_LABELS[method],
                                "scene_ser": float(scene_ser),
                                "matched_detection_count": int(len(matched_rows)),
                                "matched_detection_rate": float(
                                    len(matched_rows) / max(1, len(per_packet))
                                ),
                                "conditional_ser_detected_packets": (
                                    float(
                                        np.mean(
                                            [float(row["ser"]) for row in matched_rows]
                                        )
                                    )
                                    if matched_rows
                                    else None
                                ),
                                "detected_count": int(detected_count),
                                "truth_packet_count": int(order),
                                "distinct_source_position_count": int(
                                    distinct_position_count
                                ),
                                "reuses_measured_position": bool(
                                    distinct_position_count < int(order)
                                ),
                                "maximum_simultaneous_preambles": int(
                                    max_preamble_overlap
                                ),
                                "oracle_start_cfo_channel_supplied": False,
                            }
                        )
                        for row in per_packet:
                            packet_ser_rows.append(
                                {
                                    **row,
                                    "collision_order": int(order),
                                    "scene_index": int(scene_index),
                                    "method": method,
                                    "method_label": METHOD_LABELS[method],
                                }
                            )
            print(
                f"FIG11_SHARED_FRONT order={order} scene={scene_index}/{args.scenes_per_order}",
                flush=True,
            )

    summary_rows = aggregate_rows(
        timing_rows, ser_scene_rows, np.random.default_rng(args.seed ^ 0x5A5A)
    )
    write_csv(args.out_dir / "fig11_decoder_time_raw.csv", timing_rows)
    write_csv(args.out_dir / "fig11_decoder_ser_raw.csv", packet_ser_rows)
    write_csv(args.out_dir / "fig11_decoder_time_ser_summary.csv", summary_rows)
    write_csv(
        args.out_dir / "fig11_decoder_time_summary.csv",
        [
            {
                key: value
                for key, value in row.items()
                if key.startswith("payload_decode_time")
                or key
                in {
                    "collision_order",
                    "method",
                    "method_label",
                    "scene_count",
                    "timed_scene_count",
                }
            }
            for row in summary_rows
        ],
    )
    write_csv(
        args.out_dir / "fig11_decoder_ser_summary.csv",
        [
            {
                key: value
                for key, value in row.items()
                if key.startswith("ser_")
                or key
                in {
                    "collision_order",
                    "method",
                    "method_label",
                    "scene_count",
                    "mean_detected_packet_count",
                    "matched_detection_rate_mean",
                    "conditional_ser_detected_packets_mean",
                }
            }
            for row in summary_rows
        ],
    )
    plot_runtime(
        summary_rows,
        args.out_dir / "fig11_decoder_time",
        runtime_orders=tuple(int(value) for value in args.runtime_orders),
    )
    plot_ser(summary_rows, args.out_dir / "fig11_decoder_ser")
    plot_combined(
        summary_rows,
        args.out_dir / "fig11_end_to_end_time_ser",
        runtime_orders=tuple(int(value) for value in args.runtime_orders),
    )

    audit = {
        "schema": "sp_fig11_post_coarse_runtime_shared_detection_ser_v5",
        "source": str(args.clean_packets),
        "source_sha256": sha256_file(args.clean_packets),
        "source_packet_count": int(len(packets)),
        "distinct_measured_position_count": int(len(available_positions)),
        "source_sample_rate_hz": float(source_rate_hz),
        "evaluation_sample_rate_hz": float(cfg.sample_rate_hz),
        "trace_driven_known_phy": bool(args.trace_driven_known_phy),
        "payload_seed": int(args.payload_seed),
        "scene_snr_db": float(args.scene_snr_db),
        "evaluation_phy": {
            "sf": int(cfg.sf),
            "bandwidth_hz": float(cfg.bw_hz),
            "coding_rate_index": int(cfg.cr),
            "preamble_symbols": int(cfg.preamble_len),
            "sync_word": f"0x{int(cfg.sync_word):02x}",
            "payload_bytes": int(cfg.payload_len),
            "crc_on": bool(cfg.crc_on),
            "implicit_header": bool(cfg.implicit_header),
        },
        "sample_rate_conversion": (
            "scipy.signal.resample_poly band-limited conversion before collision construction"
            if abs(source_rate_hz - cfg.sample_rate_hz) > 1e-9
            else "none"
        ),
        "collision_orders": list(args.collision_orders),
        "runtime_orders": list(args.runtime_orders),
        "scenes_per_order": int(args.scenes_per_order),
        "timing_repeats_per_scene": int(args.timing_repeats),
        "configured_sp_sync_refinement_trials": int(args.sp_sync_max_trials),
        "sp_preamble_scan_phase_count": int(args.sp_scan_phase_count),
        "methods": [METHOD_LABELS[method] for method in METHODS],
        "oracle_start_cfo_channel_supplied_to_any_decoder": False,
        "truth_usage": (
            "source identity, start, and transmitted symbol bins are held in an "
            "evaluation-only table and used only after timed decoding for "
            "one-to-one matching and SER; synchronization/refinement failures "
            "receive SER=1"
        ),
        "timing_scope": (
            "normalized per detected packet after shared final SP fine start/CFO/STO. "
            "LoRaWAN times payload decoding only; MRC, CIC, PCube, and MaLoRaGW "
            "include their required channel/RSSI-frequency/PDoA/channel-matrix "
            "estimation plus payload decoding; no method re-synchronizes"
        ),
        "ser_scope": (
            "all methods share SP's detected packet list and exact final fine "
            "start/CFO/STO without method-specific resynchronization; each method "
            "then performs only its required parameter estimation and payload decode"
        ),
        "mrc_frontend_note": (
            "MRC shares SP fine start/CFO/STO, estimates its own physical-pair "
            "preamble channel at that fixed sync, and applies fixed-channel MRC top-1"
        ),
        "sp_scope": (
            "SER uses interleaved SP preamble proposals plus a sample-continuous "
            "SFD-pair completeness supplement, re-estimates every supplemental "
            "channel in the SP whitened domain, then applies robust reliability, "
            "lambda selection, and SP+sync-refine; no comparison payload decision "
            "is reused. Latency replays local SP coarse-to-fine start/CFO/channel "
            "estimation from quantized coarse starts before lambda configuration "
            "and signed payload decoding"
        ),
        "comparison_implementation": {
            "frontend_orchestrator": "shared final SP fine synchronization in build_fig11_trace_runtime.py",
            "shared_detection_policy": (
                "all methods receive identical SP candidate/start/CFO/STO; no method "
                "re-synchronizes, and each runs only required estimation and decoding"
            ),
            "cic_frontend": "compare/native_frontends.py::cic_native_estimates",
            "pcube_maloragw_frontend": "compare/native_frontends.py::projected_preamble_native_estimates",
            "pcube_maloragw_detector_helper": "real_collision_experiment/node01_sp_receiver/real_sp_frontend.py::pcube_sp_estimates_real",
            "payload_decoders": {
                "lorawan": "compare/real_packet_decoders.py::PaperComparisonContext.decode_lorawan",
                "mrc": "compare/real_packet_decoders.py::PaperComparisonContext.decode_mrc",
                "mrc_cic": "compare/real_packet_decoders.py::PaperComparisonContext.decode_cic",
                "pcube": "compare/real_packet_decoders.py::PaperComparisonContext.decode_pcube",
                "maloragw": "compare/real_packet_decoders.py::PaperComparisonContext.decode_maloragw"
            }
        },
        "native_frontends": {
            method: sorted(values) for method, values in frontend_names.items()
        },
        "scene_construction": (
            "equal-total-RMS standard CRC-valid frames passed through measured "
            "dual-channel directions and measured packet CFO; each scene first "
            "uses one packet from each available measured RF position and, for "
            "orders above the 10-position trace bank, fills the remaining slots "
            "with unused clean repetitions. This 12-packet case is a trace-driven "
            "collision-order stress test rather than 12 distinct physical "
            "positions; selected packets are chosen without consulting decoder "
            "outcomes; signed "
            "fractional-symbol offsets in "
            f"[{float(args.min_offset_symbols):g}, {float(args.max_offset_symbols):g}] "
            f"symbols and at least {float(args.min_fractional_chirp_offset):g} "
            "symbol away from integer-chirp alignment, implemented as exact "
            "integer-ADC-sample shifts; every packet pair retains a non-empty "
            "payload overlap. For every collision order, starts are approximately "
            f"{float(args.uniform_stagger_spacing_symbols):g} symbols apart inside "
            "a span shorter than one frame, so the latest packet starts before "
            "the earliest packet ends. With the fixed +/-max-offset span, "
            "10/12-packet scenes necessarily raise the maximum simultaneous "
            "preamble overlap relative to 2/4/6/8. Integer-ADC shifts are pairwise non-aligned modulo one "
            "chirp; offsets remain randomized across measured positions"
        ),
        "ser_definition": (
            "payload symbol errors divided by the full reference-symbol count; "
            "missing decoded symbols and method-specific refinement failures "
            "count as errors"
        ),
        "seed": int(args.seed),
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "thread_environment": {
                key: os.environ.get(key)
                for key in (
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            },
        },
        "summary": summary_rows,
    }
    (args.out_dir / "fig11_decoder_time_summary.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"FIG11_SHARED_FRONT_DONE out={args.out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
