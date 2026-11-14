"""Real-capture SP frontend wrapper with configurable CFO range."""

from __future__ import annotations

import math

import numpy as np

from lora_mrc_sp_core import LoRaConfig, SyncCandidate, apply_rf_calibration, pca_project_streams
from sp_detection_frontend import (
    PreambleFFTCache,
    batched_stable_preamble_tracks,
    coherent_preamble_track_score,
    complex_pairs,
    fixed_cfo_frame_score,
    joint_start_cfo_sto_refine,
    preamble_multi_tracks,
    preamble_channel_near_cfo,
    refine_detection_candidate_fast,
    refine_start_cfo_coherent,
    refine_start_fixed_cfo,
    sfd_anchored_start_cfo_refine,
    sfd_score,
    stable_preamble_multi_tracks,
    sync_word_score,
)


def _estimate_channel(est: dict) -> np.ndarray:
    values = est.get("channel", [])
    return np.asarray([complex(float(r), float(i)) for r, i in values], dtype=np.complex128)


def same_packet_estimate(a: dict, b: dict, cfg: LoRaConfig) -> bool:
    """Return true only for a repeated time/CFO/spatial target estimate."""

    start_a = float(a["start_sample"]) + float(a.get("sto_samples", 0.0))
    start_b = float(b["start_sample"]) + float(b.get("sto_samples", 0.0))
    # A LoRa preamble is symbol-periodic, so the coarse grid commonly emits
    # the same target exactly one symbol early.  Refined estimates within
    # 1.25 symbols are duplicates only when their CFO and spatial directions
    # also agree; a different dual-channel direction is kept as another user.
    if abs(start_a - start_b) > 1.25 * cfg.samples_per_symbol:
        return False
    cfo_a = float(a.get("continuous_cfo_bins", a.get("cfo_bins", 0.0)))
    cfo_b = float(b.get("continuous_cfo_bins", b.get("cfo_bins", 0.0)))
    if abs(cfo_a - cfo_b) > 2.5:
        return False
    h_a = _estimate_channel(a)
    h_b = _estimate_channel(b)
    if h_a.size == 0 or h_a.shape != h_b.shape:
        return True
    denom = math.sqrt(float(np.vdot(h_a, h_a).real * np.vdot(h_b, h_b).real))
    coherence = float(abs(np.vdot(h_a, h_b)) / max(denom, 1e-30))
    return coherence >= 0.97


