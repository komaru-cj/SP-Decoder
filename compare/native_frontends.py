"""Paper-native packet front ends for real dual-B210 captures.

These front ends intentionally do not consume SP packet estimates:

* LoRaWAN observes physical Ch0 only and independently detects a dominant
  preamble, confirms the sync word/SFD, and estimates start/CFO/STO.
* MRC independently detects a dominant preamble on the physical Rx pair,
  confirms sync/SFD, and estimates its own dual-channel vector.
* CIC follows the authors' public implementation: correlate for consecutive
  SFD downchirps first, then confirm the preceding preamble/sync structure.
* PCube searches physical Rx streams for separated preamble tracks and uses
  preamble/SFD joint CFO/CTO calibration.
* MaLoRaGW performs the same search after PCA signal projection, which is the
  paper's mechanism for exposing weak collided preambles without prior CSI.

The common RF-energy ranges only bound computation.  They do not supply packet
start, CFO, STO, channel, payload, or manifest information.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable

import numpy as np
from scipy.signal import fftconvolve, find_peaks

from lora_mrc_sp_core import instantaneous_chirp
from real_sp_frontend import pcube_sp_estimates_real, same_packet_estimate
from sp_detection_frontend import (
    preamble_channel_near_cfo,
    sfd_anchored_start_cfo_refine,
    sfd_score,
    sync_word_score,
)


def _offset_estimate(estimate: dict, offset: int, method: str) -> dict:
    out = dict(estimate)
    out["start_sample"] = float(out["start_sample"]) + float(offset)
    out["native_frontend_method"] = method
    out["native_frontend_window_start_sample"] = int(offset)
    return out


def _deduplicate(estimates: Iterable[dict], cfg, max_candidates: int) -> list[dict]:
    selected: list[dict] = []
    for estimate in sorted(estimates, key=lambda row: float(row["start_sample"])):
        if any(same_packet_estimate(estimate, old, cfg) for old in selected):
            continue
        selected.append(estimate)
        if len(selected) >= int(max_candidates):
            break
    return selected


def cic_native_estimates(
    samples: np.ndarray,
    cfg,
    scan_ranges: list[tuple[int, int]],
    *,
    cfo_min: float,
    cfo_max: float,
    max_candidates: int,
) -> tuple[list[dict], dict]:
    """CIC Sec. 5.8 / authors' public-code SFD-first packet detector."""

    x = np.asarray(samples, dtype=np.complex64)
    x = x - np.mean(x, axis=1, keepdims=True)
    template = instantaneous_chirp(0, cfg, up=False).astype(np.complex128)
    n_symbol = int(cfg.samples_per_symbol)
    rows: list[dict] = []
    window_diagnostics: list[dict] = []

    for window_index, (range_start, range_end) in enumerate(scan_ranges):
        segment = np.asarray(x[0, range_start:range_end], dtype=np.complex128)
        if segment.size < int((cfg.preamble_len + 4) * n_symbol):
            continue
        correlation = fftconvolve(
            segment,
            np.conj(template[::-1]),
            mode="valid",
        )
        sample_power = fftconvolve(
            np.abs(segment) ** 2,
            np.ones(n_symbol, dtype=np.float64),
            mode="valid",
        )
        normalized = np.abs(correlation) / np.sqrt(
            np.maximum(sample_power * float(n_symbol), 1e-30)
        )
        # The authors' Python release uses four times the capture-local mean
        # correlation.  Retain that rule with a small absolute floor so a
        # noise-only window cannot manufacture a packet.
        threshold = max(0.08, 4.0 * float(np.mean(normalized)))
        peaks, properties = find_peaks(
            normalized,
            height=threshold,
            distance=max(1, int(0.75 * n_symbol)),
        )
        paired = 0
        for left_index, left in enumerate(peaks):
            expected = int(left) + n_symbol
            candidates = peaks[left_index + 1 :]
            if candidates.size == 0:
                continue
            right = int(candidates[int(np.argmin(np.abs(candidates - expected)))])
            if abs(right - expected) > max(8, 2 * int(cfg.osr)):
                continue
            paired += 1
            coarse_start = float(range_start + int(left) - (cfg.preamble_len + 2) * n_symbol)
            refined_start, cfo, cto_samples, structure_score, _, _ = (
                sfd_anchored_start_cfo_refine(
                    x,
                    coarse_start,
                    cfg,
                    symbol_radius=1,
                    local_radius_bins=int(max(96.0, abs(cfo_min), abs(cfo_max))),
                    use_integer_alias_branch=False,
                )
            )
            if not (float(cfo_min) <= float(cfo) <= float(cfo_max)):
                continue
            sync = float(sync_word_score(x, int(round(refined_start)), cfo, cfg))
            sfd = float(sfd_score(x, int(round(refined_start)), cfo, cfg))
            if structure_score <= 0.0 or sync < 10.0 or sfd < 10.0:
                continue
            preamble_ratio, channel, peak_bin = preamble_channel_near_cfo(
                x, refined_start, cfo, cfg, radius_bins=2
            )
            if preamble_ratio < 10.0:
                continue
            rows.append(
                {
                    "start_sample": float(math.floor(refined_start)),
                    "sto_samples": float(refined_start - math.floor(refined_start)),
                    "cfo_bins": float(cfo),
                    "continuous_cfo_bins": float(cfo),
                    "channel": [
                        [float(np.real(value)), float(np.imag(value))]
                        for value in channel
                    ],
                    "power": float(np.vdot(channel, channel).real),
                    "confidence": float(structure_score),
                    "peak_bin": int(peak_bin),
                    "native_frontend_method": "mrc_cic",
                    "native_frontend_stage": "sfd_downchirp_pair_then_preamble_sync_confirmation",
                    "native_cic_correlation_threshold": float(threshold),
                    "native_cic_sfd_pair_correlation": [
                        float(normalized[int(left)]),
                        float(normalized[int(right)]),
                    ],
                    "native_cic_cto_samples": float(cto_samples),
                    "native_sync_score": sync,
                    "native_sfd_score": sfd,
                    "native_preamble_ratio": float(preamble_ratio),
                }
            )
        window_diagnostics.append(
            {
                "window_index": int(window_index),
                "start_sample": int(range_start),
                "end_sample": int(range_end),
                "correlation_threshold": float(threshold),
                "downchirp_peak_count": int(peaks.size),
                "consecutive_downchirp_pair_count": int(paired),
            }
        )

    selected = _deduplicate(rows, cfg, max_candidates)
    return selected, {
        "paper_frontend": "CIC SFD-downchirp-first detector (Sec. 5.8)",
        "upstream_reference": "https://github.com/osama4933/CIC",
        "manifest_used": False,
        "candidate_count": len(selected),
        "windows": window_diagnostics,
    }


