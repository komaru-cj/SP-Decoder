#!/usr/bin/env python3
"""Build global anonymous physical-candidate databases for PRR figures.

The formal detector scans the complete centered five-second business-IQ slice.
Manifest packet schedules are never exposed to candidate discovery, timing
refinement, ranking, deduplication, or residual search.  The manifest is used
only to locate the business slice, configure the PHY, and compute a scalar
post-detection candidate-count assertion.

Every stored row is a structurally certified physical preamble/SFD hypothesis.
Node identity and sequence are learned only later from a CRC-valid payload.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "real_collision_experiment"
RECEIVER = EXPERIMENT / "node01_sp_receiver"
for directory in (ROOT, RECEIVER, EXPERIMENT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from lora_mrc_sp_core import (  # noqa: E402
    pca_project_streams,
)
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import (  # noqa: E402
    dc_remove_and_whiten,
    read_sc16,
)
from sp_detection_frontend import (  # noqa: E402
    preamble_channel_near_cfo,
    refine_start_fixed_cfo,
    sfd_anchored_start_cfo_refine,
    sfd_score,
    sliding_preamble_sp_estimates,
    sync_word_score,
)


ANALYSIS_DURATION_S = 5.0
ANONYMOUS_FINE_SYNC_SCHEMA = "fine_sync_anonymous_physical_v2"

# Structural evidence thresholds.  These use only preamble/sync/SFD IQ.
MIN_PREAMBLE_RATIO = 1_000.0
MIN_SYNC_CONFIDENCE = 64.0
MIN_SFD_CONFIDENCE = 128.0
# ``fixed_cfo_frame_score`` is log(preamble) + 0.35 log(sync) + 0.35 log(SFD).
# The independent structural minima imply about 10.06, so 10.0 keeps a joint
# consistency check without re-imposing a materially stricter hidden SNR gate.
MIN_FRAME_STRUCTURE_SCORE = 10.0
# A candidate that fails all of these deliberately loose local checks after
# its SFD/CFO refine has no plausible frame to justify the expensive timing
# grid.  They are independent absolute IQ thresholds, not a cross-candidate
# priority rule.
QUICK_PREAMBLE_RATIO_MIN = 8.0
QUICK_SYNC_CONFIDENCE_MIN = 2.0
QUICK_SFD_CONFIDENCE_MIN = 2.0

# Alias removal is deliberately local.  A score can choose among repeated
# algorithmic realizations only after a start/CFO/channel equivalence test.
ALIAS_START_TOLERANCE_SYMBOLS = 0.05
ALIAS_CFO_TOLERANCE_BINS = 0.20
ALIAS_CHANNEL_COHERENCE_MIN = 0.9995
# The integer-CFO ambiguity resolver can present the same head on adjacent
# integer branches.  Treat that as an alias only with strong spatial evidence;
# a spatially separable simultaneous packet stays independent.
SAME_CFO_ALIAS_CHANNEL_COHERENCE_MIN = 0.98
INTEGER_CFO_ALIAS_TOLERANCE_BINS = 0.10
INTEGER_CFO_ALIAS_CHANNEL_COHERENCE_MIN = 0.95
MAX_INTEGER_CFO_ALIAS_BINS = 3

MAX_NULL_STREAMS = 8
NULL_CHANNEL_COHERENCE = 0.995
# Zero means unlimited.  Formal discovery cannot rank away a weak hypothesis
# merely because several stronger peaks landed in the same coarse-time bucket.
HYPOTHESES_PER_COARSE_BUCKET = 0
# A downchirp-pair anchor is already within the SFD refiner's bounded timing
# radius.  Retrying half-symbol variants only duplicates the same physical IQ
# structure and triples formal-build cost.
ANCHOR_OFFSETS_SYMBOLS = (0.0,)
# A whitened constant-envelope LoRa chirp does not necessarily lift its raw
# window energy above the noise median.  Gate the already-normalized matched
# chirp response instead.  This is an absolute IQ structure condition applied
# independently to every peak, not a score quota or manifest-derived prior.
MIN_UPCHIRP_PEAK_CORRELATION = 0.70

# Structural cancellation is deliberately limited to the deterministic LoRa
# frame head: preamble, sync word, and SFD.  It never estimates, reconstructs,
# or subtracts payload symbols, so the anonymous detector cannot inherit a
# payload, CRC, identity, or schedule oracle.
STRUCTURAL_HEAD_RIDGE_RELATIVE = 1e-3
MIN_STRUCTURAL_HEAD_CHANNEL_COHERENCE = 0.80
MIN_STRUCTURAL_HEAD_ATOM_FIT_FRACTION = 0.01
MIN_STRUCTURAL_HEAD_COMPONENT_REDUCTION_FRACTION = 0.01
MAX_STRUCTURAL_HEAD_CONDITION_NUMBER = 1e6


class CandidateOverflowError(RuntimeError):
    """Raised instead of silently truncating certified physical candidates."""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def manifest_for_run(runs_root: Path, run_name: str) -> dict:
    candidates = (
        runs_root / run_name / f"{run_name}.json",
        runs_root / "manifests" / f"{run_name}.json",
    )
    for candidate in candidates:
        if candidate.exists():
            return load_json(candidate)
    raise FileNotFoundError(f"no manifest for {run_name}")


def traffic_start_s_for_run(
    runs_root: Path,
    run_name: str,
    reports_root: Path,
) -> float:
    merged_map = reports_root / "merged_traffic_starts.json"
    if merged_map.exists():
        mapping = load_json(merged_map)
        if run_name in mapping:
            return float(mapping[run_name])
    alignment = reports_root / f"{run_name}.business_alignment.json"
    if alignment.exists():
        return float(load_json(alignment)["traffic_start_s"])
    raise ValueError(f"no traffic-start reference for {run_name}")


def row_start_sample(row: dict) -> float:
    return float(row["start_sample"]) + float(row.get("sto_samples", 0.0))


def row_cfo_bins(row: dict) -> float:
    return float(row.get("continuous_cfo_bins", row.get("cfo_bins", 0.0)))


def row_channel(row: dict) -> np.ndarray:
    return np.asarray(
        [complex(value[0], value[1]) for value in row["channel"]],
        dtype=np.complex128,
    )


def channel_coherence(a: np.ndarray, b: np.ndarray) -> float:
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 1e-30:
        return 0.0
    return float(abs(np.vdot(a, b)) / denominator)


def same_physical_candidate(a: dict, b: dict, n_symbol: int) -> bool:
    """Return true only for an indistinguishable physical-head alias.

    The integer CFO branch resolver may land on adjacent coupled branches for
    the same waveform.  This is an estimator ambiguity, not evidence for a
    second packet, but it is safe to collapse only when the two-receiver
    channel directions are nearly the same.  A close weak packet with a
    different spatial direction remains a separate candidate.
    """

    if (
        abs(row_start_sample(a) - row_start_sample(b))
        > ALIAS_START_TOLERANCE_SYMBOLS * float(n_symbol)
    ):
        return False
    cfo_delta = abs(row_cfo_bins(a) - row_cfo_bins(b))
    coherence = channel_coherence(row_channel(a), row_channel(b))
    if (
        cfo_delta <= ALIAS_CFO_TOLERANCE_BINS
        and coherence >= SAME_CFO_ALIAS_CHANNEL_COHERENCE_MIN
    ):
        return True
    nearest_integer_branch = int(round(cfo_delta))
    return bool(
        1 <= nearest_integer_branch <= MAX_INTEGER_CFO_ALIAS_BINS
        and abs(cfo_delta - float(nearest_integer_branch))
        <= INTEGER_CFO_ALIAS_TOLERANCE_BINS
        and coherence >= INTEGER_CFO_ALIAS_CHANNEL_COHERENCE_MIN
    )


def candidate_quality(row: dict) -> tuple[float, float, float]:
    """Quality orders aliases only; it never competes across physical tracks."""

    certificate_margin = min(
        float(row.get("preamble_ratio", 0.0)) / MIN_PREAMBLE_RATIO,
        float(row.get("sync_confidence", 0.0)) / MIN_SYNC_CONFIDENCE,
        float(row.get("sfd_confidence", 0.0)) / MIN_SFD_CONFIDENCE,
        float(row.get("structure_score", 0.0)) / MIN_FRAME_STRUCTURE_SCORE,
    )
    return (
        float(row.get("structure_score", 0.0)),
        float(certificate_margin),
        float(row.get("confidence", 0.0)),
    )


def candidate_alias_distance(a: dict, b: dict, n_symbol: int) -> float:
    return float(
        abs(row_start_sample(a) - row_start_sample(b))
        / max(ALIAS_START_TOLERANCE_SYMBOLS * float(n_symbol), 1e-30)
        + abs(row_cfo_bins(a) - row_cfo_bins(b))
        / max(float(MAX_INTEGER_CFO_ALIAS_BINS), 1e-30)
        + (1.0 - channel_coherence(row_channel(a), row_channel(b)))
        / max(1.0 - INTEGER_CFO_ALIAS_CHANNEL_COHERENCE_MIN, 1e-30)
    )


def deduplicate_physical_candidates(rows: list[dict], n_symbol: int) -> list[dict]:
    """Complete-link cluster exact aliases while retaining distinct weak tracks."""

    clusters: list[list[dict]] = []
    for row in sorted(rows, key=row_start_sample):
        compatible: list[tuple[float, int]] = []
        for index, cluster in enumerate(clusters):
            if all(same_physical_candidate(row, old, n_symbol) for old in cluster):
                compatible.append(
                    (
                        max(
                            candidate_alias_distance(row, old, n_symbol)
                            for old in cluster
                        ),
                        index,
                    )
                )
        if not compatible:
            clusters.append([row])
            continue
        _, best_index = min(compatible)
        clusters[best_index].append(row)

    physical: list[dict] = []
    for cluster in clusters:
        representative = dict(max(cluster, key=candidate_quality))
        # A later spatial-null pass may hand back an already deduplicated
        # representative.  Preserve the support and pass provenance it
        # accumulated rather than treating it as one raw observation.
        representative["alias_support_count"] = sum(
            max(1, int(item.get("alias_support_count", 1)))
            for item in cluster
        )
        alias_passes: set[int] = set()
        for item in cluster:
            alias_passes.add(int(item.get("discovery_pass", 0)))
            alias_passes.update(
                int(value)
                for value in item.get("alias_discovery_passes", [])
            )
        representative["alias_discovery_passes"] = sorted(alias_passes)
        physical.append(representative)
    return sorted(physical, key=row_start_sample)


def structural_certificate(
    *,
    preamble_ratio: float,
    sync_confidence: float,
    sfd_confidence: float,
    frame_score: float,
) -> bool:
    values = (preamble_ratio, sync_confidence, sfd_confidence, frame_score)
    return bool(
        all(math.isfinite(float(value)) for value in values)
        and float(preamble_ratio) >= MIN_PREAMBLE_RATIO
        and float(sync_confidence) >= MIN_SYNC_CONFIDENCE
        and float(sfd_confidence) >= MIN_SFD_CONFIDENCE
        and float(frame_score) >= MIN_FRAME_STRUCTURE_SCORE
    )


def certificate_values_at(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    start: float,
    cfo_bins: float,
) -> tuple[dict[str, float], np.ndarray, int]:
    """Evaluate the complete preamble/sync/SFD certificate at one IQ start."""

    preamble_ratio, channel, peak_bin = preamble_channel_near_cfo(
        samples,
        float(start),
        float(cfo_bins),
        cfg,
        radius_bins=2,
    )
    sync_confidence = sync_word_score(
        samples,
        float(start),
        float(cfo_bins),
        cfg,
    )
    sfd_confidence = sfd_score(
        samples,
        float(start),
        float(cfo_bins),
        cfg,
    )
    frame_score = (
        math.log(float(preamble_ratio) + 1e-30)
        + 0.35 * math.log(float(sync_confidence) + 1e-30)
        + 0.35 * math.log(float(sfd_confidence) + 1e-30)
    )
    return {
        "preamble_ratio": float(preamble_ratio),
        "sync_confidence": float(sync_confidence),
        "sfd_confidence": float(sfd_confidence),
        "frame_structure_score": float(frame_score),
    }, channel, int(peak_bin)


def structural_head_symbol_samples(
    symbol: int,
    positions: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    up: bool,
) -> np.ndarray:
    """Evaluate one LoRa chirp at fractional intra-symbol sample positions."""

    n = np.asarray(positions, dtype=np.float64)
    symbol = int(symbol) % int(cfg.m)
    phase = (
        math.pi * n * n / (float(cfg.m) * float(cfg.osr) ** 2)
        - math.pi * n / float(cfg.osr)
        + 2.0 * math.pi * float(symbol) * n / (float(cfg.m) * float(cfg.osr))
    )
    fold = (int(cfg.m) - symbol) * int(cfg.osr)
    if symbol and fold < int(cfg.samples_per_symbol):
        phase = np.where(n >= float(fold), phase - 2.0 * math.pi * n / float(cfg.osr), phase)
    waveform = np.exp(1j * phase)
    return waveform if up else np.conj(waveform)


def structural_head_template(
    positions: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    cfo_bins: float,
) -> np.ndarray:
    """Return the known preamble/sync/SFD waveform, excluding all payload."""

    positions = np.asarray(positions, dtype=np.float64)
    n_symbol = int(cfg.samples_per_symbol)
    preamble_end = int(cfg.preamble_len) * n_symbol
    sync_end = (int(cfg.preamble_len) + 2) * n_symbol
    head_samples = int(round(float(cfg.payload_start_symbols) * n_symbol))
    out = np.zeros(positions.shape, dtype=np.complex128)
    valid = (positions >= 0.0) & (positions < float(head_samples))
    if not np.any(valid):
        return out

    local = positions[valid]
    preamble = local < float(preamble_end)
    if np.any(preamble):
        out_positions = np.flatnonzero(valid)[preamble]
        out[out_positions] = structural_head_symbol_samples(
            0,
            np.mod(local[preamble], n_symbol),
            cfg,
            up=True,
        )

    sync_symbols = (
        ((int(cfg.sync_word) & 0xF0) >> 4) << 3,
        (int(cfg.sync_word) & 0x0F) << 3,
    )
    for sync_index, symbol in enumerate(sync_symbols):
        lo = preamble_end + sync_index * n_symbol
        hi = lo + n_symbol
        mask = (local >= float(lo)) & (local < float(hi))
        if not np.any(mask):
            continue
        out_positions = np.flatnonzero(valid)[mask]
        out[out_positions] = structural_head_symbol_samples(
            symbol,
            local[mask] - float(lo),
            cfg,
            up=True,
        )

    sfd = (local >= float(sync_end)) & (local < float(head_samples))
    if np.any(sfd):
        out_positions = np.flatnonzero(valid)[sfd]
        out[out_positions] = structural_head_symbol_samples(
            0,
            np.mod(local[sfd] - float(sync_end), n_symbol),
            cfg,
            up=False,
        )

    carrier = np.exp(
        2j * math.pi * float(cfo_bins) * positions / float(n_symbol)
    )
    return out * carrier


def structural_head_atom(
    row: dict,
    cfg: RealCollisionLoRaConfig,
    *,
    sample_count: int,
    candidate_index: int,
) -> dict | None:
    """Build one anonymous known-head atom over its observed sample support."""

    start = row_start_sample(row)
    head_samples = int(round(float(cfg.payload_start_symbols) * cfg.samples_per_symbol))
    lo = max(0, int(math.ceil(start)))
    hi = min(int(sample_count), int(math.ceil(start + head_samples)))
    if hi <= lo:
        return None
    positions = np.arange(lo, hi, dtype=np.float64) - float(start)
    template = structural_head_template(
        positions,
        cfg,
        cfo_bins=row_cfo_bins(row),
    )
    energy = float(np.vdot(template, template).real)
    if not math.isfinite(energy) or energy <= 1e-18:
        return None
    return {
        "candidate_index": int(candidate_index),
        "lo": int(lo),
        "hi": int(hi),
        "template": template,
        "energy": energy,
        "channel": row_channel(row),
    }


def structural_head_components(atoms: list[dict]) -> list[list[dict]]:
    """Group only frame heads with overlapping known-structure support."""

    components: list[list[dict]] = []
    current: list[dict] = []
    current_hi = -1
    for atom in sorted(atoms, key=lambda item: (int(item["lo"]), int(item["hi"]))):
        if current and int(atom["lo"]) >= current_hi:
            components.append(current)
            current = []
            current_hi = -1
        current.append(atom)
        current_hi = max(current_hi, int(atom["hi"]))
    if current:
        components.append(current)
    return components


def head_component_normal_equations(
    samples: np.ndarray,
    atoms: list[dict],
) -> tuple[np.ndarray, np.ndarray]:
    """Return joint two-channel normal equations without materializing a dense window."""

    count = len(atoms)
    channels = int(samples.shape[0])
    gram = np.zeros((count, count), dtype=np.complex128)
    rhs = np.zeros((channels, count), dtype=np.complex128)
    for left, atom in enumerate(atoms):
        lo = int(atom["lo"])
        hi = int(atom["hi"])
        template = np.asarray(atom["template"], dtype=np.complex128)
        gram[left, left] = complex(float(atom["energy"]), 0.0)
        rhs[:, left] = np.asarray(
            [np.vdot(template, samples[channel, lo:hi]) for channel in range(channels)],
            dtype=np.complex128,
        )
        for right in range(left + 1, count):
            other = atoms[right]
            overlap_lo = max(lo, int(other["lo"]))
            overlap_hi = min(hi, int(other["hi"]))
            if overlap_hi <= overlap_lo:
                continue
            left_values = template[overlap_lo - lo : overlap_hi - lo]
            other_values = np.asarray(other["template"], dtype=np.complex128)[
                overlap_lo - int(other["lo"]) : overlap_hi - int(other["lo"])
            ]
            gram[left, right] = np.vdot(left_values, other_values)
            gram[right, left] = np.conj(gram[left, right])
    return gram, rhs


def solve_structural_head_component(
    samples: np.ndarray,
    atoms: list[dict],
) -> tuple[np.ndarray, np.ndarray, float, list[dict]]:
    """Jointly fit known heads in one overlap component on both RX channels."""

    gram, rhs = head_component_normal_equations(samples, atoms)
    diagonal = np.maximum(np.real(np.diag(gram)), 1e-18)
    normalizer = np.sqrt(diagonal)
    normalized_gram = gram / normalizer[:, None] / normalizer[None, :]
    condition_number = float(np.linalg.cond(normalized_gram))
    ridge = STRUCTURAL_HEAD_RIDGE_RELATIVE * np.diag(diagonal)
    try:
        gains = np.linalg.solve(gram + ridge, rhs.T).T
    except np.linalg.LinAlgError:
        gains = np.linalg.lstsq(gram + ridge, rhs.T, rcond=None)[0].T

    component_lo = min(int(atom["lo"]) for atom in atoms)
    component_hi = max(int(atom["hi"]) for atom in atoms)
    model = np.zeros(
        (samples.shape[0], component_hi - component_lo),
        dtype=np.complex128,
    )
    rows: list[dict] = []
    for index, atom in enumerate(atoms):
        lo = int(atom["lo"])
        hi = int(atom["hi"])
        template = np.asarray(atom["template"], dtype=np.complex128)
        model[:, lo - component_lo : hi - component_lo] += (
            gains[:, index, None] * template[None, :]
        )
        observed = samples[:, lo:hi]
        observed_energy = float(np.vdot(observed, observed).real)
        model_energy = float(np.vdot(gains[:, index], gains[:, index]).real) * float(
            atom["energy"]
        )
        fitted_channel = np.asarray(gains[:, index], dtype=np.complex128)
        rows.append(
            {
                "candidate_index": int(atom["candidate_index"]),
                "channel_coherence": channel_coherence(
                    fitted_channel,
                    np.asarray(atom["channel"], dtype=np.complex128),
                ),
                "atom_fit_fraction": model_energy / max(observed_energy, 1e-30),
            }
        )
    return model, gains, condition_number, rows


def cancel_structural_heads(
    samples: np.ndarray,
    candidates: list[dict],
    cfg: RealCollisionLoRaConfig,
) -> tuple[np.ndarray, dict]:
    """Subtract only jointly certified known heads; payload samples remain untouched."""

    residual = np.asarray(samples, dtype=np.complex64).copy()
    atoms = [
        atom
        for candidate_index, row in enumerate(candidates)
        if (
            atom := structural_head_atom(
                row,
                cfg,
                sample_count=int(samples.shape[1]),
                candidate_index=candidate_index,
            )
        )
        is not None
    ]
    component_diagnostics: list[dict] = []
    accepted_candidate_count = 0
    for component_index, component in enumerate(structural_head_components(atoms)):
        _, _, _, atom_rows = solve_structural_head_component(
            samples,
            component,
        )
        accepted_indices = {
            int(row["candidate_index"])
            for row in atom_rows
            if float(row["channel_coherence"])
            >= MIN_STRUCTURAL_HEAD_CHANNEL_COHERENCE
            and float(row["atom_fit_fraction"])
            >= MIN_STRUCTURAL_HEAD_ATOM_FIT_FRACTION
        }
        accepted_atoms = [
            atom for atom in component if int(atom["candidate_index"]) in accepted_indices
        ]
        component_lo = min(int(atom["lo"]) for atom in component)
        component_hi = max(int(atom["hi"]) for atom in component)
        model = np.zeros(
            (samples.shape[0], component_hi - component_lo),
            dtype=np.complex128,
        )
        condition_number = float("inf")
        if accepted_atoms:
            accepted_model, _, condition_number, atom_rows = solve_structural_head_component(
                samples,
                accepted_atoms,
            )
            accepted_lo = min(int(atom["lo"]) for atom in accepted_atoms)
            accepted_hi = max(int(atom["hi"]) for atom in accepted_atoms)
            model[:, accepted_lo - component_lo : accepted_hi - component_lo] = accepted_model
        before = np.asarray(samples[:, component_lo:component_hi], dtype=np.complex128)
        after = before - model
        energy_before = float(np.vdot(before, before).real)
        energy_after = float(np.vdot(after, after).real)
        reduction_fraction = (energy_before - energy_after) / max(energy_before, 1e-30)
        accepted = bool(
            accepted_atoms
            and math.isfinite(condition_number)
            and condition_number <= MAX_STRUCTURAL_HEAD_CONDITION_NUMBER
            and reduction_fraction >= MIN_STRUCTURAL_HEAD_COMPONENT_REDUCTION_FRACTION
        )
        if accepted:
            residual[:, component_lo:component_hi] = after.astype(np.complex64)
            accepted_candidate_count += len(accepted_atoms)
        recorded_condition_number = (
            float(condition_number) if math.isfinite(condition_number) else None
        )
        component_diagnostics.append(
            {
                "component": int(component_index),
                "candidate_count": len(component),
                "accepted_candidate_count": len(accepted_atoms) if accepted else 0,
                "condition_number": recorded_condition_number,
                "energy_reduction_fraction": float(reduction_fraction),
                "accepted": accepted,
                "atom_fits": atom_rows,
            }
        )
    return residual, {
        "scope": "known_preamble_sync_sfd_only_no_payload",
        "input_certified_candidate_count": len(candidates),
        "head_atom_count": len(atoms),
        "component_count": len(component_diagnostics),
        "accepted_candidate_count": int(accepted_candidate_count),
        "components": component_diagnostics,
    }


def plausible_for_timing_refinement(values: dict[str, float]) -> bool:
    """Keep only IQ-supported near misses for the expensive timing grid."""

    return bool(
        float(values["preamble_ratio"]) >= QUICK_PREAMBLE_RATIO_MIN
        and float(values["sync_confidence"]) >= QUICK_SYNC_CONFIDENCE_MIN
        and float(values["sfd_confidence"]) >= QUICK_SFD_CONFIDENCE_MIN
    )


def certify_global_proposal(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    proposal: dict,
    *,
    cfo_limit: float,
    discovery_pass: int,
    rejection_counts: dict[str, int] | None = None,
    certificate_maxima: dict[str, float] | None = None,
) -> dict | None:
    """Refine a detected structure around its observed IQ start, without priors."""

    n_symbol = int(cfg.samples_per_symbol)
    def reject(reason: str) -> None:
        if rejection_counts is not None:
            rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    proposed_start = row_start_sample(proposal)
    proposed_cfo = (
        row_cfo_bins(proposal)
        if bool(proposal.get("coarse_cfo_available", True))
        else None
    )
    refined_start, refined_cfo, _, sfd_anchor_score, _, _ = (
        sfd_anchored_start_cfo_refine(
            samples,
            proposed_start,
            cfg,
            symbol_radius=1,
            local_radius_bins=int(max(96.0, cfo_limit)),
            use_integer_alias_branch=True,
            coarse_up_bin=proposed_cfo,
            physical_cfo_min=-float(cfo_limit),
            physical_cfo_max=float(cfo_limit),
            max_start_correction_samples=0.80 * float(n_symbol),
        )
    )
    if (
        float(sfd_anchor_score) <= 0.0
        or not -float(cfo_limit) <= float(refined_cfo) <= float(cfo_limit)
        or abs(float(refined_start) - float(proposed_start))
        > 1.25 * float(n_symbol)
    ):
        reject("sfd_anchor_refine")
        return None

    start = float(refined_start)
    certificate_values, channel, peak_bin = certificate_values_at(
        samples,
        cfg,
        start=start,
        cfo_bins=float(refined_cfo),
    )
    # Most global structural proposals are aliases or partial heads.  A
    # complete certificate at the SFD-refined start needs no second timing
    # search.  Only an IQ-supported near miss pays for the legacy fine grid.
    if not structural_certificate(
        preamble_ratio=certificate_values["preamble_ratio"],
        sync_confidence=certificate_values["sync_confidence"],
        sfd_confidence=certificate_values["sfd_confidence"],
        frame_score=certificate_values["frame_structure_score"],
    ):
        if not plausible_for_timing_refinement(certificate_values):
            reject("quick_structure")
            return None
        start, _ = refine_start_fixed_cfo(
            samples,
            float(refined_start),
            float(refined_cfo),
            cfg,
        )
        if (
            abs(float(start) - float(refined_start))
            > 0.80 * float(n_symbol)
            or start < 0.0
            or start + float(cfg.frame_samples) > float(samples.shape[1])
        ):
            reject("fixed_cfo_start_refine")
            return None
        certificate_values, channel, peak_bin = certificate_values_at(
            samples,
            cfg,
            start=float(start),
            cfo_bins=float(refined_cfo),
        )
    if certificate_maxima is not None:
        for name, value in certificate_values.items():
            certificate_maxima[name] = max(
                certificate_maxima.get(name, float("-inf")), value
            )
    if not structural_certificate(
        preamble_ratio=certificate_values["preamble_ratio"],
        sync_confidence=certificate_values["sync_confidence"],
        sfd_confidence=certificate_values["sfd_confidence"],
        frame_score=certificate_values["frame_structure_score"],
    ):
        for name, value, minimum in (
            ("preamble_ratio", certificate_values["preamble_ratio"], MIN_PREAMBLE_RATIO),
            ("sync_confidence", certificate_values["sync_confidence"], MIN_SYNC_CONFIDENCE),
            ("sfd_confidence", certificate_values["sfd_confidence"], MIN_SFD_CONFIDENCE),
            ("frame_structure_score", certificate_values["frame_structure_score"], MIN_FRAME_STRUCTURE_SCORE),
        ):
            if not math.isfinite(value) or value < minimum:
                reject(name)
        return None

    start_floor = math.floor(float(start))
    return {
        "start_sample": float(start_floor),
        "sto_samples": float(start) - float(start_floor),
        "cfo_bins": float(refined_cfo),
        "continuous_cfo_bins": float(refined_cfo),
        "channel": [
            [float(np.real(value)), float(np.imag(value))]
            for value in channel
        ],
        "power": float(np.vdot(channel, channel).real),
        "confidence": float(
            max(
                float(proposal.get("confidence", 0.0)),
                float(sfd_anchor_score),
                float(certificate_values["preamble_ratio"]),
            )
        ),
        "preamble_ratio": float(certificate_values["preamble_ratio"]),
        "sync_confidence": float(certificate_values["sync_confidence"]),
        "sfd_confidence": float(certificate_values["sfd_confidence"]),
        "structure_score": float(certificate_values["frame_structure_score"]),
        "sfd_anchor_score": float(sfd_anchor_score),
        "peak_bin": int(peak_bin),
        "stage": "global_anonymous_preamble_sfd",
        "structure_certified": True,
        "discovery_pass": int(discovery_pass),
        "proposal_stage": str(
            proposal.get("frontend_candidate_stage", "global_sliding")
        ),
    }


def distinct_null_channels(rows: list[dict]) -> list[np.ndarray]:
    selected: list[np.ndarray] = []
    for row in sorted(rows, key=lambda item: float(item.get("power", 0.0)), reverse=True):
        channel = row_channel(row)
        norm = float(np.linalg.norm(channel))
        if channel.size != 2 or norm <= 1e-30:
            continue
        channel = channel / norm
        if any(channel_coherence(channel, old) >= NULL_CHANNEL_COHERENCE for old in selected):
            continue
        selected.append(channel)
        if len(selected) >= MAX_NULL_STREAMS:
            break
    return selected


def discovery_streams(
    samples: np.ndarray,
    prior_candidates: list[dict],
) -> np.ndarray:
    streams, eigvecs, _ = pca_project_streams(samples, include_original=True)
    residual_stream = (
        np.conj(eigvecs[:, -1])[None, :] @ samples
    ).astype(np.complex64)
    result = [streams, residual_stream]
    for channel in distinct_null_channels(prior_candidates):
        # [-h1, h0] @ h == 0.  This exposes a weaker spatially distinct head
        # without knowing or decoding either packet's payload.
        projector = np.asarray([-channel[1], channel[0]], dtype=np.complex128)
        projector /= max(float(np.linalg.norm(projector)), 1e-30)
        result.append((projector[None, :] @ samples).astype(np.complex64))
    return np.vstack(result)


def global_detection_pass(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    cfo_limit: float,
    discovery_pass: int,
    prior_candidates: list[dict],
) -> tuple[list[dict], dict]:
    """Run one complete-window preamble/SFD search with no schedule windows."""

    streams = discovery_streams(samples, prior_candidates)
    base_stream_count = 2 * int(samples.shape[0]) + 1
    spatial_null_stream_count = max(0, int(streams.shape[0]) - base_stream_count)
    print(
        f"FINE_SYNC_NULLING pass={discovery_pass} "
        f"prior_physical={len(prior_candidates)} "
        f"null_streams={spatial_null_stream_count}",
        flush=True,
    )
    proposals = sliding_preamble_sp_estimates(
        samples,
        cfg,
        streams=streams,
        threshold=3.0,
        cfo_min=-float(cfo_limit),
        cfo_max=float(cfo_limit),
        max_candidates=1,
        min_sfd_score=1.0,
        min_refined_sync_score=10.0,
        top_peaks_per_stream=0,
        refine_budget=0,
        hypotheses_per_bucket=HYPOTHESES_PER_COARSE_BUCKET,
        anchor_offsets_symbols=ANCHOR_OFFSETS_SYMBOLS,
        defer_sfd_refinement=True,
        min_preamble_run_symbols=8,
        preamble_run_chain_tolerance_symbols=0.025,
        structural_preamble_run_only=True,
        min_upchirp_peak_correlation=MIN_UPCHIRP_PEAK_CORRELATION,
        progress=lambda message: print(
            f"FINE_SYNC_FRONTEND pass={discovery_pass} {message}", flush=True
        ),
    )
    print(
        f"FINE_SYNC_CERTIFY_START pass={discovery_pass} "
        f"proposal_count={len(proposals)}",
        flush=True,
    )
    certified: list[dict] = []
    rejection_counts: dict[str, int] = {}
    certificate_maxima: dict[str, float] = {}
    for index, proposal in enumerate(proposals, start=1):
        row = certify_global_proposal(
            samples,
            cfg,
            proposal,
            cfo_limit=cfo_limit,
            discovery_pass=discovery_pass,
            rejection_counts=rejection_counts,
            certificate_maxima=certificate_maxima,
        )
        if row is not None:
            certified.append(row)
        if index % 32 == 0:
            print(
                f"FINE_SYNC_CERTIFY pass={discovery_pass} "
                f"processed={index}/{len(proposals)} accepted={len(certified)}",
                flush=True,
            )
    print(
        f"FINE_SYNC_CERTIFY_REJECTIONS pass={discovery_pass} {rejection_counts}",
        flush=True,
    )
    print(
        f"FINE_SYNC_CERTIFY_MAXIMA pass={discovery_pass} {certificate_maxima}",
        flush=True,
    )
    physical = deduplicate_physical_candidates(
        certified,
        int(cfg.samples_per_symbol),
    )
    return physical, {
        "pass": int(discovery_pass),
        "stream_count": int(streams.shape[0]),
        "spatial_null_stream_count": int(spatial_null_stream_count),
        "prior_physical_candidate_count": int(len(prior_candidates)),
        "raw_proposal_count": len(proposals),
        "certified_proposal_count": len(certified),
        "physical_candidate_count": len(physical),
        "certificate_rejection_counts": rejection_counts,
        "certificate_maxima": certificate_maxima,
    }


def discover_global_physical_candidates(
    samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    *,
    cfo_limit: float,
) -> tuple[list[dict], list[dict]]:
    """Reach a manifest-free global spatial-nulling discovery fixed point."""

    physical: list[dict] = []
    pass_diagnostics: list[dict] = []
    discovery_pass = 0
    while True:
        pass_rows, pass_diagnostic = global_detection_pass(
            samples,
            cfg,
            cfo_limit=cfo_limit,
            discovery_pass=discovery_pass,
            prior_candidates=physical,
        )
        previous_count = len(physical)
        physical = deduplicate_physical_candidates(
            [*physical, *pass_rows],
            int(cfg.samples_per_symbol),
        )
        new_count = len(physical) - previous_count
        if new_count < 0:
            raise RuntimeError("anonymous physical candidate set unexpectedly shrank")
        pass_diagnostic["new_physical_candidate_count"] = int(new_count)
        pass_diagnostic["cumulative_physical_candidate_count"] = int(len(physical))
        pass_diagnostics.append(pass_diagnostic)
        print(
            f"FINE_SYNC_NULLING_DONE pass={discovery_pass} "
            f"new={new_count} cumulative={len(physical)}",
            flush=True,
        )
        if new_count == 0:
            break
        discovery_pass += 1
    return physical, pass_diagnostics


def scheduled_packet_upper_bound(
    manifest: dict,
    *,
    duration_s: float,
) -> int:
    """Return a schedule-time-free absolute candidate ceiling.

    Candidate discovery never sees this value.  Without individual packet
    timestamps, no proportional slice estimate can be a true upper bound: a
    random traffic realization may concentrate more than its average share in
    the centered five-second slice.  The full-run scalar transmission count is
    the conservative manifest-only bound, with no node/time calibration.
    """

    schedules = manifest.get("expected_node_schedules", {})
    if not isinstance(schedules, dict):
        return 0
    total_packets = 0
    for schedule in schedules.values():
        if not isinstance(schedule, dict):
            continue
        tx_count = int(schedule.get("tx_count", 0))
        if tx_count > 0:
            total_packets += tx_count
    return int(total_packets)


def enforce_candidate_upper_bound(
    candidates: list[dict],
    upper_bound: int,
    *,
    run_name: str,
) -> None:
    """Fail closed; never let a score ranking discard a certified candidate."""

    if len(candidates) > int(upper_bound):
        raise CandidateOverflowError(
            f"{run_name}: globally certified {len(candidates)} physical candidates "
            f"exceed manifest scalar upper bound {upper_bound}; "
            "refusing score-based truncation"
        )


def build_run_database(
    runs_root: Path,
    reports_root: Path,
    out_root: Path,
    run_name: str,
    *,
    overwrite: bool,
    analysis_duration_s: float = ANALYSIS_DURATION_S,
) -> dict:
    if not math.isclose(
        float(analysis_duration_s),
        ANALYSIS_DURATION_S,
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"formal anonymous databases require {ANALYSIS_DURATION_S:g} s, "
            f"got {analysis_duration_s:g} s"
        )

    output = out_root / "fine_sync" / f"{run_name}.json"
    if output.exists() and not overwrite:
        existing = load_json(output)
        existing_schema = existing.get("schema")
        if existing_schema == ANONYMOUS_FINE_SYNC_SCHEMA:
            print(f"SKIP_EXISTING {output}", flush=True)
            return existing
        raise ValueError(
            f"{output} uses stale schema {existing_schema!r}; rerun with "
            "--overwrite to replace it"
        )

    manifest = manifest_for_run(runs_root, run_name)
    figure = str(manifest.get("experiment", {}).get("figure", ""))
    if figure not in {"fig9_10", "fig11", "fig12", "fig13", "fig14", "fig15"}:
        raise ValueError(f"{run_name}: not a supported PRR-figure run")

    traffic_start_s = traffic_start_s_for_run(runs_root, run_name, reports_root)
    business_duration_s = (
        float(manifest.get("config", {}).get("duration_ms", 0.0)) / 1000.0
    )
    if business_duration_s <= 0.0:
        business_duration_s = float(
            manifest.get("traffic", {}).get("duration_s", 0.0)
        )
    if business_duration_s < ANALYSIS_DURATION_S:
        raise ValueError(
            f"{run_name}: business duration {business_duration_s:g} s is shorter "
            f"than the formal {ANALYSIS_DURATION_S:g} s window"
        )

    relative_window_start_s = 0.5 * (
        float(business_duration_s) - ANALYSIS_DURATION_S
    )
    analysis_start_s = float(traffic_start_s) + relative_window_start_s
    run_dir = runs_root / run_name
    iq_path = run_dir / f"{run_name}.sc16"
    metadata = load_json(iq_path.with_suffix(iq_path.suffix + ".json"))
    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    bandwidth_hz = float(manifest.get("radio", {}).get("bandwidth_hz", 0.0))
    sf = int(manifest.get("radio", {}).get("spreading_factor", 10))
    cfg = RealCollisionLoRaConfig(
        sf=sf,
        bw_hz=bandwidth_hz,
        sample_rate_hz=rate,
        ldro=(2**sf) / bandwidth_hz >= 0.016,
    )

    samples = read_sc16(
        iq_path,
        start_sample_per_channel=round(analysis_start_s * rate),
        max_samples_per_channel=round(ANALYSIS_DURATION_S * rate),
    )
    white, _, _, _ = dc_remove_and_whiten(
        samples,
        noise_samples=int(round(min(3.0, ANALYSIS_DURATION_S) * rate)),
    )
    cfo_limit = max(
        32,
        int(math.ceil(15_625.0 / (bandwidth_hz / (2**sf)))),
    )
    print(
        f"FINE_SYNC_GLOBAL_START {run_name} "
        f"window={analysis_start_s:.6f}+{ANALYSIS_DURATION_S:g}s",
        flush=True,
    )
    physical, pass_diagnostics = discover_global_physical_candidates(
        white,
        cfg,
        cfo_limit=cfo_limit,
    )
    candidate_upper_bound = scheduled_packet_upper_bound(
        manifest,
        duration_s=ANALYSIS_DURATION_S,
    )
    enforce_candidate_upper_bound(
        physical,
        candidate_upper_bound,
        run_name=run_name,
    )

    database = {
        "schema": ANONYMOUS_FINE_SYNC_SCHEMA,
        "run_id": run_name,
        "source_iq": str(iq_path),
        "bandwidth_hz": float(bandwidth_hz),
        "spreading_factor": int(sf),
        "sample_rate_hz": float(rate),
        "window": {
            "traffic_start_s": float(traffic_start_s),
            "analysis_start_s": float(analysis_start_s),
            "relative_business_start_s": float(relative_window_start_s),
            "duration_s": ANALYSIS_DURATION_S,
        },
        "candidate_discovery": {
            "scope": "global_full_window",
            "full_window_scanned_s": ANALYSIS_DURATION_S,
            "manifest_role": "window_phy_and_post_detection_count_assertion_only",
            "manifest_schedule_exposed_to_detector": False,
            "identity_binding": "crc_valid_payload_only_after_candidate_database",
            "node_timing_calibration": False,
            "planned_start_search_windows": False,
            "score_truncation": False,
            "coarse_bucket_hypothesis_limit": None,
            "candidate_overflow_policy": "fail_closed_without_truncation",
            "residual_policy": "iterative_global_spatial_nulling_without_structural_head_cancellation",
            "discovery_passes": pass_diagnostics,
        },
        "deduplication": {
            "dimensions": ["physical_start", "cfo", "dual_channel_direction"],
            "linkage": "complete",
            "start_tolerance_symbols": ALIAS_START_TOLERANCE_SYMBOLS,
            "cfo_tolerance_bins": ALIAS_CFO_TOLERANCE_BINS,
            "channel_coherence_min": ALIAS_CHANNEL_COHERENCE_MIN,
            "same_cfo_alias_channel_coherence_min": (
                SAME_CFO_ALIAS_CHANNEL_COHERENCE_MIN
            ),
            "integer_cfo_alias_tolerance_bins": INTEGER_CFO_ALIAS_TOLERANCE_BINS,
            "integer_cfo_alias_channel_coherence_min": (
                INTEGER_CFO_ALIAS_CHANNEL_COHERENCE_MIN
            ),
            "integer_cfo_alias_max_bins": MAX_INTEGER_CFO_ALIAS_BINS,
            "representative_policy": "highest_structure_score_within_exact_alias_cluster_only",
        },
        "structure_certificate": {
            "preamble_ratio_min": MIN_PREAMBLE_RATIO,
            "sync_confidence_min": MIN_SYNC_CONFIDENCE,
            "sfd_confidence_min": MIN_SFD_CONFIDENCE,
            "frame_structure_score_min": MIN_FRAME_STRUCTURE_SCORE,
            "upchirp_peak_correlation_min": MIN_UPCHIRP_PEAK_CORRELATION,
        },
        "scheduled_packet_upper_bound": int(candidate_upper_bound),
        "detected_physical_candidate_count": len(physical),
        "detection_rate_vs_scheduled_upper_bound": (
            float(len(physical) / candidate_upper_bound)
            if candidate_upper_bound
            else 0.0
        ),
        "packets": physical,
    }
    save_json(output, database)
    print(
        f"FINE_SYNC_GLOBAL_DONE {run_name} candidates={len(physical)}/"
        f"{candidate_upper_bound} passes={len(pass_diagnostics)} out={output}",
        flush=True,
    )
    return database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=EXPERIMENT / "runs")
    parser.add_argument(
        "--reports",
        type=Path,
        default=EXPERIMENT / "analysis/fig9_10_12_preview/reports",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=EXPERIMENT / "analysis/fig9_10_12_preview",
    )
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--duration-s", type=float, default=ANALYSIS_DURATION_S)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not math.isclose(args.duration_s, ANALYSIS_DURATION_S, abs_tol=1e-9):
        raise SystemExit(
            f"--duration-s must be {ANALYSIS_DURATION_S:g} for formal databases"
        )
    selected = {value.lower().removeprefix("run_") for value in args.run_id}
    manifest_paths: dict[str, Path] = {
        path.stem: path.resolve()
        for path in (args.runs / "manifests").glob("run_*.json")
    }
    for run_dir in args.runs.glob("run_*"):
        candidate = run_dir / f"{run_dir.name}.json"
        if candidate.exists():
            manifest_paths[candidate.stem] = candidate.resolve()

    built = 0
    for manifest_path in sorted(manifest_paths.values()):
        name = manifest_path.stem
        if selected and name.removeprefix("run_").lower() not in selected:
            continue
        figure = str(load_json(manifest_path).get("experiment", {}).get("figure", ""))
        if figure not in {"fig9_10", "fig11", "fig12", "fig13", "fig14", "fig15"}:
            continue
        build_run_database(
            args.runs,
            args.reports,
            args.out_dir,
            name,
            overwrite=args.overwrite,
            analysis_duration_s=args.duration_s,
        )
        built += 1
    print(f"FINE_SYNC_GLOBAL_DATABASE_DONE runs={built}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