def pcube_sp_estimates_real(
    samples,
    cfg: LoRaConfig,
    *,
    max_candidates: int,
    raw_candidate_limit: int | None = None,
    threshold: float,
    step_samples: int,
    scan_phase_count: int = 1,
    min_sync_score: float,
    min_coherent_metric: float,
    cfo_min: float,
    cfo_max: float,
    min_sfd_score: float = 10.0,
    min_refined_sync_score: float = 500.0,
    use_local_projection_tracks: bool = False,
    use_spatial_residual_tracks: bool = False,
    fast_single_node: bool = True,
    fast_grid_refine: bool = False,
    stable_stream_mode: str = "physical_and_pca",
    stable_top_k: int = 10,
    stable_min_hits: int = 4,
    stable_max_tracks: int = 4,
    use_integer_alias_branch: bool = True,
    stable_chirp_count: int | None = None,
) -> list[dict]:
    """Same SP.md frontend as the main code, but without the old pos-data CFO prior."""

    x = apply_rf_calibration(samples)
    x = x - x.mean(axis=1, keepdims=True)
    pca_streams, stable_eigvecs, _ = pca_project_streams(x, include_original=False)
    if stable_stream_mode == "physical":
        stable_streams = x
    elif stable_stream_mode == "pca":
        stable_streams = pca_streams
    elif stable_stream_mode == "physical_and_pca":
        stable_streams = np.vstack([x, pca_streams]).astype(np.complex64)
    else:
        raise ValueError(
            "stable_stream_mode must be physical, pca, or physical_and_pca"
        )
    preamble_cache = PreambleFFTCache(x, cfg)
    last = x.shape[1] - (cfg.preamble_len + 4) * cfg.samples_per_symbol

    scan_step = max(1, int(step_samples))
    phase_count = max(1, min(int(scan_phase_count), scan_step))
    # A one-symbol coarse stride with only phase zero leaves almost an entire
    # chirp-period blind region.  That is particularly harmful when a new
    # preamble begins inside an already-busy collision interval: an energy
    # gate cannot expose the new arrival, and the preamble track must itself
    # be sampled at several phases.  Evenly interleaved phases cover the full
    # symbol period while keeping the expensive multi-track FFT search bounded;
    # the accepted hypotheses are subsequently refined to fractional samples.
    scan_phases = sorted(
        {
            min(scan_step - 1, (phase_index * scan_step) // phase_count)
            for phase_index in range(phase_count)
        }
    )

    raw: list[
        tuple[
            float,
            float,
            float,
            int,
            float,
            float,
            int,
            np.ndarray | None,
            int,
        ]
    ] = []
    for phase_offset in scan_phases:
        phase_seeds = list(range(int(phase_offset), max(0, last), scan_step))
        if not phase_seeds:
            continue
        batched_seed_results = batched_stable_preamble_tracks(
            x,
            np.asarray(phase_seeds, dtype=np.int64),
            cfg,
            top_k=max(1, int(stable_top_k)),
            min_hits=max(1, int(stable_min_hits)),
            max_tracks=max(1, int(stable_max_tracks)),
            streams=stable_streams,
            residual_projector=(
                stable_eigvecs[:, -1] if use_spatial_residual_tracks else None
            ),
            chirp_count=stable_chirp_count,
        )
        for start, (batched_tracks, spatial_tracks) in zip(
            phase_seeds, batched_seed_results
        ):
            tracks = list(batched_tracks)
            if use_local_projection_tracks:
                tracks.extend(
                    preamble_multi_tracks(
                        x,
                        start,
                        cfg,
                        top_k=20,
                        min_hits=3,
                        max_tracks=8,
                    )
                )
            tagged_tracks = [(*track, None) for track in tracks]
            tagged_tracks.extend(spatial_tracks)
            for score, peak_bin, cfo, power, hits, projector in tagged_tracks:
                if score < threshold:
                    continue
                sync = sync_word_score(x, start, cfo, cfg)
                sfd = sfd_score(x, start, cfo, cfg)
                if min_sync_score > 0.0 and sync * sfd < min_sync_score:
                    continue
                confidence = float(
                    score
                    * math.sqrt(max(sync, 1.0))
                    * math.sqrt(max(sfd, 1.0))
                    * math.sqrt(max(hits, 1))
                )
                raw.append(
                    (
                        confidence,
                        float(start),
                        float(cfo),
                        int(peak_bin),
                        float(power),
                        float(sync),
                        int(hits),
                        projector,
                        int(phase_offset),
                    )
                )

    selected_limit = int(raw_candidate_limit) if raw_candidate_limit is not None else max(30, int(max_candidates) * 2)
    selected_limit = max(1, selected_limit)
    selected: list[
        tuple[
            float,
            float,
            float,
            int,
            float,
            float,
            int,
            np.ndarray | None,
            int,
        ]
    ] = []
    # Build one ranked bucket for every phase x stream, then draw candidates
    # round-robin under one *global* budget.  Pooling all rows lets aliases from
    # a strong phase starve weak targets; assigning a full quota independently
    # to the main and residual streams silently doubles refinement work.  The
    # round-robin policy gives every non-empty bucket an early opportunity yet
    # never refines more than selected_limit proposals in total.
    selection_buckets: list[list[tuple]] = []
    for phase_offset in scan_phases:
        for residual_group in (False, True):
            group_rows = sorted(
                (
                    row
                    for row in raw
                    if row[8] == int(phase_offset)
                    and (row[7] is not None) == residual_group
                ),
                key=lambda row: row[0],
                reverse=True,
            )
            unique_group_rows: list[tuple] = []
            for row in group_rows:
                _, start, cfo, *_ = row
                projector = row[7]
                if any(
                    abs(start - old[1]) < 0.75 * cfg.samples_per_symbol
                    and abs(float(cfo) - float(old[2])) <= 1.5
                    and (
                        projector is None
                        or old[7] is not None
                        and abs(np.vdot(projector, old[7])) >= 0.97
                    )
                    for old in unique_group_rows
                ):
                    continue
                unique_group_rows.append(row)
            if unique_group_rows:
                selection_buckets.append(unique_group_rows)

    bucket_rank = 0
    while len(selected) < selected_limit:
        added = False
        for bucket in selection_buckets:
            if bucket_rank >= len(bucket):
                continue
            selected.append(bucket[bucket_rank])
            added = True
            if len(selected) >= selected_limit:
                break
        if not added:
            break
        bucket_rank += 1

    def in_cfo_range(cfo: float) -> bool:
        return float(cfo_min) <= float(cfo) <= float(cfo_max)

    def refine_priority(row) -> tuple[int, float, float, float]:
        confidence, _, cfo, _, _, sync, hits, _, _ = row
        return (int(in_cfo_range(cfo)), float(hits), float(confidence), float(sync))

    selected.sort(key=refine_priority, reverse=True)
    estimates: list[dict] = []
    coherent_refine_budget = max(1, min(int(max_candidates), selected_limit))
    coherent_refines_used = 0
    fast_grid_refine_budget = max(1, min(int(max_candidates), selected_limit))
    fast_grid_refines_used = 0

    for u, (
        confidence,
        start,
        cfo,
        peak_bin,
        power,
        _sync,
        hits,
        projector,
        detector_phase_offset,
    ) in enumerate(selected):
        if fast_single_node:
            projection_origin = 0
            refine_start_seed = float(start)
            if projector is None:
                refine_samples = x
            else:
                # A busy interval can be several seconds long.  Projecting it
                # once per residual candidate made the fallback scale with
                # busy-region length.  SFD refinement only needs the local
                # frame head, so keep a fixed 17-symbol slice instead.
                projection_origin = max(0, int(math.floor(start)) - 2 * cfg.samples_per_symbol)
                projection_end = min(
                    x.shape[1],
                    int(math.ceil(start)) + 15 * cfg.samples_per_symbol,
                )
                refine_samples = (
                    np.conj(projector) @ x[:, projection_origin:projection_end]
                )[None, :].astype(np.complex64)
                refine_start_seed = float(start) - float(projection_origin)
            sfd_start, sfd_cfo, cto_samples, sfd_struct_score, _, _ = sfd_anchored_start_cfo_refine(
                refine_samples,
                refine_start_seed,
                cfg,
                # Interleaved scan phases already place the seed within at
                # most half a phase spacing of the packet start.  Searching a
                # full neighbouring chirp here lets a weak candidate jump to
                # a stronger packet's SFD and later disappear as a duplicate.
                # Keep the legacy +/-1-symbol capture range only when there is
                # a single coarse scan phase.
                symbol_radius=0 if len(scan_phases) > 1 else 1,
                # LoRa start/CFO aliases can put the coarse peak close to
                # +/-M/2 even when the physical CFO is only a few bins.  This
                # is a de-aliasing radius, not the accepted physical CFO
                # range; final hypotheses are still filtered by cfo_min/max.
                local_radius_bins=int(max(96.0, abs(cfo_min), abs(cfo_max))),
                use_integer_alias_branch=bool(use_integer_alias_branch),
                coarse_up_bin=(float(cfo) if len(scan_phases) > 1 else None),
                physical_cfo_min=(
                    float(cfo_min) if len(scan_phases) > 1 else None
                ),
                physical_cfo_max=(
                    float(cfo_max) if len(scan_phases) > 1 else None
                ),
                max_start_correction_samples=(
                    0.75
                    * float(scan_step)
                    / float(max(1, len(scan_phases)))
                    if len(scan_phases) > 1
                    else None
                ),
            )
            sfd_start += float(projection_origin)
            raw_cfo_is_physical = in_cfo_range(float(cfo))
            sfd_cfo_is_physical = in_cfo_range(float(sfd_cfo))
            sfd_cfo_is_consistent = abs(float(sfd_cfo) - float(cfo)) <= 2.5
            sfd_start_is_local = abs(float(sfd_start) - float(start)) <= 1.75 * cfg.samples_per_symbol
            use_sfd_anchor = (
                sfd_struct_score > 0.0
                and sfd_cfo_is_physical
                and sfd_start_is_local
                and (sfd_cfo_is_consistent or not raw_cfo_is_physical)
            )
            if use_sfd_anchor:
                final_start = float(math.floor(float(sfd_start)))
                joint_sto = float(float(sfd_start) - final_start)
                final_cfo = float(sfd_cfo)
                struct_score = float(sfd_struct_score)
            else:
                final_start = float(start)
                joint_sto = 0.0
                final_cfo = float(cfo)
                cto_samples = 0.0
                struct_score = float(confidence)

            # The SFD-only shortcut can lock to a start/CFO alias when the
            # coarse detector is one or more chirp bins away from the physical
            # track.  This is especially common at 4x oversampling: shifting
            # the window and shifting CFO produce nearly equivalent preamble
            # peaks, while only one hypothesis aligns the whole frame.  The
            # original SP frontend also ran a local separated-preamble grid
            # before its joint STO refinement.  Keep the cheap SFD path for
            # clear candidates, but restore that local grid as a bounded
            # fallback when the SFD structure is weak or was not accepted.
            fast_grid_refine_used = False
            anchor_sfd_score = float(
                sfd_score(
                    refine_samples,
                    int(round(final_start + joint_sto - projection_origin)),
                    final_cfo,
                    cfg,
                )
            )
            needs_fast_grid_refine = (
                fast_grid_refine
                and (not use_sfd_anchor or anchor_sfd_score < 50.0)
                and int(hits) >= 6
                and float(confidence) >= 1.0e3
                and fast_grid_refines_used < fast_grid_refine_budget
            )
            if needs_fast_grid_refine:
                fast_grid_refines_used += 1
                refined_start, refined_score, refined_peak, refined_cfo, refined_power = (
                    refine_detection_candidate_fast(
                        x,
                        int(round(start)),
                        cfg,
                        search_radius_samples=int(round(0.75 * cfg.samples_per_symbol)),
                        stable_streams=stable_streams,
                    )
                )
                refined_is_local = abs(float(refined_start) - float(start)) <= 0.75 * cfg.samples_per_symbol
                refined_is_physical = in_cfo_range(float(refined_cfo))
                refined_frame_score = fixed_cfo_frame_score(x, refined_start, refined_cfo, cfg)
                anchor_frame_score = fixed_cfo_frame_score(x, final_start + joint_sto, final_cfo, cfg)
                if (
                    refined_is_local
                    and refined_is_physical
                    and refined_frame_score > anchor_frame_score
                ):
                    final_start = float(refined_start)
                    joint_sto = 0.0
                    final_cfo = float(refined_cfo)
                    power = float(max(power, refined_power))
                    cto_samples = 0.0
                    struct_score = float(max(refined_score, refined_frame_score))
                    fast_grid_refine_used = True

            aligned_start = float(final_start) + float(joint_sto)
            coherent_score, coherent_cfo, coherent_channel, coherent_peak, coherent_power, coherent_metric, coherent_hits = (
                coherent_preamble_track_score(
                    x,
                    aligned_start,
                    final_cfo,
                    cfg,
                    radius_bins=1,
                    eps_grid=11,
                    cache=preamble_cache,
                )
            )
            channel_score, channel, local_peak = preamble_channel_near_cfo(
                x,
                aligned_start,
                final_cfo,
                cfg,
                cache=preamble_cache,
            )
            if coherent_score > max(channel_score, 1e-30):
                channel_score = float(coherent_score)
                channel = coherent_channel
                local_peak = int(coherent_peak)
                power = float(max(power, coherent_power))

            if channel_score < min_coherent_metric or not in_cfo_range(final_cfo):
                continue
            continuous_cfo = float(final_cfo)
            rounded_cfo = float(math.floor(continuous_cfo + 0.5))
            final_sfd_confidence = float(
                sfd_score(
                    refine_samples,
                    int(round(aligned_start - projection_origin)),
                    rounded_cfo,
                    cfg,
                )
            )
            final_sync_confidence = float(
                sync_word_score(
                    refine_samples,
                    int(round(aligned_start - projection_origin)),
                    rounded_cfo,
                    cfg,
                )
            )
            estimates.append(
                {
                    "packet_index": int(u),
                    "start_sample": float(final_start),
                    "cfo_bins": rounded_cfo,
                    "continuous_cfo_bins": continuous_cfo,
                    "sto_samples": float(joint_sto),
                    "channel": complex_pairs(channel),
                    "confidence": float(confidence),
                    "sfd_confidence": final_sfd_confidence,
                    "sync_confidence": final_sync_confidence,
                    "ml_cfo_bins": rounded_cfo,
                    "ml_continuous_cfo_bins": continuous_cfo,
                    "ml_coherent_metric": float(channel_score),
                    "peak_bin": int(local_peak),
                    "power": float(power),
                    "cto_samples": float(cto_samples),
                    "pcube_track_hits": int(hits),
                    "pcube_structure_score": float(struct_score),
                    "pcube_used_refined": bool(use_sfd_anchor or fast_grid_refine_used),
                    "pcube_fast_refine_enabled": bool(fast_grid_refine_used),
                    "pcube_coherent_score": float(coherent_score),
                    "preamble_phase_drift_cfo_bins": float(coherent_cfo),
                    "pcube_coherent_metric": float(coherent_metric),
                    "pcube_coherent_hits": int(coherent_hits),
                    "frontend_candidate_stage": (
                        "local_spatial_residual_fast_sfd"
                        if projector is not None
                        else "stable_pca_real_cfo_fast_sfd"
                    ),
                    "pre_joint_start_sample": float(start),
                    "pre_joint_cfo_bins": float(cfo),
                    "joint_cfo_delta_bins": float(abs(continuous_cfo - float(cfo))),
                    "joint_start_delta_samples": float(abs(aligned_start - float(start))),
                    "joint_refine_accepted": bool(use_sfd_anchor),
                    "detector_scan_phase_samples": int(detector_phase_offset),
                }
            )
            continue

        use_fast_refine = int(hits) >= 6 and float(confidence) >= 1.0e3
        if use_fast_refine:
            fixed_start, fixed_score = refine_start_fixed_cfo(x, start, cfo, cfg)
            refined_start, refined_score, refined_peak, refined_cfo, refined_power = refine_detection_candidate_fast(
                x,
                int(round(start)),
                cfg,
                search_radius_samples=int(round(0.75 * cfg.samples_per_symbol)),
                stable_streams=stable_streams,
            )
        else:
            fixed_start, fixed_score = float(start), 0.0
            refined_start, refined_score, refined_peak, refined_cfo, refined_power = (
                float(start),
                0.0,
                int(peak_bin),
                float(cfo),
                float(power),
            )

        fixed_sync = sync_word_score(x, int(round(fixed_start)), cfo, cfg)
        fixed_sfd = sfd_score(x, int(round(fixed_start)), cfo, cfg)
        refined_sync = sync_word_score(x, int(round(refined_start)), refined_cfo, cfg)
        refined_sfd = sfd_score(x, int(round(refined_start)), refined_cfo, cfg)
        refined_cfo_is_stable = abs(float(refined_cfo) - float(cfo)) <= 1.25
        use_refined = use_fast_refine and (
            (
                refined_cfo_is_stable
                and abs(float(refined_start) - float(fixed_start)) <= 0.25 * cfg.samples_per_symbol
                and refined_sfd >= max(50.0, 20.0 * max(fixed_sfd, 1e-30))
                and refined_sync >= 0.2 * max(fixed_sync, 1e-30)
            )
            or (
                refined_cfo_is_stable
                and abs(float(refined_start) - float(fixed_start))
                <= 0.25 * cfg.samples_per_symbol
                and refined_sync >= 0.8 * max(fixed_sync, 1e-30)
            )
        )
        if use_refined:
            final_start = float(refined_start)
            final_cfo = float(refined_cfo)
            final_power = float(refined_power)
            struct_score = float(refined_score)
        else:
            final_start = float(fixed_start)
            final_cfo = float(cfo)
            final_power = float(power)
            struct_score = float(fixed_score)

        pre_joint_start = float(final_start)
        pre_joint_cfo = float(final_cfo)
        joint_start, joint_sto, joint_cfo, joint_score, cto_samples = joint_start_cfo_sto_refine(x, final_start, final_cfo, cfg)
        joint_cfo_delta = abs(float(joint_cfo) - float(pre_joint_cfo))
        joint_start_delta = abs((float(joint_start) + float(joint_sto)) - float(pre_joint_start))
        joint_is_consistent = joint_cfo_delta <= 2.25 and joint_start_delta <= 0.75 * cfg.samples_per_symbol
        joint_accepted = bool(joint_score > max(struct_score, 0.0) and joint_is_consistent)
        if joint_accepted:
            final_start = float(joint_start)
            final_cfo = float(joint_cfo)
            struct_score = float(joint_score)
        else:
            joint_sto = 0.0
            cto_samples = 0.0
        aligned_start = float(final_start) + float(joint_sto)

        coherent_score, coherent_cfo, coherent_channel, coherent_peak, coherent_power, coherent_metric, coherent_hits = (
            coherent_preamble_track_score(x, aligned_start, final_cfo, cfg, radius_bins=1, eps_grid=21, cache=preamble_cache)
        )
        channel_score, channel, local_peak = preamble_channel_near_cfo(x, aligned_start, final_cfo, cfg, cache=preamble_cache)
        if coherent_score > max(channel_score, 1e-30):
            channel_score = float(coherent_score)
            channel = coherent_channel
            local_peak = int(coherent_peak)
            final_power = float(max(final_power, coherent_power))

        nonphysical_cfo = not in_cfo_range(final_cfo)
        needs_coherent_refine = (
            (channel_score < float(min_coherent_metric) or nonphysical_cfo)
            and int(hits) >= 8
            and coherent_refines_used < coherent_refine_budget
        )
        if needs_coherent_refine:
            coherent_refines_used += 1
            sfd_start, _, _, sfd_struct_score, _, _ = sfd_anchored_start_cfo_refine(x, start, cfg)
            refine_seed = float(sfd_start) if abs(float(sfd_start) - float(start)) <= 2.0 * cfg.samples_per_symbol else float(start)
            coh_start, coh_cfo, coh_channel, coh_peak, coh_power, coh_score, coh_metric = refine_start_cfo_coherent(
                x,
                refine_seed,
                cfg,
                cfo_min=float(cfo_min),
                cfo_max=float(cfo_max),
                radius_samples=(
                    0.5 * cfg.samples_per_symbol
                    if refine_seed != float(start)
                    else 1.5 * cfg.samples_per_symbol
                ),
            )
            if coh_score > max(channel_score, 1e-30):
                final_start = float(math.floor(coh_start))
                joint_sto = float(coh_start - math.floor(coh_start))
                final_cfo = float(coh_cfo)
                channel = coh_channel
                local_peak = int(coh_peak)
                final_power = float(max(final_power, coh_power))
                channel_score = float(coh_score)
                coherent_score = float(coh_score)
                coherent_metric = float(coh_metric)
                struct_score = max(float(sfd_struct_score), fixed_cfo_frame_score(x, final_start, final_cfo, cfg))

        if channel_score < min_coherent_metric:
            continue
        continuous_cfo = float(final_cfo)
        rounded_cfo = float(math.floor(continuous_cfo + 0.5))
        estimates.append(
            {
                "packet_index": int(u),
                "start_sample": float(final_start),
                "cfo_bins": rounded_cfo,
                "continuous_cfo_bins": continuous_cfo,
                "sto_samples": float(joint_sto),
                "channel": complex_pairs(channel),
                "confidence": float(confidence),
                "sfd_confidence": float(sfd_score(x, int(round(float(final_start) + float(joint_sto))), rounded_cfo, cfg)),
                "sync_confidence": float(
                    sync_word_score(
                        x,
                        int(round(float(final_start) + float(joint_sto))),
                        rounded_cfo,
                        cfg,
                    )
                ),
                "ml_cfo_bins": rounded_cfo,
                "ml_continuous_cfo_bins": continuous_cfo,
                "ml_coherent_metric": float(channel_score),
                "peak_bin": int(local_peak),
                "power": float(final_power),
                "cto_samples": float(cto_samples),
                "pcube_track_hits": int(hits),
                "pcube_structure_score": float(struct_score),
                "pcube_used_refined": bool(use_refined),
                "pcube_fast_refine_enabled": bool(use_fast_refine),
                "pcube_coherent_score": float(coherent_score),
                "preamble_phase_drift_cfo_bins": float(coherent_cfo),
                "pcube_coherent_metric": float(coherent_metric),
                "pcube_coherent_hits": int(coherent_hits),
                "frontend_candidate_stage": "stable_pca_real_cfo",
                "pre_joint_start_sample": float(pre_joint_start),
                "pre_joint_cfo_bins": float(pre_joint_cfo),
                "joint_cfo_delta_bins": float(joint_cfo_delta),
                "joint_start_delta_samples": float(joint_start_delta),
                "joint_refine_accepted": bool(joint_accepted),
                "detector_scan_phase_samples": int(detector_phase_offset),
            }
        )

    def final_priority(est: dict) -> tuple[int, int, float]:
        cfo = float(est.get("continuous_cfo_bins", est.get("cfo_bins", 0.0)))
        hits = int(est.get("pcube_track_hits", 0))
        score = float(est.get("pcube_structure_score", 0.0)) * math.sqrt(max(float(est.get("confidence", 0.0)), 1.0))
        return int(in_cfo_range(cfo)), hits, score

    estimates = [
        est
        for est in estimates
        if float(est.get("sfd_confidence", 0.0)) >= float(min_sfd_score)
        and float(est.get("sync_confidence", float("inf")))
        >= float(min_refined_sync_score)
    ]
    final_limit = int(raw_candidate_limit) if raw_candidate_limit is not None else max(30, int(max_candidates))
    final_limit = max(1, final_limit)
    final_estimates: list[dict] = []
    final_buckets: list[list[dict]] = []
    for residual_group in (False, True):
        group_estimates = sorted(
            (
                est
                for est in estimates
                if (
                    est.get("frontend_candidate_stage")
                    == "local_spatial_residual_fast_sfd"
                )
                == residual_group
            ),
            key=final_priority,
            reverse=True,
        )
        if group_estimates:
            final_buckets.append(group_estimates)
    final_rank = 0
    while len(final_estimates) < final_limit:
        added = False
        for bucket in final_buckets:
            while final_rank < len(bucket) and any(
                same_packet_estimate(bucket[final_rank], old, cfg)
                for old in final_estimates
            ):
                # This bucket's current rank aliases an estimate already kept
                # from the other stream.  Consume it without consuming budget.
                bucket.pop(final_rank)
            if final_rank >= len(bucket):
                continue
            final_estimates.append(bucket[final_rank])
            added = True
            if len(final_estimates) >= final_limit:
                break
        if not added:
            break
        final_rank += 1
    final_estimates.sort(key=lambda est: float(est["start_sample"]) + float(est.get("sto_samples", 0.0)))
    return final_estimates


def detected_estimates_real(
    samples,
    cfg: LoRaConfig,
    *,
    max_candidates: int,
    raw_candidate_limit: int | None = None,
    threshold: float,
    step_samples: int,
    scan_phase_count: int = 1,
    min_sync_score: float,
    min_coherent_metric: float,
    cfo_min: float,
    cfo_max: float,
    min_sfd_score: float = 10.0,
    min_refined_sync_score: float = 500.0,
    use_local_projection_tracks: bool = False,
    use_spatial_residual_tracks: bool = False,
    fast_single_node: bool = True,
    fast_grid_refine: bool = False,
    stable_top_k: int = 10,
    stable_min_hits: int = 4,
    stable_max_tracks: int = 4,
    stable_chirp_count: int | None = None,
) -> tuple[list[dict], list[SyncCandidate]]:
    return (
        pcube_sp_estimates_real(
            samples,
            cfg,
            max_candidates=max_candidates,
            raw_candidate_limit=raw_candidate_limit,
            threshold=threshold,
            step_samples=step_samples,
            scan_phase_count=scan_phase_count,
            min_sync_score=min_sync_score,
            min_coherent_metric=min_coherent_metric,
            cfo_min=cfo_min,
            cfo_max=cfo_max,
            min_sfd_score=min_sfd_score,
            min_refined_sync_score=min_refined_sync_score,
            use_local_projection_tracks=use_local_projection_tracks,
            use_spatial_residual_tracks=use_spatial_residual_tracks,
            fast_single_node=fast_single_node,
            fast_grid_refine=fast_grid_refine,
            stable_top_k=stable_top_k,
            stable_min_hits=stable_min_hits,
            stable_max_tracks=stable_max_tracks,
            stable_chirp_count=stable_chirp_count,
        ),
        [],
    )