def projected_preamble_native_estimates(
    samples: np.ndarray,
    cfg,
    scan_ranges: list[tuple[int, int]],
    *,
    method: str,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    max_candidates: int,
    candidates_per_window: int,
    scan_phase_count: int = 1,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict], dict]:
    """PCube physical-stream or MaLoRaGW PCA-stream preamble receiver."""

    if method not in {"pcube", "maloragw"}:
        raise ValueError("method must be pcube or maloragw")
    stream_mode = "physical" if method == "pcube" else "pca"
    # Busy-region energy only bounds computation; it cannot reveal a second
    # preamble that begins while another packet is already on air.  Interleaved
    # phases approximate the papers' continuously running correlation search.
    # Do not add SP's minor-direction residual proposal here: PCube detects on
    # its physical Rx pair, while MaLoRaGW's ``pca`` streams already are the
    # strong/weak principal-component projections claimed by that paper.
    use_residual = False
    estimates: list[dict] = []
    window_diagnostics: list[dict] = []
    for window_index, (range_start, range_end) in enumerate(scan_ranges):
        if progress is not None:
            progress(
                f"COMPARISON_RELOCATE_SCAN method={method} "
                f"candidate_window={window_index + 1}/{len(scan_ranges)}"
            )
        segment = samples[:, range_start:range_end]
        if segment.shape[1] < int((cfg.preamble_len + 4) * cfg.samples_per_symbol):
            continue
        local = pcube_sp_estimates_real(
            segment,
            cfg,
            max_candidates=max(1, int(candidates_per_window)),
            raw_candidate_limit=max(1, int(candidates_per_window)),
            threshold=float(threshold),
            step_samples=int(cfg.samples_per_symbol),
            scan_phase_count=max(1, int(scan_phase_count)),
            min_sync_score=0.0,
            min_coherent_metric=0.0,
            cfo_min=float(cfo_min),
            cfo_max=float(cfo_max),
            min_sfd_score=10.0,
            min_refined_sync_score=500.0,
            use_local_projection_tracks=False,
            use_spatial_residual_tracks=use_residual,
            fast_single_node=True,
            fast_grid_refine=False,
            stable_stream_mode=stream_mode,
            use_integer_alias_branch=False,
        )
        estimates.extend(_offset_estimate(row, range_start, method) for row in local)
        window_diagnostics.append(
            {
                "window_index": int(window_index),
                "start_sample": int(range_start),
                "end_sample": int(range_end),
                "candidate_count": int(len(local)),
            }
        )
    selected = _deduplicate(estimates, cfg, max_candidates)
    if method == "pcube":
        description = (
            "physical-Rx separated preamble search plus preamble/SFD CFO-STO calibration"
        )
    else:
        description = (
            "PCA spatial projection plus preamble/SFD detection, CFO-CTO calibration, "
            "and physical-channel estimation"
        )
    return selected, {
        "paper_frontend": description,
        "stable_stream_mode": stream_mode,
        "busy_region_scan_phase_count": max(1, int(scan_phase_count)),
        "spatial_residual_candidate_proposals": bool(use_residual),
        "continuous_search_approximation_only": True,
        "paper_native_projection_only": True,
        "start_cfo_policy": "paper_up_down_chirp_midpoint",
        "shared_search_only_not_sp_payload_decoder": True,
        "manifest_used": False,
        "candidate_count": len(selected),
        "windows": window_diagnostics,
    }


