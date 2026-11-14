"""评估最终 MRC/SP-Dechirp 接收链路。

脚本功能：
1. 用 clean pos 包合成并发双天线接收信号；
2. 运行 oracle 参数和检测估计参数两条链路；
3. 输出 MRC 基线与 SP-Dechirp 的 SER/PRR。
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sp_noise_competition import (
    DEFAULT_NOISE_FALSE_ALARM,
    POLICY as SP_LAMBDA_POLICY,
    TWO_PACKET_POLICY,
    select_with_noise,
)

from lora_mrc_sp_core import (
    LoRaConfig,
    add_fractional_waveform,
    apply_rf_calibration,
    compensate_symbol_window,
    decode_packet_branch,
    fixed_mrc_branch_parameters,
    fractional_read_2d,
    instantaneous_chirp,
    lora_symbol_fft,
    peak_margin,
    signed_bin,
)
from sp_detection_frontend import (
    ReferencePacket,
    build_references,
    channel_coherence,
    detected_estimates,
    load_scene,
    match_by_start,
    packet_ser,
)
from real_usrp_clean_packet_synth import load_extracted, save_synthesized


DEFAULT_SOURCE_ORDER = (9, 6, 20, 4, 17, 1, 25, 15, 10, 21)


@dataclass(frozen=True)
class SPDecodeStats:
    bins: list[int]
    top_bins: list[list[int]]
    margins: list[float]
    truth_margins: list[float]
    target_powers: list[float]
    blocker_powers: list[float]


@dataclass(frozen=True)
class SPPacketReliability:
    """SP 前端传给包级 lambda 选择器的可靠性参数。"""

    theta_obs: float
    theta_drift: float
    theta_total: float
    L: float
    power: float
    noise_sigma2: float
    robust_hit_count: int
    certified: bool = False
    U_max: float = 1.0
    lambda_sp: float = 0.0


def source_label(meta: dict) -> str:
    return Path(str(meta.get("source_file", "unknown"))).stem


def parse_source_order(value: str) -> tuple[int, ...]:
    if not value.strip():
        return DEFAULT_SOURCE_ORDER
    return tuple(int(x.strip()) for x in value.split(",") if x.strip())


def parse_offset_deltas(value: str, packet_count: int) -> list[float] | None:
    if not value.strip():
        return None
    deltas = [float(x.strip()) for x in value.split(",") if x.strip()]
    if len(deltas) == packet_count - 1:
        deltas = [0.0] + deltas
    if len(deltas) != packet_count:
        raise ValueError("offset deltas must contain either packet_count or packet_count-1 values")
    if abs(deltas[0]) > 1e-12:
        raise ValueError("the first offset delta must be zero")
    return deltas


def parse_rf_correction(value: str) -> np.ndarray | None:
    """解析两路射频链复校准系数，格式：real0,imag0;real1,imag1。"""

    if not value.strip():
        return None
    items = [part.strip() for part in value.split(";") if part.strip()]
    vals: list[complex] = []
    for item in items:
        pair = [float(x.strip()) for x in item.split(",") if x.strip()]
        if len(pair) != 2:
            raise ValueError("rf correction must use 'real0,imag0;real1,imag1'")
        vals.append(complex(pair[0], pair[1]))
    if len(vals) != 2:
        raise ValueError("rf correction must contain exactly two complex coefficients")
    return np.asarray(vals, dtype=np.complex64)


def synthesize_ordered_collision(
    clean_path: Path,
    out_path: Path,
    cfg: LoRaConfig,
    *,
    source_order: tuple[int, ...],
    seed: int,
    offset_range: tuple[float, float],
    offset_deltas: list[float] | None = None,
    guard_symbols: float = 3.0,
) -> tuple[np.ndarray, dict]:
    packets, clean_meta = load_extracted(clean_path)
    metas = clean_meta["packets"] if isinstance(clean_meta, dict) and "packets" in clean_meta else clean_meta
    rng = np.random.default_rng(seed)
    starts = [guard_symbols * cfg.samples_per_symbol + float(rng.random())]
    if offset_deltas is None:
        deltas = [0.0]
        for _ in range(1, len(source_order)):
            delta = float(rng.uniform(offset_range[0], offset_range[1]))
            deltas.append(delta)
            starts.append(starts[-1] + delta * cfg.samples_per_symbol)
    else:
        deltas = [float(x) for x in offset_deltas]
        for delta in deltas[1:]:
            if delta < offset_range[0] or delta > offset_range[1]:
                raise ValueError("explicit offset delta outside configured range")
            starts.append(starts[-1] + delta * cfg.samples_per_symbol)
    total_len = int(math.ceil(starts[-1] + cfg.frame_samples + guard_symbols * cfg.samples_per_symbol))
    samples = np.zeros((2, total_len), dtype=np.complex64)
    truth_packets: list[dict] = []
    for out_idx, src in enumerate(source_order):
        snippet = packets[int(src)]
        start = float(starts[out_idx])
        for ch in range(2):
            add_fractional_waveform(samples[ch], snippet[ch], start, 1.0 + 0.0j)
        meta = metas[int(src)]
        truth_packets.append(
            {
                "output_packet_index": int(out_idx),
                "source_packet_index": int(src),
                "source_label": source_label(meta),
                "source_meta": meta,
                "start_sample": start,
                "delta_from_previous_symbols": float(deltas[out_idx]),
                "scale": 1.0,
            }
        )
    metadata = {
        "source": "evaluate_sp_dechirp_real_pos.synthesize_ordered_collision",
        "packet_count": len(source_order),
        "offset_symbols_range": [float(offset_range[0]), float(offset_range[1])],
        "offset_rule": "each packet starts after the previous packet by one random fractional-symbol offset",
        "seed": int(seed),
        "normalize_rms": False,
        "source_order": list(map(int, source_order)),
        "explicit_offset_deltas": offset_deltas is not None,
        "config": asdict(cfg),
        "packets": truth_packets,
    }
    save_synthesized(out_path, samples, metadata, cfg)
    return samples, metadata


def coherence_squared(a: np.ndarray, b: np.ndarray) -> float:
    aa = float(np.vdot(a, a).real)
    bb = float(np.vdot(b, b).real)
    return float(abs(np.vdot(a, b)) ** 2 / max(aa * bb, 1e-30))


def unit_channel(h: np.ndarray) -> np.ndarray:
    norm = math.sqrt(float(np.vdot(h, h).real))
    if norm <= 0.0:
        return np.asarray([1.0 + 0.0j, 0.0 + 0.0j], dtype=np.complex128)
    return np.asarray(h, dtype=np.complex128).reshape(2) / norm


def channel_angle(a: np.ndarray, b: np.ndarray) -> float:
    au = unit_channel(a)
    bu = unit_channel(b)
    c = float(np.clip(abs(np.vdot(au, bu)), 0.0, 1.0))
    return float(math.acos(c))


def estimate_sp_whitener(samples: np.ndarray, meta: dict, cfg: LoRaConfig) -> tuple[np.ndarray, np.ndarray, float]:
    """按 SP 方案从背景区估计噪声协方差并预白化。

    合成场景的包外区域通常接近全零；这种情况下返回单位白化矩阵，避免
    把数值零噪声放大。
    """

    mask = np.ones(samples.shape[1], dtype=bool)
    guard = int(round(0.5 * cfg.samples_per_symbol))
    for packet in meta.get("packets", []):
        start = max(0, int(math.floor(float(packet["start_sample"]))) - guard)
        stop = min(samples.shape[1], int(math.ceil(float(packet["start_sample"]) + cfg.frame_samples)) + guard)
        mask[start:stop] = False
    noise = np.asarray(samples[:, mask], dtype=np.complex128)
    if noise.shape[1] < 128 or float(np.mean(np.abs(noise) ** 2)) < 1e-18:
        w = np.eye(samples.shape[0], dtype=np.complex128)
        return np.asarray(samples, dtype=np.complex64), w, 1e-12
    cov = (noise @ noise.conj().T) / max(1, noise.shape[1])
    cov += np.eye(cov.shape[0], dtype=np.complex128) * max(float(np.trace(cov).real), 1e-18) * 1e-6
    vals, vecs = np.linalg.eigh(cov)
    floor = max(float(np.max(vals).real), 1e-18) * 1e-6
    vals = np.maximum(vals.real, floor)
    w = (vecs @ np.diag(1.0 / np.sqrt(vals)) @ vecs.conj().T).astype(np.complex128)
    white = (w @ np.asarray(samples, dtype=np.complex128)).astype(np.complex64)
    wn = w @ noise
    sigma2_time = float(np.mean(np.abs(wn) ** 2))
    return white, w, max(cfg.m * sigma2_time, 1e-12)


def transform_estimate_channels(estimates: list[dict], w: np.ndarray) -> list[dict]:
    out: list[dict] = []
    for est in estimates:
        row = dict(est)
        h = np.asarray([complex(r, i) for r, i in est["channel"]], dtype=np.complex128)
        row["channel"] = [[float(np.real(v)), float(np.imag(v))] for v in (w @ h)]
        out.append(row)
    return out


def robust_preamble_channel_sp(
    samples: np.ndarray,
    start_sample: float,
    cfo_bins: float,
    sto_samples: float,
    cfg: LoRaConfig,
) -> tuple[np.ndarray, SPPacketReliability]:
    """SP 碰撞鲁棒前导信道估计、leave-one-out 置信锥和漂移估计。"""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    center = int(round(cfo_bins)) % cfg.m
    signed_center = float(signed_bin(center, cfg.m))
    eps = float(cfo_bins) - signed_center
    local = np.asarray([(center + dk) % cfg.m for dk in range(-2, 3)], dtype=np.int64)
    coeff = np.asarray([0.12, 0.45, 1.0, 0.45, 0.12], dtype=np.float64)
    snapshots: list[np.ndarray] = []
    isolation: list[float] = []
    powers: list[float] = []
    for p in range(cfg.preamble_len):
        s = float(start_sample) + float(sto_samples) + p * cfg.samples_per_symbol
        if s < 0.0 or s + cfg.samples_per_symbol > samples.shape[1]:
            continue
        window = fractional_read_2d(samples, s, cfg.samples_per_symbol)
        spec = np.vstack([lora_symbol_fft(window[ch] * downchirp, cfg) for ch in range(samples.shape[0])])
        vec = np.sum(spec[:, local] * coeff[None, :], axis=1)
        vec = vec * np.exp(-1j * 2.0 * math.pi * eps * p)
        local_energy = float(np.sum(np.abs(spec[:, local]) ** 2))
        total_energy = float(np.sum(np.abs(spec) ** 2)) + 1e-30
        snapshots.append(vec)
        isolation.append(local_energy / total_energy)
        powers.append(float(np.vdot(vec, vec).real))
    if not snapshots:
        h0 = np.asarray([1.0 + 0.0j, 0.0 + 0.0j], dtype=np.complex128)
        rel = SPPacketReliability(0.5, 0.0, 0.5, float(math.cos(0.5) ** 2), 1.0, 1e-12, 0)
        return h0, rel

    z = np.asarray(snapshots, dtype=np.complex128)
    iso = np.asarray(isolation, dtype=np.float64)
    iso = np.maximum(iso, np.percentile(iso, 25))
    w_iso = iso / (float(np.max(iso)) + 1e-30)
    h_init = np.sum(z * w_iso[:, None], axis=0) / (float(np.sum(w_iso)) + 1e-30)
    angles = np.asarray([channel_angle(row, h_init) for row in z], dtype=np.float64)
    w_res = np.exp(-((angles / 0.35) ** 2))
    weights = np.maximum(w_iso * w_res, 1e-6)
    h = np.sum(z * weights[:, None], axis=0) / (float(np.sum(weights)) + 1e-30)

    loo_angles: list[float] = []
    if z.shape[0] >= 4:
        for i in range(z.shape[0]):
            ww = np.delete(weights, i)
            zz = np.delete(z, i, axis=0)
            h_loo = np.sum(zz * ww[:, None], axis=0) / (float(np.sum(ww)) + 1e-30)
            loo_angles.append(channel_angle(h_loo, h))
    theta_obs = float(np.quantile(loo_angles, 0.80)) if loo_angles else 0.35
    mid = max(1, z.shape[0] // 2)
    h_early = np.sum(z[:mid] * weights[:mid, None], axis=0) / (float(np.sum(weights[:mid])) + 1e-30)
    h_late = np.sum(z[mid:] * weights[mid:, None], axis=0) / (float(np.sum(weights[mid:])) + 1e-30) if z.shape[0] > mid else h_early
    theta_drift = channel_angle(h_early, h_late)
    theta_rf = 0.02
    theta_total = float(min(math.pi / 2.0, theta_obs + theta_drift + theta_rf))
    rel = SPPacketReliability(
        theta_obs=theta_obs,
        theta_drift=theta_drift,
        theta_total=theta_total,
        L=float(math.cos(theta_total) ** 2),
        power=float(np.vdot(h, h).real),
        noise_sigma2=1e-12,
        robust_hit_count=int(z.shape[0]),
    )
    return h, rel


def choose_lambda_sp(
    target_index: int,
    reliabilities: list[SPPacketReliability],
    channels: list[np.ndarray],
    *,
    gamma: float,
    max_lambda: float | None,
    noise_bin_count: int | None = None,
    noise_false_alarm: float = DEFAULT_NOISE_FALSE_ALARM,
    retain_bounded_candidate_cap: float | None = None,
) -> tuple[float, float, bool, list[dict], dict]:
    """Select one preamble-only weight. Noise-policy callers supply bin count.

    noise_bin_count=None retains the historical pair-only analytic helper for
    reproducing old mechanism plots; the receiver always supplies cfg.m-1.
    max_lambda=None removes only the optional global cap, never reliability.
    """

    rel_u = reliabilities[target_index]
    h_u = channels[target_index]
    if rel_u.L <= gamma or len(channels) <= 1:
        reason = (
            "target_reliability_at_or_below_gamma"
            if rel_u.L <= gamma
            else "no_payload_overlapping_competitor"
        )
        return 0.0, 0.0, False, [], {
            "lambda_cap": 0.0,
            "selected_lambda": 0.0,
            "selected_threshold": 0.0,
            "selected_objective": None,
            "candidate_points": [{"lambda": 0.0, "sources": ["boundary_low"], "objective": None}],
            "selection_reason": reason,
            "policy": SP_LAMBDA_POLICY if noise_bin_count is not None else "pair_only_legacy",
            "noise_bin_count": noise_bin_count,
            "noise_false_alarm": noise_false_alarm if noise_bin_count is not None else None,
        }
    theta_u = rel_u.theta_total
    _ = theta_u
    rows: list[dict] = []
    u_max = 0.0
    cap = min(float(max_lambda) if max_lambda is not None else float('inf'),
              (rel_u.L - gamma) / max(1.0 - rel_u.L, 1e-12))
    candidate_sources: dict[float, list[str]] = {}

    def add_candidate(value: float, source: str) -> None:
        lam = float(np.clip(float(value), 0.0, max(0.0, cap)))
        key = round(lam, 12)
        candidate_sources.setdefault(key, [])
        if source not in candidate_sources[key]:
            candidate_sources[key].append(source)

    add_candidate(0.0, "boundary_low")
    add_candidate(cap, "boundary_cap")
    for v, h_v in enumerate(channels):
        if v == target_index:
            continue
        rel_v = reliabilities[v]
        theta_hat = channel_angle(h_u, h_v)
        u_uv = float(math.cos(max(theta_hat - rel_v.theta_total, 0.0)) ** 2)
        u_max = max(u_max, u_uv)
        a_under = rel_u.power * rel_u.L - rel_v.power * u_uv
        b_under = rel_v.power * (1.0 - u_uv) - rel_u.power * (1.0 - rel_u.L)
        sigma2 = max(rel_u.noise_sigma2, rel_v.noise_sigma2, 1e-12)
        c0 = 2.0 * sigma2 * sigma2 + 2.0 * sigma2 * (rel_u.power * rel_u.L + rel_v.power * u_uv)
        c2 = 2.0 * sigma2 * sigma2 + 2.0 * sigma2 * (
            rel_u.power * (1.0 - rel_u.L) + rel_v.power * (1.0 - u_uv)
        )
        flip = float("inf")
        if a_under < 0.0 and b_under > 0.0:
            flip = -a_under / max(b_under, 1e-30)
            if 0.0 <= flip <= cap:
                add_candidate(flip, f"pair_{v}_flip")
        if a_under > 0.0 and b_under > 0.0 and c2 > 0.0:
            stat = b_under * c0 / max(a_under * c2, 1e-30)
            if 0.0 <= stat <= cap:
                add_candidate(stat, f"pair_{v}_stat")
        rows.append(
            {
                "interferer_index": int(v),
                "U_uv": u_uv,
                "A_under": float(a_under),
                "B_under": float(b_under),
                "C0": float(c0),
                "C2": float(c2),
                "lambda_flip_under": float(flip),
            }
        )
    if u_max < rel_u.L:
        t_mid = 0.5 * (rel_u.L + u_max)
        lam_mid = t_mid / max(1.0 - t_mid, 1e-12)
        if 0.0 <= lam_mid <= cap:
            add_candidate(lam_mid, "reliable_polarity_midpoint")
    # A handful of deterministic checkpoints makes the bounded one-dimensional
    # search auditable.  Pair-specific flip/peak points above carry the model
    # structure; these checkpoints only cover crossings between pairwise risks.
    for frac in (0.25, 0.50, 0.75):
        add_candidate(cap * frac, f"fixed_checkpoint_{frac:.2f}")
    if retain_bounded_candidate_cap is not None:
        previous_cap=min(cap,float(retain_bounded_candidate_cap))
        add_candidate(previous_cap,'previous_bounded_cap_checkpoint')
        for frac in (0.25,0.50,0.75):
            add_candidate(previous_cap*frac,f'previous_bounded_checkpoint_{frac:.2f}')

    def objective(lam: float) -> float:
        if not rows:
            return 0.0
        vals = [
            (row["A_under"] + lam * row["B_under"]) / math.sqrt(max(row["C0"] + lam * lam * row["C2"], 1e-30))
            for row in rows
        ]
        return float(min(vals))

    evaluated = [
        {
            "lambda": float(lam),
            "sources": list(candidate_sources[lam]),
            "objective": float(objective(float(lam))),
        }
        for lam in sorted(candidate_sources)
    ]
    selected = max(evaluated, key=lambda item: (float(item["objective"]), -float(item["lambda"])))
    best_lam = float(selected["lambda"])
    selected_threshold = best_lam / (1.0 + best_lam)
    certified = bool(u_max < selected_threshold < rel_u.L and best_lam <= cap + 1e-12)
    search_diag = {
        "policy": "pair_only_legacy",
        "noise_bin_count": None,
        "noise_false_alarm": None,
        "lambda_cap": float(cap),
        "selected_lambda": best_lam,
        "selected_threshold": float(selected_threshold),
        "selected_objective": float(selected["objective"]),
        "candidate_points": evaluated,
        "selection_reason": (
            "risk_maximizer" if best_lam > 0.0 else "mrc_is_risk_maximizer"
        ),
    }
    if noise_bin_count is not None:
        search_diag = select_with_noise(
            rows, evaluated, power=rel_u.power, reliability=rel_u.L,
            noise_sigma2=rel_u.noise_sigma2, cap=cap,
            noise_bin_count=noise_bin_count, noise_false_alarm=noise_false_alarm,
        )
        best_lam = float(search_diag['selected_lambda'])
        selected_threshold = best_lam / (1.0 + best_lam)
        certified = bool(u_max < selected_threshold < rel_u.L and best_lam <= cap + 1e-12)
    return best_lam, float(u_max), certified, rows, search_diag


def attach_sp_reliability_and_lambda(
    samples: np.ndarray,
    estimates: list[dict],
    cfg: LoRaConfig,
    *,
    noise_sigma2: float,
    gamma: float,
    max_lambda: float | None = None,
    noise_competition: bool = False,
    noise_two_packet_only: bool = False,
    reference_guard: bool = False,
    physical_samples: np.ndarray | None = None,
    whitener: np.ndarray | None = None,
    remove_multiuser_lambda_cap: bool = False,
    multiuser_lambda_cap: float = 4.0,
) -> list[dict]:
    """为每个检测包补齐 SP 前端输出：鲁棒 h、L/U、noise 和 lambda。"""

    if reference_guard:
        noise_competition = noise_two_packet_only = True

    enriched: list[dict] = []
    reliabilities: list[SPPacketReliability] = []
    channels: list[np.ndarray] = []
    for est in estimates:
        reliability_started_ns = time.perf_counter_ns()
        row = dict(est)
        row.pop("mrc_decision_channel_sp", None)
        cfo = float(row.get("continuous_cfo_bins", row["cfo_bins"]))
        sto = float(row.get("sto_samples", 0.0))
        h_robust, rel = robust_preamble_channel_sp(samples, float(row["start_sample"]), cfo, sto, cfg)
        if rel.robust_hit_count < max(4, cfg.preamble_len // 2):
            h_robust = np.asarray([complex(r, i) for r, i in row["channel"]], dtype=np.complex128)
        rel = SPPacketReliability(
            theta_obs=rel.theta_obs,
            theta_drift=rel.theta_drift,
            theta_total=rel.theta_total,
            L=rel.L,
            power=max(float(np.vdot(h_robust, h_robust).real), 1e-30),
            noise_sigma2=float(noise_sigma2),
            robust_hit_count=rel.robust_hit_count,
        )
        row["channel_sp"] = [[float(np.real(v)), float(np.imag(v))] for v in h_robust]
        row["cfo_bins_sp"] = cfo
        row["sto_samples_sp"] = sto
        row["theta_obs"] = rel.theta_obs
        row["theta_drift"] = rel.theta_drift
        row["theta_total"] = rel.theta_total
        row["L_u"] = rel.L
        row["power_sp"] = rel.power
        row["noise_sigma2_sp"] = rel.noise_sigma2
        row["robust_hit_count"] = rel.robust_hit_count
        enriched.append(row)
        reliabilities.append(rel)
        channels.append(h_robust)
        row["lambda_reliability_elapsed_ms"] = (
            time.perf_counter_ns() - reliability_started_ns
        ) / 1_000_000.0

    frame_samples = float(
        (cfg.payload_start_symbols + cfg.payload_symbol_count) * cfg.samples_per_symbol
    )
    payload_offset_samples = float(cfg.payload_start_symbols * cfg.samples_per_symbol)
    aligned_starts = [
        float(row["start_sample"]) + float(row.get("sto_samples_sp", 0.0))
        for row in enriched
    ]
    for u, row in enumerate(enriched):
        selection_started_ns = time.perf_counter_ns()
        target_payload_start = aligned_starts[u] + payload_offset_samples
        target_end = aligned_starts[u] + frame_samples
        overlap_indices = [
            v
            for v in range(len(enriched))
            if v != u
            and aligned_starts[v] < target_end
            and aligned_starts[v] + frame_samples > target_payload_start
        ]
        local_indices = [u, *overlap_indices]
        use_noise = noise_competition and (not noise_two_packet_only or len(local_indices) == 2)
        lambda_limit = max_lambda
        remove_fixed_cap=bool(remove_multiuser_lambda_cap and not use_noise and len(local_indices)>2)
        if remove_fixed_cap:
            # Remove the historical fixed cap only; choose_lambda_sp retains
            # the reference-reliability bound and the same objective.
            lambda_limit=max_lambda
        elif noise_two_packet_only and not use_noise:
            lambda_limit = min(multiuser_lambda_cap, max_lambda) if max_lambda is not None else multiuser_lambda_cap
        elif max_lambda is None and not use_noise:
            lambda_limit = multiuser_lambda_cap
        lam, u_max, certified, lambda_rows, lambda_search = choose_lambda_sp(
            0,
            [reliabilities[v] for v in local_indices],
            [channels[v] for v in local_indices],
            gamma=gamma,
            max_lambda=lambda_limit,
            noise_bin_count=int(cfg.m) - 1 if use_noise else None,
            retain_bounded_candidate_cap=4.0 if (remove_fixed_cap or (not use_noise and len(local_indices)>2 and multiuser_lambda_cap>4)) else None,
        )
        for pair_row in lambda_rows:
            local_v = int(pair_row["interferer_index"])
            pair_row["interferer_index"] = int(local_indices[local_v])
        row["lambda_sp"] = lam
        row["U_max_sp"] = u_max
        row["certified_sp"] = certified
        row["lambda_pair_rows_sp"] = lambda_rows
        row["lambda_cap_sp"] = float(lambda_search["lambda_cap"])
        if remove_fixed_cap:
            row['lambda_fixed_global_cap_removed_sp']=True
            row['lambda_global_max_sp']=lambda_limit
            row['lambda_range_policy_sp']='multiuser_reliability_bound_only'
        elif not use_noise and len(local_indices)>2 and multiuser_lambda_cap!=4.0:
            row['lambda_global_max_sp']=lambda_limit
            row['lambda_range_policy_sp']=f'multiuser_fixed_cap_{multiuser_lambda_cap:g}'
        row["lambda_threshold_sp"] = float(lambda_search["selected_threshold"])
        row["lambda_objective_sp"] = lambda_search["selected_objective"]
        row["lambda_candidate_points_sp"] = lambda_search["candidate_points"]
        row["overlapping_interferer_count_sp"] = int(len(overlap_indices))
        row["lambda_selection_reason_sp"] = str(
            lambda_search["selection_reason"]
        )
        row["lambda_policy_sp"] = lambda_search["policy"]
        row["lambda_noise_bin_count_sp"] = lambda_search["noise_bin_count"]
        row["lambda_noise_false_alarm_sp"] = lambda_search["noise_false_alarm"]
        row["lambda_pair_objective_sp"] = lambda_search.get("selected_pair_objective")
        row["lambda_noise_objective_sp"] = lambda_search.get("selected_noise_objective")
        row["lambda_noise_max_threshold_sp"] = lambda_search.get("noise_max_threshold")
        if noise_two_packet_only:
            row["lambda_gate_policy_sp"] = TWO_PACKET_POLICY
            row["lambda_gate_reason_sp"] = ("one_overlapping_competitor" if use_noise
                else "retain_legacy_for_non_pair_overlap")
        row["lambda_selection_elapsed_ms"] = (
            time.perf_counter_ns() - selection_started_ns
        ) / 1_000_000.0
        row["lambda_config_elapsed_ms"] = (
            float(row["lambda_reliability_elapsed_ms"])
            + float(row["lambda_selection_elapsed_ms"])
        )
    if reference_guard:
        from sp_reference_guard import apply_reference_guard
        return apply_reference_guard(physical_samples, whitener, enriched, cfg,
            gamma=gamma, max_lambda=max_lambda)
    return enriched


def sp_dechirp_decode_bins(
    samples: np.ndarray,
    start_sample: float,
    cfo_bins: float,
    sto_samples: float,
    channel: np.ndarray,
    cfg: LoRaConfig,
    truth_bins: list[int],
    *,
    lam: float,
) -> SPDecodeStats:
    """SP-Dechirp payload 符号判决。

    对双天线 FFT 结果构造两个投影：
    - P[k]：目标信道方向；
    - Q[k]：目标正交方向。
    最终分数为 |P[k]|^2 - lambda |Q[k]|^2，使目标聚焦、非目标受抑。
    """

    h = np.asarray(channel, dtype=np.complex128).reshape(2)
    norm = math.sqrt(float(np.vdot(h, h).real))
    if norm <= 0.0:
        raise ValueError("SP-Dechirp target channel must be nonzero")
    a = h / norm
    b = np.asarray([-np.conj(a[1]), np.conj(a[0])], dtype=np.complex128)

    decoded: list[int] = []
    top_bins: list[list[int]] = []
    margins: list[float] = []
    truth_margins: list[float] = []
    target_powers: list[float] = []
    blocker_powers: list[float] = []
    downchirp = instantaneous_chirp(0, cfg, up=False)
    for q in range(cfg.payload_symbol_count):
        symbol_start = start_sample + (cfg.payload_start_symbols + q) * cfg.samples_per_symbol
        comp = compensate_symbol_window(samples, symbol_start, cfo_bins, cfg, sto_samples=sto_samples)
        ant_spec = np.vstack([lora_symbol_fft(comp[ch] * downchirp, cfg) for ch in range(comp.shape[0])])
        p_spec = np.conj(a[0]) * ant_spec[0] + np.conj(a[1]) * ant_spec[1]
        q_spec = np.conj(b[0]) * ant_spec[0] + np.conj(b[1]) * ant_spec[1]
        score = (np.abs(p_spec) ** 2 - float(lam) * np.abs(q_spec) ** 2).real
        peak = int(np.argmax(score))
        top_count = min(3, int(score.size))
        top = np.argpartition(score, -top_count)[-top_count:]
        top = top[np.argsort(score[top])[::-1]]
        other = np.delete(score, peak)
        margin = float(score[peak] - (float(np.max(other)) if other.size else -float("inf")))
        truth = int(truth_bins[q]) if q < len(truth_bins) else peak
        truth_other = np.delete(score, truth)
        truth_margin = float(score[truth] - (float(np.max(truth_other)) if truth_other.size else -float("inf")))
        decoded.append(peak)
        top_bins.append([int(v) for v in top])
        margins.append(margin)
        truth_margins.append(truth_margin)
        target_powers.append(float(np.abs(p_spec[truth]) ** 2))
        blocker_powers.append(float(np.abs(q_spec[truth]) ** 2))
    return SPDecodeStats(
        bins=decoded,
        top_bins=top_bins,
        margins=margins,
        truth_margins=truth_margins,
        target_powers=target_powers,
        blocker_powers=blocker_powers,
    )


def sp_projected_spectra(
    samples: np.ndarray,
    start_sample: float,
    cfo_bins: float,
    sto_samples: float,
    channel: np.ndarray,
    cfg: LoRaConfig,
    symbol_index: int,
) -> tuple[np.ndarray, np.ndarray]:
    """返回 SP 理论中的 P[k] 和 Q[k]，用于逐 symbol margin 解释。"""

    h = np.asarray(channel, dtype=np.complex128).reshape(2)
    a = unit_channel(h)
    b = np.asarray([-np.conj(a[1]), np.conj(a[0])], dtype=np.complex128)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    symbol_start = start_sample + (cfg.payload_start_symbols + symbol_index) * cfg.samples_per_symbol
    comp = compensate_symbol_window(samples, symbol_start, cfo_bins, cfg, sto_samples=sto_samples)
    ant_spec = np.vstack([lora_symbol_fft(comp[ch] * downchirp, cfg) for ch in range(comp.shape[0])])
    p_spec = np.conj(a[0]) * ant_spec[0] + np.conj(a[1]) * ant_spec[1]
    q_spec = np.conj(b[0]) * ant_spec[0] + np.conj(b[1]) * ant_spec[1]
    return p_spec, q_spec


def mrc_error_margin_diagnostics(
    samples: np.ndarray,
    start_sample: float,
    cfo_bins: float,
    sto_samples: float,
    channel: np.ndarray,
    cfg: LoRaConfig,
    truth_bins: list[int],
    mrc_bins: list[int],
    sp_bins: list[int],
    lam: float,
) -> list[dict]:
    """输出每个 MRC 错误 symbol 的 A、B、lambda_flip 和实际 lambda。"""

    rows: list[dict] = []
    for q, (mrc_bin, truth_bin) in enumerate(zip(mrc_bins, truth_bins)):
        if int(mrc_bin) == int(truth_bin):
            continue
        p_spec, q_spec = sp_projected_spectra(samples, start_sample, cfo_bins, sto_samples, channel, cfg, q)
        s = int(truth_bin)
        k = int(mrc_bin)
        a_margin = float(np.abs(p_spec[s]) ** 2 - np.abs(p_spec[k]) ** 2)
        b_margin = float(np.abs(q_spec[k]) ** 2 - np.abs(q_spec[s]) ** 2)
        if b_margin > 0.0:
            lambda_flip = max(0.0, -a_margin / b_margin)
        else:
            lambda_flip = float("inf")
        signed_margin = float(a_margin + float(lam) * b_margin)
        rows.append(
            {
                "symbol_index": int(q),
                "truth_bin": s,
                "mrc_bin": k,
                "sp_bin": int(sp_bins[q]) if q < len(sp_bins) else -1,
                "A_s_k": a_margin,
                "B_s_k": b_margin,
                "lambda_flip": float(lambda_flip),
                "lambda_actual": float(lam),
                "signed_margin_at_lambda": signed_margin,
                "mrc_error_repaired_by_sp": bool(q < len(sp_bins) and int(sp_bins[q]) == s),
                "theory_predicts_repair": bool(signed_margin > 0.0),
            }
        )
    return rows


def mrc_decode_bins(
    samples: np.ndarray,
    start_sample: float,
    cfo_bins: float,
    sto_samples: float,
    channel: np.ndarray,
    cfg: LoRaConfig,
) -> tuple[list[int], list[float]]:
    """MRC 基线 payload 符号判决。"""

    decoded = decode_packet_branch(
        samples,
        0,
        start_sample,
        cfo_bins,
        fixed_mrc_branch_parameters(channel),
        cfg,
        sto_samples=sto_samples,
    )
    return [int(d.symbol_bin) for d in decoded.decisions], [float(d.margin_db) for d in decoded.decisions]


def oracle_estimates(meta: dict, refs: dict[int, ReferencePacket]) -> list[dict]:
    estimates: list[dict] = []
    for u, p in enumerate(meta["packets"]):
        ref = refs[int(p["source_packet_index"])]
        estimates.append(
            {
                "packet_index": int(u),
                "start_sample": float(p["start_sample"]),
                "cfo_bins": float(ref.cfo_bins),
                "sto_samples": float(ref.sto_samples),
                "channel": ref.channel,
            }
        )
    return estimates


def evaluate_sp_with_estimates(
    samples: np.ndarray,
    meta: dict,
    cfg: LoRaConfig,
    refs: dict[int, ReferencePacket],
    estimates: list[dict],
) -> dict[str, object]:
    """SP 完整链路：可靠性约束 lambda + signed spectrum + MRC 错误解释。"""

    truth_packets = meta["packets"]
    matched = match_by_start(estimates, truth_packets)
    labels = [str(p.get("source_label", f"src{p['source_packet_index']}")) for p in truth_packets]
    packets: list[dict] = []
    all_diag: list[dict] = []
    for u, (truth, est) in enumerate(zip(truth_packets, matched)):
        src = int(truth["source_packet_index"])
        ref = refs[src]
        if est is None:
            row = {
                "packet_index": int(u),
                "source_index": src,
                "source_label": labels[u],
                "detected": False,
                "mrc_ser": 1.0,
                "sp_ser": 1.0,
                "mrc_success": False,
                "sp_success": False,
                "mrc_error_diagnostics": [],
            }
            packets.append(row)
            continue

        h = np.asarray([complex(r, i) for r, i in est.get("channel_sp", est["channel"])], dtype=np.complex128)
        start = float(est["start_sample"])
        cfo = float(est.get("cfo_bins_sp", est.get("continuous_cfo_bins", est["cfo_bins"])))
        sto = float(est.get("sto_samples_sp", est.get("sto_samples", 0.0)))
        lam = float(est.get("lambda_sp", 0.0))
        mrc_bins, mrc_margins = mrc_decode_bins(samples, start, cfo, sto, h, cfg)
        sp = sp_dechirp_decode_bins(samples, start, cfo, sto, h, cfg, ref.symbol_bins, lam=lam)
        mrc_ser = packet_ser(mrc_bins, ref.symbol_bins)
        sp_ser = packet_ser(sp.bins, ref.symbol_bins)
        diag = mrc_error_margin_diagnostics(samples, start, cfo, sto, h, cfg, ref.symbol_bins, mrc_bins, sp.bins, lam)
        for item in diag:
            item["packet_index"] = int(u)
            item["source_label"] = labels[u]
        all_diag.extend(diag)
        oracle_start = float(truth["start_sample"])
        oracle_cfo = float(ref.cfo_bins)
        row = {
            "packet_index": int(u),
            "source_index": src,
            "source_label": labels[u],
            "detected": True,
            "start_sample": start,
            "cfo_bins": cfo,
            "sto_samples": sto,
            "start_error_samples": start + sto - oracle_start,
            "cfo_error_bins": cfo - oracle_cfo,
            "lambda_sp": lam,
            "L_u": float(est.get("L_u", 0.0)),
            "U_max_sp": float(est.get("U_max_sp", 1.0)),
            "certified_sp": bool(est.get("certified_sp", False)),
            "theta_total": float(est.get("theta_total", 0.0)),
            "power_sp": float(est.get("power_sp", 0.0)),
            "noise_sigma2_sp": float(est.get("noise_sigma2_sp", 0.0)),
            "robust_hit_count": int(est.get("robust_hit_count", 0)),
            "mrc_ser": mrc_ser,
            "sp_ser": sp_ser,
            "mrc_success": bool(mrc_ser <= 0.20),
            "sp_success": bool(sp_ser <= 0.20),
            "mrc_mean_margin_db": float(np.mean(mrc_margins)) if mrc_margins else 0.0,
            "sp_mean_margin": float(np.mean(sp.margins)) if sp.margins else 0.0,
            "sp_mean_truth_margin": float(np.mean(sp.truth_margins)) if sp.truth_margins else 0.0,
            "mrc_error_diagnostics": diag,
        }
        packets.append(row)

    repaired = [d for d in all_diag if d["mrc_error_repaired_by_sp"]]
    predicted = [d for d in all_diag if d["theory_predicts_repair"]]
    finite_start = [abs(float(p["start_error_samples"])) for p in packets if p.get("detected") and math.isfinite(float(p["start_error_samples"]))]
    finite_cfo = [abs(float(p["cfo_error_bins"])) for p in packets if p.get("detected") and math.isfinite(float(p["cfo_error_bins"]))]
    summary = {
        "packet_count": len(packets),
        "symbol_count": len(packets) * cfg.payload_symbol_count,
        "mrc_ser": float(np.mean([p["mrc_ser"] for p in packets])) if packets else 1.0,
        "sp_ser": float(np.mean([p["sp_ser"] for p in packets])) if packets else 1.0,
        "mrc_pdr": int(sum(bool(p["mrc_success"]) for p in packets)),
        "sp_pdr": int(sum(bool(p["sp_success"]) for p in packets)),
        "prr_denominator": len(packets),
        "mrc_error_symbol_count": len(all_diag),
        "sp_repaired_mrc_error_symbol_count": len(repaired),
        "theory_predicted_repair_count": len(predicted),
        "mean_abs_start_error_samples": float(np.mean(finite_start)) if finite_start else float("inf"),
        "mean_abs_cfo_error_bins": float(np.mean(finite_cfo)) if finite_cfo else float("inf"),
    }
    return {"summary": summary, "packets": packets, "mrc_error_symbol_diagnostics": all_diag}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", default="real_usrp_outputs/clean_pos_packets.npz")
    parser.add_argument("--synth-out", default="real_usrp_outputs/synth_sp_pos01to10_offset5_15_seed31.npz")
    parser.add_argument("--out", default="real_usrp_outputs/eval_sp_pos01to10_offset5_15_seed31.json")
    parser.add_argument("--source-order", default="")
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--min-offset-symbols", type=float, default=5.0)
    parser.add_argument("--max-offset-symbols", type=float, default=15.0)
    parser.add_argument("--offset-deltas", default="")
    parser.add_argument("--sp-gamma", type=float, default=0.05)
    parser.add_argument("--sp-lambda-max", type=float, default=None,
                        help="Optional global cap; legacy defaults to 4, experimental noise policy uses reliability cap")
    parser.add_argument("--sp-lambda-policy", choices=("pair_only_legacy", SP_LAMBDA_POLICY, TWO_PACKET_POLICY),
                        default=TWO_PACKET_POLICY)
    parser.add_argument("--rf-correction", default="")
    parser.add_argument("--frontend", choices=("pcube_sp",), default="pcube_sp")
    parser.add_argument("--threshold", type=float, default=5.5)
    parser.add_argument("--step", type=int, default=4096)
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--min-sync-score", type=float, default=0.0)
    parser.add_argument("--min-coherent-metric", type=float, default=0.0)
    parser.add_argument("--skip-detected", action="store_true")
    parser.add_argument("--reuse-synth", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    cfg = LoRaConfig()
    synth_path = Path(args.synth_out)
    source_order = parse_source_order(args.source_order)
    offset_deltas = parse_offset_deltas(args.offset_deltas, len(source_order))
    if args.reuse_synth and synth_path.exists():
        samples, meta, cfg = load_scene(synth_path)
    else:
        samples, meta = synthesize_ordered_collision(
            Path(args.clean),
            synth_path,
            cfg,
            source_order=source_order,
            seed=args.seed,
            offset_range=(args.min_offset_symbols, args.max_offset_symbols),
            offset_deltas=offset_deltas,
        )
    rf_correction = parse_rf_correction(args.rf_correction)
    samples = apply_rf_calibration(samples, rf_correction)
    source_indices = [int(p["source_packet_index"]) for p in meta["packets"]]
    refs = build_references(Path(args.clean), source_indices, cfg)
    sp_samples, sp_whitener, sp_noise_sigma2 = estimate_sp_whitener(samples, meta, cfg)

    oracle_est = attach_sp_reliability_and_lambda(
        sp_samples,
        transform_estimate_channels(oracle_estimates(meta, refs), sp_whitener),
        cfg,
        noise_sigma2=sp_noise_sigma2,
        gamma=args.sp_gamma,
        max_lambda=args.sp_lambda_max,
        noise_competition=args.sp_lambda_policy != "pair_only_legacy",
        noise_two_packet_only=args.sp_lambda_policy == TWO_PACKET_POLICY,
    )
    oracle_core = evaluate_sp_with_estimates(sp_samples, meta, cfg, refs, oracle_est)
    if args.skip_detected:
        det_est: list[dict] = []
        detected_core: dict[str, object] = {"summary": {"skipped": "true"}}
    else:
        det_seed, _ = detected_estimates(
            sp_samples,
            cfg,
            max_candidates=args.max_candidates,
            threshold=args.threshold,
            step_samples=args.step,
            min_sync_score=args.min_sync_score,
            min_coherent_metric=args.min_coherent_metric,
            frontend=args.frontend,
        )
        det_est = attach_sp_reliability_and_lambda(
            sp_samples,
            det_seed,
            cfg,
            noise_sigma2=sp_noise_sigma2,
            gamma=args.sp_gamma,
            max_lambda=args.sp_lambda_max,
            noise_competition=args.sp_lambda_policy != "pair_only_legacy",
            noise_two_packet_only=args.sp_lambda_policy == TWO_PACKET_POLICY,
        )
        detected_core = evaluate_sp_with_estimates(sp_samples, meta, cfg, refs, det_est)
    report = {
        "input": str(synth_path),
        "config": {
            "source_order": source_indices,
            "seed": int(args.seed),
            "offset_symbols_range": [float(args.min_offset_symbols), float(args.max_offset_symbols)],
            "sp_gamma": float(args.sp_gamma),
            "sp_lambda_max": args.sp_lambda_max,
            "sp_lambda_policy": args.sp_lambda_policy,
            "rf_correction": (
                [[float(np.real(v)), float(np.imag(v))] for v in rf_correction]
                if rf_correction is not None
                else "identity"
            ),
            "sp_noise_sigma2": float(sp_noise_sigma2),
            "sp_whitener": [
                [[float(np.real(v)), float(np.imag(v))] for v in row]
                for row in np.asarray(sp_whitener, dtype=np.complex128)
            ],
            "frontend": args.frontend,
            "threshold": float(args.threshold),
            "step": int(args.step),
            "max_candidates": int(args.max_candidates),
            "min_sync_score": float(args.min_sync_score),
            "min_coherent_metric": float(args.min_coherent_metric),
        },
        "truth_packets": meta["packets"],
        "references": {str(k): asdict(v) for k, v in refs.items()},
        "oracle_estimates": oracle_est,
        "detected_estimates": det_est,
        "oracle": oracle_core,
        "detected": detected_core,
        "sp_self_check": {
            "signed_spectrum_top1": True,
            "mrc_used_only_as_baseline": True,
            "delta_margin_diagnostics_for_mrc_errors": True,
            "packet_level_lambda_shared_by_payload_symbols": True,
            "noise_prewhitening_enabled_or_identity_when_no_background_noise": True,
            "continuous_cfo_field_used_for_sp": True,
            "fractional_sto_field_used_by_symbol_window": True,
            "robust_preamble_channel_and_confidence_cone": True,
            "risk_constrained_lambda_max_min": True,
        },
    }
    text = json.dumps(report, indent=2)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text, encoding="utf-8")
    if not args.quiet:
        print(text)


if __name__ == "__main__":
    main()
