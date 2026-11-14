#!/usr/bin/env python3
"""Node01 single-node closed-loop receiver for real B210 captures."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONTROL_DIR = ROOT / "real_collision_experiment" / "control_usrp"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from lora_mrc_sp_core import (
    decode_packet_branch,
    fixed_mrc_branch_parameters,
    pca_project_streams,
)
from evaluate_sp_dechirp_real_pos import (
    attach_sp_reliability_and_lambda,
    mrc_decode_bins,
    sp_dechirp_decode_bins,
)
from sp_noise_competition import POLICY as SP_LAMBDA_POLICY, TWO_PACKET_POLICY
from sp_reference_guard import GUARDED_PAIR_POLICY, decision_channel
from protocol import (
    DATA_PAYLOAD_SIZE,
    DataPayload,
    RunConfig,
    build_data_payload,
    decode_data_payload,
    expected_tx_schedule_ms,
)

from lora_phy_decode import PhyPayloadDecode, decode_payload_from_symbol_bins
from real_lora_config import RealCollisionLoRaConfig
from real_sp_frontend import detected_estimates_real, same_packet_estimate
from sp_detection_frontend import (
    batched_stable_preamble_tracks,
    preamble_channel_near_cfo,
    sfd_anchored_start_cfo_refine,
    sfd_score,
    sliding_preamble_sp_estimates,
    stable_preamble_multi_tracks,
    sync_word_score,
)
from sc16_io import (
    adc_clipping_statistics,
    dc_remove_and_whiten,
    load_capture,
    read_sc16,
)
from compare.real_packet_decoders import (
    PaperComparisonContext,
    PhysicalEvidencePayloadCache,
)
from compare.native_frontends import (
    cic_native_estimates,
    detect_native_frontends,
    refine_paper_frontend_from_sp_fine,
)


DECODER_METHODS = (
    "lorawan",
    "ch0",
    "ch1",
    "mrc",
    "sp_core",
    "sp_sync_refine",
    "sp",
    "mrc_cic",
    "pcube",
    "maloragw",
)

PAYLOAD_BITS = DATA_PAYLOAD_SIZE * 8
WINDOW_MANIFEST_PRR_SOURCE = (
    "min_manifest_window_expected_or_anonymous_detected_packets"
)
WINDOW_MANIFEST_PRR_POLICY = (
    "unique_crc_valid_payload_identities_over_"
    "min_manifest_window_expected_or_anonymous_detected_packets"
)


def physical_evidence_key(est: dict, candidate_id: int) -> tuple:
    """Bind reusable work to one certified anonymous physical candidate.

    The database candidate id prevents time-near simultaneous packets from
    sharing work.  Start/CFO/STO and the normalized two-channel direction are
    retained as an audit guard against accidentally reusing a stale estimate.
    """

    channel = complex_pairs_to_array(est.get("channel_sp", est.get("channel", [])))
    norm = float(np.linalg.norm(channel))
    if norm > 1e-30:
        channel = channel / norm
    direction = tuple(
        (round(float(value.real), 9), round(float(value.imag), 9))
        for value in channel
    )
    return (
        "anonymous_physical_candidate",
        int(candidate_id),
        round(float(est["start_sample"]), 9),
        round(float(est.get("sto_samples_sp", est.get("sto_samples", 0.0))), 9),
        round(
            float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))),
            9,
        ),
        direction,
    )


def sp_trial_cache_key(physical_key: tuple, est: dict) -> tuple:
    channel = complex_pairs_to_array(decision_channel(est))
    norm = float(np.linalg.norm(channel))
    if norm > 1e-30:
        channel = channel / norm
    direction = tuple(
        (round(float(value.real), 9), round(float(value.imag), 9))
        for value in channel
    )
    return (
        physical_key,
        round(float(est["start_sample"]), 9),
        round(float(est.get("sto_samples_sp", est.get("sto_samples", 0.0))), 9),
        round(
            float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))),
            9,
        ),
        round(float(est.get("lambda_sp", 0.0)), 12),
        direction,
    )


@dataclass
class SharedPhysicalDecodeCache:
    """Cache only exact reuses of computation tied to physical evidence."""

    sp_payload_trials: dict[tuple, dict] = field(default_factory=dict)
    sp_payload_hits: int = 0
    sp_payload_misses: int = 0

    def decode_sp(
        self,
        samples: np.ndarray,
        est: dict,
        cfg: RealCollisionLoRaConfig,
        *,
        physical_key: tuple,
    ) -> dict:
        key = sp_trial_cache_key(physical_key, est)
        cached = self.sp_payload_trials.get(key)
        if cached is not None:
            self.sp_payload_hits += 1
            return copy.deepcopy(cached)
        self.sp_payload_misses += 1
        decoded = decode_method("sp", samples, est, cfg)
        self.sp_payload_trials[key] = copy.deepcopy(decoded)
        return decoded

    def audit(self) -> dict:
        return {
            "scope": "same_anonymous_physical_candidate_and_exact_sync_channel_lambda",
            "sp_payload_trial_hits": int(self.sp_payload_hits),
            "sp_payload_trial_misses": int(self.sp_payload_misses),
            "cached_sp_payload_trials": int(len(self.sp_payload_trials)),
        }



def payload_goodput_kbps(
    packet_count: int,
    duration_s: float | None,
    *,
    payload_bits: int = PAYLOAD_BITS,
) -> float | None:
    """CRC-valid application payload bits per business second, in decimal kbps."""
    if not duration_s:
        return None
    return float(packet_count) * int(payload_bits) / float(duration_s) / 1000.0


def native_method_metrics(
    method: str,
    rows: list[dict],
    *,
    business_duration_s: float | None,
    manifest_expected_packet_count: int | None = None,
) -> dict:
    """Diagnostic native-front-end decode counters; not formal shared-D PRR."""

    identities: set[tuple[int, int]] = set()
    identity_mismatch_count = 0
    for row in rows:
        decoded = next(
            (item for item in row.get("methods", []) if item.get("method") == method),
            None,
        )
        if decoded is None:
            continue
        app = decoded.get("application", {})
        payload = app.get("decoded")
        if bool(app.get("app_crc_ok", False)) and isinstance(payload, dict):
            identities.add((int(payload["node_id"]), int(payload["sequence"])))
        elif isinstance(payload, dict):
            identity_mismatch_count += 1
    complete_count = len(rows)
    success_count = len(identities)
    formal_window_prr = manifest_expected_packet_count is not None
    decoded_success_count = (
        success_count if formal_window_prr else success_count + identity_mismatch_count
    )
    prr_denominator_packet_count = (
        min(int(manifest_expected_packet_count), complete_count)
        if formal_window_prr
        else complete_count + identity_mismatch_count
    )
    metrics = {
        "execution_status": "completed",
        "frontend_scope": "receiver_native_end_to_end",
        "complete_detected_packet_count": int(complete_count),
        "identity_matched_success_count": int(success_count),
        "identity_mismatch_count": int(identity_mismatch_count),
        "decoded_success_count": int(decoded_success_count),
        "prr_denominator_packet_count": int(prr_denominator_packet_count),
        "prr_denominator_source": (
            WINDOW_MANIFEST_PRR_SOURCE
            if formal_window_prr
            else "complete_detected_packets"
        ),
        "prr_counting_policy": (
            WINDOW_MANIFEST_PRR_POLICY
            if formal_window_prr
            else "detected_packets_plus_identity_mismatches"
        ),
        "prr": (
            float(decoded_success_count) / prr_denominator_packet_count
            if prr_denominator_packet_count
            else None
        ),
        "decoded_success_tps": (
            float(decoded_success_count) / business_duration_s if business_duration_s else None
        ),
        "payload_goodput_kbps": payload_goodput_kbps(
            decoded_success_count, business_duration_s
        ),
        "decoded_identities": [
            {"node_id": node_id, "sequence": sequence}
            for node_id, sequence in sorted(identities)
        ],
    }
    if formal_window_prr:
        metrics["manifest_expected_packet_count_in_analysis_window"] = int(
            manifest_expected_packet_count
        )
        metrics["prr_detected_physical_packet_count"] = int(complete_count)
    return metrics


def complex_pairs_to_array(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(r, i) for r, i in values], dtype=np.complex128)


def load_manifest(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_expected_sequences_in_window(
    manifest: dict,
    active_nodes: set[int],
    *,
    start_ms: float | None,
    duration_ms: float | None,
) -> dict[int, list[int]] | None:
    """Return manifest sequence IDs whose planned TX starts fall in one slice.

    This is a post-decode reporting helper.  It is never supplied to the
    synchronization frontend, candidate discovery, refinement, or decoding.
    """

    if start_ms is None or duration_ms is None:
        return None
    if not math.isfinite(float(start_ms)) or float(duration_ms) <= 0.0:
        raise ValueError("planned business window must have finite start and positive duration")
    schedules = manifest.get("expected_node_schedules", {})
    if not isinstance(schedules, dict):
        raise ValueError("planned business-window PRR requires manifest schedules")
    end_ms = float(start_ms) + float(duration_ms)
    expected: dict[int, list[int]] = {}
    for node_id in sorted(active_nodes):
        schedule = schedules.get(str(int(node_id)))
        if not isinstance(schedule, dict):
            raise ValueError(
                f"planned business-window PRR has no manifest schedule for node {node_id}"
            )
        starts = schedule.get("tx_start_ms_from_traffic_begin")
        if not isinstance(starts, list):
            raise ValueError(
                f"planned business-window PRR has no start list for node {node_id}"
            )
        expected[int(node_id)] = [
            int(sequence)
            for sequence, planned_start_ms in enumerate(starts)
            if float(start_ms) <= float(planned_start_ms) < end_ms
        ]
    return expected


def metadata_number(value, default: float) -> float:
    if value is None:
        return float(default)
    if isinstance(value, (list, tuple)):
        if not value:
            return float(default)
        return float(value[0])
    return float(value)


def energy_candidate_ranges(
    samples: np.ndarray,
    *,
    rate: float,
    cfg: RealCollisionLoRaConfig,
    top_windows: int,
    window_seconds: float,
    min_ratio: float,
    expected_events: int = 0,
    block_samples: int = 1024,
    noise_floor_power: float | None = None,
) -> tuple[list[tuple[int, int]], dict]:
    """Find independent RF bursts and return preamble-only scan windows.

    The former implementation selected a capture-wide threshold from the
    *expected* packet count, clustered events less than 250 ms apart, and then
    scanned 0.8 s around each peak.  A LoRa frame in this profile is about
    371 ms long, so two legitimate frames can have only a few tens of
    milliseconds of silence between them.  Peak clustering consequently
    merged packets, while the large windows produced many payload aliases that
    competed in a global candidate budget.

    This detector is deliberately independent of the manifest.  It identifies
    energy rising edges at 2 ms resolution, bridges only very short holes, and
    gives every burst its own small preamble/SFD window.  Payload decoding still
    uses the original full capture after the start/CFO estimate is obtained.
    """
    n = int(samples.shape[1])
    if n <= 0:
        return [], {"enabled": True, "ranges": []}
    block_samples = max(256, int(block_samples))
    usable = (n // block_samples) * block_samples
    if usable <= 0:
        return [(0, n)], {"enabled": True, "ranges": [{"start_sample": 0, "end_sample": n}]}
    block_count = usable // block_samples
    power = np.empty(block_count, dtype=np.float64)
    # Keep the temporary working set small.  The old all-capture abs/square
    # expression briefly allocated hundreds of MB for a 60 s dual-B210 file.
    chunk_blocks = 2048
    for block_begin in range(0, block_count, chunk_blocks):
        block_end = min(block_count, block_begin + chunk_blocks)
        sample_begin = block_begin * block_samples
        sample_end = block_end * block_samples
        chunk = samples[:, sample_begin:sample_end].reshape(
            samples.shape[0], block_end - block_begin, block_samples
        )
        power[block_begin:block_end] = np.mean(np.abs(chunk) ** 2, axis=(0, 2))
    median_power = float(np.median(power))
    # A busy capture can contain signal for more than half its duration, which
    # makes the median a signal level rather than a noise estimate.  A lower
    # robust percentile remains capture-local without using manifest counts.
    noise_floor_percentile = 20.0
    if noise_floor_power is None or float(noise_floor_power) <= 0.0:
        noise_floor_power = float(np.percentile(power, noise_floor_percentile))
    else:
        noise_floor_power = float(noise_floor_power)
    requested_min_ratio = max(float(min_ratio), 1.0)
    selected_min_ratio = requested_min_ratio
    threshold = noise_floor_power * requested_min_ratio
    active = power >= threshold

    # Bridge detector holes no longer than 12 ms.  This repairs a faded burst
    # but cannot join distinct frames whose mandatory idle gap is longer.
    bridge_blocks = max(1, int(round(0.012 * rate / block_samples)))
    active_indices = np.flatnonzero(active)
    for left, right in zip(active_indices[:-1], active_indices[1:]):
        if 0 < int(right - left - 1) <= bridge_blocks:
            active[left : right + 1] = True

    min_event_blocks = max(2, int(round(0.020 * rate / block_samples)))
    events: list[dict] = []
    idx = 0
    while idx < int(power.size):
        if not bool(active[idx]):
            idx += 1
            continue
        begin = idx
        while idx < int(power.size) and bool(active[idx]):
            idx += 1
        end = idx
        if end - begin < min_event_blocks:
            continue
        peak = float(np.max(power[begin:end]))
        events.append(
            {
                "begin_block": int(begin),
                "end_block": int(end),
                "peak_relative_db": float(
                    10.0 * math.log10((peak + 1e-30) / (noise_floor_power + 1e-30))
                ),
            }
        )

    event_count_before_limit = len(events)
    if int(top_windows) > 0 and len(events) > int(top_windows):
        events = sorted(events, key=lambda row: row["peak_relative_db"], reverse=True)[: int(top_windows)]
        events.sort(key=lambda row: row["begin_block"])

    preamble_search_margin = int(round(2.5 * cfg.samples_per_symbol))
    # 16.5 symbols gives the coarse detector four possible start phases and
    # enough tail for the 12.25-symbol preamble/sync/SFD structure.
    detection_window_len = int(round(16.5 * cfg.samples_per_symbol))
    frame_samples = int(
        round((cfg.payload_start_symbols + cfg.payload_symbol_count) * cfg.samples_per_symbol)
    )
    selected: list[tuple[int, int]] = []
    for event in events:
        onset = int(event["begin_block"]) * block_samples
        event_end = int(min(n, int(event["end_block"]) * block_samples))
        # A busy interval longer than one frame implies that another packet
        # may have started after the first rising edge.  Extend the compact
        # preamble window only by that excess duration: this scans every
        # possible later preamble while avoiding capture-wide/payload scans.
        overlap_extension = max(0, event_end - onset - frame_samples)
        start = max(0, onset - preamble_search_margin)
        end = min(n, start + detection_window_len + overlap_extension)
        start = max(0, end - detection_window_len - overlap_extension)
        event["onset_sample"] = int(onset)
        event["end_sample"] = int(event_end)
        event["duration_s"] = float(event["end_sample"] - onset) / rate
        event["busy_overlap_extension_samples"] = int(overlap_extension)
        selected.append((start, end))
    diag = {
        "enabled": True,
        "block_samples": block_samples,
        "median_power": median_power,
        "noise_floor_percentile": noise_floor_percentile,
        "noise_floor_power": noise_floor_power,
        "min_ratio": float(selected_min_ratio),
        "requested_min_ratio": float(requested_min_ratio),
        "threshold_power": float(threshold),
        "event_count_before_limit": int(event_count_before_limit),
        "raw_event_count_before_cluster": int(event_count_before_limit),
        "expected_event_count": int(expected_events),
        "expected_event_count_used_for_detection": False,
        "range_strategy": "rising_edge_plus_busy_interval_continuous_preamble_scan",
        "event_cluster_seconds": 0.0,
        "bridge_gap_seconds": 0.012,
        "top_windows": int(top_windows),
        "window_seconds": float(window_seconds),
        "actual_detection_window_seconds": float(detection_window_len) / rate,
        "merge_overlapping_event_windows": False,
        "events": events,
        "ranges": [
            {
                "start_sample": int(start),
                "end_sample": int(end),
                "start_time_s": float(start) / rate,
                "end_time_s": float(end) / rate,
            }
            for start, end in selected
        ],
    }
    return selected, diag


def offset_estimate_samples(est: dict, offset: int) -> dict:
    out = dict(est)
    for key in ("start_sample", "pre_joint_start_sample"):
        if key in out:
            out[key] = float(out[key]) + float(offset)
    out["frontend_window_start_sample"] = int(offset)
    return out


def supplement_sp_estimates_with_continuous_sfd(
    physical_samples: np.ndarray,
    whitened_samples: np.ndarray,
    cfg: RealCollisionLoRaConfig,
    seed_estimates: list[dict],
    scan_ranges: list[tuple[int, int]],
    *,
    cfo_min: float,
    cfo_max: float,
    max_candidates: int,
) -> tuple[list[dict], dict]:
    """Add sample-continuous SFD-pair proposals to SP preamble proposals.

    This is the shared implementation used by both the formal real-capture
    receiver and Fig. 11.  The SFD path proposes packet timing/CFO only; every
    accepted supplemental candidate gets a fresh two-channel estimate in the
    same whitened domain used by SP, and no CIC payload decision is reused.
    """

    sfd_rows, native_diagnostics = cic_native_estimates(
        physical_samples,
        cfg,
        scan_ranges,
        cfo_min=float(cfo_min),
        cfo_max=float(cfo_max),
        max_candidates=max(1, int(max_candidates)),
    )
    combined = [dict(item) for item in seed_estimates]
    added_count = 0
    for native_sfd in sfd_rows:
        aligned = float(native_sfd["start_sample"]) + float(
            native_sfd.get("sto_samples", 0.0)
        )
        cfo = float(
            native_sfd.get(
                "continuous_cfo_bins", native_sfd.get("cfo_bins", 0.0)
            )
        )
        if not (float(cfo_min) <= cfo <= float(cfo_max)):
            continue
        channel_score, channel, peak_bin = preamble_channel_near_cfo(
            whitened_samples, aligned, cfo, cfg, radius_bins=2
        )
        supplemental = dict(native_sfd)
        supplemental.update(
            {
                "start_sample": float(math.floor(aligned)),
                "sto_samples": float(aligned - math.floor(aligned)),
                "cfo_bins": cfo,
                "continuous_cfo_bins": cfo,
                "channel": [
                    [float(np.real(value)), float(np.imag(value))]
                    for value in channel
                ],
                "power": float(np.vdot(channel, channel).real),
                "confidence": float(
                    max(channel_score, native_sfd.get("confidence", 0.0))
                ),
                "peak_bin": int(peak_bin),
                "frontend_candidate_stage": "continuous_sfd_pair_supplement",
                "native_frontend_method": "sp_sfd_supplement",
            }
        )
        if any(same_packet_estimate(supplemental, old, cfg) for old in combined):
            continue
        combined.append(supplemental)
        added_count += 1

    complete: list[dict] = []
    for estimate in sorted(
        combined,
        key=lambda row: float(row["start_sample"])
        + float(row.get("sto_samples", 0.0)),
    ):
        aligned = float(estimate["start_sample"]) + float(
            estimate.get("sto_samples", 0.0)
        )
        if aligned < 0.0 or aligned + float(cfg.frame_samples) > float(
            whitened_samples.shape[1]
        ):
            continue
        if any(same_packet_estimate(estimate, old, cfg) for old in complete):
            continue
        complete.append(estimate)
        if len(complete) >= max(1, int(max_candidates)):
            break

    diagnostics = {
        "enabled": True,
        "implementation": "shared_continuous_sfd_pair_supplement_v1",
        "preamble_seed_count": int(len(seed_estimates)),
        "sfd_raw_candidate_count": int(len(sfd_rows)),
        "sfd_new_candidate_count_before_completeness": int(added_count),
        "final_complete_candidate_count": int(len(complete)),
        "native_sfd_detector": native_diagnostics,
    }
    return complete, diagnostics


def run_config_from_manifest(manifest: dict, args: argparse.Namespace) -> RunConfig | None:
    cfg = manifest.get("config")
    if not isinstance(cfg, dict):
        return None
    keys = {
        "run_id",
        "active_mask",
        "num_active_nodes",
        "phy_profile_id",
        "traffic_profile_id",
        "node_tx_power_dbm",
        "duration_ms",
        "warmup_ms",
        "global_seed",
        "payload_seed",
        "flags",
    }
    return RunConfig(**{k: int(v) for k, v in cfg.items() if k in keys})


RUN_CONFIG_KEYS = (
    "run_id",
    "active_mask",
    "num_active_nodes",
    "phy_profile_id",
    "traffic_profile_id",
    "node_tx_power_dbm",
    "duration_ms",
    "warmup_ms",
    "global_seed",
    "payload_seed",
    "flags",
)


def run_config_from_dict(source: dict, fallback: RunConfig | None) -> RunConfig | None:
    """Build the RunConfig that reproduces a node's transmitted payload."""

    if not isinstance(source, dict):
        return fallback
    values = {key: source.get(key) for key in RUN_CONFIG_KEYS}
    if not any(value is not None for value in values.values()):
        return fallback
    return RunConfig(**{key: int(values[key]) for key in RUN_CONFIG_KEYS})