def standard_native_estimates(
    samples: np.ndarray,
    cfg,
    scan_ranges: list[tuple[int, int]],
    *,
    method: str,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    max_candidates: int,
    candidates_per_window: int,
    scan_phase_count: int = 1,
) -> tuple[list[dict], dict]:
    """Independent standard LoRaWAN or fixed-MRC packet acquisition.

    This deliberately uses neither SP candidates nor SP spatial residual
    tracks.  LoRaWAN is given only physical Ch0.  MRC is given both physical
    channels, but it must acquire and synchronize the packet before its own
    channel estimate can be used for fixed maximum-ratio combining.

    The detector retains only the dominant stable preamble track at each
    coarse time hypothesis.  Multiple scan phases approximate a continuously
    running receiver; they are not multiple-user separation branches.
    """

    if method not in {"lorawan", "mrc"}:
        raise ValueError("method must be lorawan or mrc")
    source = np.asarray(samples[:1] if method == "lorawan" else samples)
    estimates: list[dict] = []
    window_diagnostics: list[dict] = []
    for window_index, (range_start, range_end) in enumerate(scan_ranges):
        segment = source[:, range_start:range_end]
        if segment.shape[1] < int((cfg.preamble_len + 4) * cfg.samples_per_symbol):
            continue
        local = pcube_sp_estimates_real(
            segment,
            cfg,
            max_candidates=max(1, int(candidates_per_window)),
            raw_candidate_limit=max(1, int(candidates_per_window)),
            threshold=float(threshold),
            step_samples=int(cfg.samples_per_symbol),
            scan_phase_count=max(1, int(scan_phase_count)),
            min_sync_score=0.0,
            min_coherent_metric=0.0,
            cfo_min=float(cfo_min),
            cfo_max=float(cfo_max),
            min_sfd_score=10.0,
            min_refined_sync_score=500.0,
            use_local_projection_tracks=False,
            use_spatial_residual_tracks=False,
            fast_single_node=True,
            fast_grid_refine=False,
            stable_stream_mode="physical",
            stable_max_tracks=1,
            use_integer_alias_branch=False,
        )
        estimates.extend(_offset_estimate(row, range_start, method) for row in local)
        window_diagnostics.append(
            {
                "window_index": int(window_index),
                "start_sample": int(range_start),
                "end_sample": int(range_end),
                "candidate_count": int(len(local)),
            }
        )
    selected = _deduplicate(estimates, cfg, max_candidates)
    channel_mode = "physical_ch0_only" if method == "lorawan" else "physical_ch0_ch1"
    return selected, {
        "paper_frontend": (
            "standard single-channel LoRa preamble/sync-word/SFD acquisition"
            if method == "lorawan"
            else "independent dual-channel preamble/sync-word/SFD acquisition for fixed MRC"
        ),
        "physical_input_channels": 1 if method == "lorawan" else int(source.shape[0]),
        "channel_mode": channel_mode,
        "dominant_preamble_tracks_per_time_hypothesis": 1,
        "busy_region_scan_phase_count": max(1, int(scan_phase_count)),
        "spatial_residual_candidate_proposals": False,
        "local_projection_candidate_proposals": False,
        "sp_candidate_or_sync_reuse": False,
        "start_cfo_policy": "independent_up_down_chirp_midpoint",
        "energy_ranges_supply_packet_timing": False,
        "manifest_used": False,
        "candidate_count": len(selected),
        "windows": window_diagnostics,
    }


def detect_native_frontends(
    samples: np.ndarray,
    cfg,
    scan_ranges: list[tuple[int, int]],
    *,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    max_candidates: int,
    candidates_per_window: int,
    scan_phase_count: int = 1,
) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    estimates: dict[str, list[dict]] = {}
    diagnostics: dict[str, dict] = {}
    for method in ("lorawan", "mrc"):
        estimates[method], diagnostics[method] = standard_native_estimates(
            samples,
            cfg,
            scan_ranges,
            method=method,
            threshold=threshold,
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            max_candidates=max_candidates,
            candidates_per_window=candidates_per_window,
            scan_phase_count=scan_phase_count,
        )
    estimates["mrc_cic"], diagnostics["mrc_cic"] = cic_native_estimates(
        samples,
        cfg,
        scan_ranges,
        cfo_min=cfo_min,
        cfo_max=cfo_max,
        max_candidates=max_candidates,
    )
    for method in ("pcube", "maloragw"):
        estimates[method], diagnostics[method] = projected_preamble_native_estimates(
            samples,
            cfg,
            scan_ranges,
            method=method,
            threshold=threshold,
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            max_candidates=max_candidates,
            candidates_per_window=candidates_per_window,
            scan_phase_count=scan_phase_count,
        )
    diagnostics["mrc_cic"]["busy_region_phase_coverage"] = (
        "sample-continuous SFD correlation; no coarse phase grid"
    )
    diagnostics["mrc_cic"]["shared_search_only_not_sp_payload_decoder"] = True
    return estimates, diagnostics


def _sp_fine_seed_rows(
    samples: np.ndarray,
    cfg,
    sp_fine_estimates: list[dict],
) -> tuple[list[dict], list[tuple[int, int]]]:
    """Build narrow paper-refinement windows around exact SP fine sync."""

    symbol_samples = int(cfg.samples_per_symbol)
    seed_rows: list[dict] = []
    scan_ranges: list[tuple[int, int]] = []
    for seed_index, fine in enumerate(sp_fine_estimates):
        aligned = float(fine["start_sample"]) + float(
            fine.get("sto_samples", 0.0)
        )
        range_start = max(0, int(math.floor(aligned - 1.0 * symbol_samples)))
        range_end = min(
            int(samples.shape[1]),
            int(
                math.ceil(
                    aligned
                    + (float(cfg.preamble_len) + 5.5) * symbol_samples
                )
            ),
        )
        seed_rows.append(
            {
                "seed_index": int(seed_index),
                "fine_start_sample_shared": float(aligned),
                "fine_cfo_bins_shared": float(
                    fine.get(
                        "cfo_bins_sp",
                        fine.get("continuous_cfo_bins", fine.get("cfo_bins", 0.0)),
                    )
                ),
                "range_start": int(range_start),
                "range_end": int(range_end),
            }
        )
        scan_ranges.append((range_start, range_end))
    return seed_rows, scan_ranges