def merged_identity_alias_map(manifest: dict) -> dict[tuple[int, int], int]:
    """Map (source_run_id, source_node_id) to the merged manifest node id.

    Merged/simulated runs keep the physical packets of both source captures,
    so the payload-embedded identity still names the source node and source
    run.  For normal runs every schedule entry has no alias and the map stays
    empty, meaning the decoded identity is used unchanged.
    """

    aliases: dict[tuple[int, int], int] = {}
    schedules = manifest.get("expected_node_schedules", {})
    if not isinstance(schedules, dict):
        return aliases
    for node_text, schedule in schedules.items():
        if not isinstance(schedule, dict):
            continue
        source_run_id = schedule.get("source_run_id")
        source_node_id = schedule.get("source_node_id")
        if source_run_id is None or source_node_id is None:
            continue
        aliases[(int(source_run_id), int(source_node_id))] = int(node_text)
    return aliases


def payload_config_for_node(
    manifest: dict,
    node_id: int,
    fallback: RunConfig | None,
) -> RunConfig | None:
    """Return the RunConfig that reproduces a node's transmitted payload.

    Merged runs store per-node ``source_config`` (the exact source run config
    under which that physical packet was transmitted).  Normal runs have no
    per-node override and use the current run's config.
    """

    schedules = manifest.get("expected_node_schedules", {})
    if isinstance(schedules, dict):
        schedule = schedules.get(str(int(node_id)))
        if isinstance(schedule, dict):
            source_cfg = run_config_from_dict(schedule.get("source_config"), fallback)
            if source_cfg is not None:
                return source_cfg
    return fallback


def scheduled_identity_key(
    decoded: dict,
    identity_aliases: dict[tuple[int, int], int],
    default_run_id: int | None,
) -> tuple[int, int]:
    """Map a decoded payload identity to the manifest-scheduled (node, seq)."""

    node_id = int(decoded["node_id"])
    run_id = decoded.get("run_id", default_run_id)
    merged_node = identity_aliases.get((int(run_id), node_id))
    return (int(merged_node) if merged_node is not None else node_id, int(decoded["sequence"]))