def refine_paper_frontend_from_sp_fine(
    samples: np.ndarray,
    cfg,
    sp_fine_estimates: list[dict],
    *,
    method: str,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    candidates_per_window: int,
    scan_phase_count: int = 8,
    coarse_phase_count: int | None = None,
    match_tolerance_symbols: float = 0.35,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict], dict]:
    """Refine exact SP fine-sync targets with one paper's own estimator.

    LoRaWAN and fixed MRC intentionally keep the shared SP fine synchronization
    and parameters.  CIC, PCube, and MaLoRaGW use that exact target only as an
    initialization/search window, then run their paper-native SFD/preamble
    refinement and parameter estimation.  A failed paper refinement falls back
    to the SP fine result so every method is evaluated on the same candidate
    identity set.
    """

    symbol_samples = int(cfg.samples_per_symbol)
    seed_rows, scan_ranges = _sp_fine_seed_rows(samples, cfg, sp_fine_estimates)

    if method in ("lorawan", "mrc"):
        estimates: list[dict] = []
        for seed_index, fine in enumerate(sp_fine_estimates):
            row = dict(fine)
            row["native_frontend_method"] = f"{method}_shared_sp_fine_sync"
            row["shared_sp_fine_sync_and_parameters"] = True
            row["paper_method_refinement_applied"] = False
            row["paper_method_parameter_estimation_applied"] = False
            row["_comparison_candidate_index"] = int(seed_index)
            estimates.append(row)
        return estimates, {
            "paper_frontend": f"{method} with shared SP fine synchronization/parameters",
            "shared_sp_detection": True,
            "shared_sp_fine_sync_and_parameters": True,
            "paper_method_refinement": "not_required",
            "paper_method_parameter_estimation": "not_required",
            "candidate_count": int(len(estimates)),
        }

    if not scan_ranges:
        return [], {
            "shared_sp_detection": True,
            "coarse_seed_count": 0,
            "candidate_count": 0,
        }

    if method == "mrc_cic":
        candidates, native_diag = cic_native_estimates(
            samples,
            cfg,
            scan_ranges,
            cfo_min=float(cfo_min),
            cfo_max=float(cfo_max),
            max_candidates=max(1, 4 * len(scan_ranges)),
        )
    elif method in ("pcube", "maloragw"):
        candidates, native_diag = projected_preamble_native_estimates(
            samples,
            cfg,
            scan_ranges,
            method=method,
            threshold=float(threshold),
            cfo_min=float(cfo_min),
            cfo_max=float(cfo_max),
            max_candidates=max(1, 4 * len(scan_ranges)),
            candidates_per_window=max(1, int(candidates_per_window)),
            scan_phase_count=max(1, int(scan_phase_count)),
            progress=progress,
        )
    else:
        raise ValueError(f"unsupported native frontend method: {method}")

    tolerance = float(match_tolerance_symbols) * float(symbol_samples)
    pairs: list[tuple[float, float, int, int]] = []
    for seed_index, seed in enumerate(seed_rows):
        shared_fine = float(seed["fine_start_sample_shared"])
        for candidate_index, candidate in enumerate(candidates):
            start = float(candidate["start_sample"]) + float(
                candidate.get("sto_samples", 0.0)
            )
            error = abs(start - shared_fine)
            if error <= tolerance:
                confidence = float(candidate.get("confidence", 0.0))
                pairs.append((error, -confidence, seed_index, candidate_index))
    chosen_by_seed: dict[int, dict] = {}
    used_seeds: set[int] = set()
    used_candidates: set[int] = set()
    for _, _, seed_index, candidate_index in sorted(pairs):
        if seed_index in used_seeds or candidate_index in used_candidates:
            continue
        shared = sp_fine_estimates[seed_index]
        row = dict(candidates[candidate_index])
        refined_start = float(row["start_sample"]) + float(
            row.get("sto_samples", 0.0)
        )
        refined_cfo = float(
            row.get("continuous_cfo_bins", row.get("cfo_bins", 0.0))
        )
        shared_start = float(seed_rows[seed_index]["fine_start_sample_shared"])
        shared_cfo = float(seed_rows[seed_index]["fine_cfo_bins_shared"])
        row["sp_fine_seed_index"] = int(seed_index)
        row["shared_sp_fine_start_sample"] = shared_start
        row["shared_sp_fine_cfo_bins"] = shared_cfo
        row["shared_sp_fine_sync_seed"] = True
        if "_physical_evidence_key" in shared:
            row["_physical_evidence_key"] = shared["_physical_evidence_key"]
        row["paper_method_refinement_applied"] = True
        row["paper_method_parameter_estimation_applied"] = True
        row["paper_refinement_start_delta_samples"] = float(
            refined_start - shared_start
        )
        row["paper_refinement_cfo_delta_bins"] = float(refined_cfo - shared_cfo)
        row["manifest_oracle_expected_identities"] = list(
            shared.get("manifest_oracle_expected_identities", [])
        )
        row["_comparison_candidate_index"] = int(seed_index)
        chosen_by_seed[seed_index] = row
        used_seeds.add(seed_index)
        used_candidates.add(candidate_index)

    chosen: list[dict] = []
    fallback_count = 0
    for seed_index, shared in enumerate(sp_fine_estimates):
        row = chosen_by_seed.get(seed_index)
        if row is None:
            row = dict(shared)
            row["native_frontend_method"] = (
                f"{method}_paper_refinement_fallback_shared_sp_fine_sync"
            )
            row["sp_fine_seed_index"] = int(seed_index)
            row["shared_sp_fine_sync_seed"] = True
            row["paper_method_refinement_applied"] = False
            row["paper_method_parameter_estimation_applied"] = True
            row["paper_refinement_fallback_reason"] = (
                "no paper-native estimate matched the shared SP fine target"
            )
            fallback_count += 1
        row["_comparison_candidate_index"] = int(seed_index)
        chosen.append(row)
    diagnostics = {
        **native_diag,
        "shared_sp_detection": True,
        "shared_sp_fine_sync_seed": True,
        "shared_information": "candidate identity plus exact SP fine start/CFO/STO initialization",
        "refinement_evidence": (
            "method-native projected preamble, sync word, and SFD only; no payload, "
            "FEC/CRC, manifest, expected payload, SP lambda, or SP residual"
        ),
        "fine_seed_count": int(len(seed_rows)),
        "fine_match_tolerance_symbols": float(match_tolerance_symbols),
        "candidate_count_before_seed_matching": int(len(candidates)),
        "candidate_count": int(len(chosen)),
        "paper_refinement_success_count": int(len(chosen) - fallback_count),
        "paper_refinement_fallback_count": int(fallback_count),
        "fine_seeds": seed_rows,
    }
    if method == "mrc_cic":
        diagnostics["busy_region_phase_coverage"] = (
            "sample-continuous SFD correlation initialized by exact SP fine-sync packets"
        )
        diagnostics["shared_search_only_not_sp_payload_decoder"] = True
    return chosen, diagnostics