def detection_decode_statistics(
    *,
    run_cfg: RunConfig | None,
    manifest: dict,
    active_nodes: set[int],
    energy_diag: dict,
    candidates: list[dict],
    complete_burst_threshold_s: float,
    business_duration_s: float | None,
    capture_sample_count: int,
    frame_sample_count: int,
    packet_alias_time_tolerance_samples: float,
    executed_methods: set[str] | None = None,
    accepted_run_ids: set[int] | None = None,
    identity_aliases: dict[tuple[int, int], int] | None = None,
    fine_sync_candidate_count: int | None = None,
    expected_sequences_by_node: dict[int, list[int]] | None = None,
) -> dict:
    """Report detection separately from CRC-closed decoding.

    Truncated RF bursts are recorded but excluded from both numerator and
    denominator. Formal PRR callers supply an identity-free shared physical
    candidate count; without one these are diagnostic complete-candidate
    metrics only.
    """

    schedules = manifest.get("expected_node_schedules", {}) if isinstance(manifest, dict) else {}
    window_expected_identities: set[tuple[int, int]] | None = None
    if expected_sequences_by_node is not None:
        window_expected_identities = {
            (int(node_id), int(sequence))
            for node_id, sequences in expected_sequences_by_node.items()
            if int(node_id) in active_nodes
            for sequence in sequences
        }
        expected_count = len(window_expected_identities)
    else:
        expected_count = 0
        if isinstance(schedules, dict):
            for node_id in active_nodes:
                schedule = schedules.get(str(node_id), {})
                if isinstance(schedule, dict):
                    expected_count += int(schedule.get("tx_count", 0))
        if expected_count <= 0 and run_cfg is not None:
            expected_count = sum(
                len(expected_tx_schedule_ms(run_cfg, node_id)) for node_id in active_nodes
            )

    formal_window_prr = expected_sequences_by_node is not None

    payload_bytes = int(
        manifest.get("traffic", {}).get("data_payload_bytes", DATA_PAYLOAD_SIZE)
    )
    payload_bits = max(0, payload_bytes) * 8

    events = list(energy_diag.get("events", [])) if isinstance(energy_diag, dict) else []
    ranges = list(energy_diag.get("ranges", [])) if isinstance(energy_diag, dict) else []
    event_count = min(len(events), len(ranges))
    methods = DECODER_METHODS
    executed = set(methods) if executed_methods is None else set(executed_methods)
    unknown = executed - set(methods)
    if unknown:
        raise ValueError(f"unknown executed decoder methods: {sorted(unknown)}")

    def metrics_for_method(
        method: str,
        *,
        complete_count: int,
        identity_matched_success_count: int,
        prr_denominator_source: str = "complete_detected_packets",
        identity_confirmation_required: bool = False,
        identity_mismatch_count: int = 0,
        prr_counting_policy: str = "detected_packets_plus_identity_mismatches",
    ) -> dict:
        decoded_success_count = (
            int(identity_matched_success_count)
            if formal_window_prr
            else int(identity_matched_success_count) + int(identity_mismatch_count)
        )
        prr_denominator_packet_count = (
            min(expected_count, int(complete_count))
            if formal_window_prr
            else int(complete_count) + int(identity_mismatch_count)
        )
        if formal_window_prr:
            prr_denominator_source = WINDOW_MANIFEST_PRR_SOURCE
            prr_counting_policy = WINDOW_MANIFEST_PRR_POLICY
        if method not in executed:
            return {
                "execution_status": "not_run",
                "not_run_reason": "disabled by --skip-comparison-decoders",
                "complete_detected_packet_count": None,
                "decoded_success_count": None,
                "prr": None,
                "decoded_success_tps": None,
                "payload_goodput_kbps": None,
                "prr_denominator_source": prr_denominator_source,
                "identity_confirmation_required": identity_confirmation_required,
                "identity_matched_success_count": None,
                "identity_mismatch_count": None,
                "prr_denominator_packet_count": None,
                "prr_counting_policy": prr_counting_policy,
            }
        metrics = {
            "execution_status": "completed",
            "complete_detected_packet_count": int(complete_count),
            "decoded_success_count": decoded_success_count,
            "prr": (
                float(decoded_success_count) / prr_denominator_packet_count
                if prr_denominator_packet_count > 0
                else None
            ),
            "decoded_success_tps": (
                float(decoded_success_count) / business_duration_s
                if business_duration_s
                else None
            ),
            "payload_goodput_kbps": payload_goodput_kbps(
                decoded_success_count, business_duration_s, payload_bits=payload_bits
            ),
            "prr_denominator_source": prr_denominator_source,
            "identity_confirmation_required": bool(identity_confirmation_required),
            "identity_matched_success_count": int(identity_matched_success_count),
            "identity_mismatch_count": int(identity_mismatch_count),
            "prr_denominator_packet_count": prr_denominator_packet_count,
            "prr_counting_policy": prr_counting_policy,
        }
        if formal_window_prr:
            metrics["manifest_expected_packet_count_in_analysis_window"] = int(
                expected_count
            )
            metrics["prr_detected_physical_packet_count"] = int(complete_count)
        return metrics

    def decoded_identity(candidate: dict, method: str) -> tuple[int, int] | None:
        decoded = next(
            (item for item in candidate.get("methods", []) if item.get("method") == method),
            None,
        )
        if decoded is None:
            return None
        app = decoded.get("application", {})
        payload = app.get("decoded")
        if not bool(app.get("app_crc_ok", False)) or not isinstance(payload, dict):
            return None
        if run_cfg is not None:
            accepted = set(accepted_run_ids or set())
            accepted.add(int(run_cfg.run_id))
            if int(payload.get("run_id", -1)) not in accepted:
                return None
        source_node_id = int(payload.get("node_id", -1))
        source_run_id = int(payload.get("run_id", -1))
        node_id = int((identity_aliases or {}).get((source_run_id, source_node_id), source_node_id))
        if active_nodes and node_id not in active_nodes:
            return None
        return node_id, int(payload.get("sequence", -1))

    def crc_valid_identity(candidate: dict, method: str) -> tuple[int, int] | None:
        """Return a protocol/CRC-valid payload identity before run/node filtering.

        The formal PRR definition deliberately keeps an identity-mismatched
        CRC-valid payload visible as ``U``.  ``decoded_identity`` above is
        still the accepted-identity helper used by the legacy, non-fine-sync
        metrics; this helper must not discard a payload merely because its
        identity does not match the current target.
        """

        decoded = next(
            (item for item in candidate.get("methods", []) if item.get("method") == method),
            None,
        )
        if decoded is None:
            return None
        app = decoded.get("application", {})
        payload = app.get("decoded")
        if not bool(app.get("app_crc_ok", False)) or not isinstance(payload, dict):
            return None
        source_node_id = int(payload.get("node_id", -1))
        source_run_id = int(payload.get("run_id", -1))
        node_id = int((identity_aliases or {}).get((source_run_id, source_node_id), source_node_id))
        return node_id, int(payload.get("sequence", -1))

    def identity_mismatched_decode(candidate: dict, method: str) -> tuple[int, int] | None:
        """Return a CRC-valid payload that fails this run's identity filter."""

        decoded = next(
            (item for item in candidate.get("methods", []) if item.get("method") == method),
            None,
        )
        if decoded is None:
            return None
        app = decoded.get("application", {})
        payload = app.get("decoded")
        if bool(app.get("app_crc_ok", False)) or not isinstance(payload, dict):
            return None
        source_node_id = int(payload.get("node_id", -1))
        source_run_id = int(payload.get("run_id", -1))
        node_id = int((identity_aliases or {}).get((source_run_id, source_node_id), source_node_id))
        return node_id, int(payload.get("sequence", -1))

    if fine_sync_candidate_count is not None:
        # A formal database row represents one anonymous, structurally
        # certified physical frame head.  Identity is intentionally not an
        # input to this metric: a candidate passes when this decoder produces
        # a CRC-valid application payload, regardless of the decoded node or
        # sequence carried by that payload.
        detected_count = int(fine_sync_candidate_count)
        if detected_count < 0:
            raise ValueError("fine_sync_candidate_count must be non-negative")
        if len(candidates) != detected_count:
            raise ValueError(
                "anonymous fine-sync database candidate count does not match "
                f"receiver candidates ({detected_count} != {len(candidates)})"
            )
        packet_rows: list[dict] = []
        successful_identities = {method: set() for method in methods}
        for candidate in candidates:
            candidate_id = int(candidate.get("candidate_id", -1))
            method_success: dict[str, bool] = {}
            decoded_identities: dict[str, list[int] | None] = {}
            for method in methods:
                identity = crc_valid_identity(candidate, method)
                method_success[method] = identity is not None
                decoded_identities[method] = list(identity) if identity is not None else None
                if identity is not None:
                    successful_identities[method].add(identity)
            packet_rows.append(
                {
                    "candidate_id": candidate_id,
                    "complete": True,
                    "discarded_as_truncated": False,
                    "decode_success_by_method": method_success,
                    # Post-decode payload metadata only.  It is excluded from
                    # PRR attribution and candidate construction.
                    "decoded_identity_by_method": decoded_identities,
                }
            )

        def anonymous_metrics(method: str) -> dict:
            if method not in executed:
                return {
                    "execution_status": "not_run",
                    "not_run_reason": "disabled by --skip-comparison-decoders",
                    "complete_detected_packet_count": None,
                    "decoded_success_count": None,
                    "prr": None,
                    "decoded_success_tps": None,
                    "payload_goodput_kbps": None,
                    "manifest_expected_packet_count_in_analysis_window": expected_count,
                    "prr_detected_physical_packet_count": detected_count,
                    "prr_denominator_source": WINDOW_MANIFEST_PRR_SOURCE,
                    "prr_counting_policy": WINDOW_MANIFEST_PRR_POLICY,
                }
            decoded_count = len(successful_identities[method])
            prr_denominator_packet_count = min(expected_count, detected_count)
            return {
                "execution_status": "completed",
                "complete_detected_packet_count": detected_count,
                "decoded_success_count": decoded_count,
                "unique_crc_valid_payload_identity_count": decoded_count,
                "manifest_expected_packet_count_in_analysis_window": expected_count,
                "prr_detected_physical_packet_count": detected_count,
                "prr_denominator_packet_count": prr_denominator_packet_count,
                "prr": (
                    float(decoded_count) / prr_denominator_packet_count
                    if prr_denominator_packet_count
                    else None
                ),
                "decoded_success_tps": (
                    float(decoded_count) * payload_bits / business_duration_s
                    if business_duration_s
                    else None
                ),
                "payload_goodput_kbps": payload_goodput_kbps(
                    decoded_count, business_duration_s, payload_bits=payload_bits
                ),
                "prr_denominator_source": WINDOW_MANIFEST_PRR_SOURCE,
                "prr_counting_policy": WINDOW_MANIFEST_PRR_POLICY,
                "decoded_identities": [
                    {"node_id": node_id, "sequence": sequence}
                    for node_id, sequence in sorted(successful_identities[method])
                ],
            }

        return {
            "definition": {
                "packet_detection_rate": "anonymous structurally certified physical candidates / planned-packet count",
                "prr": (
                    "unique CRC-valid payload identities / min(manifest planned "
                    "packet count in analysis window, anonymous detected physical candidates)"
                ),
                "decoded_success_tps": "unique CRC-valid payload identities * manifest payload bits / business duration",
                "payload_goodput_kbps": "unique CRC-valid payload identities * manifest payload bits / business duration / 1000",
            },
            "expected_packet_count": int(expected_count) if expected_count > 0 else None,
            "raw_detected_rf_burst_count": int(event_count),
            "complete_detected_packet_count": detected_count,
            "fine_sync_detected_packet_count": detected_count,
            "complete_candidate_hypothesis_count": int(len(candidates)),
            "truncated_rf_burst_count": 0,
            "short_non_packet_rf_event_count": 0,
            "raw_rf_burst_detection_rate": None,
            "packet_detection_rate": (
                float(detected_count) / expected_count if expected_count > 0 else None
            ),
            "business_duration_s": business_duration_s,
            "payload_bits": payload_bits,
            "manifest_expected_packet_count_in_analysis_window": expected_count,
            "prr_detected_physical_packet_count": detected_count,
            "prr_denominator_source": WINDOW_MANIFEST_PRR_SOURCE,
            "prr_counting_policy": WINDOW_MANIFEST_PRR_POLICY,
            "by_method": {method: anonymous_metrics(method) for method in methods},
            "packets": packet_rows,
        }

    # Multiple overlapping packets can form one continuous RF-energy burst.
    # In that case PRR and detection must be counted per refined packet target,
    # not per energy interval.  RF events remain an independent diagnostic.
    if len(active_nodes) > 1:
        candidate_rows: list[dict] = []
        truncated_count = 0
        for candidate in candidates:
            start = float(candidate.get("start_sample", -1.0))
            complete = bool(
                start >= 0.0
                and start + int(frame_sample_count) <= int(capture_sample_count)
            )
            truncated_count += int(not complete)
            method_success: dict[str, bool] = {}
            identities: dict[str, list[int] | None] = {}
            mismatched_identities: dict[str, list[int] | None] = {}
            for method in methods:
                identity = decoded_identity(candidate, method) if complete else None
                mismatched = (
                    identity_mismatched_decode(candidate, method) if complete else None
                )
                method_success[method] = identity is not None
                identities[method] = list(identity) if identity is not None else None
                mismatched_identities[method] = (
                    list(mismatched) if mismatched is not None else None
                )
            candidate_rows.append(
                {
                    "candidate_id": int(candidate.get("candidate_id", -1)),
                    "start_sample": start,
                    "complete": complete,
                    "discarded_as_truncated": bool(not complete),
                    "decode_success_by_method": method_success,
                    "decoded_identity_by_method": identities,
                    "identity_mismatched_decode_by_method": mismatched_identities,
                    "channel_sp": candidate.get("channel_sp"),
                }
            )

        # The front end deliberately keeps close time/CFO hypotheses until after
        # decoding so that a weak packet is not destroyed by an early merge.  Two
        # such hypotheses can nevertheless close to the same application packet.
        # Collapse those aliases here: candidates are decoder hypotheses, while
        # this metric's denominator is the number of detected packet targets.
        complete_rows = [row for row in candidate_rows if row["complete"]]
        parents = list(range(len(complete_rows)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        owner_by_identity: dict[tuple[int, int], int] = {}
        for row_index, row in enumerate(complete_rows):
            identities = {
                tuple(identity)
                for identity in row["decoded_identity_by_method"].values()
                if identity is not None
            }
            for identity in identities:
                owner = owner_by_identity.get(identity)
                if owner is None:
                    owner_by_identity[identity] = row_index
                else:
                    union(row_index, owner)

        def channel_direction(row: dict) -> np.ndarray | None:
            values = row.get("channel_sp")
            if not isinstance(values, list) or len(values) != 2:
                return None
            try:
                channel = np.asarray(
                    [complex(float(value[0]), float(value[1])) for value in values],
                    dtype=np.complex128,
                )
            except (TypeError, ValueError, IndexError):
                return None
            norm = math.sqrt(float(np.vdot(channel, channel).real))
            return channel / norm if norm > 0.0 else None

        # A failed CFO alias has no decoded identity of its own, so identity
        # dedup alone cannot remove it from the packet denominator.  Merge such
        # an unresolved hypothesis only when it is nearly simultaneous with a
        # decoded target and its two-channel direction is essentially the same.
        # Truly simultaneous users with distinct spatial directions remain
        # independent packet targets.
        decoded_row_indices = [
            index
            for index, row in enumerate(complete_rows)
            if any(value is not None for value in row["decoded_identity_by_method"].values())
        ]
        for row_index, row in enumerate(complete_rows):
            if row_index in decoded_row_indices:
                continue
            direction = channel_direction(row)
            if direction is None:
                continue
            for decoded_index in decoded_row_indices:
                decoded_row = complete_rows[decoded_index]
                if abs(float(row["start_sample"]) - float(decoded_row["start_sample"])) > float(
                    packet_alias_time_tolerance_samples
                ):
                    continue
                decoded_direction = channel_direction(decoded_row)
                if decoded_direction is None:
                    continue
                coherence = float(abs(np.vdot(direction, decoded_direction)) ** 2)
                if coherence >= 0.98:
                    union(row_index, decoded_index)
                    row["spatial_alias_of_candidate_id"] = int(decoded_row["candidate_id"])
                    row["spatial_alias_coherence"] = coherence
                    break

        groups: dict[int, list[dict]] = {}
        for row_index, row in enumerate(complete_rows):
            groups.setdefault(find(row_index), []).append(row)

        packet_rows: list[dict] = []
        success_ids = {method: set() for method in methods}
        mismatch_counts = {method: 0 for method in methods}
        aliased_candidate_count = 0
        for rows in groups.values():
            aliased_candidate_count += len(rows) - 1
            method_success: dict[str, bool] = {}
            identities: dict[str, list[int] | None] = {}
            for method in methods:
                method_identities = {
                    tuple(identity)
                    for row in rows
                    for identity in [row["decoded_identity_by_method"].get(method)]
                    if identity is not None
                }
                method_success[method] = bool(method_identities)
                identity = min(method_identities) if method_identities else None
                identities[method] = list(identity) if identity is not None else None
                success_ids[method].update(method_identities)
                mismatch_present = any(
                    row["identity_mismatched_decode_by_method"].get(method) is not None
                    for row in rows
                )
                if not method_identities and mismatch_present:
                    mismatch_counts[method] += 1
            packet_rows.append(
                {
                    "candidate_id": int(rows[0]["candidate_id"]),
                    "candidate_ids": [int(row["candidate_id"]) for row in rows],
                    "start_sample": min(float(row["start_sample"]) for row in rows),
                    "complete": True,
                    "discarded_as_truncated": False,
                    "decode_success_by_method": method_success,
                    "decoded_identity_by_method": identities,
                    "candidate_alias_count": len(rows) - 1,
                }
            )
        packet_rows.extend(row for row in candidate_rows if not row["complete"])
        complete_count = len(groups)

        by_method: dict[str, dict] = {}
        for method in methods:
            success_count = len(success_ids[method])
            by_method[method] = metrics_for_method(
                method,
                complete_count=complete_count,
                identity_matched_success_count=success_count,
                identity_mismatch_count=mismatch_counts[method],
            )
        short_rf_count = sum(
            float(event.get("duration_s", 0.0)) < float(complete_burst_threshold_s)
            for event in events
        )
        return {
            "definition": {
                "raw_rf_burst_detection_rate": "not defined for concurrent packets because one RF burst may contain multiple packets",
                "packet_detection_rate": "complete refined packet targets / planned packets",
                "prr": (
                    "(identity-matched CRC-valid packets + identity-mismatched "
                    "CRC-valid packets) / (complete detected packet targets + "
                    "identity-mismatched CRC-valid packets); truncated targets are excluded"
                ),
                "decoded_success_tps": (
                    "(identity-matched CRC-valid packets + identity-mismatched "
                    "CRC-valid packets) / business duration"
                ),
                "payload_goodput_kbps": (
                    "(identity-matched CRC-valid packets + identity-mismatched "
                    "CRC-valid packets) * 20 bytes * 8 / business duration / 1000"
                ),
            },
            "expected_packet_count": int(expected_count) if expected_count > 0 else None,
            "raw_detected_rf_burst_count": int(event_count),
            "complete_detected_packet_count": int(complete_count),
            "complete_candidate_hypothesis_count": int(len(complete_rows)),
            "decoded_identity_alias_candidate_count": int(aliased_candidate_count),
            "truncated_rf_burst_count": int(truncated_count),
            "short_non_packet_rf_event_count": int(short_rf_count),
            "raw_rf_burst_detection_rate": None,
            "packet_detection_rate": (
                float(complete_count) / expected_count if expected_count > 0 else None
            ),
            "business_duration_s": business_duration_s,
            "by_method": by_method,
            "packets": packet_rows,
        }

    packet_rows: list[dict] = []
    complete_count = 0
    truncated_count = 0
    success_by_method = {method: 0 for method in methods}
    mismatch_by_method = {method: 0 for method in methods}

    for event_index in range(event_count):
        event = events[event_index]
        window = ranges[event_index]
        duration_s = float(event.get("duration_s", 0.0))
        complete = bool(duration_s >= float(complete_burst_threshold_s))
        complete_count += int(complete)
        truncated_count += int(not complete)
        start = int(window.get("start_sample", 0))
        end = int(window.get("end_sample", start))
        rows = [c for c in candidates if start <= float(c.get("start_sample", -1.0)) < end]
        method_success: dict[str, bool] = {}
        for method in methods:
            crc_closed = False
            identity_mismatched = False
            if complete:
                for candidate in rows:
                    decoded = next(
                        (item for item in candidate.get("methods", []) if item.get("method") == method),
                        None,
                    )
                    if decoded is None:
                        continue
                    app = decoded.get("application", {})
                    payload = app.get("decoded")
                    if not isinstance(payload, dict):
                        continue
                    if not bool(app.get("app_crc_ok", False)):
                        identity_mismatched = True
                        continue
                    if run_cfg is not None and int(payload.get("run_id", -1)) != int(run_cfg.run_id):
                        identity_mismatched = True
                        continue
                    if active_nodes and int(payload.get("node_id", -1)) not in active_nodes:
                        identity_mismatched = True
                        continue
                    crc_closed = True
                    break
            method_success[method] = crc_closed
            success_by_method[method] += int(crc_closed)
            mismatch_by_method[method] += int(not crc_closed and identity_mismatched)
        packet_rows.append(
            {
                "event_index": int(event_index),
                "onset_sample": int(event.get("onset_sample", 0)),
                "duration_s": duration_s,
                "complete": complete,
                "discarded_as_truncated": bool(not complete),
                "decode_success_by_method": method_success,
            }
        )

    raw_detection_rate = float(event_count) / expected_count if expected_count > 0 else None
    complete_detection_rate = float(complete_count) / expected_count if expected_count > 0 else None
    by_method: dict[str, dict] = {}
    for method in methods:
        success_count = int(success_by_method[method])
        by_method[method] = metrics_for_method(
            method,
            complete_count=complete_count,
            identity_matched_success_count=success_count,
            identity_mismatch_count=mismatch_by_method[method],
        )
    return {
        "definition": {
            "raw_rf_burst_detection_rate": "all detected RF bursts, including truncated bursts, / planned packets",
            "packet_detection_rate": "complete detected packets / planned packets",
            "prr": (
                "(identity-matched CRC-valid packets + identity-mismatched CRC-valid "
                "packets) / (complete detected packets + identity-mismatched CRC-valid "
                "packets); truncated bursts are excluded"
            ),
            "decoded_success_tps": (
                "(identity-matched CRC-valid packets + identity-mismatched CRC-valid "
                "packets) / business duration; missing and truncated packets reduce TPS"
            ),
            "payload_goodput_kbps": (
                "(identity-matched CRC-valid packets + identity-mismatched CRC-valid "
                "packets) * 20 bytes * 8 / business duration / 1000; "
                "missing and truncated packets reduce goodput"
            ),
        },
        "expected_packet_count": int(expected_count) if expected_count > 0 else None,
        "raw_detected_rf_burst_count": int(event_count),
        "complete_detected_packet_count": int(complete_count),
        "truncated_rf_burst_count": int(truncated_count),
        "raw_rf_burst_detection_rate": raw_detection_rate,
        "packet_detection_rate": complete_detection_rate,
        "business_duration_s": business_duration_s,
        "by_method": by_method,
        "packets": packet_rows,
    }


def manual_expected_counts(args: argparse.Namespace, active_nodes: set[int]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for item in args.expected_node_tx_count:
        if ":" not in item:
            raise ValueError("--expected-node-tx-count must use NODE:COUNT")
        node_text, count_text = item.split(":", 1)
        node_id = int(node_text, 0)
        count = int(count_text, 0)
        if count < 0:
            raise ValueError("expected TX count must be non-negative")
        counts[node_id] = count
    if args.expected_tx_count is not None:
        if args.expected_tx_count < 0:
            raise ValueError("--expected-tx-count must be non-negative")
        if len(active_nodes) != 1:
            raise ValueError("--expected-tx-count is only unambiguous with exactly one active node")
        counts[next(iter(active_nodes))] = int(args.expected_tx_count)
    return counts


def planned_collision_recovery_statistics(
    *,
    manifest: dict,
    active_nodes: set[int],
    candidates: list[dict],
    frame_duration_ms: float,
) -> dict:
    """Label decoded identities by manifest-planned temporal overlap."""

    schedules = manifest.get("expected_node_schedules", {}) if isinstance(manifest, dict) else {}
    planned: list[tuple[tuple[int, int], float]] = []
    if isinstance(schedules, dict):
        for node_id in sorted(active_nodes):
            row = schedules.get(str(node_id), {})
            starts = row.get("tx_start_ms_from_traffic_begin", []) if isinstance(row, dict) else []
            planned.extend(
                ((int(node_id), int(sequence)), float(start_ms))
                for sequence, start_ms in enumerate(starts)
            )
    collided: set[tuple[int, int]] = set()
    collision_order: dict[tuple[int, int], int] = {}
    for identity, start in planned:
        overlaps = 0
        for other_identity, other_start in planned:
            if identity == other_identity:
                continue
            if max(start, other_start) < min(
                start + float(frame_duration_ms),
                other_start + float(frame_duration_ms),
            ):
                overlaps += 1
        collision_order[identity] = 1 + overlaps
        if overlaps:
            collided.add(identity)

    decoded_by_method: dict[str, set[tuple[int, int]]] = {
        method: set()
        for method in DECODER_METHODS
    }
    for candidate in candidates:
        for method_row in candidate.get("methods", []):
            method = str(method_row.get("method", ""))
            if method not in decoded_by_method:
                continue
            app = method_row.get("application", {})
            payload = app.get("decoded")
            if not bool(app.get("app_crc_ok", False)) or not isinstance(payload, dict):
                continue
            node_id = int(payload.get("node_id", -1))
            if node_id not in active_nodes:
                continue
            decoded_by_method[method].add((node_id, int(payload.get("sequence", -1))))

    planned_ids = {identity for identity, _ in planned}
    noncollided = planned_ids - collided
    by_method: dict[str, dict] = {}
    for method, decoded in decoded_by_method.items():
        collision_success = decoded & collided
        noncollision_success = decoded & noncollided
        by_method[method] = {
            "planned_collision_packet_count": len(collided),
            "collision_success_count": len(collision_success),
            "collision_delivery_ratio": (
                float(len(collision_success)) / len(collided) if collided else None
            ),
            "planned_noncollision_packet_count": len(noncollided),
            "noncollision_success_count": len(noncollision_success),
            "noncollision_delivery_ratio": (
                float(len(noncollision_success)) / len(noncollided) if noncollided else None
            ),
            "collision_success_identities": [
                {"node_id": node_id, "sequence": sequence}
                for node_id, sequence in sorted(collision_success)
            ],
        }
    sp_collision = decoded_by_method["sp"] & collided
    mrc_collision = decoded_by_method["mrc"] & collided
    return {
        "definition": "post-hoc collision labels from manifest-planned packet interval overlap; manifest is not used by the detector",
        "frame_duration_ms": float(frame_duration_ms),
        "planned_packet_count": len(planned_ids),
        "planned_collision_packet_count": len(collided),
        "planned_noncollision_packet_count": len(noncollided),
        "collision_order_by_identity": [
            {"node_id": node_id, "sequence": sequence, "collision_order": collision_order[(node_id, sequence)]}
            for node_id, sequence in sorted(planned_ids)
        ],
        "by_method": by_method,
        "sp_added_over_mrc_collision_count": len(sp_collision - mrc_collision),
        "sp_added_over_mrc_collision_identities": [
            {"node_id": node_id, "sequence": sequence}
            for node_id, sequence in sorted(sp_collision - mrc_collision)
        ],
        "mrc_only_collision_count": len(mrc_collision - sp_collision),
    }


def validate_payload(
    payload_bytes: bytes,
    *,
    run_id: int | None,
    active_nodes: set[int],
    accepted_run_ids: set[int] | None = None,
) -> tuple[DataPayload | None, bool, str]:
    try:
        decoded = decode_data_payload(payload_bytes)
    except Exception as exc:
        return None, False, str(exc)
    if run_id is not None:
        accepted = set(accepted_run_ids or set())
        accepted.add(int(run_id))
        if accepted and int(decoded.run_id) not in accepted:
            return decoded, False, f"run_id mismatch: got 0x{decoded.run_id:08X}"
    if active_nodes and int(decoded.node_id) not in active_nodes:
        return decoded, False, f"node_id {decoded.node_id} not active"
    return decoded, True, "ok"


def decoded_payload_from_method(method_row: dict) -> dict | None:
    app = method_row.get("application", {})
    decoded = app.get("decoded")
    return decoded if isinstance(decoded, dict) else None


def method_decode_statistics(candidates: list[dict]) -> dict:
    """按解码方法统计候选包通过/失败原因。"""

    stats: dict[str, dict] = {}
    for row in candidates:
        for method_row in row.get("methods", []):
            method = str(method_row.get("method", "unknown"))
            phy = method_row.get("phy", {})
            app = method_row.get("application", {})
            item = stats.setdefault(
                method,
                {
                    "detected_candidates": 0,
                    "phy_crc_ok": 0,
                    "phy_crc_failed_likely_symbol_error": 0,
                    "application_protocol_valid": 0,
                    "accepted_after_run_node_filters": 0,
                    "rejected_by_run_id_or_node_filter": 0,
                    "application_crc_failed": 0,
                    "payload_magic_or_version_failed": 0,
                    "not_enough_symbols_or_codewords": 0,
                    "other_failures": 0,
                    "corrected_codewords_total": 0,
                    "uncorrected_codewords_total": 0,
                    "mean_symbol_margin": 0.0,
                },
            )
            item["detected_candidates"] += 1
            item["corrected_codewords_total"] += int(phy.get("corrected_codewords", 0))
            item["uncorrected_codewords_total"] += int(phy.get("uncorrected_codewords", 0))
            item["mean_symbol_margin"] += float(method_row.get("mean_symbol_margin", 0.0))
            if bool(phy.get("phy_crc_ok", False)):
                item["phy_crc_ok"] += 1
            else:
                item["phy_crc_failed_likely_symbol_error"] += 1
            status = str(app.get("status", ""))
            if decoded_payload_from_method(method_row) is not None:
                item["application_protocol_valid"] += 1
                if bool(app.get("app_crc_ok", False)):
                    item["accepted_after_run_node_filters"] += 1
                else:
                    item["rejected_by_run_id_or_node_filter"] += 1
            elif "application CRC16 mismatch" in status:
                item["application_crc_failed"] += 1
            elif "magic/version" in status:
                item["payload_magic_or_version_failed"] += 1
            elif "not_enough" in str(phy.get("status", "")):
                item["not_enough_symbols_or_codewords"] += 1
            else:
                item["other_failures"] += 1
    for item in stats.values():
        total = max(1, int(item["detected_candidates"]))
        item["mean_symbol_margin"] = float(item["mean_symbol_margin"]) / total
        item["phy_crc_success_rate_over_detected"] = float(item["phy_crc_ok"]) / total
        item["accepted_rate_over_detected"] = float(item["accepted_after_run_node_filters"]) / total
    return stats


def prr_tps_statistics(
    *,
    run_cfg: RunConfig | None,
    manifest: dict,
    active_nodes: set[int],
    successes: dict[str, dict],
    protocol_successes: dict[str, dict],
    capture_duration_s: float,
    manual_expected_by_node: dict[int, int] | None = None,
    manual_business_duration_s: float | None = None,
    expected_sequences_by_node: dict[int, list[int]] | None = None,
) -> dict:
    """生成正式 PRR/TPS；没有 manifest 时只给观测口径 TPS。"""

    accepted_by_node: dict[int, set[int]] = {}
    protocol_by_node: dict[int, set[int]] = {}
    accepted_by_method_node: dict[str, dict[int, set[int]]] = {}
    protocol_by_method_node: dict[str, dict[int, set[int]]] = {}
    for item in successes.values():
        node_id = int(item["node_id"])
        sequence = int(item["sequence"])
        accepted_by_node.setdefault(node_id, set()).add(sequence)
        for method in item.get("methods", []):
            accepted_by_method_node.setdefault(str(method), {}).setdefault(node_id, set()).add(sequence)
    for item in protocol_successes.values():
        node_id = int(item["node_id"])
        sequence = int(item["sequence"])
        protocol_by_node.setdefault(node_id, set()).add(sequence)
        for method in item.get("methods", []):
            protocol_by_method_node.setdefault(str(method), {}).setdefault(node_id, set()).add(sequence)

    business_duration_s = (
        float(manual_business_duration_s)
        if manual_business_duration_s is not None
        else (float(run_cfg.duration_ms) / 1000.0 if run_cfg is not None else None)
    )
    expected_by_node: dict[int, list[int]] = {}
    denominator_source = "none"
    if expected_sequences_by_node is not None:
        expected_by_node = {
            int(node_id): sorted({int(sequence) for sequence in sequences})
            for node_id, sequences in expected_sequences_by_node.items()
            if int(node_id) in active_nodes
        }
        denominator_source = "manifest_tx_starts_in_business_analysis_window"
    elif manual_expected_by_node:
        for node_id, tx_count in manual_expected_by_node.items():
            if int(node_id) in active_nodes:
                expected_by_node[int(node_id)] = list(range(max(0, int(tx_count))))
        denominator_source = "manual"
    schedules = manifest.get("expected_node_schedules") if isinstance(manifest, dict) else None
    if not expected_by_node and isinstance(schedules, dict):
        for node_text, schedule in schedules.items():
            if int(node_text) not in active_nodes:
                continue
            if isinstance(schedule, dict):
                tx_count = int(schedule.get("tx_count", 0))
                expected_by_node[int(node_text)] = list(range(tx_count))
        denominator_source = "manifest"
    elif not expected_by_node and run_cfg is not None:
        for node_id in sorted(active_nodes):
            expected_by_node[int(node_id)] = list(range(len(expected_tx_schedule_ms(run_cfg, int(node_id)))))
        denominator_source = "run_config"

    node_rows: dict[str, dict] = {}
    total_expected = 0
    total_accepted = 0
    total_protocol = 0
    for node_id in sorted(active_nodes):
        accepted = sorted(accepted_by_node.get(node_id, set()))
        protocol = sorted(protocol_by_node.get(node_id, set()))
        if accepted:
            sequence_span = list(range(min(accepted), max(accepted) + 1))
            missing_in_sequence_span = sorted(set(sequence_span) - set(accepted))
            sequence_span_coverage = float(len(accepted)) / max(1, len(sequence_span))
        else:
            sequence_span = []
            missing_in_sequence_span = []
            sequence_span_coverage = None
        expected = expected_by_node.get(node_id)
        if expected is None:
            missing = None
            prr = None
            expected_count = None
            accepted_expected = accepted
            extra_sequences = []
        else:
            expected_set = set(expected)
            accepted_set = set(accepted)
            accepted_expected = sorted(expected_set & accepted_set)
            extra_sequences = sorted(accepted_set - expected_set)
            missing = sorted(expected_set - accepted_set)
            prr = float(len(accepted_expected)) / max(1, len(expected))
            expected_count = len(expected)
            total_expected += len(expected)
        total_accepted += len(accepted_expected)
        total_protocol += len(protocol)
        node_rows[str(node_id)] = {
            "expected_tx_count": expected_count,
            "accepted_success_count": len(accepted_expected),
            "accepted_success_count_including_unexpected_sequences": len(accepted),
            "protocol_valid_before_filters_count": len(protocol),
            "accepted_sequences": accepted,
            "accepted_expected_sequences": accepted_expected,
            "extra_sequences_not_in_expected_schedule": extra_sequences,
            "protocol_valid_sequences_before_filters": protocol,
            "missing_sequences": missing,
            "accepted_sequence_span": [sequence_span[0], sequence_span[-1]] if sequence_span else None,
            "missing_sequences_in_accepted_span": missing_in_sequence_span,
            "sequence_span_coverage_diagnostic": sequence_span_coverage,
            "planned_crc_delivery_ratio": prr,
            "tps_business_s": (float(len(accepted_expected)) / business_duration_s) if business_duration_s else None,
            "payload_goodput_kbps": payload_goodput_kbps(
                len(accepted_expected), business_duration_s
            ),
            "observed_tps_capture_s": float(len(accepted_expected)) / max(capture_duration_s, 1e-9),
        }

    aggregate_prr = float(total_accepted) / max(1, total_expected) if total_expected > 0 else None
    method_rows: dict[str, dict] = {}
    all_methods = sorted(
        set(accepted_by_method_node)
        | set(protocol_by_method_node)
        | set(DECODER_METHODS)
    )
    for method in all_methods:
        method_accepted_total = 0
        method_accepted_total_with_extra = 0
        for node_id, seqs in accepted_by_method_node.get(method, {}).items():
            expected = expected_by_node.get(node_id)
            method_accepted_total_with_extra += len(seqs)
            method_accepted_total += len(seqs if expected is None else (set(expected) & set(seqs)))
        method_protocol_total = sum(len(v) for v in protocol_by_method_node.get(method, {}).values())
        method_rows[method] = {
            "expected_tx_count": int(total_expected) if total_expected > 0 else None,
            "accepted_success_count": int(method_accepted_total),
            "accepted_success_count_including_unexpected_sequences": int(method_accepted_total_with_extra),
            "protocol_valid_before_filters_count": int(method_protocol_total),
            "planned_crc_delivery_ratio": (
                float(method_accepted_total) / max(1, total_expected)
            ) if total_expected > 0 else None,
            "tps_business_s": (float(method_accepted_total) / business_duration_s) if business_duration_s else None,
            "payload_goodput_kbps": payload_goodput_kbps(
                method_accepted_total, business_duration_s
            ),
            "observed_tps_capture_s": float(method_accepted_total) / max(capture_duration_s, 1e-9),
        }
    return {
        "definition": {
            "planned_crc_delivery_ratio": (
                "CRC-valid accepted packets / ideal planned TX count from manifest/RunConfig; "
                "this is not the conditional PRR"
            ),
            "tps_business_s": "accepted unique data packets divided by configured business duration",
            "payload_goodput_kbps": (
                "accepted unique 20-byte payloads * 8 divided by configured "
                "business duration and 1000"
            ),
            "observed_tps_capture_s": "accepted unique data packets divided by IQ capture duration; diagnostic only",
            "phy_crc_failed_likely_symbol_error": "detected candidate whose LoRa PHY CRC did not pass for that method",
        },
        "has_planned_denominator": bool(total_expected > 0 and business_duration_s is not None),
        "has_official_denominator": bool(
            total_expected > 0
            and business_duration_s is not None
            and denominator_source == "manual"
        ),
        "denominator_source": denominator_source,
        "business_duration_s": business_duration_s,
        "capture_duration_s": float(capture_duration_s),
        "aggregate": {
            "expected_tx_count": int(total_expected) if total_expected > 0 else None,
            "accepted_success_count": int(total_accepted),
            "protocol_valid_before_filters_count": int(total_protocol),
            "planned_crc_delivery_ratio": aggregate_prr,
            "tps_business_s": (float(total_accepted) / business_duration_s) if business_duration_s else None,
            "payload_goodput_kbps": payload_goodput_kbps(
                total_accepted, business_duration_s
            ),
            "observed_tps_capture_s": float(total_accepted) / max(capture_duration_s, 1e-9),
        },
        "by_method": method_rows,
        "by_node": node_rows,
    }


def decode_method(
    method: str,
    samples: np.ndarray,
    est: dict,
    cfg: RealCollisionLoRaConfig,
) -> dict:
    start = float(est["start_sample"])
    cfo = float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"])))
    sto = float(est.get("sto_samples_sp", est.get("sto_samples", 0.0)))
    # Formal decoding keeps a failed physical payload as a failure.  The
    # legacy repair helper remains below only to preserve old report parsing,
    # but no current or future direct call may enter it.
    repair_enabled = False

    def repair_piecewise_bin_drift(
        source_bins: list[int],
        source_phy: PhyPayloadDecode,
        *,
        allow_block_beam: bool,
        source_alternatives: list[list[int]] | None = None,
    ) -> tuple[list[int], PhyPayloadDecode, dict | None]:
        """Repair a late ±1-bin boundary crossing without another FFT pass.

        Real B210 captures occasionally cross an FFT-bin boundary late in a
        frame (sampling-clock drift and, especially, clipping make this more
        likely).  The explicit header is decoded before trying this bounded
        list.  PHY/application CRC closure is required, so no manifest bytes
        or expected sequence number participate in the repair.
        """

        expected_header = (1, 4, 3, 1, 7)
        if source_phy.phy_crc_ok or tuple(source_phy.header_nibbles) != expected_header:
            return source_bins, source_phy, None

        first_data_symbol = int(cfg.explicit_header_symbol_count)
        last_symbol = min(len(source_bins), int(cfg.payload_symbol_count))

        def shifted(*, suffix: int, suffix_delta: int) -> list[int]:
            out = list(source_bins)
            for q in range(suffix, last_symbol):
                out[q] = (int(out[q]) + int(suffix_delta)) % cfg.m
            return out

        # Most drift events are one boundary crossing.  This costs only PHY
        # deinterleave/FEC/CRC attempts; spectra are not recomputed.
        if method == "sp":
            for suffix in range(first_data_symbol, last_symbol):
                for delta in (-1, 1):
                    trial_bins = shifted(suffix=suffix, suffix_delta=delta)
                    trial_phy = decode_payload_from_symbol_bins(trial_bins, cfg)
                    if trial_phy.phy_crc_ok:
                        return trial_bins, trial_phy, {
                            "kind": "suffix",
                            "suffix_start_symbol": int(suffix),
                            "suffix_delta_bins": int(delta),
                        }

        def application_crc_ok(phy: PhyPayloadDecode) -> bool:
            try:
                decode_data_payload(phy.payload)
            except Exception:
                return False
            return True

        # In a real collision the wrong decision is often the other user's
        # peak, not an adjacent FFT bin.  SP already computed the spectrum, so
        # retain its second/third peaks and try one evidence-backed symbol
        # substitution.  This is bounded to at most 2 * payload symbols and
        # performs no additional FFTs or manifest-assisted decoding.
        if method == "sp" and source_alternatives:
            for q in range(first_data_symbol, min(last_symbol, len(source_alternatives))):
                for alternative in source_alternatives[q][1:3]:
                    if int(alternative) == int(source_bins[q]):
                        continue
                    trial_bins = list(source_bins)
                    trial_bins[q] = int(alternative) % cfg.m
                    trial_phy = decode_payload_from_symbol_bins(trial_bins, cfg)
                    if trial_phy.phy_crc_ok or application_crc_ok(trial_phy):
                        return trial_bins, trial_phy, {
                            "kind": "single_symbol_ranked_peak",
                            "symbol_index": int(q),
                            "old_bin": int(source_bins[q]),
                            "new_bin": int(alternative),
                            "closed_by": (
                                "phy_crc" if trial_phy.phy_crc_ok else "application_crc"
                            ),
                        }

        # Several symbols can be captured by different colliders.  Walk the
        # measured top-3 alternatives with a small FEC-guided beam.  This is
        # linear in payload length, adds no FFTs, and is entered only for a
        # correctly synchronized/FEC-correctable candidate.
        if (
            allow_block_beam
            and method == "sp"
            and source_alternatives
            and float(est.get("sync_confidence", 0.0)) >= 1000.0
            and int(source_phy.uncorrected_codewords) == 0
            and int(source_phy.corrected_codewords) > 0
        ):
            ranked_beam_width = 4
            ranked_states: list[
                tuple[tuple[int, ...], PhyPayloadDecode, list[dict]]
            ] = [(tuple(int(v) for v in source_bins), source_phy, [])]
            ranked_trial_count = 0
            for q in range(first_data_symbol, min(last_symbol, len(source_alternatives))):
                expanded_ranked: dict[
                    tuple[bytes, bool, int, int],
                    tuple[tuple[int, ...], PhyPayloadDecode, list[dict]],
                ] = {}
                for state_bins, _, history in ranked_states:
                    options = [
                        int(state_bins[q]),
                        *[int(v) for v in source_alternatives[q][1:3]],
                    ]
                    for alternative in dict.fromkeys(options):
                        trial = list(state_bins)
                        trial[q] = int(alternative) % cfg.m
                        trial_phy = decode_payload_from_symbol_bins(trial, cfg)
                        ranked_trial_count += 1
                        trial_history = history + (
                            []
                            if int(alternative) == int(state_bins[q])
                            else [
                                {
                                    "symbol_index": int(q),
                                    "old_bin": int(state_bins[q]),
                                    "new_bin": int(alternative),
                                }
                            ]
                        )
                        state = (tuple(trial), trial_phy, trial_history)
                        key = (
                            trial_phy.payload,
                            bool(trial_phy.phy_crc_ok),
                            int(trial_phy.corrected_codewords),
                            int(trial_phy.uncorrected_codewords),
                        )
                        expanded_ranked.setdefault(key, state)
                        if trial_phy.phy_crc_ok or application_crc_ok(trial_phy):
                            return trial, trial_phy, {
                                "kind": "ranked_peak_beam",
                                "beam_width": int(ranked_beam_width),
                                "trial_count": int(ranked_trial_count),
                                "changes": trial_history,
                                "closed_by": (
                                    "phy_crc" if trial_phy.phy_crc_ok else "application_crc"
                                ),
                            }
                ranked_states = sorted(
                    expanded_ranked.values(),
                    key=lambda row: (
                        int(row[1].uncorrected_codewords),
                        int(row[1].corrected_codewords),
                    ),
                )[:ranked_beam_width]

        # Fractional CFO close to an FFT-bin boundary plus a small sampling
        # clock drift can make only some symbols in each CR4/5 interleaver
        # block toggle by one bin.  Search the physical five-symbol blocks
        # independently with a two-state beam.  Random aliases and truncated
        # frames are excluded by the strong-SFD and FEC-correctable guards.
        if (
            allow_block_beam
            and method == "sp"
            and float(est.get("sfd_confidence", 0.0)) >= 20.0
            and int(source_phy.uncorrected_codewords) == 0
            and int(source_phy.corrected_codewords) > 0
        ):
            beam_width = 2
            states: list[tuple[tuple[int, ...], PhyPayloadDecode, list[dict]]] = [
                (tuple(int(v) for v in source_bins), source_phy, [])
            ]
            block_width = int(cfg.cr + 4)
            trial_count = 0
            for block_begin in range(first_data_symbol, last_symbol, block_width):
                block_end = min(last_symbol, block_begin + block_width)
                symbol_count = block_end - block_begin
                expanded: dict[
                    tuple[bytes, bool, int, int],
                    tuple[tuple[int, ...], PhyPayloadDecode, list[dict]],
                ] = {}
                for state_bins, _, history in states:
                    options = [(0, 0)] + [
                        (delta, mask)
                        for delta in (-1, 1)
                        for mask in range(1, 1 << symbol_count)
                    ]
                    for delta, mask in options:
                        trial = list(state_bins)
                        if mask:
                            for local_symbol in range(symbol_count):
                                if (mask >> local_symbol) & 1:
                                    q = block_begin + local_symbol
                                    trial[q] = (int(trial[q]) + int(delta)) % cfg.m
                        trial_phy = decode_payload_from_symbol_bins(trial, cfg)
                        trial_count += 1
                        trial_history = history + (
                            []
                            if not mask
                            else [
                                {
                                    "block_start_symbol": int(block_begin),
                                    "delta_bins": int(delta),
                                    "symbol_mask": int(mask),
                                }
                            ]
                        )
                        state = (tuple(trial), trial_phy, trial_history)
                        key = (
                            trial_phy.payload,
                            bool(trial_phy.phy_crc_ok),
                            int(trial_phy.corrected_codewords),
                            int(trial_phy.uncorrected_codewords),
                        )
                        expanded.setdefault(key, state)
                        app_closed = application_crc_ok(trial_phy)
                        if trial_phy.phy_crc_ok or app_closed:
                            return trial, trial_phy, {
                                "kind": "block_local_boundary_beam",
                                "beam_width": int(beam_width),
                                "trial_count": int(trial_count),
                                "changes": trial_history,
                                "closed_by": "phy_crc" if trial_phy.phy_crc_ok else "application_crc",
                            }
                states = sorted(
                    expanded.values(),
                    key=lambda row: (
                        int(row[1].uncorrected_codewords),
                        int(row[1].corrected_codewords),
                    ),
                )[:beam_width]

        # Do not search an isolated-symbol x suffix Cartesian product here.
        # It was introduced for old clipped gain=40 captures and can turn one
        # false header into thousands of FEC passes.  Current captures reject
        # clipping up front; the physically relevant one-boundary model above
        # is bounded to at most 2 * payload_symbol_count cheap trials.
        return source_bins, source_phy, None

    def cfo_trials(value: float) -> list[float]:
        anchors = [
            value,
            round(2.0 * value) / 2.0,
            float(round(value)),
            value + 0.5,
            value - 0.5,
            value + 1.0,
            value - 1.0,
        ]
        out: list[float] = []
        for item in anchors:
            trial = float(item)
            if not any(abs(trial - old) < 1e-9 for old in out):
                out.append(trial)
        return out

    def branch_channel(trial_cfo: float) -> np.ndarray:
        if method == "ch0":
            return np.asarray([1.0 + 0.0j, 0.0 + 0.0j], dtype=np.complex128)
        if method == "ch1":
            return np.asarray([0.0 + 0.0j, 1.0 + 0.0j], dtype=np.complex128)
        if abs(float(trial_cfo) - float(cfo)) < 1e-9:
            return complex_pairs_to_array(decision_channel(est))
        _, channel, _ = preamble_channel_near_cfo(samples, start + sto, trial_cfo, cfg)
        return channel

    def run_trial(
        trial_cfo: float,
    ) -> tuple[
        list[int],
        list[float],
        PhyPayloadDecode,
        float,
        np.ndarray,
        dict | None,
        list[list[int]] | None,
    ]:
        h = branch_channel(trial_cfo)
        if method in ("ch0", "ch1", "mrc"):
            trial_bins, trial_margins = mrc_decode_bins(samples, start, trial_cfo, sto, h, cfg)
            trial_alternatives = None
        elif method == "sp":
            sp = sp_dechirp_decode_bins(samples, start, trial_cfo, sto, h, cfg, [], lam=lam)
            trial_bins = sp.bins
            trial_margins = sp.margins
            trial_alternatives = sp.top_bins
        else:
            raise ValueError(f"unknown method {method}")
        trial_phy = decode_payload_from_symbol_bins(trial_bins, cfg)
        drift_repair = None
        margin = float(np.mean(trial_margins)) if trial_margins else 0.0
        return trial_bins, trial_margins, trial_phy, margin, h, drift_repair, trial_alternatives

    lam = float(est.get("lambda_sp", 0.0)) if method == "sp" else 0.0
    best_bins: list[int] = []
    best_margins: list[float] = []
    best_phy: PhyPayloadDecode | None = None
    best_cfo = cfo
    best_drift_repair: dict | None = None
    best_alternatives: list[list[int]] | None = None
    best_key: tuple[int, int, int, float] | None = None
    trial_results: list[
        tuple[
            tuple[int, int, int, float],
            list[int],
            list[float],
            PhyPayloadDecode,
            float,
            list[list[int]] | None,
        ]
    ] = []
    trial_cfo_values = [cfo] if bool(est.get("_sp_disable_cfo_trials", False)) else cfo_trials(cfo)
    for trial_index, trial_cfo in enumerate(trial_cfo_values):
        trial_bins, trial_margins, trial_phy, margin, _, drift_repair, trial_alternatives = run_trial(trial_cfo)
        key = (
            int(trial_phy.phy_crc_ok),
            -int(trial_phy.uncorrected_codewords),
            -int(trial_phy.corrected_codewords),
            margin,
        )
        trial_results.append(
            (key, trial_bins, trial_margins, trial_phy, float(trial_cfo), trial_alternatives)
        )
        if best_key is None or key > best_key:
            best_key = key
            best_bins = trial_bins
            best_margins = trial_margins
            best_phy = trial_phy
            best_cfo = float(trial_cfo)
            best_drift_repair = drift_repair
            best_alternatives = trial_alternatives
        if trial_phy.phy_crc_ok:
            break
        # A random/alias candidate almost never has this exact explicit
        # header.  Avoid four more full payload FFT passes for such candidates.
        if (
            trial_index == 0
            and tuple(trial_phy.header_nibbles) != (1, 4, 3, 1, 7)
            and float(est.get("sync_confidence", 0.0)) < 1000.0
        ):
            break
    # A refinement hypothesis is allowed to replace the frontend result only
    # when it closes the PHY CRC.  Falling back to the best FEC/margin score
    # without CRC evidence can damage an otherwise correct packet (and makes
    # the supposedly CRC-triggered search a heuristic selector).  We still
    # execute and time the bounded trials above; absent closure, retain the
    # first/frontend CFO hypothesis exactly.
    if trial_results and not any(row[3].phy_crc_ok for row in trial_results):
        (
            _,
            best_bins,
            best_margins,
            best_phy,
            best_cfo,
            best_alternatives,
        ) = trial_results[0]
        best_drift_repair = None
    # First try the cheap one-boundary suffix model on every viable CFO.  Only
    # if none closes CRC do we run the block-local beam once on the best FEC
    # hypothesis.  This keeps both fallback classes without multiplying their
    # costs by the CFO grid size.
    if (
        best_phy is not None
        and not best_phy.phy_crc_ok
        and not bool(est.get("_sp_disable_repair", False))
        and repair_enabled
    ):
        for _, trial_bins, trial_margins, trial_phy, trial_cfo, trial_alternatives in sorted(
            trial_results, key=lambda row: row[0], reverse=True
        ):
            repaired_bins, repaired_phy, drift_repair = repair_piecewise_bin_drift(
                trial_bins,
                trial_phy,
                allow_block_beam=False,
                source_alternatives=trial_alternatives,
            )
            if drift_repair is None:
                continue
            best_bins = repaired_bins
            best_margins = trial_margins
            best_phy = repaired_phy
            best_cfo = trial_cfo
            best_drift_repair = drift_repair
            best_alternatives = trial_alternatives
            break
        if best_drift_repair is None:
            repaired_bins, repaired_phy, drift_repair = repair_piecewise_bin_drift(
                best_bins,
                best_phy,
                allow_block_beam=True,
                source_alternatives=best_alternatives,
            )
            if drift_repair is not None:
                best_bins = repaired_bins
                best_phy = repaired_phy
                best_drift_repair = drift_repair
    bins = best_bins
    margins = best_margins
    phy = best_phy if best_phy is not None else decode_payload_from_symbol_bins([], cfg)

    result = {
        "method": method,
        "used_cfo_bins": float(best_cfo),
        "symbol_bins": [int(x) for x in bins],
        "mean_symbol_margin": float(np.mean(margins)) if margins else 0.0,
        "lambda_sp": lam,
        "bin_drift_repair": best_drift_repair,
        "phy": {
            "payload_hex": phy.payload.hex(),
            "phy_crc_ok": bool(phy.phy_crc_ok),
            "corrected_codewords": int(phy.corrected_codewords),
            "uncorrected_codewords": int(phy.uncorrected_codewords),
            "header_nibbles": [int(x) for x in phy.header_nibbles],
            "status": phy.status,
        },
    }
    return result


def timed_decode_method(
    method: str,
    samples: np.ndarray,
    est: dict,
    cfg: RealCollisionLoRaConfig,
) -> dict:
    """Time one payload decoder call, excluding the shared front end."""
    started_ns = time.perf_counter_ns()
    result = decode_method(method, samples, est, cfg)
    result["decode_elapsed_ms"] = (time.perf_counter_ns() - started_ns) / 1_000_000.0
    result["decode_timing_scope"] = "payload_decoder_only_common_frontend_excluded"
    return result


SP_SYNC_RETRY_POLICIES = ("strict_header", "relaxed_structure")
SP_HEADER_NIBBLES = (1, 4, 3, 1, 7)


def sp_sync_retry_gate(
    est: dict,
    result: dict,
    *,
    retry_policy: str,
    max_sync_trials: int,
    relaxed_max_trials: int,
) -> tuple[bool, str | None, int, str | None]:
    """Choose an IQ-only SP synchronization-retry budget.

    ``strict_header`` retains the historical certified-frame-head gate.  The
    optional ``relaxed_structure`` policy additionally retries candidates with
    a plausible preamble/SFD anchor, but limits them to a short local search.
    Neither policy consults manifest timing, sender identity, sequence, or a
    CRC result when deciding whether to open the search.
    """

    if retry_policy not in SP_SYNC_RETRY_POLICIES:
        raise ValueError(f"unknown SP synchronization retry policy: {retry_policy!r}")
    try:
        header = tuple(
            int(value) for value in result.get("phy", {}).get("header_nibbles", [])
        )
    except (TypeError, ValueError):
        header = ()
    preamble_ratio = float(est.get("preamble_ratio", 10.0))
    sync_confidence = float(est.get("sync_confidence", 0.0))
    sfd_confidence = float(est.get("sfd_confidence", 0.0))
    strict_structure = bool(est.get("structure_certified", False)) or (
        sync_confidence >= 10.0
        and sfd_confidence >= 10.0
        and preamble_ratio >= 10.0
    )
    if strict_structure and header == SP_HEADER_NIBBLES:
        return True, "strict_header", max(1, int(max_sync_trials)), None

    relaxed_structure = (
        preamble_ratio >= 10.0
        and sync_confidence >= 3.0
        and sfd_confidence >= 3.0
    )
    if retry_policy == "relaxed_structure" and relaxed_structure:
        return (
            True,
            "relaxed_structure",
            min(max(1, int(max_sync_trials)), max(1, int(relaxed_max_trials))),
            None,
        )
    if retry_policy == "strict_header":
        return False, None, 1, "missing_explicit_header_or_structure_certificate"
    return False, None, 1, "missing_relaxed_preamble_sfd_support"


def decode_sp_stages(
    samples: np.ndarray,
    est: dict,
    cfg: RealCollisionLoRaConfig,
    *,
    max_sync_trials: int = 32,
    sync_retry_policy: str = "strict_header",
    relaxed_sync_max_trials: int = 8,
    shared_cache: SharedPhysicalDecodeCache | None = None,
    physical_key: tuple | None = None,
) -> list[dict]:
    """Run auditable cumulative SP decoder stages.

    ``sp_core`` uses one frontend synchronization result, one risk-constrained
    package lambda, signed top-1, and ordinary PHY FEC/CRC.  ``sp_sync_refine``
    adds a bounded coupled start/CFO search only after core failure.
    There is deliberately no post-failure symbol/FEC repair.  The formal
    ``sp`` row aliases ``sp_sync_refine``: it uses the one packet-level lambda
    selected before payload decoding and never lets CRC select another lambda.
    """

    stages_started_ns = time.perf_counter_ns()
    if shared_cache is not None and physical_key is None:
        raise ValueError("shared SP cache requires an anonymous physical evidence key")
    cache_hits_before = int(shared_cache.sp_payload_hits) if shared_cache else 0
    cache_misses_before = int(shared_cache.sp_payload_misses) if shared_cache else 0

    def decode_sp_payload(trial_est: dict) -> dict:
        if shared_cache is None:
            return decode_method("sp", samples, trial_est, cfg)
        return shared_cache.decode_sp(
            samples,
            trial_est,
            cfg,
            physical_key=physical_key,
        )

    def renamed(result: dict, method: str, **extra: object) -> dict:
        row = dict(result)
        row["method"] = method
        row.update(extra)
        return row

    def result_key(result: dict) -> tuple[int, int, int, int, float]:
        phy = result.get("phy", {})
        header_ok = tuple(phy.get("header_nibbles", [])) == (1, 4, 3, 1, 7)
        return (
            int(bool(phy.get("phy_crc_ok", False))),
            int(header_ok),
            -int(phy.get("uncorrected_codewords", 0)),
            -int(phy.get("corrected_codewords", 0)),
            float(result.get("mean_symbol_margin", 0.0)),
        )

    def crc_closed(result: dict) -> bool:
        phy = result.get("phy", {})
        if bool(phy.get("phy_crc_ok", False)):
            return True
        try:
            decode_data_payload(bytes.fromhex(str(phy.get("payload_hex", ""))))
        except Exception:
            return False
        return True

    core_est = dict(est)
    core_est["_sp_disable_cfo_trials"] = True
    core_est["_sp_disable_repair"] = True
    core_raw = decode_sp_payload(core_est)
    core = renamed(
        core_raw,
        "sp_core",
        decoder_stage="core",
        synchronization_trials=1,
        risk_lambda_fixed=True,
        decode_elapsed_ms=(time.perf_counter_ns() - stages_started_ns) / 1_000_000.0,
        decode_timing_scope="payload_decoder_only_common_frontend_excluded_cumulative_stage",
    )

    best_sync_raw = core_raw
    best_sync_est = core_est
    sync_trial_count = 1
    sync_closed = crc_closed(core_raw)
    if sync_closed:
        sync_retry_gate_passed = False
        sync_retry_gate_policy = "not_needed_crc_closed"
        sync_retry_trial_budget = 1
        sync_retry_skip_reason = None
    else:
        (
            sync_retry_gate_passed,
            sync_retry_gate_policy,
            sync_retry_trial_budget,
            sync_retry_skip_reason,
        ) = sp_sync_retry_gate(
            est,
            core_raw,
            retry_policy=sync_retry_policy,
            max_sync_trials=max_sync_trials,
            relaxed_max_trials=relaxed_sync_max_trials,
        )
    if not sync_closed and sync_retry_gate_passed:
        base_start = float(est["start_sample"]) + float(
            est.get("sto_samples_sp", est.get("sto_samples", 0.0))
        )
        base_cfo = float(
            est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))
        )
        # Real captures showed a small systematic late-window bias.  Search
        # likely corrections first so a CRC-closing packet normally costs only
        # a few additional FFT passes; the full set remains bounded.
        start_deltas = (-2.0, -1.0, -3.0, -0.5, -1.5, -2.5, -3.5, 0.5, 1.0, 2.0, 3.0, 4.0, -4.0, 0.0)
        cfo_values: list[float] = []
        for value in (
            base_cfo,
            base_cfo - 0.1,
            base_cfo + 0.1,
            base_cfo - 0.2,
            base_cfo + 0.2,
            base_cfo - 0.3,
            base_cfo + 0.3,
            round(2.0 * base_cfo) / 2.0,
            float(round(base_cfo)),
            base_cfo - 0.5,
            base_cfo + 0.5,
            base_cfo - 1.0,
            base_cfo + 1.0,
        ):
            value = float(value)
            if not any(abs(value - old) < 1e-9 for old in cfo_values):
                cfo_values.append(value)

        for start_delta in start_deltas:
            if sync_closed or sync_trial_count >= sync_retry_trial_budget:
                break
            trial_start = base_start + float(start_delta)
            for trial_cfo in cfo_values:
                if sync_trial_count >= sync_retry_trial_budget:
                    break
                if abs(start_delta) < 1e-12 and abs(trial_cfo - base_cfo) < 1e-12:
                    continue
                _, trial_channel, _ = preamble_channel_near_cfo(
                    samples, trial_start, trial_cfo, cfg
                )
                trial_est = dict(est)
                trial_est["start_sample"] = float(trial_start)
                trial_est["sto_samples"] = 0.0
                trial_est["sto_samples_sp"] = 0.0
                trial_est["continuous_cfo_bins"] = float(trial_cfo)
                trial_est["cfo_bins_sp"] = float(trial_cfo)
                trial_est["channel_sp"] = [
                    [float(np.real(value)), float(np.imag(value))]
                    for value in trial_channel
                ]
                trial_est["_sp_disable_cfo_trials"] = True
                trial_est["_sp_disable_repair"] = True
                trial_raw = decode_sp_payload(trial_est)
                sync_trial_count += 1
                # Sync refinement is CRC-triggered and CRC-accepted.  FEC
                # statistics rank diagnostics only; they are not sufficient
                # evidence for changing a packet-level synchronization result.
                if crc_closed(trial_raw):
                    best_sync_raw = trial_raw
                    best_sync_est = trial_est
                    sync_closed = True
                    break

    used_start = float(best_sync_est["start_sample"]) + float(
        best_sync_est.get("sto_samples_sp", best_sync_est.get("sto_samples", 0.0))
    )
    original_start = float(est["start_sample"]) + float(
        est.get("sto_samples_sp", est.get("sto_samples", 0.0))
    )
    original_cfo = float(
        est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))
    )
    sync_refine = renamed(
        best_sync_raw,
        "sp_sync_refine",
        decoder_stage="sync_refine",
        synchronization_trials=int(sync_trial_count),
        sync_refine_applied=bool(sync_trial_count > 1),
        sync_refine_crc_closed=bool(sync_closed),
        sync_refine_start_delta_samples=float(used_start - original_start),
        sync_refine_cfo_delta_bins=float(
            float(best_sync_raw.get("used_cfo_bins", original_cfo)) - original_cfo
        ),
        risk_lambda_fixed=True,
        repair_result=None,
        sync_retry_gate_passed=bool(sync_retry_gate_passed),
        sync_retry_gate_policy=sync_retry_gate_policy,
        sync_retry_trial_budget=int(sync_retry_trial_budget),
        sync_retry_skip_reason=sync_retry_skip_reason,
        decode_elapsed_ms=(time.perf_counter_ns() - stages_started_ns) / 1_000_000.0,
        decode_timing_scope="payload_decoder_only_common_frontend_excluded_cumulative_stage",
    )
    compatibility = renamed(
        best_sync_raw,
        "sp",
        decoder_stage="formal_alias_of_sp_sync_refine",
        inherited_sync_trials=int(sync_trial_count),
        repair_result=None,
        lambda_candidate_retry=None,
        risk_lambda_fixed=True,
        decode_elapsed_ms=sync_refine["decode_elapsed_ms"],
        decode_timing_scope=sync_refine["decode_timing_scope"],
    )
    # The final SP payload result is one of the core/sync trials above.  Reuse
    # that exact evidence-bound cache entry instead of running a duplicate FFT
    # pass merely for timing bookkeeping.
    post_sp_started_ns = time.perf_counter_ns()
    if shared_cache is not None:
        decode_sp_payload(best_sync_est)
    sync_refine["parameter_estimation_elapsed_ms"] = 0.0
    sync_refine["post_sp_total_elapsed_ms"] = (
        time.perf_counter_ns() - post_sp_started_ns
    ) / 1_000_000.0
    sync_refine["post_sp_total_elapsed_ms"] += float(
        est.get("lambda_config_elapsed_ms", 0.0)
    )
    sync_refine["post_sp_timing_scope"] = (
        "lambda_reliability_config_plus_cached_payload_result_at_fixed_shared_sp_fine_sync"
    )
    sync_refine["shared_sync_cache"] = {
        "physical_evidence_bound": True,
        "payload_trial_cache_hits": (
            int(shared_cache.sp_payload_hits) - cache_hits_before
            if shared_cache is not None
            else None
        ),
        "payload_trial_cache_misses": (
            int(shared_cache.sp_payload_misses) - cache_misses_before
            if shared_cache is not None
            else None
        ),
    }
    return [core, sync_refine, compatibility]