def refine_paper_frontends_from_sp_fine(
    samples: np.ndarray,
    cfg,
    sp_fine_estimates: list[dict],
    *,
    threshold: float,
    cfo_min: float,
    cfo_max: float,
    candidates_per_window: int,
    scan_phase_count: int = 8,
    coarse_phase_count: int | None = None,
    match_tolerance_symbols: float = 0.35,
) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Apply the requested shared-SP-fine then paper-refinement comparison."""

    estimates: dict[str, list[dict]] = {}
    diagnostics: dict[str, dict] = {}
    for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw"):
        estimates[method], diagnostics[method] = refine_paper_frontend_from_sp_fine(
            samples,
            cfg,
            sp_fine_estimates,
            method=method,
            threshold=threshold,
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            candidates_per_window=candidates_per_window,
            scan_phase_count=scan_phase_count,
            coarse_phase_count=coarse_phase_count,
            match_tolerance_symbols=match_tolerance_symbols,
        )
    return estimates, diagnostics


# Compatibility aliases for older analysis notebooks.  Their behavior is now
# the exact shared-SP-fine policy above rather than quantized coarse seeding.
refine_native_frontend_from_sp_coarse = refine_paper_frontend_from_sp_fine
refine_native_frontends_from_sp_coarse = refine_paper_frontends_from_sp_fine