def configure_sp_lambda_batch(
    samples: np.ndarray,
    seed_estimates: list[dict],
    cfg: RealCollisionLoRaConfig,
    *,
    noise_sigma2: float,
    gamma: float,
    max_lambda: float | None,
    noise_competition: bool = False,
    noise_two_packet_only: bool = False,
    reference_guard: bool = False,
    physical_samples: np.ndarray | None = None,
    whitener: np.ndarray | None = None,
) -> tuple[list[dict], dict]:
    """Configure every target against all payload-overlapping DB targets.

    SP-Decode v2 defines the competitor set from packet intervals, not from a
    per-target detector invocation.  Keeping this operation batch-scoped is
    essential: passing one estimate at a time silently makes every target an
    isolated MRC case and forces lambda to zero.
    """

    started_ns = time.perf_counter_ns()
    estimates = attach_sp_reliability_and_lambda(
        samples,
        seed_estimates,
        cfg,
        noise_sigma2=noise_sigma2,
        gamma=gamma,
        max_lambda=max_lambda,
        noise_competition=noise_competition,
        noise_two_packet_only=noise_two_packet_only,
        reference_guard=reference_guard,
        physical_samples=physical_samples,
        whitener=whitener,
    )
    if len(estimates) != len(seed_estimates):
        raise RuntimeError("lambda configuration changed the fine-sync target count")

    frame_samples = float(
        (cfg.payload_start_symbols + cfg.payload_symbol_count) * cfg.samples_per_symbol
    )
    payload_offset_samples = float(cfg.payload_start_symbols * cfg.samples_per_symbol)
    starts = [
        float(row["start_sample"]) + float(row.get("sto_samples_sp", row.get("sto_samples", 0.0)))
        for row in estimates
    ]
    expected_overlap_counts: list[int] = []
    for target_index, target_start in enumerate(starts):
        target_payload_start = target_start + payload_offset_samples
        target_end = target_start + frame_samples
        expected_overlap_counts.append(
            sum(
                other_index != target_index
                and other_start < target_end
                and other_start + frame_samples > target_payload_start
                for other_index, other_start in enumerate(starts)
            )
        )

    selection_reasons: dict[str, int] = {}
    for target_index, row in enumerate(estimates):
        expected_count = expected_overlap_counts[target_index]
        observed_count = int(row.get("overlapping_interferer_count_sp", -1))
        if observed_count != expected_count:
            raise RuntimeError(
                "lambda overlap audit failed for fine-sync target "
                f"{target_index}: expected {expected_count}, observed {observed_count}"
            )
        if expected_count == 0 and abs(float(row.get("lambda_sp", 0.0))) > 1e-12:
            raise RuntimeError("isolated fine-sync target received a nonzero lambda")
        for pair_row in row.get("lambda_pair_rows_sp", []):
            interferer_index = int(pair_row["interferer_index"])
            pair_row["interferer_candidate_id"] = interferer_index
        reason = str(row.get("lambda_selection_reason_sp", "unknown"))
        selection_reasons[reason] = selection_reasons.get(reason, 0) + 1

    return estimates, {
        "policy": "sp_decode_v2_payload_interval_batch_configuration",
        "target_count": int(len(estimates)),
        "payload_overlap_edge_count": int(sum(expected_overlap_counts) // 2),
        "targets_with_payload_competitor": int(
            sum(count > 0 for count in expected_overlap_counts)
        ),
        "targets_with_positive_lambda": int(
            sum(float(row.get("lambda_sp", 0.0)) > 0.0 for row in estimates)
        ),
        "selection_reasons": selection_reasons,
        "batch_elapsed_ms": (time.perf_counter_ns() - started_ns) / 1_000_000.0,
    }


def candidate_to_json(est: dict, candidate_id: int) -> dict:
    keep = {
        "packet_index",
        "start_sample",
        "cfo_bins",
        "continuous_cfo_bins",
        "sto_samples",
        "confidence",
        "sfd_confidence",
        "sync_confidence",
        "peak_bin",
        "power",
        "L_u",
        "U_max_sp",
        "lambda_sp",
        "lambda_cap_sp",
        "lambda_threshold_sp",
        "lambda_objective_sp",
        "lambda_candidate_points_sp",
        "lambda_pair_rows_sp",
        "lambda_selection_reason_sp",
        "lambda_policy_sp",
        "lambda_gate_policy_sp",
        "lambda_gate_reason_sp",
        "lambda_noise_bin_count_sp",
        "lambda_noise_false_alarm_sp",
        "lambda_pair_objective_sp",
        "lambda_noise_objective_sp",
        "lambda_noise_max_threshold_sp",
        "lambda_reliability_elapsed_ms",
        "lambda_selection_elapsed_ms",
        "lambda_config_elapsed_ms",
        "certified_sp",
        "channel_sp",
        "mrc_decision_channel_sp",
        "sp_mrc_fallback",
        "reference_channel_source_sp",
        "lambda_guard_policy_sp",
        "lambda_guard_reason_sp",
        "lambda_guard_strength_margin_sp",
        "lambda_guard_proposed_lambda_sp",
        "lambda_guard_proposed_objective_sp",
        "lambda_reference_guard_elapsed_ms",
        "overlapping_interferer_count_sp",
        "theta_total",
        "robust_hit_count",
        "pcube_track_hits",
        "pcube_structure_score",
        "pcube_used_refined",
        "pcube_fast_refine_enabled",
        "pcube_coherent_metric",
        "frontend_candidate_stage",
        "detector_scan_phase_samples",
        "pre_joint_start_sample",
        "pre_joint_cfo_bins",
        "joint_start_delta_samples",
        "joint_cfo_delta_bins",
        "joint_refine_accepted",
    }
    out = {"candidate_id": int(candidate_id)}
    for key in keep:
        if key in est:
            value = est[key]
            if isinstance(value, (np.floating, np.integer)):
                value = value.item()
            out[key] = value
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iq", type=Path, required=True, help="Input .sc16 capture")
    parser.add_argument("--metadata", type=Path, default=None, help="Optional .sc16.json metadata")
    parser.add_argument("--manifest", type=Path, default=None, help="Control manifest for offline validation only")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON report")
    parser.add_argument("--run-id", type=lambda x: int(x, 0), default=None)
    parser.add_argument(
        "--sf",
        type=int,
        choices=(8, 10, 12),
        default=None,
        help="Data PHY SF; defaults to manifest radio.spreading_factor",
    )
    parser.add_argument(
        "--bandwidth-hz",
        type=float,
        choices=(125_000.0, 250_000.0, 500_000.0),
        default=None,
        help="Data PHY bandwidth; defaults to manifest radio.bandwidth_hz",
    )
    parser.add_argument("--active-node", type=int, action="append", default=[1])
    parser.add_argument(
        "--expected-tx-count",
        type=int,
        default=None,
        help="Manual expected TX packet count for a single active node when no manifest is available.",
    )
    parser.add_argument(
        "--expected-node-tx-count",
        action="append",
        default=[],
        help="Manual expected count per node, format NODE:COUNT; may be repeated.",
    )
    parser.add_argument(
        "--business-duration-s",
        type=float,
        default=None,
        help="Manual business duration for TPS when no manifest is available.",
    )
    parser.add_argument(
        "--planned-business-window-start-ms",
        type=float,
        default=None,
        help=(
            "Business-relative start of the decoded analysis slice. Used only "
            "after decoding to select the manifest PRR denominator."
        ),
    )
    parser.add_argument(
        "--planned-business-window-duration-ms",
        type=float,
        default=None,
        help=(
            "Duration of the business-relative analysis slice. Used only after "
            "decoding to select the manifest PRR denominator."
        ),
    )
    parser.add_argument("--noise-seconds", type=float, default=3.0)
    parser.add_argument(
        "--max-capture-seconds",
        type=float,
        default=None,
        help=(
            "Analyze only this many seconds from the beginning of the IQ file. "
            "Used by the one-time low-memory link gate; normal paper decoding uses the full capture."
        ),
    )
    parser.add_argument(
        "--capture-start-seconds",
        type=float,
        default=0.0,
        help="Start offset used for bounded-memory diagnostic decoding.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Raw preamble threshold; default 3.0 for schedule-free multi-user discovery.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        help="Sliding detector step in samples; default 0 uses one LoRa symbol at the capture sample rate.",
    )
    parser.add_argument(
        "--detector-scan-phases",
        type=int,
        default=0,
        help=(
            "Interleaved phases of the coarse preamble scan. 0 selects 8 "
            "schedule-free multi-user phases; each accepted coarse "
            "candidate is still refined to fractional-sample start/CFO/STO."
        ),
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=800,
        help=(
            "Global candidate limit after preamble/SFD merge; the standalone "
            "formal default is 800 and campaign automation scales it to three "
            "times the manifest's expected packet count."
        ),
    )
    parser.add_argument("--min-sync-score", type=float, default=0.0)
    parser.add_argument("--min-coherent-metric", type=float, default=0.0)
    parser.add_argument(
        "--min-sfd-score",
        type=float,
        default=1.0,
        help=(
            "Minimum refined SFD score. The high-recall experiment default is 1; "
            "use 10 for the strict-candidate ablation."
        ),
    )
    parser.add_argument(
        "--min-refined-sync-score",
        type=float,
        default=50.0,
        help=(
            "Minimum sync-word score after start/CFO refinement. The high-recall "
            "experiment default is 50; use 500 for the strict-candidate ablation."
        ),
    )
    parser.add_argument(
        "--local-projection-tracks",
        action="store_true",
        help="Add original SP Ch0/Ch1/local-eigenvector preamble tracks for weak concurrent users.",
    )
    parser.add_argument(
        "--spatial-residual-tracks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use the PCA minor-direction weak-preamble stream; default on for multi-node runs.",
    )
    parser.add_argument("--cfo-min", type=float, default=-32.0)
    parser.add_argument("--cfo-max", type=float, default=32.0)
    parser.add_argument("--sp-gamma", type=float, default=0.05)
    parser.add_argument("--sp-lambda-max", type=float, default=None,
                        help="Optional global cap; legacy defaults to 4, experimental noise policy uses reliability cap")
    parser.add_argument("--sp-lambda-policy", choices=("pair_only_legacy", SP_LAMBDA_POLICY, TWO_PACKET_POLICY, GUARDED_PAIR_POLICY),
                        default=GUARDED_PAIR_POLICY, help="Single-path SP with preamble reference/strength guards; historical policies remain available")
    parser.add_argument(
        "--sp-sync-max-trials",
        type=int,
        default=32,
        help="Maximum cumulative SP core+start/CFO synchronization trials per candidate.",
    )
    parser.add_argument(
        "--sp-sync-retry-policy",
        choices=SP_SYNC_RETRY_POLICIES,
        default="strict_header",
        help=(
            "strict_header retries only a certified frame head with the expected "
            "explicit header; relaxed_structure additionally retries plausible "
            "preamble/SFD anchors using --sp-sync-relaxed-max-trials."
        ),
    )
    parser.add_argument(
        "--sp-sync-relaxed-max-trials",
        type=int,
        default=8,
        help=(
            "Maximum cumulative core+start/CFO trials for a relaxed-structure "
            "SP candidate; strict-header candidates retain --sp-sync-max-trials."
        ),
    )
    parser.add_argument(
        "--skip-comparison-decoders",
        action="store_true",
        help=(
            "Skip the native LoRaWAN/MRC/CIC/PCube/MaLoRaGW comparison receivers "
            "for a detector-only diagnostic run; normal experiment reports include them."
        ),
    )
    parser.add_argument(
        "--comparison-frontend-scope",
        choices=("native", "common"),
        default="common",
        help=(
            "common (formal default) gives every comparison decoder the same SP-refined "
            "packet start/CFO/STO; native is the independent end-to-end-front-end ablation"
        ),
    )
    parser.add_argument(
        "--comparison-paper-local-refinement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "In common comparison mode, let PCube and MaLoRaGW make one bounded "
            "paper-native preamble/SFD start-CFO refinement from each shared fine-sync "
            "seed. This never uses payload, FEC/CRC, manifest, SP lambda, or SP residuals."
        ),
    )
    parser.add_argument("--disable-energy-prefilter", action="store_true")
    parser.add_argument(
        "--energy-top-windows",
        type=int,
        default=0,
        help="Maximum energy events to scan; 0 keeps all events above --energy-min-ratio.",
    )
    parser.add_argument(
        "--energy-window-seconds",
        type=float,
        default=0.8,
        help="Context kept around each energy event for stable preamble/SFD refinement.",
    )
    parser.add_argument("--energy-min-ratio", type=float, default=3.0)
    parser.add_argument(
        "--frontend-candidates-per-window",
        type=int,
        default=64,
        help=(
            "Base preamble-refinement budget per search window; formal campaign "
            "automation uses max(64, 4 times the active-node count)."
        ),
    )
    parser.add_argument(
        "--continuous-sfd-supplement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Add the shared sample-continuous SFD-pair proposal path after the "
            "multi-phase preamble search (enabled by default for formal runs)."
        ),
    )
    parser.add_argument(
        "--sp-preamble-top-k",
        type=int,
        default=10,
        help="FFT peaks retained per preamble chirp by the SP high-recall proposal stage.",
    )
    parser.add_argument(
        "--sp-preamble-min-hits",
        type=int,
        default=4,
        help="Minimum repeated preamble-chirp hits for an SP raw track.",
    )
    parser.add_argument(
        "--sp-preamble-max-tracks",
        type=int,
        default=4,
        help="Maximum SP raw preamble tracks retained at each coarse start.",
    )
    parser.add_argument(
        "--fast-grid-refine",
        action="store_true",
        help="Enable the slower local start/CFO grid fallback; off by default for single-node runs.",
    )
    parser.add_argument(
        "--disable-detector-phase-retry",
        action="store_true",
        help="Disable the half-symbol detector phase retry used only when a window has no strong SFD candidate.",
    )
    parser.add_argument(
        "--full-refine",
        action="store_true",
        help="Use the slower full start/CFO/STO grid refinement instead of the default SFD-anchored real-capture path.",
    )
    parser.add_argument(
        "--fast-blind",
        action="store_true",
        help=(
            "Blind-frontend speed mode: 2-symbol coarse step with the same "
            "8-phase grid, 6 preamble chirps per seed, energy-burst windows "
            "using a pre-traffic noise floor, and no continuous-SFD "
            "supplement.  Trades a small amount of high-order-collision "
            "recall for a large reduction in scan seeds."
        ),
    )
    parser.add_argument(
        "--frontend-scan-chirps",
        type=int,
        default=None,
        help="Preamble chirps used by the coarse multi-track scan (default: full preamble).",
    )
    parser.add_argument(
        "--force-energy-prefilter",
        action="store_true",
        help="Enable the rising-edge energy prefilter on short slices too.",
    )
    parser.add_argument(
        "--noise-floor-seconds",
        type=float,
        default=0.0,
        help=(
            "Seconds read from the very beginning of the full IQ file to "
            "estimate a true noise floor for the energy prefilter."
        ),
    )
    parser.add_argument(
        "--skip-continuous-sfd-supplement",
        action="store_true",
        help="Skip the shared sample-continuous SFD-pair supplement pass.",
    )
    parser.add_argument(
        "--sliding-frontend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use the SPv2 Sec. 5.2 sliding downchirp/SFD frontend (a few FFT "
            "convolutions plus peak pairing) instead of the legacy per-seed "
            "multi-track scan.  Defaults to on."
        ),
    )
    parser.add_argument(
        "--fine-sync-db",
        type=Path,
        default=None,
        help=(
            "Read shared fine-synchronization hypotheses (start/STO/CFO/"
            "channel) from a build_fine_sync_database.py output file instead "
            "of running detection.  All decoders then use these hypotheses."
        ),
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.sp_sync_max_trials < 1 or args.sp_sync_relaxed_max_trials < 1:
        raise ValueError("SP synchronization trial budgets must be positive")
    default_cfg = RealCollisionLoRaConfig()
    manifest = load_manifest(args.manifest)
    run_cfg = run_config_from_manifest(manifest, args)
    run_id = args.run_id
    if run_id is None and run_cfg is not None:
        run_id = int(run_cfg.run_id)
    accepted_run_ids: set[int] = set()
    if run_id is not None:
        accepted_run_ids.add(int(run_id))
    merged_source_run_ids = (manifest.get("config") or {}).get(
        "merged_source_run_ids"
    )
    if isinstance(merged_source_run_ids, (list, tuple, set)):
        accepted_run_ids.update(int(value) for value in merged_source_run_ids)
    identity_aliases = merged_identity_alias_map(manifest)
    active_nodes = set(int(x) for x in (manifest.get("active_nodes") or args.active_node))
    if (args.planned_business_window_start_ms is None) != (
        args.planned_business_window_duration_ms is None
    ):
        raise ValueError(
            "--planned-business-window-start-ms and "
            "--planned-business-window-duration-ms must be supplied together"
        )
    planned_window_sequences = manifest_expected_sequences_in_window(
        manifest,
        active_nodes,
        start_ms=args.planned_business_window_start_ms,
        duration_ms=args.planned_business_window_duration_ms,
    )
    detector_scan_phase_count = (
        int(args.detector_scan_phases)
        if int(args.detector_scan_phases) > 0
        else 8
    )
    use_spatial_residual_tracks = (
        True
        if args.spatial_residual_tracks is None
        else bool(args.spatial_residual_tracks)
    )
    frontend_threshold = (
        float(args.threshold)
        if args.threshold is not None
        else 3.0
    )
    manual_counts = manual_expected_counts(args, active_nodes)

    def log(message: str) -> None:
        if not args.quiet:
            print(message, flush=True)

    log(f"[1/6] loading IQ: {args.iq}")
    capture = load_capture(
        args.iq,
        args.metadata,
        start_time_s=args.capture_start_seconds,
        max_duration_s=args.max_capture_seconds,
    )
    adc_stats = adc_clipping_statistics(capture.samples)
    if any(int(v) > 0 for v in adc_stats["clipped_count"]):
        capture.warnings.append(
            "ADC clipping detected: clipped_count=" + str(adc_stats["clipped_count"])
            + "; reduce RX gain before using this capture for PRR validation"
        )
    actual_metadata = capture.metadata.get("actual", {}) if capture.metadata else {}
    requested_metadata = capture.metadata.get("requested", {}) if capture.metadata else {}
    rate = metadata_number(
        actual_metadata.get("rate_hz", requested_metadata.get("sample_rate_hz")),
        default_cfg.sample_rate_hz,
    )
    manifest_radio = manifest.get("radio", {}) if isinstance(manifest, dict) else {}
    sf = int(
        args.sf
        if args.sf is not None
        else manifest_radio.get("spreading_factor", default_cfg.sf)
    )
    bandwidth_hz = float(
        args.bandwidth_hz
        if args.bandwidth_hz is not None
        else manifest_radio.get("bandwidth_hz", default_cfg.bw_hz)
    )
    cfg = RealCollisionLoRaConfig(
        sf=sf,
        bw_hz=bandwidth_hz,
        sample_rate_hz=rate,
        ldro=(2**sf) / bandwidth_hz >= 0.016,
    )
    _ = cfg.osr
    if int(args.step) > 0:
        step_samples = int(args.step)
    elif args.fast_blind:
        step_samples = int(2 * cfg.samples_per_symbol)
    else:
        step_samples = int(cfg.samples_per_symbol)
    scan_chirps = (
        int(args.frontend_scan_chirps)
        if args.frontend_scan_chirps is not None
        else (6 if args.fast_blind else None)
    )
    log(f"[2/6] loaded {capture.samples.shape[1] / rate:.3f}s, channels={capture.samples.shape[0]}, whitening")
    noise_samples = int(round(max(args.noise_seconds, 0.0) * rate))
    white, whitener, sigma2_time, calibration = dc_remove_and_whiten(capture.samples, noise_samples=noise_samples)
    dc = np.asarray(
        [complex(float(value[0]), float(value[1])) for value in calibration["dc"]],
        dtype=np.complex64,
    )
    physical_centered = np.asarray(capture.samples - dc[:, None], dtype=np.complex64)
    noise_sigma2_fft = max(cfg.m * sigma2_time, 1e-12)

    fine_sync_entries: list[dict] = []
    fine_sync_candidate_count: int | None = None
    fine_sync_database_loaded = False
    fine_sync_database_audit: dict | None = None
    if args.fine_sync_db is not None and Path(args.fine_sync_db).exists():
        fine_sync_database = json.loads(
            Path(args.fine_sync_db).read_text(encoding="utf-8")
        )
        fine_sync_entries = fine_sync_database.get("packets", [])
        discovery = fine_sync_database.get("candidate_discovery", {})
        if fine_sync_database.get("schema") == "fine_sync_anonymous_physical_v2":
            if any(
                row.get("node_id") is not None or row.get("sequence") is not None
                for row in fine_sync_entries
            ):
                raise ValueError("anonymous fine-sync database must not contain identities")
            required_discovery = {
                "scope": "global_full_window",
                "manifest_schedule_exposed_to_detector": False,
                "node_timing_calibration": False,
                "planned_start_search_windows": False,
                "score_truncation": False,
            }
            invalid = {
                key: discovery.get(key)
                for key, expected in required_discovery.items()
                if discovery.get(key) != expected
            }
            if invalid:
                raise ValueError(
                    "fine-sync database violates global anonymous discovery "
                    f"contract: {invalid}"
                )
            if discovery.get("candidate_overflow_policy") not in {
                "fail_closed_without_truncation",
                "retain_excess_candidates_without_truncation",
            }:
                raise ValueError("fine-sync database has an unknown candidate-overflow policy")
            fine_sync_candidate_count = len(fine_sync_entries)
            fine_sync_database_loaded = True
            if planned_window_sequences is None:
                raise ValueError(
                    "formal fine-sync PRR requires --planned-business-window-start-ms "
                    "and --planned-business-window-duration-ms; these values are used "
                    "only after decoding for its metric denominator"
                )
            fine_sync_database_audit = {
                "path": str(Path(args.fine_sync_db)),
                "schema": str(fine_sync_database.get("schema")),
                "candidate_discovery": discovery,
                "detected_physical_candidate_count": int(
                    fine_sync_database.get(
                        "detected_physical_candidate_count",
                        len(fine_sync_entries),
                    )
                ),
            }
        else:
            raise ValueError(
                "--fine-sync-db must use fine_sync_anonymous_physical_v2; "
                "rebuild the database with build_fine_sync_database.py --overwrite"
            )
        log(
            f"[3/6] fine-sync database: {len(fine_sync_entries)} hypotheses, "
            f"{fine_sync_candidate_count} "
            f"anonymous physical candidates "
            f"from {Path(args.fine_sync_db).name}"
        )

    # Keep the energy prefilter off for the middle-business-window slices:
    # a busy five-second traffic slice has no noise-dominated samples, so the
    # prefilter's 20%-percentile noise floor is polluted and its threshold
    # silently drops most RF bursts (verified on the duty-0.75 Fig. 12 run:
    # ~81 scheduled packets produced only 9 prefilter events).  The prefilter
    # is only sound on full captures whose early region is noise-dominated.
    if fine_sync_database_loaded:
        scan_ranges = []
        energy_diag = {"enabled": False, "ranges": []}
        use_energy_prefilter = False
        log("[3/6] fine-sync frontend: hypotheses loaded, blind scan skipped")
    else:
        long_capture = white.shape[1] > int(round(10.0 * rate))
        use_energy_prefilter = (
            long_capture or args.force_energy_prefilter or args.fast_blind
        ) and not args.disable_energy_prefilter
        energy_diag = {"enabled": False, "ranges": [{"start_sample": 0, "end_sample": int(white.shape[1])}]}
    if use_energy_prefilter:
        noise_floor_power: float | None = None
        if args.noise_floor_seconds > 0.0:
            try:
                noise_samples = int(round(float(args.noise_floor_seconds) * rate))
                noise_iq = read_sc16(
                    Path(args.iq),
                    start_sample_per_channel=0,
                    max_samples_per_channel=noise_samples,
                )
                noise_floor_power = float(
                    np.mean(np.mean(np.abs(noise_iq) ** 2, axis=1))
                )
                log(
                    f"[3/6] pre-traffic noise floor: "
                    f"{noise_floor_power:.4e} (first {args.noise_floor_seconds:g}s)"
                )
            except Exception as exc:  # pragma: no cover - defensive
                log(f"[3/6] noise-floor read failed, using slice percentile: {exc}")
                noise_floor_power = None
        scan_ranges, energy_diag = energy_candidate_ranges(
            white,
            rate=rate,
            cfg=cfg,
            top_windows=args.energy_top_windows,
            window_seconds=args.energy_window_seconds,
            min_ratio=args.energy_min_ratio,
            expected_events=0,
            noise_floor_power=noise_floor_power,
        )
        log(f"[3/6] energy prefilter selected {len(scan_ranges)} windows")
    elif not fine_sync_database_loaded:
        scan_ranges = [(0, int(white.shape[1]))]
        log("[3/6] energy prefilter disabled; scanning full capture")

    # Blind synchronization has no node-count prior.  Keep its multi-user
    # floor fixed; formal figure decoding instead bypasses this path by loading
    # the global anonymous physical-candidate database.
    effective_candidates_per_window = max(
        int(args.frontend_candidates_per_window),
        64,
    )
    seed_estimates: list[dict] = []
    frontend_window_details: list[dict] = []
    for window_index, (range_start, range_end) in enumerate(scan_ranges, start=1):
        segment = white[:, range_start:range_end]
        if segment.shape[1] < int(round((cfg.preamble_len + 4) * cfg.samples_per_symbol)):
            continue
        window_duration_s = float(range_end - range_start) / max(rate, 1e-9)
        context_s = max(float(args.energy_window_seconds), 1e-9)
        window_units = min(2, max(1, int(math.ceil(window_duration_s / context_s))))
        local_candidate_limit = max(
            int(effective_candidates_per_window),
            int(effective_candidates_per_window) * window_units,
        )
        log(
            f"[4/6] frontend window {window_index}/{len(scan_ranges)}: "
            f"{range_start / rate:.3f}-{range_end / rate:.3f}s, "
            f"refine_limit={local_candidate_limit}"
        )
        if args.sliding_frontend:
            sliding_streams, sliding_eigvecs, _ = pca_project_streams(
                segment, include_original=True
            )
            residual_stream = (
                np.conj(sliding_eigvecs[:, -1])[None, :] @ segment
            ).astype(np.complex64)
            sliding_streams = np.vstack([sliding_streams, residual_stream])
            local_estimates = sliding_preamble_sp_estimates(
                segment,
                cfg,
                streams=sliding_streams,
                threshold=frontend_threshold,
                cfo_min=args.cfo_min,
                cfo_max=args.cfo_max,
                max_candidates=local_candidate_limit,
                min_sfd_score=args.min_sfd_score,
                min_refined_sync_score=10.0,
            )
            phase_retry_used = False
        else:
            local_estimates, _ = detected_estimates_real(
                segment,
                cfg,
                max_candidates=args.max_candidates,
                raw_candidate_limit=local_candidate_limit,
                threshold=frontend_threshold,
                step_samples=step_samples,
                scan_phase_count=detector_scan_phase_count,
                min_sync_score=args.min_sync_score,
                min_coherent_metric=args.min_coherent_metric,
                cfo_min=args.cfo_min,
                cfo_max=args.cfo_max,
                min_sfd_score=args.min_sfd_score,
                min_refined_sync_score=args.min_refined_sync_score,
                use_local_projection_tracks=bool(args.local_projection_tracks),
                use_spatial_residual_tracks=use_spatial_residual_tracks,
                fast_single_node=not args.full_refine,
                fast_grid_refine=bool(args.fast_grid_refine),
                stable_top_k=args.sp_preamble_top_k,
                stable_min_hits=args.sp_preamble_min_hits,
                stable_max_tracks=args.sp_preamble_max_tracks,
                stable_chirp_count=scan_chirps,
            )
            phase_retry_used = False
            phase_retry_offset = max(1, step_samples // 2)
            has_strong_local_candidate = any(
                est.get("frontend_candidate_stage") != "local_spatial_residual_fast_sfd"
                and float(est.get("sfd_confidence", 0.0)) >= 50.0
                and float(args.cfo_min)
                <= float(est.get("continuous_cfo_bins", est.get("cfo_bins", 0.0)))
                <= float(args.cfo_max)
                for est in local_estimates
            )
            if (
                not args.disable_detector_phase_retry
                and detector_scan_phase_count == 1
                and not has_strong_local_candidate
                and segment.shape[1] - phase_retry_offset
                >= int(round((cfg.preamble_len + 4) * cfg.samples_per_symbol))
            ):
                phase_estimates, _ = detected_estimates_real(
                    segment[:, phase_retry_offset:],
                    cfg,
                    max_candidates=args.max_candidates,
                    raw_candidate_limit=local_candidate_limit,
                    threshold=frontend_threshold,
                    step_samples=step_samples,
                    scan_phase_count=detector_scan_phase_count,
                    min_sync_score=args.min_sync_score,
                    min_coherent_metric=args.min_coherent_metric,
                    cfo_min=args.cfo_min,
                    cfo_max=args.cfo_max,
                    min_sfd_score=args.min_sfd_score,
                    min_refined_sync_score=args.min_refined_sync_score,
                    use_local_projection_tracks=bool(args.local_projection_tracks),
                    use_spatial_residual_tracks=use_spatial_residual_tracks,
                    fast_single_node=not args.full_refine,
                    fast_grid_refine=bool(args.fast_grid_refine),
                    stable_top_k=args.sp_preamble_top_k,
                    stable_min_hits=args.sp_preamble_min_hits,
                    stable_max_tracks=args.sp_preamble_max_tracks,
                    stable_chirp_count=scan_chirps,
                )
                local_estimates.extend(
                    offset_estimate_samples(est, phase_retry_offset)
                    for est in phase_estimates
                )
                phase_retry_used = True
        accepted_before = len(seed_estimates)
        for est in local_estimates:
            final_cfo = float(est.get("continuous_cfo_bins", est.get("cfo_bins", 0.0)))
            if not (float(args.cfo_min) <= final_cfo <= float(args.cfo_max)):
                continue
            seed_estimates.append(offset_estimate_samples(est, range_start))
        frontend_window_details.append(
            {
                "window_index": int(window_index),
                "start_sample": int(range_start),
                "end_sample": int(range_end),
                "start_time_s": float(range_start) / rate,
                "end_time_s": float(range_end) / rate,
                "duration_s": float(window_duration_s),
                "candidate_limit": int(local_candidate_limit),
                "local_estimate_count": int(len(local_estimates)),
                "accepted_estimate_count": int(len(seed_estimates) - accepted_before),
                "phase_retry_used": bool(phase_retry_used),
                "phase_retry_offset_samples": int(phase_retry_offset) if phase_retry_used else 0,
            }
        )
        log(f"[4/6] accumulated seed candidates: {len(seed_estimates)}")
    if fine_sync_database_loaded:
        seed_estimates = []
        for row in fine_sync_entries:
            row_cfo = float(row.get("continuous_cfo_bins", row.get("cfo_bins", 0.0)))
            if not float(args.cfo_min) <= row_cfo <= float(args.cfo_max):
                continue
            estimate = {
                "start_sample": float(row["start_sample"]),
                "sto_samples": float(row.get("sto_samples", 0.0)),
                "cfo_bins": row_cfo,
                "continuous_cfo_bins": row_cfo,
                "channel": [
                    [float(v[0]), float(v[1])]
                    for v in row.get("channel", [[1.0, 0.0], [0.0, 1.0]])
                ],
                "power": float(row.get("power", 0.0)),
                "confidence": float(row.get("confidence", 0.0)),
                "preamble_ratio": float(row.get("preamble_ratio", 0.0)),
                "sfd_confidence": float(row.get("sfd_confidence", 0.0)),
                "sync_confidence": float(row.get("sync_confidence", 0.0)),
                "structure_certified": bool(row.get("structure_certified", False)),
                "peak_bin": int(row.get("peak_bin", 0)),
                "frontend_candidate_stage": str(row.get("stage", "fine_sync_db")),
            }
            seed_estimates.append(estimate)
        log(f"[4/6] fine-sync hypotheses -> {len(seed_estimates)} candidates")
    seed_estimates.sort(key=lambda est: float(est["start_sample"]) + float(est.get("sto_samples", 0.0)))
    deduped_seed_estimates: list[dict] = []
    for est in seed_estimates:
        duplicate = next(
            (
                old
                for old in deduped_seed_estimates
                if same_packet_estimate(est, old, cfg)
            ),
            None,
        )
        if duplicate is not None:
            continue
        deduped_seed_estimates.append(est)
        if (
            fine_sync_candidate_count is None
            and len(deduped_seed_estimates) >= max(1, int(args.max_candidates))
        ):
            break
    # The anonymous builder has already globally deduplicated physical tracks.
    # Do not silently reduce its denominator with the receiver's broader
    # convenience deduplicator or its normal candidate cap.
    if fine_sync_candidate_count is None:
        seed_estimates = deduped_seed_estimates
    if fine_sync_candidate_count is not None and len(seed_estimates) != fine_sync_candidate_count:
        raise RuntimeError("anonymous fine-sync candidate count changed before decoding")
    for candidate_id, estimate in enumerate(seed_estimates):
        estimate["_anonymous_physical_candidate_id"] = int(candidate_id)
        estimate["_physical_evidence_key"] = physical_evidence_key(
            estimate, candidate_id
        )
    if (
        args.continuous_sfd_supplement
        and not args.skip_continuous_sfd_supplement
        and not args.fast_blind
        and not args.sliding_frontend
        and not fine_sync_database_loaded
    ):
        log("[4/6] running shared sample-continuous SFD-pair supplement")
        seed_estimates, continuous_sfd_diagnostics = (
            supplement_sp_estimates_with_continuous_sfd(
                physical_centered,
                white,
                cfg,
                seed_estimates,
                scan_ranges,
                cfo_min=args.cfo_min,
                cfo_max=args.cfo_max,
                max_candidates=args.max_candidates,
            )
        )
        log(
            "[4/6] continuous SFD supplement: "
            f"raw={continuous_sfd_diagnostics['sfd_raw_candidate_count']}, "
            f"new={continuous_sfd_diagnostics['sfd_new_candidate_count_before_completeness']}, "
            f"combined={len(seed_estimates)}"
        )
    else:
        continuous_sfd_diagnostics = {
            "enabled": False,
            "preamble_seed_count": int(len(seed_estimates)),
            "final_complete_candidate_count": int(len(seed_estimates)),
            "skipped_by_fast_blind": bool(
                (args.fast_blind or args.skip_continuous_sfd_supplement)
                and args.continuous_sfd_supplement
            ),
        }
    log(f"[5/6] reliability/lambda on {len(seed_estimates)} candidates")
    estimates, lambda_configuration_audit = configure_sp_lambda_batch(
        white,
        seed_estimates,
        cfg,
        noise_sigma2=noise_sigma2_fft,
        gamma=args.sp_gamma,
        max_lambda=args.sp_lambda_max,
        noise_competition=args.sp_lambda_policy != "pair_only_legacy",
        noise_two_packet_only=args.sp_lambda_policy in (TWO_PACKET_POLICY, GUARDED_PAIR_POLICY),
        reference_guard=args.sp_lambda_policy == GUARDED_PAIR_POLICY,
        physical_samples=physical_centered,
        whitener=whitener,
    )
    log(
        "[5/6] lambda audit: "
        f"payload_overlap_edges={lambda_configuration_audit['payload_overlap_edge_count']} "
        f"targets_with_competitor="
        f"{lambda_configuration_audit['targets_with_payload_competitor']}/"
        f"{lambda_configuration_audit['target_count']} "
        f"positive_lambda={lambda_configuration_audit['targets_with_positive_lambda']}",
    )
    shared_decode_cache = SharedPhysicalDecodeCache()
    comparison_payload_cache = PhysicalEvidencePayloadCache()
    comparison_contexts: dict[str, PaperComparisonContext] = {}
    comparison_estimation_ms_per_candidate: dict[str, float] = {}
    comparison_estimates_by_method: dict[str, list[dict]] = {}
    common_comparison_frontends: dict[str, dict] = {}
    prepared_common_rows: list[tuple[list[dict], dict]] = []
    if (
        not args.skip_comparison_decoders
        and args.comparison_frontend_scope == "common"
    ):
        log("[5/6] preparing shared SP-fine-sync targets for all comparison decoders")
        comparison_estimates: list[dict] = []
        for cid, est in enumerate(estimates):
            sp_stage_rows = decode_sp_stages(
                white,
                est,
                cfg,
                max_sync_trials=args.sp_sync_max_trials,
                sync_retry_policy=args.sp_sync_retry_policy,
                relaxed_sync_max_trials=args.sp_sync_relaxed_max_trials,
                shared_cache=shared_decode_cache,
                physical_key=tuple(est["_physical_evidence_key"]),
            )
            comparison_est = dict(est)
            comparison_est["_comparison_candidate_index"] = int(cid)
            # Every comparator consumes the same fine-sync database target.
            # Do not pass a start/CFO selected by SP payload CRC to a baseline.
            comparison_est["start_sample"] = (
                float(est["start_sample"])
                + float(est.get("sto_samples_sp", est.get("sto_samples", 0.0)))
            )
            comparison_est["sto_samples"] = 0.0
            comparison_est["sto_samples_sp"] = 0.0
            comparison_est["continuous_cfo_bins"] = float(
                est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))
            )
            comparison_est["cfo_bins_sp"] = comparison_est["continuous_cfo_bins"]
            comparison_est["shared_sp_fine_sync"] = True
            comparison_est["shared_sp_fine_sync_seed"] = True
            prepared_common_rows.append((sp_stage_rows, comparison_est))
            comparison_estimates.append(comparison_est)
            sync_row = next(
                row for row in sp_stage_rows if row["method"] == "sp_sync_refine"
            )
            cache_audit = sync_row.get("shared_sync_cache", {})
            log(
                f"[5/6] shared-sync candidate={cid + 1}/{len(estimates)} "
                f"id={cid} trials={sync_row['synchronization_trials']} "
                f"retry_gate={'pass' if sync_row['sync_retry_gate_passed'] else 'skip'} "
                f"cache=h{cache_audit.get('payload_trial_cache_hits', 0)}"
                f"/m{cache_audit.get('payload_trial_cache_misses', 0)}",
            )
        estimation_policy = {
            "lorawan": "none; physical Ch0 top-1 payload decisions",
            "mrc": "own physical-pair preamble channel estimate at fixed SP sync",
            "mrc_cic": "fixed physical-preamble MRC, then combined preamble RSSI and fractional-frequency features",
            "pcube": (
                "own physical-Rx preamble/SFD local start-CFO refinement from the shared "
                "fine-sync seed, then target-preamble PDoA estimation and clustering"
                if args.comparison_paper_local_refinement
                else "own target-preamble PDoA estimate at fixed SP sync"
            ),
            "maloragw": (
                "own PCA-projected preamble/SFD local start-CFO refinement from the shared "
                "fine-sync seed, then preamble channel-matrix estimation, ZF, and peak features"
                if args.comparison_paper_local_refinement
                else "own preamble channel matrix and peak features at fixed SP sync"
            ),
        }
        for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw"):
            method_estimates = [
                dict(estimate) for estimate in comparison_estimates
            ]
            refinement_audit: dict | None = None
            if (
                args.comparison_paper_local_refinement
                and method in {"pcube", "maloragw"}
            ):
                method_estimates, refinement_audit = refine_paper_frontend_from_sp_fine(
                    physical_centered,
                    cfg,
                    method_estimates,
                    method=method,
                    threshold=frontend_threshold,
                    cfo_min=args.cfo_min,
                    cfo_max=args.cfo_max,
                    candidates_per_window=effective_candidates_per_window,
                    scan_phase_count=detector_scan_phase_count,
                    # This is a synchronization correction, not a second packet
                    # detector.  It must stay materially narrower than a symbol.
                    match_tolerance_symbols=0.125,
                    progress=lambda message: log(f"[5/6] {message}"),
                )
                if len(method_estimates) != len(comparison_estimates):
                    raise RuntimeError(
                        f"{method} paper-local refinement changed the shared target count"
                    )
            comparison_estimates_by_method[method] = method_estimates
            for cid, method_estimate in enumerate(
                comparison_estimates_by_method[method]
            ):
                method_estimate["_comparison_candidate_index"] = int(cid)
                method_estimate.setdefault("paper_method_refinement_applied", False)
                method_estimate.setdefault(
                    "paper_method_parameter_estimation_applied", bool(method != "lorawan")
                )
            common_comparison_frontends[method] = {
                "shared_sp_candidate_identity": True,
                "shared_sp_fine_start_cfo_sto": (
                    "database_seed_then_bounded_paper_preamble_sfd_refinement_before_payload"
                    if refinement_audit is not None
                    else "database_fixed_before_payload"
                ),
                "method_specific_resynchronization": bool(refinement_audit is not None),
                "method_parameter_estimation": estimation_policy[method],
                "candidate_count": int(len(comparison_estimates)),
            }
            if refinement_audit is not None:
                common_comparison_frontends[method]["paper_local_refinement"] = {
                    **refinement_audit,
                    "payload_fec_crc_used": False,
                    "manifest_or_expected_payload_used": False,
                    "sp_lambda_or_residual_used": False,
                }
            estimation_started_ns = time.perf_counter_ns()
            comparison_contexts[method] = PaperComparisonContext(
                physical_centered,
                comparison_estimates_by_method[method],
                cfg,
                frontend_method=method,
                payload_spectrum_cache=comparison_payload_cache,
            )
            common_comparison_frontends[method][
                "local_refinement_cache"
            ] = comparison_contexts[method].cache_audit()
            estimation_elapsed_ms = (
                time.perf_counter_ns() - estimation_started_ns
            ) / 1_000_000.0
            comparison_estimation_ms_per_candidate[method] = (
                0.0
                if method == "lorawan"
                else estimation_elapsed_ms / max(1, len(comparison_estimates))
            )
            common_comparison_frontends[method][
                "parameter_estimation_elapsed_total_ms"
            ] = float(estimation_elapsed_ms)
            common_comparison_frontends[method][
                "parameter_estimation_elapsed_per_candidate_ms"
            ] = float(comparison_estimation_ms_per_candidate[method])

    candidates: list[dict] = []
    successes: dict[str, dict] = {}
    protocol_successes: dict[str, dict] = {}
    log(f"[6/6] decoding {len(estimates)} candidates")
    for cid, est in enumerate(estimates):
        sp_hits_before = int(shared_decode_cache.sp_payload_hits)
        sp_misses_before = int(shared_decode_cache.sp_payload_misses)
        fft_hits_before = int(comparison_payload_cache.spectrum_hits)
        fft_misses_before = int(comparison_payload_cache.spectrum_misses)
        row = candidate_to_json(est, cid)
        row["sp_repair"] = None
        row["start_time_s"] = float(est["start_sample"]) / rate
        row["methods"] = []
        decoded_rows = [
            timed_decode_method(method, white, est, cfg)
            for method in ("ch0", "ch1")
        ]
        if prepared_common_rows:
            sp_stage_rows, comparison_est = prepared_common_rows[cid]
        else:
            sp_stage_rows = decode_sp_stages(
                white,
                est,
                cfg,
                max_sync_trials=args.sp_sync_max_trials,
                sync_retry_policy=args.sp_sync_retry_policy,
                relaxed_sync_max_trials=args.sp_sync_relaxed_max_trials,
                shared_cache=shared_decode_cache,
                physical_key=tuple(est["_physical_evidence_key"]),
            )
            comparison_est = dict(est)
            comparison_est["_comparison_candidate_index"] = int(cid)
            comparison_est["start_sample"] = (
                float(est["start_sample"])
                + float(est.get("sto_samples_sp", est.get("sto_samples", 0.0)))
            )
            comparison_est["sto_samples"] = 0.0
            comparison_est["sto_samples_sp"] = 0.0
            comparison_est["continuous_cfo_bins"] = float(
                est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"]))
            )
            comparison_est["cfo_bins_sp"] = comparison_est["continuous_cfo_bins"]
        decoded_rows.extend(sp_stage_rows)
        # Formal comparisons share the database's pre-payload fine sync. Each
        # baseline retains its own payload-domain combining, separation, peak
        # selection, FEC, and CRC processing.
        if args.skip_comparison_decoders:
            decoded_rows.append(timed_decode_method("mrc", white, comparison_est, cfg))
        if comparison_contexts:
            for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw"):
                context = comparison_contexts[method]
                method_estimate = comparison_estimates_by_method[method][cid]
                decoder = {
                    "lorawan": context.decode_lorawan,
                    "mrc": context.decode_mrc,
                    "mrc_cic": context.decode_cic,
                    "pcube": context.decode_pcube,
                    "maloragw": context.decode_maloragw,
                }[method]
                started_ns = time.perf_counter_ns()
                comparison_result = decoder(method_estimate)
                comparison_result["decode_elapsed_ms"] = (
                    time.perf_counter_ns() - started_ns
                ) / 1_000_000.0
                comparison_result["parameter_estimation_elapsed_ms"] = float(
                    comparison_estimation_ms_per_candidate.get(method, 0.0)
                )
                comparison_result["post_sp_total_elapsed_ms"] = float(
                    comparison_result["decode_elapsed_ms"]
                    + comparison_result["parameter_estimation_elapsed_ms"]
                )
                comparison_result["decode_timing_scope"] = (
                    "method_estimation_and_payload_decode_after_shared_sp_fine_sync"
                )
                if comparison_result.get("method") != method:
                    raise RuntimeError(f"comparison decoder returned wrong method: {method}")
                decoded_rows.append(comparison_result)
        for decoded in decoded_rows:
            method = str(decoded["method"])
            payload = bytes.fromhex(decoded["phy"]["payload_hex"])
            app, app_ok, app_status = validate_payload(
                payload,
                run_id=run_id,
                active_nodes=active_nodes,
                accepted_run_ids=accepted_run_ids,
            )
            decoded["application"] = {
                "app_crc_ok": bool(app_ok),
                "status": app_status,
                "decoded": asdict(app) if app is not None else None,
            }
            if app is not None and run_cfg is not None:
                payload_cfg = payload_config_for_node(
                    manifest, int(app.node_id), run_cfg
                )
                expected_payload = (
                    build_data_payload(payload_cfg, int(app.node_id), int(app.sequence))
                    if payload_cfg is not None
                    else None
                )
                decoded["application"]["manifest_payload_match"] = bool(
                    expected_payload is not None and payload == expected_payload
                )
                decoded["application"]["manifest_expected_payload_hex"] = (
                    expected_payload.hex() if expected_payload is not None else None
                )
            if app is not None:
                protocol_key = f"{app.run_id:08x}:{app.node_id}:{app.sequence}"
                protocol_successes.setdefault(
                    protocol_key,
                    {
                        "run_id": int(app.run_id),
                        "node_id": int(app.node_id),
                        "sequence": int(app.sequence),
                        "first_candidate_id": int(cid),
                        "accepted": bool(app_ok),
                        "reject_statuses": [],
                        "methods": [],
                    },
                )["methods"].append(method)
                if not app_ok:
                    protocol_successes[protocol_key]["accepted"] = False
                    if app_status not in protocol_successes[protocol_key]["reject_statuses"]:
                        protocol_successes[protocol_key]["reject_statuses"].append(app_status)
            if app_ok and app is not None:
                key = f"{app.run_id:08x}:{app.node_id}:{app.sequence}"
                successes.setdefault(
                    key,
                    {
                        "run_id": int(app.run_id),
                        "node_id": int(app.node_id),
                        "sequence": int(app.sequence),
                        "first_candidate_id": int(cid),
                        "methods": [],
                    },
                )["methods"].append(method)
            row["methods"].append(decoded)
        candidates.append(row)
        sync_row = next(
            item for item in sp_stage_rows if item["method"] == "sp_sync_refine"
        )
        method_successes = [
            str(item["method"])
            for item in row["methods"]
            if bool(item.get("application", {}).get("app_crc_ok", False))
        ]
        log(
            f"DECODE_CANDIDATE {cid + 1}/{len(estimates)} id={cid} "
            f"sp_trials={sync_row['synchronization_trials']} "
            f"sp_cache=+h{shared_decode_cache.sp_payload_hits - sp_hits_before}"
            f"/+m{shared_decode_cache.sp_payload_misses - sp_misses_before} "
            f"payload_fft=+h{comparison_payload_cache.spectrum_hits - fft_hits_before}"
            f"/+m{comparison_payload_cache.spectrum_misses - fft_misses_before} "
            f"app_crc_methods={','.join(method_successes) if method_successes else 'none'}",
        )

    native_comparison_rows_by_method: dict[str, list[dict]] = {
        "lorawan": [],
        "mrc": [],
        "mrc_cic": [],
        "pcube": [],
        "maloragw": [],
    }
    native_comparison_frontends: dict[str, dict] = {}
    if (
        not args.skip_comparison_decoders
        and args.comparison_frontend_scope == "native"
    ):
        log(
            "[6/6] running independent native LoRaWAN/MRC/CIC/PCube/MaLoRaGW front ends"
        )
        frontend_started_ns = time.perf_counter_ns()
        native_estimates, native_comparison_frontends = detect_native_frontends(
            physical_centered,
            cfg,
            scan_ranges,
            threshold=frontend_threshold,
            cfo_min=args.cfo_min,
            cfo_max=args.cfo_max,
            max_candidates=args.max_candidates,
            candidates_per_window=args.frontend_candidates_per_window,
            scan_phase_count=detector_scan_phase_count,
        )
        native_frontend_elapsed_ms = (
            time.perf_counter_ns() - frontend_started_ns
        ) / 1_000_000.0
        for details in native_comparison_frontends.values():
            details["frontend_elapsed_ms_all_methods_shared_wall_clock"] = float(
                native_frontend_elapsed_ms
            )

        for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw"):
            complete_estimates = [
                estimate
                for estimate in native_estimates.get(method, [])
                if float(estimate["start_sample"]) >= 0.0
                and float(estimate["start_sample"]) + float(cfg.frame_samples)
                <= float(physical_centered.shape[1])
            ]
            native_comparison_frontends.setdefault(method, {})[
                "complete_candidate_count"
            ] = len(complete_estimates)
            native_comparison_frontends[method]["truncated_candidate_count"] = (
                len(native_estimates.get(method, [])) - len(complete_estimates)
            )
            if not complete_estimates:
                continue
            for native_index, estimate in enumerate(complete_estimates):
                estimate["_comparison_candidate_index"] = int(native_index)
            context = PaperComparisonContext(
                physical_centered,
                complete_estimates,
                cfg,
            )
            decoder = {
                "lorawan": context.decode_lorawan,
                "mrc": context.decode_mrc,
                "mrc_cic": context.decode_cic,
                "pcube": context.decode_pcube,
                "maloragw": context.decode_maloragw,
            }[method]
            for native_index, estimate in enumerate(complete_estimates):
                row = candidate_to_json(estimate, native_index)
                row["native_frontend_method"] = method
                row["start_time_s"] = float(estimate["start_sample"]) / rate
                started_ns = time.perf_counter_ns()
                decoded = decoder(estimate)
                decoded["decode_elapsed_ms"] = (
                    time.perf_counter_ns() - started_ns
                ) / 1_000_000.0
                decoded["decode_timing_scope"] = (
                    "payload_decoder_after_paper_native_frontend"
                )
                payload = bytes.fromhex(decoded["phy"]["payload_hex"])
                app, app_ok, app_status = validate_payload(
                    payload,
                    run_id=run_id,
                    active_nodes=active_nodes,
                    accepted_run_ids=accepted_run_ids,
                )
                decoded["application"] = {
                    "app_crc_ok": bool(app_ok),
                    "status": app_status,
                    "decoded": asdict(app) if app is not None else None,
                }
                if app is not None and run_cfg is not None:
                    payload_cfg = payload_config_for_node(
                        manifest, int(app.node_id), run_cfg
                    )
                    expected_payload = (
                        build_data_payload(
                            payload_cfg,
                            int(app.node_id),
                            int(app.sequence),
                        )
                        if payload_cfg is not None
                        else None
                    )
                    decoded["application"]["manifest_payload_match"] = bool(
                        expected_payload is not None
                        and payload == expected_payload
                    )
                    decoded["application"]["manifest_expected_payload_hex"] = (
                        expected_payload.hex() if expected_payload is not None else None
                    )
                if app is not None:
                    protocol_key = f"{app.run_id:08x}:{app.node_id}:{app.sequence}"
                    protocol_successes.setdefault(
                        protocol_key,
                        {
                            "run_id": int(app.run_id),
                            "node_id": int(app.node_id),
                            "sequence": int(app.sequence),
                            "first_candidate_id": -1 - int(native_index),
                            "accepted": bool(app_ok),
                            "reject_statuses": [],
                            "methods": [],
                        },
                    )["methods"].append(method)
                    if not app_ok:
                        protocol_successes[protocol_key]["accepted"] = False
                        if (
                            app_status
                            not in protocol_successes[protocol_key]["reject_statuses"]
                        ):
                            protocol_successes[protocol_key]["reject_statuses"].append(
                                app_status
                            )
                if app_ok and app is not None:
                    key = f"{app.run_id:08x}:{app.node_id}:{app.sequence}"
                    successes.setdefault(
                        key,
                        {
                            "run_id": int(app.run_id),
                            "node_id": int(app.node_id),
                            "sequence": int(app.sequence),
                            "first_candidate_id": -1 - int(native_index),
                            "methods": [],
                        },
                    )["methods"].append(method)
                row["methods"] = [decoded]
                native_comparison_rows_by_method[method].append(row)

    node_counts: dict[str, int] = {}
    for item in successes.values():
        node_counts[str(item["node_id"])] = node_counts.get(str(item["node_id"]), 0) + 1
    protocol_node_counts: dict[str, int] = {}
    protocol_run_counts: dict[str, int] = {}
    rejected_protocol_successes = []
    for item in protocol_successes.values():
        protocol_node_counts[str(item["node_id"])] = protocol_node_counts.get(str(item["node_id"]), 0) + 1
        run_key = f"0x{int(item['run_id']):08X}"
        protocol_run_counts[run_key] = protocol_run_counts.get(run_key, 0) + 1
        if not item["accepted"]:
            rejected_protocol_successes.append(item)
    manifest_payload_match = 0
    manifest_payload_mismatch = 0
    all_method_rows = candidates + [
        row
        for method_rows in native_comparison_rows_by_method.values()
        for row in method_rows
    ]
    for row in all_method_rows:
        for method_row in row.get("methods", []):
            app = method_row.get("application", {})
            if "manifest_payload_match" not in app:
                continue
            if bool(app["manifest_payload_match"]):
                manifest_payload_match += 1
            else:
                manifest_payload_mismatch += 1
    capture_duration_s = float(capture.samples.shape[1]) / max(rate, 1e-9)
    method_stats = method_decode_statistics(all_method_rows)
    prr_tps = prr_tps_statistics(
        run_cfg=run_cfg,
        manifest=manifest,
        active_nodes=active_nodes,
        successes=successes,
        protocol_successes=protocol_successes,
        capture_duration_s=capture_duration_s,
        manual_expected_by_node=manual_counts,
        manual_business_duration_s=args.business_duration_s,
        expected_sequences_by_node=planned_window_sequences,
    )
    sp_method_stats = method_stats.get("sp", {})
    mrc_method_stats = method_stats.get("mrc", {})
    sp_prr_tps = prr_tps.get("by_method", {}).get("sp", {})
    theoretical_frame_duration_s = float(
        (cfg.payload_start_symbols + cfg.payload_symbol_count) * cfg.samples_per_symbol / rate
    )
    complete_burst_threshold_s = 0.9 * theoretical_frame_duration_s
    rf_events = energy_diag.get("events", []) if isinstance(energy_diag, dict) else []
    complete_rf_events = [
        event
        for event in rf_events
        if float(event.get("duration_s", 0.0)) >= complete_burst_threshold_s
    ]
    incomplete_rf_events = [
        event
        for event in rf_events
        if float(event.get("duration_s", 0.0)) < complete_burst_threshold_s
    ]
    detection_decode_stats = detection_decode_statistics(
        run_cfg=run_cfg,
        manifest=manifest,
        active_nodes=active_nodes,
        energy_diag=energy_diag,
        candidates=candidates,
        complete_burst_threshold_s=complete_burst_threshold_s,
        business_duration_s=prr_tps.get("business_duration_s"),
        capture_sample_count=int(capture.samples.shape[1]),
        frame_sample_count=int(round(theoretical_frame_duration_s * rate)),
        packet_alias_time_tolerance_samples=0.10 * float(cfg.samples_per_symbol),
        executed_methods=(
            set(DECODER_METHODS) - {"lorawan", "mrc_cic", "pcube", "maloragw"}
            if args.skip_comparison_decoders
            else set(DECODER_METHODS)
        ),
        accepted_run_ids=accepted_run_ids,
        identity_aliases=identity_aliases,
        fine_sync_candidate_count=fine_sync_candidate_count,
        expected_sequences_by_node=planned_window_sequences,
    )
    if (
        not args.skip_comparison_decoders
        and args.comparison_frontend_scope == "native"
        and fine_sync_candidate_count is None
    ):
        for method, method_rows in native_comparison_rows_by_method.items():
            detection_decode_stats["by_method"][method] = native_method_metrics(
                method,
                method_rows,
                business_duration_s=prr_tps.get("business_duration_s"),
                manifest_expected_packet_count=(
                    sum(len(sequences) for sequences in planned_window_sequences.values())
                    if planned_window_sequences is not None
                    else None
                ),
            )
    elif (
        not args.skip_comparison_decoders
        and args.comparison_frontend_scope == "common"
    ):
        for method in ("lorawan", "mrc", "mrc_cic", "pcube", "maloragw"):
            detection_decode_stats["by_method"].setdefault(method, {})[
                "frontend_scope"
            ] = "shared_sp_fine_sync_then_method_estimation_and_decode"
    decode_methods = detection_decode_stats.get("by_method", {})
    sp_decode_stats = decode_methods.get("sp", {})
    sp_core_decode_stats = decode_methods.get("sp_core", {})
    sp_sync_decode_stats = decode_methods.get("sp_sync_refine", {})
    lorawan_decode_stats = decode_methods.get("lorawan", {})
    mrc_decode_stats = decode_methods.get("mrc", {})
    cic_decode_stats = decode_methods.get("mrc_cic", {})
    pcube_decode_stats = decode_methods.get("pcube", {})
    maloragw_decode_stats = decode_methods.get("maloragw", {})
    sp_accepted_count = int(sp_prr_tps.get("accepted_success_count_including_unexpected_sequences", 0))
    sp_crc_valid_per_complete_rf_burst = (
        float(sp_accepted_count) / len(complete_rf_events)
        if len(active_nodes) == 1 and complete_rf_events
        else None
    )
    planned_collision_stats = planned_collision_recovery_statistics(
        manifest=manifest,
        active_nodes=active_nodes,
        candidates=all_method_rows,
        frame_duration_ms=theoretical_frame_duration_s * 1000.0,
    )
    sp_collision_stats = planned_collision_stats.get("by_method", {}).get("sp", {})
    mrc_collision_stats = planned_collision_stats.get("by_method", {}).get("mrc", {})
    zero_observed_active_nodes = sorted(
        int(node_id)
        for node_id in active_nodes
        if protocol_node_counts.get(str(int(node_id)), 0) == 0
    )
    report = {
        "schema": "node01_sp_receiver_report_v6",
        "comparison_baseline_revision": "target_mrc_cic_v1",
        "sp_lambda_policy": args.sp_lambda_policy,
        "input": {
            "iq": str(args.iq),
            "metadata": str(args.metadata or args.iq.with_suffix(args.iq.suffix + ".json")),
            "manifest": str(args.manifest) if args.manifest else None,
            "analysis_slice": capture.metadata.get("analysis_slice"),
            "fine_sync_database": fine_sync_database_audit,
            "planned_prr_window": (
                {
                    "business_relative_start_ms": float(
                        args.planned_business_window_start_ms
                    ),
                    "duration_ms": float(args.planned_business_window_duration_ms),
                    "expected_sequences_by_node": {
                        str(node_id): list(sequences)
                        for node_id, sequences in sorted(
                            (planned_window_sequences or {}).items()
                        )
                    },
                    "manifest_use": "post_decode_prr_denominator_only",
                }
                if planned_window_sequences is not None
                else None
            ),
        },
        "config": {
            "sf": cfg.sf,
            "bw_hz": cfg.bw_hz,
            "sample_rate_hz": cfg.sample_rate_hz,
            "cr": "4/5",
            "preamble_len": cfg.preamble_len,
            "sync_word": cfg.sync_word,
            "explicit_header": True,
            "phy_crc": True,
            "payload_len": cfg.payload_len,
            "payload_symbol_count": cfg.payload_symbol_count,
            "payload_start_symbols": cfg.payload_start_symbols,
        },
        "run_id": run_id,
        "active_nodes": sorted(active_nodes),
        "capture_warnings": capture.warnings,
        "adc": adc_stats,
        "calibration": calibration,
        "frontend": {
            "threshold": frontend_threshold,
            "step": step_samples,
            "scan_phase_count": detector_scan_phase_count,
            "max_candidates": args.max_candidates,
            "frontend_candidates_per_window_requested": args.frontend_candidates_per_window,
            "frontend_candidates_per_window": effective_candidates_per_window,
            "sp_preamble_top_k": args.sp_preamble_top_k,
            "sp_preamble_min_hits": args.sp_preamble_min_hits,
            "sp_preamble_max_tracks": args.sp_preamble_max_tracks,
            "min_sync_score": args.min_sync_score,
            "min_coherent_metric": args.min_coherent_metric,
            "min_sfd_score": args.min_sfd_score,
            "min_refined_sync_score": args.min_refined_sync_score,
            "local_projection_tracks": bool(args.local_projection_tracks),
            "spatial_residual_tracks": bool(use_spatial_residual_tracks),
            "full_refine": bool(args.full_refine),
            "fast_grid_refine": bool(args.fast_grid_refine),
            "detector_phase_retry": not bool(args.disable_detector_phase_retry),
            "cfo_min": args.cfo_min,
            "cfo_max": args.cfo_max,
            "seed_candidate_count": len(seed_estimates),
            "candidate_count": len(estimates),
            "continuous_sfd_supplement": continuous_sfd_diagnostics,
            "noise_sigma2_fft": noise_sigma2_fft,
            "energy_prefilter": energy_diag,
            "window_details": frontend_window_details,
        },
        "decoder": {
            "sp_stages": ["sp_core", "sp_sync_refine"],
            "sp_repair": None,
            "sp_repair_policy": "disabled; failed decode remains null",
            "sp_sync_max_trials": int(args.sp_sync_max_trials),
            "sp_sync_retry_policy": str(args.sp_sync_retry_policy),
            "sp_sync_relaxed_max_trials": int(args.sp_sync_relaxed_max_trials),
            "sp_sync_relaxed_structure": {
                "preamble_ratio_min": 10.0,
                "sync_confidence_min": 3.0,
                "sfd_confidence_min": 3.0,
                "header_requirement": "none for relaxed candidates",
            },
            "sp_lambda_candidate_strategy": (
                "Single preamble-only max-min over overlapping-packet risks and "
                "the noise-bin maximum: reference-reliability cap, pair analytic "
                "points, geometric checkpoints and pair/noise crossings; no CRC selection"
                if args.sp_lambda_policy != "pair_only_legacy" else
                "Legacy pair-only max-min with reference-reliability and global cap (default 4)"
            ),
            "sp_lambda_configuration": lambda_configuration_audit,
            "sp_lambda_crc_selection": "forbidden; lambda is fixed before payload",
            "compatibility_method": "sp aliases formal sp_sync_refine",
            "shared_physical_work_cache": {
                "sp_sync": shared_decode_cache.audit(),
                "comparison_payload": comparison_payload_cache.audit(),
            },
            "reported_comparison_methods": [
                "lorawan",
                "mrc",
                "mrc_cic",
                "pcube",
                "maloragw",
            ],
            "comparison_enabled": not bool(args.skip_comparison_decoders),
            "comparison_frontend_scope": args.comparison_frontend_scope,
            "shared_sp_fine_sync": bool(
                args.comparison_frontend_scope == "common"
                and not args.skip_comparison_decoders
            ),
            "shared_sp_parameters": (
                ["anonymous_physical_candidate", "pre_payload_fine_start_sample", "CFO", "STO"]
                if args.comparison_frontend_scope == "common"
                else []
            ),
            "comparison_scope": (
                (
                    "each receiver's independent native detector/synchronizer and its "
                    "receiver-specific demodulation followed by standard LoRa FEC/CRC"
                )
                if args.comparison_frontend_scope == "native"
                else (
                    "all methods share the anonymous physical candidate and pre-payload fine "
                    "start/CFO/STO seed; LoRaWAN/MRC/CIC retain it, while PCube/MaLoRaGW "
                    "optionally run bounded paper-native preamble/SFD local refinement without "
                    "payload, FEC/CRC, manifest, expected payload, SP lambda, or SP residual; "
                    "each method then performs its required parameter estimation and payload decoding"
                )
            ),
            "comparison_signal_domains": {
                "lorawan": (
                    "DC-removed physical Ch0 only; shared SP fine sync and strict "
                    "top-1 payload FFT"
                    if args.comparison_frontend_scope == "common"
                    else "DC-removed physical Ch0 only; independent dominant-preamble/"
                    "sync-word/SFD acquisition and strict top-1 payload FFT"
                ),
                "mrc": (
                    "DC-removed physical Ch0/Ch1; fixed SP fine sync, own preamble "
                    "channel estimate, then fixed-MRC top-1 payload FFT"
                    if args.comparison_frontend_scope == "common"
                    else "DC-removed physical Ch0/Ch1; independent dominant-preamble/"
                    "sync-word/SFD/channel acquisition and fixed-MRC top-1 payload FFT"
                ),
                "mrc_cic": (
                    "DC-removed physical Ch0/Ch1; fixed target MRC, then combined-preamble "
                    "RSSI/fractional-frequency estimation and CIC payload separation"
                    if args.comparison_frontend_scope == "common"
                    else "DC-removed physical Ch0/Ch1; native CIC synchronization, fixed target MRC, then CIC"
                ),
                "pcube": (
                    "DC-removed synchronized physical Ch0/Ch1 Rx-pair; shared SP fine seed, "
                    "bounded PCube physical-Rx preamble/SFD refinement, then own preamble-PDoA "
                    "estimation and clustering"
                    if (
                        args.comparison_frontend_scope == "common"
                        and args.comparison_paper_local_refinement
                    )
                    else (
                        "DC-removed synchronized physical Ch0/Ch1 Rx-pair; fixed SP fine sync, "
                        "then PCube own preamble-PDoA estimation and clustering"
                        if args.comparison_frontend_scope == "common"
                        else "DC-removed synchronized physical Ch0/Ch1 Rx-pair"
                    )
                ),
                "maloragw": (
                    "DC-removed physical Ch0/Ch1 uplink array; shared SP fine seed, bounded "
                    "MaLoRaGW PCA-preamble/SFD refinement, then own preamble-channel estimation, "
                    "ZF, and peak clustering"
                    if (
                        args.comparison_frontend_scope == "common"
                        and args.comparison_paper_local_refinement
                    )
                    else (
                        "DC-removed physical Ch0/Ch1 uplink array; fixed SP fine sync, then "
                        "MaLoRaGW own preamble-channel estimation, ZF, and peak clustering"
                        if args.comparison_frontend_scope == "common"
                        else "DC-removed physical Ch0/Ch1 uplink array"
                    )
                ),
            },
            "hardware_limits": {
                "mrc_cic": (
                    f"two physical channels combined by target MRC; capture oversampling is {cfg.osr}x "
                    "whereas the paper prototype reports 8x at BW250k"
                ),
                "pcube": "one Rx-pair; paper Eq. 9 multi-pair combining unavailable",
                "maloragw": "two receive antennas and uplink-only capture; downlink beamforming excluded",
            },
            "native_frontends": native_comparison_frontends,
            "common_sp_seeded_paper_frontends": common_comparison_frontends,
        },
        "summary": {
            "unique_success_count": len(successes),
            "unique_success_by_node": node_counts,
            "node01_success_count": node_counts.get("1", 0),
            "unique_protocol_valid_count_before_filters": len(protocol_successes),
            "unique_protocol_valid_by_node_before_filters": protocol_node_counts,
            "unique_protocol_valid_by_run_id_before_filters": protocol_run_counts,
            "unique_protocol_valid_rejected_by_filters": len(rejected_protocol_successes),
            "zero_observed_active_nodes": zero_observed_active_nodes,
            "node_outage_review_required": bool(zero_observed_active_nodes),
            "zero_node_metric_policy": (
                "retain planned denominators and measured throughput; never silently "
                "drop or impute a zero-observed active node"
            ),
            "sp_detected_candidates": sp_method_stats.get("detected_candidates", 0),
            "sp_phy_crc_failed_likely_symbol_error": sp_method_stats.get("phy_crc_failed_likely_symbol_error", 0),
            "sp_application_crc_failed": sp_method_stats.get("application_crc_failed", 0),
            "expected_packet_count": detection_decode_stats.get("expected_packet_count"),
            "raw_detected_rf_burst_count": detection_decode_stats.get("raw_detected_rf_burst_count"),
            "complete_detected_packet_count": detection_decode_stats.get("complete_detected_packet_count"),
            "complete_candidate_hypothesis_count": detection_decode_stats.get(
                "complete_candidate_hypothesis_count"
            ),
            "decoded_identity_alias_candidate_count": detection_decode_stats.get(
                "decoded_identity_alias_candidate_count", 0
            ),
            "truncated_rf_burst_count": detection_decode_stats.get("truncated_rf_burst_count"),
            "short_non_packet_rf_event_count": detection_decode_stats.get("short_non_packet_rf_event_count", 0),
            "raw_rf_burst_detection_rate": detection_decode_stats.get("raw_rf_burst_detection_rate"),
            "packet_detection_rate": detection_decode_stats.get("packet_detection_rate"),
            "sp_decoded_success_count": sp_decode_stats.get("decoded_success_count"),
            "sp_prr": sp_decode_stats.get("prr"),
            "sp_tps_business_s": sp_decode_stats.get("decoded_success_tps"),
            "sp_payload_goodput_kbps": sp_decode_stats.get("payload_goodput_kbps"),
            "sp_core_decoded_success_count": sp_core_decode_stats.get("decoded_success_count"),
            "sp_core_prr": sp_core_decode_stats.get("prr"),
            "sp_core_tps_business_s": sp_core_decode_stats.get("decoded_success_tps"),
            "sp_core_payload_goodput_kbps": sp_core_decode_stats.get(
                "payload_goodput_kbps"
            ),
            "sp_sync_refine_decoded_success_count": sp_sync_decode_stats.get(
                "decoded_success_count"
            ),
            "sp_sync_refine_prr": sp_sync_decode_stats.get("prr"),
            "sp_sync_refine_tps_business_s": sp_sync_decode_stats.get(
                "decoded_success_tps"
            ),
            "sp_sync_refine_payload_goodput_kbps": sp_sync_decode_stats.get(
                "payload_goodput_kbps"
            ),
            "sp_repair_decoded_success_count": None,
            "sp_repair_prr": None,
            "sp_repair_tps_business_s": None,
            "sp_repair_payload_goodput_kbps": None,
            "sp_crc_valid_observed_tps_capture_s": sp_prr_tps.get("observed_tps_capture_s"),
            "lorawan_decoded_success_count": lorawan_decode_stats.get(
                "decoded_success_count"
            ),
            "lorawan_prr": lorawan_decode_stats.get("prr"),
            "lorawan_tps_business_s": lorawan_decode_stats.get(
                "decoded_success_tps"
            ),
            "lorawan_payload_goodput_kbps": lorawan_decode_stats.get(
                "payload_goodput_kbps"
            ),
            "mrc_phy_crc_failed_likely_symbol_error": mrc_method_stats.get("phy_crc_failed_likely_symbol_error", 0),
            "mrc_decoded_success_count": mrc_decode_stats.get("decoded_success_count"),
            "mrc_prr": mrc_decode_stats.get("prr"),
            "mrc_tps_business_s": mrc_decode_stats.get("decoded_success_tps"),
            "mrc_payload_goodput_kbps": mrc_decode_stats.get("payload_goodput_kbps"),
            "mrc_cic_decoded_success_count": cic_decode_stats.get("decoded_success_count"),
            "mrc_cic_prr": cic_decode_stats.get("prr"),
            "mrc_cic_tps_business_s": cic_decode_stats.get("decoded_success_tps"),
            "mrc_cic_payload_goodput_kbps": cic_decode_stats.get("payload_goodput_kbps"),
            "pcube_decoded_success_count": pcube_decode_stats.get("decoded_success_count"),
            "pcube_prr": pcube_decode_stats.get("prr"),
            "pcube_tps_business_s": pcube_decode_stats.get("decoded_success_tps"),
            "pcube_payload_goodput_kbps": pcube_decode_stats.get(
                "payload_goodput_kbps"
            ),
            "maloragw_decoded_success_count": maloragw_decode_stats.get("decoded_success_count"),
            "maloragw_prr": maloragw_decode_stats.get("prr"),
            "maloragw_tps_business_s": maloragw_decode_stats.get("decoded_success_tps"),
            "maloragw_payload_goodput_kbps": maloragw_decode_stats.get(
                "payload_goodput_kbps"
            ),
            "comparison_results": {
                "lorawan": {
                    "execution_status": lorawan_decode_stats.get("execution_status"),
                    "frontend_scope": lorawan_decode_stats.get("frontend_scope"),
                    "decoded_success_count": lorawan_decode_stats.get(
                        "decoded_success_count"
                    ),
                    "identity_matched_success_count": lorawan_decode_stats.get(
                        "identity_matched_success_count"
                    ),
                    "identity_mismatch_count": lorawan_decode_stats.get(
                        "identity_mismatch_count"
                    ),
                    "prr_denominator_packet_count": lorawan_decode_stats.get(
                        "prr_denominator_packet_count"
                    ),
                    "prr": lorawan_decode_stats.get("prr"),
                    "tps_business_s": lorawan_decode_stats.get(
                        "decoded_success_tps"
                    ),
                },
                "sp+sync-refine": {
                    "decoded_success_count": sp_sync_decode_stats.get("decoded_success_count"),
                    "identity_matched_success_count": sp_sync_decode_stats.get(
                        "identity_matched_success_count"
                    ),
                    "identity_mismatch_count": sp_sync_decode_stats.get(
                        "identity_mismatch_count"
                    ),
                    "prr_denominator_packet_count": sp_sync_decode_stats.get(
                        "prr_denominator_packet_count"
                    ),
                    "prr": sp_sync_decode_stats.get("prr"),
                    "tps_business_s": sp_sync_decode_stats.get("decoded_success_tps"),
                },
                "sp+repair": None,
                "mrc": {
                    "execution_status": mrc_decode_stats.get("execution_status"),
                    "frontend_scope": mrc_decode_stats.get("frontend_scope"),
                    "decoded_success_count": mrc_decode_stats.get("decoded_success_count"),
                    "identity_matched_success_count": mrc_decode_stats.get(
                        "identity_matched_success_count"
                    ),
                    "identity_mismatch_count": mrc_decode_stats.get(
                        "identity_mismatch_count"
                    ),
                    "prr_denominator_packet_count": mrc_decode_stats.get(
                        "prr_denominator_packet_count"
                    ),
                    "prr": mrc_decode_stats.get("prr"),
                    "tps_business_s": mrc_decode_stats.get("decoded_success_tps"),
                },
                "mrc_cic": {
                    "execution_status": cic_decode_stats.get("execution_status"),
                    "frontend_scope": cic_decode_stats.get("frontend_scope"),
                    "decoded_success_count": cic_decode_stats.get("decoded_success_count"),
                    "identity_matched_success_count": cic_decode_stats.get(
                        "identity_matched_success_count"
                    ),
                    "identity_mismatch_count": cic_decode_stats.get(
                        "identity_mismatch_count"
                    ),
                    "prr_denominator_packet_count": cic_decode_stats.get(
                        "prr_denominator_packet_count"
                    ),
                    "prr": cic_decode_stats.get("prr"),
                    "tps_business_s": cic_decode_stats.get("decoded_success_tps"),
                },
                "pcube": {
                    "execution_status": pcube_decode_stats.get("execution_status"),
                    "frontend_scope": pcube_decode_stats.get("frontend_scope"),
                    "decoded_success_count": pcube_decode_stats.get("decoded_success_count"),
                    "identity_matched_success_count": pcube_decode_stats.get(
                        "identity_matched_success_count"
                    ),
                    "identity_mismatch_count": pcube_decode_stats.get(
                        "identity_mismatch_count"
                    ),
                    "prr_denominator_packet_count": pcube_decode_stats.get(
                        "prr_denominator_packet_count"
                    ),
                    "prr": pcube_decode_stats.get("prr"),
                    "tps_business_s": pcube_decode_stats.get("decoded_success_tps"),
                },
                "maloragw": {
                    "execution_status": maloragw_decode_stats.get("execution_status"),
                    "frontend_scope": maloragw_decode_stats.get("frontend_scope"),
                    "decoded_success_count": maloragw_decode_stats.get("decoded_success_count"),
                    "identity_matched_success_count": maloragw_decode_stats.get(
                        "identity_matched_success_count"
                    ),
                    "identity_mismatch_count": maloragw_decode_stats.get(
                        "identity_mismatch_count"
                    ),
                    "prr_denominator_packet_count": maloragw_decode_stats.get(
                        "prr_denominator_packet_count"
                    ),
                    "prr": maloragw_decode_stats.get("prr"),
                    "tps_business_s": maloragw_decode_stats.get("decoded_success_tps"),
                },
            },
            "prr_denominator_source": detection_decode_stats.get(
                "prr_denominator_source", "complete_detected_packets"
            ),
            "planned_crc_delivery_ratio": sp_prr_tps.get("planned_crc_delivery_ratio"),
            "planned_denominator_source": prr_tps.get("denominator_source"),
            "rf_burst_count": len(rf_events),
            "rf_complete_burst_count": len(complete_rf_events),
            "rf_incomplete_burst_count": len(incomplete_rf_events),
            "sp_crc_valid_per_complete_rf_burst": sp_crc_valid_per_complete_rf_burst,
            "manifest_payload_match_method_count": manifest_payload_match,
            "manifest_payload_mismatch_method_count": manifest_payload_mismatch,
            "planned_collision_packet_count": planned_collision_stats.get("planned_collision_packet_count"),
            "sp_collision_success_count": sp_collision_stats.get("collision_success_count"),
            "sp_collision_delivery_ratio": sp_collision_stats.get("collision_delivery_ratio"),
            "mrc_collision_success_count": mrc_collision_stats.get("collision_success_count"),
            "mrc_collision_delivery_ratio": mrc_collision_stats.get("collision_delivery_ratio"),
            "sp_added_over_mrc_collision_count": planned_collision_stats.get("sp_added_over_mrc_collision_count"),
        },
        "method_decode_statistics": method_stats,
        "detection_and_decode": detection_decode_stats,
        "planned_crc_delivery_and_tps": prr_tps,
        "planned_collision_recovery": planned_collision_stats,
        "air_observation": {
            "definition": (
                "RF-energy burst counts are capture-side diagnostics, not transmitter UART ground truth; "
                "the complete-burst CRC ratio is meaningful for isolated single-node captures after "
                "excluding foreign transmitters"
            ),
            "theoretical_frame_duration_s": theoretical_frame_duration_s,
            "complete_burst_threshold_s": complete_burst_threshold_s,
            "rf_burst_count": len(rf_events),
            "complete_rf_burst_count": len(complete_rf_events),
            "incomplete_rf_burst_count": len(incomplete_rf_events),
            "incomplete_rf_events": incomplete_rf_events,
            "sp_accepted_packet_count": sp_accepted_count,
            "sp_crc_valid_per_complete_rf_burst": sp_crc_valid_per_complete_rf_burst,
        },
        "unique_successes": list(successes.values()),
        "unique_protocol_valid_before_filters": list(protocol_successes.values()),
        "candidates": candidates,
        "native_comparison_candidates": native_comparison_rows_by_method,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if zero_observed_active_nodes:
        print(
            "NODE_OUTAGE_REVIEW_REQUIRED zero_observed_active_nodes="
            f"{zero_observed_active_nodes}; keep metrics unchanged, inspect field logs, "
            "and rerun the whole run if a hardware/control outage is verified",
            flush=True,
        )
    print(f"report={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
