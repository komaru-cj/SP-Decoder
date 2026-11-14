"""SP-Dechirp 接收前端：检测、同步、CFO 和信道估计。

本文件是最终 SP 方案的接收前端。它只服务两类解码：
1. MRC：作为对比基线；
2. SP-Dechirp：作为最终方案。

核心思想：
- 用 MaLoRaGW/PCube 风格的 separated preamble 轨道做多包检测；
- 对弱包使用 SFD-seeded coherent refine 修正 start/CFO/h；
- h 使用前导相干估计，payload CFO 使用整数 bin snap，以匹配当前 folded FFT 解调。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.signal import fftconvolve, find_peaks

from lora_mrc_sp_core import (
    LoRaConfig,
    SyncCandidate,
    apply_rf_calibration,
    dechirp_fft_dual,
    decode_packet_branch,
    estimate_preamble_ml_cfo_channel,
    fixed_mrc_branch_parameters,
    fractional_read_2d,
    instantaneous_chirp,
    lora_symbol_fft,
    pca_project_streams,
    signed_bin,
)
from real_usrp_clean_packet_synth import load_extracted


@dataclass(frozen=True)
class ReferencePacket:
    """clean 单包作为 oracle 参考时需要的参数。"""

    source_index: int
    cfo_bins: float
    sto_samples: float
    channel: list[list[float]]
    symbol_bins: list[int]


@dataclass(frozen=True)
class PreambleFFTBlock:
    """同一个 start 下 8 个前导窗口的 FFT 缓存。"""

    spectra: np.ndarray
    energy: np.ndarray
    floor: np.ndarray


class PreambleFFTCache:
    """缓存前导窗口 FFT，避免 CFO 网格搜索时重复读窗和 FFT。"""

    def __init__(self, samples: np.ndarray, cfg: LoRaConfig) -> None:
        self.samples = samples
        self.cfg = cfg
        self.downchirp = instantaneous_chirp(0, cfg, up=False)
        self._items: dict[float, PreambleFFTBlock | None] = {}

    def get(self, start: float) -> PreambleFFTBlock | None:
        key = round(float(start), 6)
        if key in self._items:
            return self._items[key]
        spectra: list[np.ndarray] = []
        energy: list[np.ndarray] = []
        floor: list[float] = []
        for p in range(self.cfg.preamble_len):
            s = float(start) + p * self.cfg.samples_per_symbol
            if s < 0 or s + self.cfg.samples_per_symbol > self.samples.shape[1]:
                self._items[key] = None
                return None
            spec = dechirp_fft_dual(
                fractional_read_2d(self.samples, s, self.cfg.samples_per_symbol),
                self.downchirp,
                self.cfg,
            )
            e = np.sum(np.abs(spec) ** 2, axis=0)
            spectra.append(spec)
            energy.append(e)
            floor.append(float(np.median(e)) + 1e-30)
        block = PreambleFFTBlock(
            spectra=np.asarray(spectra, dtype=np.complex128),
            energy=np.asarray(energy, dtype=np.float64),
            floor=np.asarray(floor, dtype=np.float64),
        )
        self._items[key] = block
        return block


def complex_pairs(values: np.ndarray) -> list[list[float]]:
    return [[float(np.real(v)), float(np.imag(v))] for v in values]


def channel_coherence(a: np.ndarray, b: np.ndarray) -> float:
    """两个双天线信道向量的方向一致性。"""

    return float(abs(np.vdot(a, b)) / math.sqrt(float(np.vdot(a, a).real * np.vdot(b, b).real) + 1e-30))


def load_scene(path: Path) -> tuple[np.ndarray, dict, LoRaConfig]:
    """读取合成并发 IQ 场景。"""

    z = np.load(path, allow_pickle=False)
    samples = z["samples"].astype(np.complex64)
    meta = json.loads(str(z["metadata_json"]))
    cfg_dict = meta.get("config", {})
    cfg = LoRaConfig(sample_rate_hz=float(cfg_dict.get("sample_rate_hz", 1_000_000.0)))
    return samples, meta, cfg


def packet_ser(decoded: list[int], truth: list[int]) -> float:
    """符号错误率。"""

    n = min(len(decoded), len(truth))
    if n <= 0:
        return 1.0
    return float(sum(int(decoded[i]) != int(truth[i]) for i in range(n)) / n)


def match_by_start(estimates: list[dict], truth_packets: list[dict]) -> list[dict | None]:
    """按 start 最近原则把检测结果匹配到 oracle truth 包。"""

    unused = set(range(len(estimates)))
    matched: list[dict | None] = []
    for truth in truth_packets:
        if not unused:
            matched.append(None)
            continue
        t = float(truth["start_sample"])
        best = min(unused, key=lambda i: abs(float(estimates[i]["start_sample"]) - t))
        matched.append(estimates[best])
        unused.remove(best)
    return matched


def build_references(clean_path: Path, source_indices: list[int], cfg: LoRaConfig) -> dict[int, ReferencePacket]:
    """从 clean 单包提取 oracle CFO/h 和 payload symbol-bin 参考。"""

    clean_packets, clean_meta = load_extracted(clean_path)
    metas = clean_meta["packets"] if isinstance(clean_meta, dict) and "packets" in clean_meta else clean_meta
    refs: dict[int, ReferencePacket] = {}
    for src in sorted(set(source_indices)):
        packet = clean_packets[int(src)]
        center = int(metas[int(src)].get("peak_bin", 0)) if isinstance(metas[int(src)], dict) else 0
        meta_cfo = float(metas[int(src)].get("cfo_bins", 0.0)) if isinstance(metas[int(src)], dict) else 0.0
        ml = estimate_preamble_ml_cfo_channel(packet, 0.0, cfg, center_bin=center, bin_radius=8, fine_cfo_grid=17)
        # SER 参考使用 clean 包在提取时记录的整数 CFO，避免 ML 小数 CFO 引入整体 bin 偏移。
        mrc = decode_packet_branch(packet, int(src), 0.0, meta_cfo, fixed_mrc_branch_parameters(ml.channel), cfg)
        refs[int(src)] = ReferencePacket(
            source_index=int(src),
            cfo_bins=float(meta_cfo),
            sto_samples=0.0,
            channel=complex_pairs(ml.channel),
            symbol_bins=[int(d.symbol_bin) for d in mrc.decisions],
        )
    return refs


def sync_word_score(samples: np.ndarray, start: float, cfo_bins: float, cfg: LoRaConfig) -> float:
    """检查两个 sync-word upchirp 是否落在期望 bin 附近。"""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    expected_offsets = [((cfg.sync_word & 0xF0) >> 4) << 3, (cfg.sync_word & 0x0F) << 3]
    ratios: list[float] = []
    for p, sym_offset in enumerate(expected_offsets):
        s = float(start) + (cfg.preamble_len + p) * cfg.samples_per_symbol
        if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
            return 0.0
        spec = dechirp_fft_dual(
            fractional_read_2d(samples, s, cfg.samples_per_symbol), downchirp, cfg
        )
        energy = np.sum(np.abs(spec) ** 2, axis=0)
        expected = (int(round(cfo_bins)) + sym_offset) % cfg.m
        local = [(expected + dk) % cfg.m for dk in range(-3, 4)]
        ratios.append(float(np.max(energy[local]) / (float(np.median(energy)) + 1e-30)))
    return float(np.median(ratios))


def sfd_score(samples: np.ndarray, start: float, cfo_bins: float, cfg: LoRaConfig) -> float:
    """检查 SFD downchirp 乘 upchirp 后是否落在 CFO bin 附近。"""

    upchirp = instantaneous_chirp(0, cfg, up=True)
    sfd0 = float(start) + (cfg.preamble_len + 2) * cfg.samples_per_symbol
    ratios: list[float] = []
    for p in range(2):
        s = sfd0 + p * cfg.samples_per_symbol
        if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
            return 0.0
        spec = dechirp_fft_dual(
            fractional_read_2d(samples, s, cfg.samples_per_symbol), upchirp, cfg
        )
        energy = np.sum(np.abs(spec) ** 2, axis=0)
        expected = int(round(cfo_bins)) % cfg.m
        local = [(expected + dk) % cfg.m for dk in range(-3, 4)]
        ratios.append(float(np.max(energy[local]) / (float(np.median(energy)) + 1e-30)))
    return float(np.median(ratios))


def local_projection_vectors(samples: np.ndarray, start: int, cfg: LoRaConfig) -> np.ndarray:
    """构造 v1 前导检测要求的 {e1,e2,v1,v2} 局部投影集合。"""

    ch = samples.shape[0]
    eyes = np.eye(ch, dtype=np.complex128)
    if ch < 2:
        return eyes
    lo = max(0, int(start))
    hi = min(samples.shape[1], int(start + cfg.preamble_len * cfg.samples_per_symbol))
    if hi <= lo + 8:
        return eyes
    block = np.asarray(samples[:, lo:hi], dtype=np.complex128)
    cov = (block @ block.conj().T) / max(1, block.shape[1])
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    vecs = [eyes[0], eyes[1]]
    vecs.extend([eigvecs[:, order[i]] for i in range(min(2, eigvecs.shape[1]))])
    out: list[np.ndarray] = []
    for v in vecs:
        vv = np.asarray(v, dtype=np.complex128)
        vv = vv / (math.sqrt(float(np.vdot(vv, vv).real)) + 1e-30)
        if not any(abs(np.vdot(vv, old)) > 0.999 for old in out):
            out.append(vv)
    return np.asarray(out, dtype=np.complex128)


def circular_bin_variance(bins: list[int], center: int, m: int) -> float:
    if not bins:
        return float("inf")
    dist = [min((int(b) - center) % m, (center - int(b)) % m) for b in bins]
    return float(np.mean(np.asarray(dist, dtype=np.float64) ** 2))


def preamble_multi_tracks(
    samples: np.ndarray,
    start: int,
    cfg: LoRaConfig,
    *,
    top_k: int = 12,
    min_hits: int = 3,
    max_tracks: int = 4,
) -> list[tuple[float, int, float, float, int]]:
    """在一个候选 start 上按 v1 多投影规则找重复前导轨道。

    对局部 {e1,e2,v1,v2} 每个投影独立检测 top-k 前导峰，再按 bin 聚合；
    轨道得分同时包含 hit 数、环形方差、局部 SNR 和 symbol 周期一致性。
    """

    downchirp = instantaneous_chirp(0, cfg, up=False)
    projections = local_projection_vectors(samples, start, cfg)
    all_tracks: list[tuple[float, int, float, float, int]] = []
    for proj in projections:
        bin_scores: dict[int, list[float]] = {}
        bin_powers: dict[int, list[float]] = {}
        bin_hits: dict[int, set[int]] = {}
        bin_observed: dict[int, list[int]] = {}
        for p in range(cfg.preamble_len):
            s = start + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                return []
            scalar = np.conj(proj) @ np.asarray(samples[:, s : s + cfg.samples_per_symbol], dtype=np.complex128)
            spec = lora_symbol_fft(scalar * downchirp, cfg)
            energy = np.abs(spec) ** 2
            floor = float(np.median(energy)) + 1e-30
            top = np.argpartition(energy, -top_k)[-top_k:]
            for b0 in top:
                b = int(b0)
                ratio = float(energy[b] / floor)
                for nb, weight in ((b, 1.0), ((b - 1) % cfg.m, 0.30), ((b + 1) % cfg.m, 0.30)):
                    bin_scores.setdefault(nb, []).append(weight * ratio)
                    bin_powers.setdefault(nb, []).append(float(energy[b]))
                    bin_hits.setdefault(nb, set()).add(int(p))
                    bin_observed.setdefault(nb, []).append(b)
        tracks: list[tuple[float, int, float, float, int]] = []
        for b, values in bin_scores.items():
            hit_set = bin_hits.get(b, set())
            hits = len(hit_set)
            if hits < min_hits:
                continue
            trimmed = sorted(values, reverse=True)[: min(cfg.preamble_len, len(values))]
            mean_snr = float(np.median(trimmed))
            var_circ = circular_bin_variance(bin_observed.get(b, []), int(b), cfg.m)
            ordered_hits = sorted(hit_set)
            span = max(1, ordered_hits[-1] - ordered_hits[0] + 1) if ordered_hits else cfg.preamble_len
            period_consistency = hits / float(span)
            hit_factor = hits / float(cfg.preamble_len)
            score = float(mean_snr * math.sqrt(hits) * hit_factor * period_consistency / (1.0 + var_circ))
            tracks.append((score, int(b), float(signed_bin(int(b), cfg.m)), float(np.median(bin_powers[b])), hits))
        all_tracks.extend(tracks)
    all_tracks.sort(key=lambda row: row[0], reverse=True)
    keep: list[tuple[float, int, float, float, int]] = []
    for row in all_tracks:
        b = row[1]
        if any(min((b - old[1]) % cfg.m, (old[1] - b) % cfg.m) <= 2 for old in keep):
            continue
        keep.append(row)
        if len(keep) >= max_tracks:
            break
    return keep


def stable_preamble_multi_tracks(
    samples: np.ndarray,
    start: int,
    cfg: LoRaConfig,
    *,
    top_k: int = 10,
    min_hits: int = 4,
    max_tracks: int = 4,
    streams: np.ndarray | None = None,
    residual_projector: np.ndarray | None = None,
    residual_tracks_out: list | None = None,
) -> list[tuple[float, int, float, float, int]]:
    """稳定候选生成器：全局 PCA/原始流 separated preamble 轨道。

    这是给混合前端使用的 raw candidate stage。它只负责高召回地产生
    start/CFO 粗候选；后续仍交给 v1 的 SFD-anchor、fractional STO 和
    相干 h 估计细化。
    """

    if streams is None:
        streams, _, _ = pca_project_streams(samples, include_original=True)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    bin_ratios: dict[int, list[float]] = {}
    bin_powers: dict[int, list[float]] = {}
    bin_hits: dict[int, set[tuple[int, int]]] = {}
    residual_ratios: dict[int, list[float]] = {}
    residual_powers: dict[int, list[float]] = {}
    residual_hits: dict[int, set[int]] = {}
    for stream_idx, stream in enumerate(streams):
        for p in range(cfg.preamble_len):
            s = start + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                return []
            spec = lora_symbol_fft(stream[s : s + cfg.samples_per_symbol] * downchirp, cfg)
            energy = np.abs(spec) ** 2
            floor = float(np.median(energy)) + 1e-30
            top = np.argpartition(energy, -top_k)[-top_k:]
            for b0 in top:
                b = int(b0)
                ratio = float(energy[b] / floor)
                bin_ratios.setdefault(b, []).append(ratio)
                bin_powers.setdefault(b, []).append(float(energy[b]))
                bin_hits.setdefault(b, set()).add((int(stream_idx), int(p)))
                if residual_tracks_out is not None and stream_idx == streams.shape[0] - 1:
                    residual_ratios.setdefault(b, []).append(ratio)
                    residual_powers.setdefault(b, []).append(float(energy[b]))
                    residual_hits.setdefault(b, set()).add(int(p))
    all_tracks: list[tuple[float, int, float, float, int]] = []
    max_hits = max(1, streams.shape[0] * cfg.preamble_len)
    for b, ratios in bin_ratios.items():
        hits = len(bin_hits.get(b, set()))
        if hits < min_hits:
            continue
        strongest = sorted(ratios, reverse=True)[: min(max_hits, len(ratios))]
        median_ratio = float(np.median(strongest))
        continuity = hits / float(max_hits)
        score = float(median_ratio * math.sqrt(hits) * continuity)
        all_tracks.append((score, int(b), float(signed_bin(int(b), cfg.m)), float(np.median(bin_powers[b])), hits))
    all_tracks.sort(key=lambda row: row[0], reverse=True)
    keep: list[tuple[float, int, float, float, int]] = []
    for row in all_tracks:
        b = int(row[1])
        if any(min((b - old[1]) % cfg.m, (old[1] - b) % cfg.m) <= 1 for old in keep):
            continue
        keep.append(row)
        if len(keep) >= max_tracks:
            break
    if residual_tracks_out is not None and residual_projector is not None:
        projector = np.asarray(residual_projector, dtype=np.complex128)
        projector /= math.sqrt(float(np.vdot(projector, projector).real)) + 1e-30
        residual_rows: list[tuple[float, int, float, float, int, np.ndarray]] = []
        for b, ratios in residual_ratios.items():
            hits = len(residual_hits.get(b, set()))
            if hits < int(min_hits):
                continue
            strongest = sorted(ratios, reverse=True)[: min(cfg.preamble_len, len(ratios))]
            median_ratio = float(np.median(strongest))
            continuity = hits / float(cfg.preamble_len)
            score = float(median_ratio * math.sqrt(hits) * continuity)
            residual_rows.append(
                (
                    score,
                    int(b),
                    float(signed_bin(int(b), cfg.m)),
                    float(np.median(residual_powers[b])),
                    int(hits),
                    projector.copy(),
                )
            )
        residual_rows.sort(key=lambda row: row[0], reverse=True)
        for row in residual_rows:
            b = int(row[1])
            if any(
                min((b - old[1]) % cfg.m, (old[1] - b) % cfg.m) <= 1
                for old in residual_tracks_out
            ):
                continue
            residual_tracks_out.append(row)
            if len(residual_tracks_out) >= 3:
                break
    return keep


def batched_stable_preamble_tracks(
    samples: np.ndarray,
    seeds: np.ndarray,
    cfg: LoRaConfig,
    *,
    top_k: int = 10,
    min_hits: int = 4,
    max_tracks: int = 4,
    streams: np.ndarray | None = None,
    residual_projector: np.ndarray | None = None,
    chirp_count: int | None = None,
) -> list[tuple[list[tuple[float, int, float, float, int]], list]]:
    """Vectorized twin of ``stable_preamble_multi_tracks`` for many seeds.

    It evaluates the exact same per-chirp FFTs, noise floors, top-k bins,
    per-bin ratio/power/hit accumulation, scoring and dedup as the sequential
    function, but batches the FFTs across seeds so the numpy overhead is paid
    once per batch instead of once per seed.  The returned per-seed tracks are
    bit-for-bit equivalent to calling the sequential function on each seed.
    """

    if streams is None:
        streams, _, _ = pca_project_streams(samples, include_original=True)
    n = samples.shape[1]
    sym = int(cfg.samples_per_symbol)
    m = int(cfg.m)
    osr = int(cfg.osr)
    preamble_len = int(cfg.preamble_len)
    if chirp_count is None:
        chirp_count = preamble_len
    chirp_count = max(1, min(int(chirp_count), preamble_len))
    stream_count = int(streams.shape[0])
    downchirp = instantaneous_chirp(0, cfg, up=False)[::osr][:m].astype(np.complex64)
    results: list[tuple[list[tuple[float, int, float, float, int]], list]] = []
    seed_array = np.asarray(seeds, dtype=np.int64).ravel()
    chunk = 64
    for chunk_start in range(0, seed_array.size, chunk):
        batch = seed_array[chunk_start : chunk_start + chunk]
        nb = batch.size
        valid = (
            (batch >= 0)
            & (batch + (chirp_count - 1) * sym + sym <= n)
        )
        valid_indices = np.flatnonzero(valid)
        energy = np.zeros((nb, stream_count * chirp_count, m), dtype=np.float64)
        for stream_idx in range(stream_count):
            stream = streams[stream_idx]
            for p in range(chirp_count):
                offset = p * sym
                row_index = stream_idx * chirp_count + p
                if valid_indices.size:
                    windows = np.stack(
                        [
                            stream[int(seed) + offset : int(seed) + offset + sym][
                                ::osr
                            ][:m]
                            for seed in batch[valid_indices]
                        ]
                    )
                    spec = np.fft.fft(windows * downchirp[None, :], axis=1)
                    energy[valid_indices, row_index, :] = np.abs(spec) ** 2
        max_hits = max(1, stream_count * chirp_count)
        for j in range(nb):
            if not bool(valid[j]):
                results.append(([], []))
                continue
            e = energy[j]  # (chirps, m)
            floors = np.median(e, axis=1) + 1e-30
            top = np.argpartition(e, -top_k, axis=1)[:, -top_k:]
            bin_ratios: dict[int, list[float]] = {}
            bin_powers: dict[int, list[float]] = {}
            bin_hits: dict[int, set[tuple[int, int]]] = {}
            residual_ratios: dict[int, list[float]] = {}
            residual_powers: dict[int, list[float]] = {}
            residual_hits: dict[int, set[int]] = {}
            for row_index in range(stream_count * chirp_count):
                stream_idx = row_index // chirp_count
                p = row_index % chirp_count
                bins = top[row_index]
                ratios = e[row_index, bins] / floors[row_index]
                powers = e[row_index, bins]
                for b0, ratio, power in zip(bins.tolist(), ratios.tolist(), powers.tolist()):
                    b = int(b0)
                    bin_ratios.setdefault(b, []).append(ratio)
                    bin_powers.setdefault(b, []).append(power)
                    bin_hits.setdefault(b, set()).add((int(stream_idx), int(p)))
                    if (
                        residual_projector is not None
                        and stream_idx == stream_count - 1
                    ):
                        residual_ratios.setdefault(b, []).append(ratio)
                        residual_powers.setdefault(b, []).append(power)
                        residual_hits.setdefault(b, set()).add(int(p))
            all_tracks: list[tuple[float, int, float, float, int]] = []
            for b, ratios in bin_ratios.items():
                hits = len(bin_hits.get(b, set()))
                if hits < min_hits:
                    continue
                strongest = sorted(ratios, reverse=True)[: min(max_hits, len(ratios))]
                median_ratio = float(np.median(strongest))
                continuity = hits / float(max_hits)
                score = float(median_ratio * math.sqrt(hits) * continuity)
                all_tracks.append(
                    (
                        score,
                        int(b),
                        float(signed_bin(int(b), cfg.m)),
                        float(np.median(bin_powers[b])),
                        hits,
                    )
                )
            all_tracks.sort(key=lambda row: row[0], reverse=True)
            keep: list[tuple[float, int, float, float, int]] = []
            for row in all_tracks:
                b = int(row[1])
                if any(
                    min((b - old[1]) % cfg.m, (old[1] - b) % cfg.m) <= 1
                    for old in keep
                ):
                    continue
                keep.append(row)
                if len(keep) >= max_tracks:
                    break
            residual_rows: list[tuple[float, int, float, float, int, np.ndarray]] = []
            if residual_projector is not None:
                projector = np.asarray(residual_projector, dtype=np.complex128)
                projector /= math.sqrt(float(np.vdot(projector, projector).real)) + 1e-30
                for b, ratios in residual_ratios.items():
                    hits = len(residual_hits.get(b, set()))
                    if hits < int(min_hits):
                        continue
                    strongest = sorted(ratios, reverse=True)[
                        : min(chirp_count, len(ratios))
                    ]
                    median_ratio = float(np.median(strongest))
                    continuity = hits / float(chirp_count)
                    score = float(median_ratio * math.sqrt(hits) * continuity)
                    residual_rows.append(
                        (
                            score,
                            int(b),
                            float(signed_bin(int(b), cfg.m)),
                            float(np.median(residual_powers[b])),
                            int(hits),
                            projector.copy(),
                        )
                    )
                residual_rows.sort(key=lambda row: row[0], reverse=True)
                residual_keep: list = []
                for row in residual_rows:
                    b = int(row[1])
                    if any(
                        min((b - old[1]) % cfg.m, (old[1] - b) % cfg.m) <= 1
                        for old in residual_keep
                    ):
                        continue
                    residual_keep.append(row)
                    if len(residual_keep) >= 3:
                        break
            else:
                residual_keep = []
            results.append((keep, residual_keep))
    return results


def sfd_paired_peak_indices(
    peaks: np.ndarray,
    *,
    n_symbol: int,
    tolerance_samples: int,
) -> np.ndarray:
    """Keep downchirp-correlation peaks that form an SFD symbol pair.

    A certified LoRa head contains two full downchirps one symbol apart.  This
    is a schedule-free structural prefilter: it rejects isolated correlation
    peaks before expensive start/CFO refinement, without comparing their
    amplitudes or imposing a candidate quota.
    """

    values = np.asarray(peaks, dtype=np.int64)
    if values.size < 2:
        return values
    values = np.sort(values)
    paired = np.zeros(values.size, dtype=bool)
    tolerance = max(0, int(tolerance_samples))
    for index, peak in enumerate(values):
        target = int(peak) + int(n_symbol)
        lower = int(np.searchsorted(values, target - tolerance, side="left"))
        upper = int(np.searchsorted(values, target + tolerance, side="right"))
        if lower >= upper:
            continue
        paired[index] = True
        paired[lower:upper] = True
    return values[paired]


def sfd_pair_anchor_peak_indices(
    peaks: np.ndarray,
    *,
    n_symbol: int,
    tolerance_samples: int,
) -> np.ndarray:
    """Return only peaks that can be the first downchirp of an SFD pair.

    The second SFD downchirp is evidence for the same head, not an independent
    timing anchor.  Starting the local refiner from it is one symbol late and
    cannot recover the actual preamble start within the bounded correction
    radius.  This check is positional only and does not compare peak scores.
    """

    values = np.sort(np.asarray(peaks, dtype=np.int64))
    if values.size < 2:
        return np.empty(0, dtype=np.int64)
    tolerance = max(0, int(tolerance_samples))
    anchors: list[int] = []
    for peak in values:
        target = int(peak) + int(n_symbol)
        lower = int(np.searchsorted(values, target - tolerance, side="left"))
        upper = int(np.searchsorted(values, target + tolerance, side="right"))
        if lower < upper:
            anchors.append(int(peak))
    return np.asarray(anchors, dtype=np.int64)


def preamble_run_support_counts(
    upchirp_peaks: np.ndarray,
    sfd_anchor_peaks: np.ndarray,
    *,
    n_symbol: int,
    tolerance_samples: int,
    min_backtrack_symbols: int,
    max_backtrack_symbols: int,
) -> np.ndarray:
    """Return the longest phase-coherent upchirp run before each SFD anchor.

    A CFO can shift all upchirp matched-filter peaks by one shared fractional
    symbol offset relative to the SFD downchirp peak.  Candidate offsets are
    learned only from local IQ peaks; every expected preamble symbol is then
    checked at that same offset.  No schedule, identity, amplitude ranking,
    or candidate quota participates in this structural test.
    """

    up_values = np.sort(np.asarray(upchirp_peaks, dtype=np.int64))
    anchors = np.asarray(sfd_anchor_peaks, dtype=np.int64)
    counts = np.zeros(anchors.size, dtype=np.int64)
    if up_values.size == 0 or anchors.size == 0:
        return counts
    phase_tolerance = max(0, int(tolerance_samples))
    offset_search = max(phase_tolerance, int(round(0.25 * n_symbol)))
    first = max(0, int(min_backtrack_symbols))
    last = max(first, int(max_backtrack_symbols))
    for index, anchor in enumerate(anchors):
        offsets: set[int] = set()
        for backtrack in range(first, last + 1):
            expected = int(anchor) - backtrack * int(n_symbol)
            lower = int(
                np.searchsorted(
                    up_values, expected - offset_search, side="left"
                )
            )
            upper = int(
                np.searchsorted(
                    up_values, expected + offset_search, side="right"
                )
            )
            offsets.update(int(value) - expected for value in up_values[lower:upper])
        best_run = 0
        for offset in offsets:
            run = 0
            for backtrack in range(first, last + 1):
                expected = int(anchor) - backtrack * int(n_symbol) + offset
                lower = int(
                    np.searchsorted(
                        up_values, expected - phase_tolerance, side="left"
                    )
                )
                upper = int(
                    np.searchsorted(
                        up_values, expected + phase_tolerance, side="right"
                    )
                )
                if lower < upper:
                    run += 1
                    best_run = max(best_run, run)
                else:
                    run = 0
        counts[index] = best_run
    return counts


def phase_coherent_preamble_offset_branches(
    upchirp_peaks: np.ndarray,
    sfd_anchor_peaks: np.ndarray,
    *,
    n_symbol: int,
    phase_tolerance_samples: int,
    min_backtrack_symbols: int,
    max_backtrack_symbols: int,
    min_run_symbols: int,
) -> list[list[int]]:
    """Return every IQ-supported up/down phase-offset branch per SFD anchor.

    A branch is an offset for which a consecutive run of upchirp peaks aligns
    with the preamble locations before one SFD anchor.  Branches are never
    ranked: retaining all of them is necessary when simultaneous packets have
    the same physical start but distinct CFOs or spatial channels.
    """

    up_values = np.sort(np.asarray(upchirp_peaks, dtype=np.int64))
    anchors = np.asarray(sfd_anchor_peaks, dtype=np.int64)
    result: list[list[int]] = [[] for _ in anchors]
    if up_values.size == 0 or anchors.size == 0:
        return result
    phase_tolerance = max(0, int(phase_tolerance_samples))
    offset_search = max(phase_tolerance, int(round(0.25 * n_symbol)))
    first = max(0, int(min_backtrack_symbols))
    last = max(first, int(max_backtrack_symbols))
    required = max(1, int(min_run_symbols))
    for index, anchor in enumerate(anchors):
        offsets: set[int] = set()
        for backtrack in range(first, last + 1):
            expected = int(anchor) - backtrack * int(n_symbol)
            lower = int(
                np.searchsorted(
                    up_values, expected - offset_search, side="left"
                )
            )
            upper = int(
                np.searchsorted(
                    up_values, expected + offset_search, side="right"
                )
            )
            offsets.update(int(value) - expected for value in up_values[lower:upper])
        branches: list[int] = []
        for offset in sorted(offsets):
            run = 0
            best_run = 0
            for backtrack in range(first, last + 1):
                expected = int(anchor) - backtrack * int(n_symbol) + offset
                lower = int(
                    np.searchsorted(
                        up_values, expected - phase_tolerance, side="left"
                    )
                )
                upper = int(
                    np.searchsorted(
                        up_values, expected + phase_tolerance, side="right"
                    )
                )
                if lower < upper:
                    run += 1
                    best_run = max(best_run, run)
                else:
                    run = 0
            if best_run >= required:
                branches.append(int(offset))
        result[index] = branches
    return result


def sliding_preamble_sp_estimates(
    samples: np.ndarray,
    cfg: LoRaConfig,
    *,
    streams: np.ndarray | None = None,
    threshold: float = 3.0,
    cfo_min: float,
    cfo_max: float,
    max_candidates: int,
    min_sfd_score: float = 1.0,
    min_refined_sync_score: float = 50.0,
    top_peaks_per_stream: int = 200,
    refine_budget: int | None = None,
    hypotheses_per_bucket: int = 2,
    anchor_offsets_symbols: tuple[float, ...] = (-0.5, 0.0, 0.5),
    defer_sfd_refinement: bool = False,
    min_preamble_run_symbols: int = 3,
    preamble_run_chain_tolerance_symbols: float = 0.20,
    structural_preamble_run_only: bool = False,
    min_upchirp_peak_correlation: float | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[dict]:
    """SPv2 Sec. 5.2 sliding preamble/SFD search over the physical/PCA streams.

    This is the complexity-reduced frontend: a downchirp matched filter slides
    over each dual-channel/PCA stream (one FFT convolution per stream), strong
    correlation peaks are paired one symbol apart as SFD downchirps, and every
    accepted coarse start goes through the same SFD-anchored start/CFO/STO
    refinement, sync-word check and two-channel channel estimate used by the
    production receiver.  The cost is O(streams * N log N) for the window
    instead of an 8-phase per-seed multi-track FFT scan.
    """

    if streams is None:
        streams, _, _ = pca_project_streams(samples, include_original=True)
    n_symbol = int(cfg.samples_per_symbol)
    template = instantaneous_chirp(0, cfg, up=False).astype(np.complex128)
    template = np.conj(template[::-1])
    window_len = (cfg.preamble_len + 4) * n_symbol
    if samples.shape[1] < window_len:
        return []
    height_floor = max(float(threshold) * 0.04, 0.12)
    raw_peaks: list[tuple[float, int, int, float]] = []
    # (height, coarse_start, stream, coarse_cfo)
    diagnostics_rows: list[dict] = []
    up_peaks_by_stream: list[np.ndarray] = []
    up_template = np.conj(
        instantaneous_chirp(0, cfg, up=True)[::-1]
    ).astype(np.complex128)
    pair_tolerance = max(4, int(round(0.20 * n_symbol)))
    preamble_tolerance = max(4, int(round(0.025 * n_symbol)))
    for stream_idx in range(streams.shape[0]):
        stream = np.asarray(streams[stream_idx], dtype=np.complex128)
        correlation = fftconvolve(stream, template, mode="valid")
        sample_power = fftconvolve(
            np.abs(stream) ** 2,
            np.ones(n_symbol, dtype=np.float64),
            mode="valid",
        )
        normalized = np.abs(correlation) / np.sqrt(
            np.maximum(sample_power * float(n_symbol), 1e-30)
        )
        height = max(height_floor, 2.0 * float(np.mean(normalized)))
        down_peaks, _ = find_peaks(
            normalized,
            height=height,
            distance=max(1, int(0.05 * n_symbol)),
        )
        raw_peak_count = int(down_peaks.size)
        paired_peaks = sfd_paired_peak_indices(
            down_peaks,
            n_symbol=n_symbol,
            tolerance_samples=pair_tolerance,
        )
        sfd_anchors = sfd_pair_anchor_peak_indices(
            down_peaks,
            n_symbol=n_symbol,
            tolerance_samples=pair_tolerance,
        )
        anchor_down_scores = np.asarray(
            normalized[sfd_anchors], dtype=np.float64
        ).copy()
        # These arrays are window-sized.  Retain only peak positions/scores
        # before calculating the upchirp evidence used by both candidate paths.
        del correlation
        del normalized

        correlation_up = fftconvolve(stream, up_template, mode="valid")
        normalized_up = np.abs(correlation_up) / np.sqrt(
            np.maximum(sample_power * float(n_symbol), 1e-30)
        )
        height_up = max(height_floor, 2.0 * float(np.mean(normalized_up)))
        peaks_up, _ = find_peaks(
            normalized_up,
            height=height_up,
            distance=max(1, int(0.05 * n_symbol)),
        )
        if min_upchirp_peak_correlation is None:
            # Retain the historical guard for the ordinary blind frontend.
            # Its raw-window energy criterion is unsuitable after whitening:
            # a real constant-envelope LoRa chirp need not increase total
            # sample energy over the whitened noise floor.
            power_floor = float(np.median(sample_power)) * 1.5
            peaks_up = peaks_up[sample_power[peaks_up] > power_floor]
        else:
            # Anonymous formal discovery uses the chirp matched-filter value
            # itself.  This is a per-peak IQ structure threshold, never a
            # score ranking or a schedule/identity-dependent selection.
            peaks_up = peaks_up[
                normalized_up[peaks_up] >= float(min_upchirp_peak_correlation)
            ]
        up_peaks_by_stream.append(np.asarray(peaks_up, dtype=np.int64).copy())
        offset_branches = phase_coherent_preamble_offset_branches(
            peaks_up,
            sfd_anchors,
            n_symbol=n_symbol,
            phase_tolerance_samples=preamble_tolerance,
            min_backtrack_symbols=3,
            max_backtrack_symbols=int(cfg.preamble_len) + 2,
            min_run_symbols=int(cfg.preamble_len),
        )
        support_mask = np.asarray(
            [bool(branches) for branches in offset_branches], dtype=bool
        )
        supported_anchors = sfd_anchors[support_mask]
        supported_scores = anchor_down_scores[support_mask]
        supported_branches = [
            branches
            for branches, keep_branch in zip(offset_branches, support_mask)
            if bool(keep_branch)
        ]
        # The two SFD downchirps are the certificate; only the first is a
        # usable start anchor.  Apply legacy optional ranking only after the
        # purely structural gate, never in formal unlimited discovery.
        if (
            top_peaks_per_stream > 0
            and supported_anchors.size > top_peaks_per_stream
        ):
            keep = np.argsort(supported_scores)[::-1][
                :top_peaks_per_stream
            ]
            supported_anchors = supported_anchors[keep]
            supported_scores = supported_scores[keep]
            supported_branches = [supported_branches[int(index)] for index in keep]
        for peak, score, branches in zip(
            supported_anchors, supported_scores, supported_branches
        ):
            sfd_start = float(peak) - (cfg.preamble_len + 2) * n_symbol
            for offset in branches:
                # The midpoint removes the coupled up/down timing shift.  The
                # half-difference is the CFO estimate in LoRa bins.
                coarse_start = int(round(sfd_start + 0.5 * float(offset)))
                coarse_cfo = -0.5 * float(offset) / float(cfg.osr)
                raw_peaks.append(
                    (float(score), coarse_start, int(stream_idx), coarse_cfo)
                )
        diagnostics_rows.append(
            {
                "stream": int(stream_idx),
                "raw_downchirp_peak_count": raw_peak_count,
                "sfd_paired_peak_count": int(paired_peaks.size),
                "sfd_anchor_peak_count": int(sfd_anchors.size),
                "preamble_supported_sfd_anchor_count": int(
                    supported_anchors.size
                ),
                "preamble_required_run_length": int(cfg.preamble_len),
                "phase_coherent_branch_count": int(
                    sum(len(branches) for branches in offset_branches)
                ),
                "upchirp_peak_count": int(peaks_up.size),
                "correlation_threshold": float(height),
            }
        )
        if progress is not None:
            progress(
                "stream="
                f"{stream_idx + 1}/{streams.shape[0]} "
                f"raw_down={raw_peak_count} paired={paired_peaks.size} "
                f"anchors={sfd_anchors.size} "
                f"preamble_supported={supported_anchors.size}/"
                f"run{cfg.preamble_len} "
                f"branches={sum(len(branches) for branches in offset_branches)} "
                f"up={peaks_up.size}"
            )
        del correlation_up
        del normalized_up
        del sample_power

    # Keep a small hypothesis set per coarse bucket: the same packet is seen
    # by every stream, but in a dense collision the strongest peak may belong
    # to the winner while a slightly weaker peak (or a half-symbol-offset
    # anchor) can lock onto a buried neighbour.  Each kept peak is refined
    # from several half-symbol anchors; the receiver dedups the accepted
    # hypotheses afterwards.
    buckets: list[list[tuple[float, int, int]]] = []
    if int(hypotheses_per_bucket) <= 0:
        # Formal anonymous discovery must not let a high-scoring peak consume
        # a per-bucket quota before the physical start/CFO/channel test.
        buckets = [
            [row]
            for row in sorted(raw_peaks, key=lambda item: (item[1], item[2], item[3]))
        ]
    else:
        raw_peaks.sort(key=lambda row: row[0], reverse=True)
        for row in raw_peaks:
            _, coarse_start, _, _ = row
            placed = False
            for bucket in buckets:
                if abs(coarse_start - bucket[0][1]) < 0.75 * n_symbol:
                    if len(bucket) < int(hypotheses_per_bucket):
                        bucket.append(row)
                    placed = True
                    break
            if not placed:
                buckets.append([row])
    refine_cap = (
        int(refine_budget)
        if refine_budget is not None
        else max(96, min(320, int(max_candidates)))
    )
    refine_coarse_starts: list[tuple[int, float]] = []
    for bucket in buckets:
        for _, coarse_start, _, coarse_cfo in bucket:
            for offset_symbols in anchor_offsets_symbols:
                refine_coarse_starts.append(
                    (
                        int(coarse_start) + int(round(offset_symbols * n_symbol)),
                        float(coarse_cfo),
                    )
                )
        if refine_cap > 0 and len(refine_coarse_starts) >= refine_cap:
            break

    if progress is not None:
        seed_label = (
            "sfd_certificate_seed_count="
            if defer_sfd_refinement
            else "sfd_refine_seed_count="
        )
        progress(
            f"{seed_label}{len(refine_coarse_starts)} unique_before_bounds="
            f"{len(set(refine_coarse_starts))}"
        )

    rows: list[dict] = []
    seen_refine: set[tuple[int, float]] = set()
    for refine_index, (coarse_start, coarse_cfo) in enumerate(
        refine_coarse_starts, start=1
    ):
        refine_key = (int(coarse_start), round(float(coarse_cfo), 6))
        if refine_key in seen_refine:
            continue
        seen_refine.add(refine_key)
        if coarse_start < 0 or coarse_start + window_len > samples.shape[1]:
            continue
        if defer_sfd_refinement:
            # The formal builder performs exactly one local SFD/CFO refine in
            # its certificate stage.  The frontend hands over a structural
            # SFD-plus-full-preamble anchor without repeating that expensive
            # calculation or supplying an identity/timing prior.
            rows.append(
                {
                    "start_sample": float(coarse_start),
                    "sto_samples": 0.0,
                    "cfo_bins": 0.0,
                    "continuous_cfo_bins": 0.0,
                    "coarse_cfo_available": False,
                    "channel": [[0.0, 0.0], [0.0, 0.0]],
                    "power": 0.0,
                    "confidence": 0.0,
                    "sfd_confidence": 0.0,
                    "sync_confidence": 0.0,
                    "peak_bin": 0,
                    "frontend_candidate_stage": "sliding_sfd_preamble_structure",
                    "sliding_detection": {
                        "streams": int(streams.shape[0]),
                        "per_stream": diagnostics_rows,
                        "raw_peak_count": len(raw_peaks),
                        "refined_coarse_start_count": len(seen_refine),
                        "coarse_bucket_count": len(buckets),
                    },
                }
            )
            continue
        start, cfo, cto_samples, score, _, _ = sfd_anchored_start_cfo_refine(
            samples,
            float(coarse_start),
            cfg,
            symbol_radius=1,
            local_radius_bins=int(max(96.0, abs(cfo_min), abs(cfo_max))),
            use_integer_alias_branch=True,
            coarse_up_bin=float(coarse_cfo),
            physical_cfo_min=float(cfo_min),
            physical_cfo_max=float(cfo_max),
            max_start_correction_samples=0.75 * float(n_symbol),
        )
        if score <= 0.0 or not float(cfo_min) <= float(cfo) <= float(cfo_max):
            continue
        rounded_start = int(round(start))
        if rounded_start < 0 or rounded_start + int(cfg.frame_samples) > samples.shape[1]:
            continue
        sync = float(sync_word_score(samples, rounded_start, cfo, cfg))
        sfd = float(sfd_score(samples, rounded_start, cfo, cfg))
        if sfd < float(min_sfd_score) or sync < float(min_refined_sync_score):
            continue
        preamble_ratio, channel, peak_bin = preamble_channel_near_cfo(
            samples, start, cfo, cfg, radius_bins=2
        )
        rows.append(
            {
                "start_sample": float(math.floor(start)),
                "sto_samples": float(start - math.floor(start)),
                "cfo_bins": float(cfo),
                "continuous_cfo_bins": float(cfo),
                "channel": [
                    [float(np.real(value)), float(np.imag(value))]
                    for value in channel
                ],
                "power": float(np.vdot(channel, channel).real),
                "confidence": float(max(score, preamble_ratio)),
                "sfd_confidence": float(sfd),
                "sync_confidence": float(sync),
                "peak_bin": int(peak_bin),
                "frontend_candidate_stage": "sliding_sfd_preamble",
                "sfd_refined": True,
                "sfd_anchor_score": float(score),
                "sliding_detection": {
                    "streams": int(streams.shape[0]),
                    "per_stream": diagnostics_rows,
                    "raw_peak_count": len(raw_peaks),
                    "refined_coarse_start_count": len(seen_refine),
                    "coarse_bucket_count": len(buckets),
                },
            }
        )
        if progress is not None and refine_index % 32 == 0:
            progress(
                f"sfd_refine={refine_index}/{len(refine_coarse_starts)} "
                f"frontend_accepted={len(rows)}"
            )

    # Preamble-run path: a weak packet whose SFD downchirps are buried under an
    # ongoing stronger frame still emits up to eight repeated preamble
    # upchirps.  Their sliding upchirp correlation forms consecutive peaks one
    # symbol apart; each run anchors a small set of coarse seeds, the batched
    # multi-track confirms a coherent preamble bin, and the packet start is
    # recovered as ``seed + cfo*osr`` (the upchirp matched-filter peak shifts
    # by ``-cfo*osr`` samples relative to the symbol boundary).
    run_seeds: set[int] = set()
    preamble_run_diag: list[dict] = []
    required_run_symbols = min(
        int(cfg.preamble_len), max(3, int(min_preamble_run_symbols))
    )
    run_tolerance_samples = max(
        1, int(round(float(preamble_run_chain_tolerance_symbols) * n_symbol))
    )
    for stream_idx, peaks_up in enumerate(up_peaks_by_stream):
        chains: list[list[int]] = []
        for peak in peaks_up:
            peak = int(peak)
            chain = [peak]
            current = peak
            while len(chain) < 10:
                expected = current + n_symbol
                lower = int(
                    np.searchsorted(
                        peaks_up, expected - run_tolerance_samples, side="left"
                    )
                )
                upper = int(
                    np.searchsorted(
                        peaks_up, expected + run_tolerance_samples, side="right"
                    )
                )
                candidates = [
                    int(q) for q in peaks_up[lower:upper]
                ]
                if not candidates:
                    break
                nxt = min(candidates, key=lambda q: abs(q - expected))
                chain.append(nxt)
                current = nxt
            if len(chain) >= required_run_symbols:
                chains.append(chain)
                if required_run_symbols >= int(cfg.preamble_len):
                    # A complete preamble chain has one physical first symbol;
                    # unlike a short partial run, it does not need nine
                    # speculative backward expansions.
                    run_seeds.add(int(chain[0]))
                else:
                    for k in range(0, 9):
                        run_seeds.add(int(chain[0] - k * n_symbol))
        preamble_run_diag.append(
            {
                "stream": int(stream_idx),
                "chain_count": int(len(chains)),
                "required_run_symbols": int(required_run_symbols),
            }
        )
    if run_seeds:
        run_seed_list = sorted(run_seeds)
        if progress is not None:
            progress(f"preamble_run_seed_count={len(run_seed_list)}")
        if structural_preamble_run_only:
            for seed in run_seed_list:
                if seed < 0 or seed + window_len > samples.shape[1]:
                    continue
                rows.append(
                    {
                        "start_sample": float(seed),
                        "sto_samples": 0.0,
                        "cfo_bins": 0.0,
                        "continuous_cfo_bins": 0.0,
                        "coarse_cfo_available": False,
                        "channel": [[0.0, 0.0], [0.0, 0.0]],
                        "power": 0.0,
                        "confidence": 0.0,
                        "sfd_confidence": 0.0,
                        "sync_confidence": 0.0,
                        "peak_bin": 0,
                        "frontend_candidate_stage": "preamble_run_structure",
                        "sliding_detection": {
                            "preamble_run_streams": preamble_run_diag,
                            "preamble_run_seed_count": len(run_seed_list),
                        },
                    }
                )
        else:
            batched_runs = batched_stable_preamble_tracks(
                samples,
                np.asarray(run_seed_list, dtype=np.int64),
                cfg,
                top_k=16,
                min_hits=3,
                max_tracks=8,
                streams=streams,
                residual_projector=None,
            )
            for seed, (tracks, _residual) in zip(run_seed_list, batched_runs):
                for track in tracks:
                    score, _peak_bin, cfo, track_power, hits = track
                    if score < max(1.0, 0.5 * float(threshold)):
                        continue
                    if not float(cfo_min) <= float(cfo) <= float(cfo_max):
                        continue
                    start_est = int(seed) + int(round(float(cfo) * float(cfg.osr)))
                    if start_est < 0 or start_est + window_len > samples.shape[1]:
                        continue
                    preamble_ratio, channel, peak = preamble_channel_near_cfo(
                        samples, float(start_est), float(cfo), cfg, radius_bins=2
                    )
                    if preamble_ratio < 5.0:
                        continue
                    sync = float(
                        sync_word_score(
                            samples, int(round(start_est)), float(cfo), cfg
                        )
                    )
                    rows.append(
                        {
                            "start_sample": float(start_est),
                            "sto_samples": 0.0,
                            "cfo_bins": float(cfo),
                            "continuous_cfo_bins": float(cfo),
                            "channel": [
                                [float(np.real(value)), float(np.imag(value))]
                                for value in channel
                            ],
                            "power": float(np.vdot(channel, channel).real),
                            "confidence": float(max(score, preamble_ratio)),
                            "sfd_confidence": 0.0,
                            "sync_confidence": sync,
                            "peak_bin": int(peak),
                            "frontend_candidate_stage": "preamble_run_anchor",
                            "preamble_run_hits": int(hits),
                            "sliding_detection": {
                                "preamble_run_streams": preamble_run_diag,
                                "preamble_run_seed_count": len(run_seed_list),
                            },
                        }
                    )
        if progress is not None:
            progress(f"frontend_total_proposal_count={len(rows)}")
    rows.sort(key=lambda row: float(row["start_sample"]))
    return rows


def preamble_channel_near_cfo(
    samples: np.ndarray,
    start: float,
    cfo_bins: float,
    cfg: LoRaConfig,
    *,
    radius_bins: int = 1,
    cache: PreambleFFTCache | None = None,
) -> tuple[float, np.ndarray, int]:
    """在指定 CFO 附近做前导相干平均，得到 h。"""

    center = int(round(cfo_bins)) % cfg.m
    local = np.asarray([(center + dk) % cfg.m for dk in range(-radius_bins, radius_bins + 1)], dtype=np.int64)
    vectors: list[np.ndarray] = []
    ratios: list[float] = []
    bins: list[int] = []
    cached = cache.get(start) if cache is not None else None
    downchirp = instantaneous_chirp(0, cfg, up=False)
    for p in range(cfg.preamble_len):
        if cached is None:
            s = start + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                continue
            spec = dechirp_fft_dual(fractional_read_2d(samples, s, cfg.samples_per_symbol), downchirp, cfg)
            energy = np.sum(np.abs(spec) ** 2, axis=0)
            floor = float(np.median(energy)) + 1e-30
        else:
            spec = cached.spectra[p]
            energy = cached.energy[p]
            floor = float(cached.floor[p])
        b = int(local[int(np.argmax(energy[local]))])
        vectors.append(spec[:, b])
        ratios.append(float(energy[b] / floor))
        bins.append(b)
    if not vectors:
        return 0.0, np.zeros(samples.shape[0], dtype=np.complex128), center
    return float(np.median(ratios)), np.mean(np.asarray(vectors, dtype=np.complex128), axis=0), int(round(float(np.median(bins)))) % cfg.m


def coherent_preamble_track_score(
    samples: np.ndarray,
    start: float,
    cfo_bins: float,
    cfg: LoRaConfig,
    *,
    radius_bins: int = 1,
    eps_grid: int = 21,
    cache: PreambleFFTCache | None = None,
) -> tuple[float, float, np.ndarray, int, float, float, int]:
    """固定 CFO/bin 的 separated preamble 相干评分。"""

    center = int(round(cfo_bins)) % cfg.m
    local = np.asarray([(center + dk) % cfg.m for dk in range(-radius_bins, radius_bins + 1)], dtype=np.int64)
    vectors: list[np.ndarray] = []
    ratios: list[float] = []
    bins: list[int] = []
    powers: list[float] = []
    cached = cache.get(start) if cache is not None else None
    downchirp = instantaneous_chirp(0, cfg, up=False)
    for p in range(cfg.preamble_len):
        if cached is None:
            s = start + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                return 0.0, float(cfo_bins), np.zeros(samples.shape[0], dtype=np.complex128), center, 0.0, 0.0, 0
            spec = dechirp_fft_dual(fractional_read_2d(samples, s, cfg.samples_per_symbol), downchirp, cfg)
            energy = np.sum(np.abs(spec) ** 2, axis=0)
            floor = float(np.median(energy)) + 1e-30
        else:
            spec = cached.spectra[p]
            energy = cached.energy[p]
            floor = float(cached.floor[p])
        local_energy = energy[local]
        b = int(local[int(np.argmax(local_energy))])
        vectors.append(spec[:, b])
        bins.append(b)
        powers.append(float(energy[b]))
        ratios.append(float(energy[b] / floor))
    if not vectors:
        return 0.0, float(cfo_bins), np.zeros(samples.shape[0], dtype=np.complex128), center, 0.0, 0.0, 0

    v = np.asarray(vectors, dtype=np.complex128)
    denom = float(np.sum(np.abs(v) ** 2)) + 1e-30
    sym_idx = np.arange(v.shape[0], dtype=np.float64)
    best_metric = -1.0
    best_eps = 0.0
    best_channel = np.zeros(samples.shape[0], dtype=np.complex128)
    for eps in np.linspace(-0.5, 0.5, int(eps_grid), dtype=np.float64):
        aligned = v * np.exp(-1j * 2.0 * math.pi * float(eps) * sym_idx)[:, None]
        coherent = float(np.vdot(np.sum(aligned, axis=0), np.sum(aligned, axis=0)).real / denom)
        channel = np.mean(aligned, axis=0)
        h_norm = math.sqrt(float(np.vdot(channel, channel).real)) + 1e-30
        directions = [
            abs(np.vdot(channel, row)) / (h_norm * (math.sqrt(float(np.vdot(row, row).real)) + 1e-30))
            for row in aligned
        ]
        metric = coherent * (float(np.median(directions)) if directions else 0.0)
        if metric > best_metric:
            best_metric = float(metric)
            best_eps = float(eps)
            best_channel = channel
    peak_bin = int(round(float(np.median(bins)))) % cfg.m
    cfo = float(signed_bin(peak_bin, cfg.m)) + best_eps
    score = float(np.median(ratios) * max(best_metric, 0.0))
    return score, cfo, best_channel, peak_bin, float(np.median(powers)), float(best_metric), len(vectors)


def fixed_cfo_frame_score(samples: np.ndarray, start: float, cfo_bins: float, cfg: LoRaConfig) -> float:
    """固定 CFO 的帧结构评分：preamble + sync + SFD。"""

    pre_score, _, _ = preamble_channel_near_cfo(samples, start, cfo_bins, cfg, radius_bins=1)
    sync = sync_word_score(samples, start, cfo_bins, cfg)
    sfd = sfd_score(samples, start, cfo_bins, cfg)
    return float(math.log(pre_score + 1e-30) + 0.35 * math.log(sync + 1e-30) + 0.35 * math.log(sfd + 1e-30))


def refine_start_fixed_cfo(samples: np.ndarray, start: float, cfo_bins: float, cfg: LoRaConfig) -> tuple[float, float]:
    """固定 CFO 下粗修 start；仅用于强候选。"""

    best_start = float(start)
    best_score = fixed_cfo_frame_score(samples, best_start, cfo_bins, cfg)
    # Preserve the original SF10/BW125 search fractions while scaling the
    # sample grid for every SF/BW/OSR profile.
    for step, radius in (
        (max(1.0, cfg.samples_per_symbol / 32.0), cfg.samples_per_symbol / 4.0),
        (max(1.0, cfg.samples_per_symbol / 256.0), cfg.samples_per_symbol / 32.0),
    ):
        center = best_start
        for i in range(int(round(2.0 * radius / step)) + 1):
            trial = center - radius + i * step
            score = fixed_cfo_frame_score(samples, trial, cfo_bins, cfg)
            if score > best_score:
                best_start = float(trial)
                best_score = float(score)
    return best_start, best_score


def topk_preamble_track_score(
    samples: np.ndarray,
    start: int,
    cfg: LoRaConfig,
    *,
    top_k: int = 8,
    min_hits: int = 4,
    stable_streams: np.ndarray | None = None,
) -> tuple[float, int, float, float, int]:
    """fast refine 使用的局部 top-K 前导轨道评分。"""

    tracks = stable_preamble_multi_tracks(
        samples,
        start,
        cfg,
        top_k=top_k,
        min_hits=min_hits,
        max_tracks=1,
        streams=stable_streams,
    )
    if not tracks:
        return 0.0, 0, 0.0, 0.0, 0
    return tracks[0]


def refine_detection_candidate_fast(
    samples: np.ndarray,
    coarse_start: int,
    cfg: LoRaConfig,
    *,
    search_radius_samples: int | None = None,
    stable_streams: np.ndarray | None = None,
) -> tuple[float, float, int, float, float]:
    """强候选局部 top-K refine。"""

    radius = search_radius_samples or int(round(0.75 * cfg.samples_per_symbol))
    last = samples.shape[1] - (cfg.preamble_len + 4) * cfg.samples_per_symbol
    best = (float(coarse_start), -1.0, 0, 0.0, 0.0)
    for step, span in ((128, radius), (16, 256), (2, 32)):
        center = int(round(best[0]))
        for start in range(max(0, center - span), min(last, center + span) + 1, step):
            score, peak_bin, cfo_bins, power, _ = topk_preamble_track_score(
                samples,
                start,
                cfg,
                top_k=8,
                min_hits=4,
                stable_streams=stable_streams,
            )
            if score > best[1]:
                best = (float(start), float(score), int(peak_bin), float(cfo_bins), float(power))
    return best


def sfd_anchored_start_cfo_refine(
    samples: np.ndarray,
    start: float,
    cfg: LoRaConfig,
    *,
    symbol_radius: int = 1,
    local_radius_bins: int = 96,
    use_integer_alias_branch: bool = True,
    coarse_up_bin: float | None = None,
    physical_cfo_min: float | None = None,
    physical_cfo_max: float | None = None,
    max_start_correction_samples: float | None = None,
) -> tuple[float, float, float, float, float, float]:
    """用 SFD 边界给 weak candidate 提供 start seed；CFO 不直接信任。"""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    upchirp = instantaneous_chirp(0, cfg, up=True)
    best: tuple[float, float, float, float, float, float] | None = None
    base = int(round(start))
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    for sym_off in range(-symbol_radius, symbol_radius + 1):
        trial = base + sym_off * cfg.samples_per_symbol
        up_bins: list[float] = []
        up_ratios: list[float] = []
        for p in range(cfg.preamble_len):
            s = trial + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                continue
            energy = np.sum(np.abs(dechirp_fft_dual(samples[:, s : s + cfg.samples_per_symbol], downchirp, cfg)) ** 2, axis=0)
            if coarse_up_bin is None:
                b = int(np.argmax(energy))
            else:
                coarse_index = int(round(float(coarse_up_bin))) % int(cfg.m)
                local = np.asarray(
                    [(coarse_index + delta) % cfg.m for delta in range(-2, 3)],
                    dtype=np.int64,
                )
                b = int(local[int(np.argmax(energy[local]))])
            up_bins.append(float(signed_bin(b, cfg.m)))
            up_ratios.append(float(energy[b] / (np.median(energy) + 1e-30)))
        sfd_bins: list[float] = []
        sfd_ratios: list[float] = []
        sfd0 = trial + (cfg.preamble_len + 2) * cfg.samples_per_symbol
        for p in range(2):
            s = sfd0 + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                continue
            energy = np.sum(np.abs(dechirp_fft_dual(samples[:, s : s + cfg.samples_per_symbol], upchirp, cfg)) ** 2, axis=0)
            if coarse_up_bin is None:
                b = int(np.argmax(energy))
            else:
                # A competing packet may have the strongest downchirp in the
                # aggregate spectrum.  Retain only peaks that form a physical
                # CFO and a local start correction together with this raw
                # candidate's upchirp track.
                top_count = min(64, int(cfg.m))
                top = np.argpartition(energy, -top_count)[-top_count:]
                valid: list[int] = []
                for candidate_bin in top:
                    z_sfd_candidate = float(
                        signed_bin(int(candidate_bin), cfg.m)
                    )
                    coupled_cfo = 0.5 * (
                        float(coarse_up_bin) + z_sfd_candidate
                    )
                    coupled_cto_samples = 0.5 * (
                        float(coarse_up_bin) - z_sfd_candidate
                    ) * float(cfg.osr)
                    if (
                        physical_cfo_min is not None
                        and coupled_cfo < float(physical_cfo_min)
                    ) or (
                        physical_cfo_max is not None
                        and coupled_cfo > float(physical_cfo_max)
                    ):
                        continue
                    if (
                        max_start_correction_samples is not None
                        and abs(coupled_cto_samples)
                        > float(max_start_correction_samples)
                    ):
                        continue
                    valid.append(int(candidate_bin))
                if not valid:
                    continue
                b = max(valid, key=lambda index: float(energy[index]))
            sfd_bins.append(float(signed_bin(b, cfg.m)))
            sfd_ratios.append(float(energy[b] / (np.median(energy) + 1e-30)))
        if not up_bins or not sfd_bins:
            continue
        z_up = float(np.median(up_bins))
        z_sfd = float(np.median(sfd_bins))
        cfo_bins = 0.5 * (z_up + z_sfd)
        cto_bins = 0.5 * (z_up - z_sfd)
        corrected_start = float(trial - cto_bins * cfg.osr)

        cfo_comp = np.exp(-1j * 2.0 * math.pi * cfo_bins * n / cfg.samples_per_symbol).astype(np.complex64)
        residual_bins: list[float] = []
        residual_ratios: list[float] = []
        corrected_sfd0 = corrected_start + (cfg.preamble_len + 2) * cfg.samples_per_symbol
        for p in range(2):
            s = corrected_sfd0 + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
                continue
            window = fractional_read_2d(samples, s, cfg.samples_per_symbol) * cfo_comp[None, :]
            energy = np.sum(np.abs(dechirp_fft_dual(window, upchirp, cfg)) ** 2, axis=0)
            local = np.asarray([(dk % cfg.m) for dk in range(-local_radius_bins, local_radius_bins + 1)], dtype=np.int64)
            b = int(local[int(np.argmax(energy[local]))])
            residual_bins.append(float(signed_bin(b, cfg.m)))
            residual_ratios.append(float(energy[b] / (np.median(energy) + 1e-30)))
        if not residual_ratios:
            continue
        residual = float(np.median(np.abs(residual_bins)))
        strength = math.sqrt(max(float(np.median(up_ratios)), 1e-30)) * float(np.median(sfd_ratios))
        corrected_strength = float(np.median(residual_ratios))
        score = strength * math.sqrt(max(corrected_strength, 1e-30)) / (1.0 + residual)
        row = (corrected_start, cfo_bins, cto_bins * cfg.osr, score, z_up, z_sfd)
        if best is None or row[3] > best[3]:
            best = row
    if best is None:
        return float(start), 0.0, 0.0, 0.0, 0.0, 0.0

    # PCube/MaLoRaGW estimate CFO and STO directly from the half-sum and
    # half-difference of separated up/down chirps.  Keep that paper-native
    # midpoint available to independent baselines.  SP uses the safer bounded
    # integer ambiguity branch below; the two synchronization policies must
    # not silently change one another.
    if not bool(use_integer_alias_branch):
        return best

    # The half-sum/half-difference solution obtained from integer FFT peaks can
    # lie midway between two LoRa start--CFO aliases.  Using that midpoint for
    # payload demodulation leaves a half-bin residual even though either
    # adjacent integer branch is valid.  Enumerate a constant-size set of
    # coupled integer-CFO branches and select one only from preamble, Sync, and
    # SFD consistency.  Moving CFO by one bin requires moving the symbol start
    # by one oversampling factor to remain on the same LoRa ambiguity ridge.
    midpoint_start, midpoint_cfo, midpoint_cto, structure, z_up, z_sfd = best
    alias_rows: list[tuple[float, float, float, float]] = []
    alias_lo = int(math.floor(midpoint_cfo)) - 3
    alias_hi = int(math.ceil(midpoint_cfo)) + 3
    for alias_cfo_int in range(alias_lo, alias_hi + 1):
        alias_cfo = float(alias_cfo_int)
        cfo_delta = alias_cfo - float(midpoint_cfo)
        alias_start = float(midpoint_start) + cfo_delta * float(cfg.osr)
        if alias_start < 0.0:
            continue
        alias_rows.append(
            (
                fixed_cfo_frame_score(samples, alias_start, alias_cfo, cfg),
                -abs(cfo_delta),
                alias_start,
                alias_cfo,
            )
        )
    if not alias_rows:
        return best
    _, _, selected_start, selected_cfo = max(alias_rows)
    selected_delta = selected_cfo - float(midpoint_cfo)
    selected_cto = float(midpoint_cto) - selected_delta * float(cfg.osr)
    return (
        float(selected_start),
        float(selected_cfo),
        float(selected_cto),
        float(structure),
        float(z_up),
        float(z_sfd),
    )


def fractional_sto_template_refine(
    samples: np.ndarray,
    start: float,
    cfo_bins: float,
    cfg: LoRaConfig,
    *,
    span_samples: float = 0.5,
    grid: int = 17,
) -> tuple[float, float]:
    """按 v1 的局部谱模板思想细化分数 STO。

    在固定 CFO 下，对 start 周围的分数采样偏移生成本地 upchirp 频谱模板；
    选择使前导局部谱最集中且跨天线一致的偏移。
    """

    downchirp = instantaneous_chirp(0, cfg, up=False)
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    cfo_comp = np.exp(-1j * 2.0 * math.pi * float(cfo_bins) * n / cfg.samples_per_symbol).astype(np.complex64)
    center = int(round(cfo_bins)) % cfg.m
    local = np.asarray([(center + dk) % cfg.m for dk in range(-3, 4)], dtype=np.int64)
    best_start = float(start)
    best_score = -1.0
    for delta in np.linspace(-float(span_samples), float(span_samples), int(grid), dtype=np.float64):
        trial = float(start) + float(delta)
        local_vectors: list[np.ndarray] = []
        local_ratios: list[float] = []
        for p in range(cfg.preamble_len):
            s = trial + p * cfg.samples_per_symbol
            if s < 0.0 or s + cfg.samples_per_symbol > samples.shape[1]:
                continue
            window = fractional_read_2d(samples, s, cfg.samples_per_symbol) * cfo_comp[None, :]
            spec = dechirp_fft_dual(window, downchirp, cfg)
            energy = np.sum(np.abs(spec) ** 2, axis=0)
            b = int(local[int(np.argmax(energy[local]))])
            local_vectors.append(spec[:, b])
            local_ratios.append(float(energy[b] / (np.median(energy) + 1e-30)))
        if len(local_vectors) < max(3, cfg.preamble_len // 2):
            continue
        v = np.asarray(local_vectors, dtype=np.complex128)
        coherent = float(np.vdot(np.sum(v, axis=0), np.sum(v, axis=0)).real / (float(np.sum(np.abs(v) ** 2)) + 1e-30))
        score = float(np.median(local_ratios) * max(coherent, 0.0))
        if score > best_score:
            best_score = score
            best_start = trial
    return best_start, float(best_score)


def joint_start_cfo_sto_refine(
    samples: np.ndarray,
    start: float,
    cfo_hint: float,
    cfg: LoRaConfig,
) -> tuple[float, float, float, float, float]:
    """v1 前导+SFD 联合估计 start、连续 CFO 和分数 STO。

    返回值为 (integer_start, sto_samples, continuous_cfo, score, cto_samples)。
    start+sto_samples 是最终连续符号起点。
    """

    sfd_start, sfd_cfo, cto_samples, sfd_score_value, _, _ = sfd_anchored_start_cfo_refine(samples, start, cfg)
    seed_start = sfd_start if sfd_score_value > 0.0 else float(start)
    seed_cfo = sfd_cfo if sfd_score_value > 0.0 else float(cfo_hint)
    refined_start, sto_score = fractional_sto_template_refine(samples, seed_start, seed_cfo, cfg)
    coh_score, coh_cfo, _, _, _, coh_metric, _ = coherent_preamble_track_score(
        samples,
        refined_start,
        seed_cfo,
        cfg,
        radius_bins=1,
        eps_grid=31,
    )
    # ``coh_cfo`` aligns phase evolution across repeated preamble chirps.  In
    # real B210 traces that evolution also contains sampling-clock drift and is
    # not necessarily the within-symbol CFO used by the payload FFT.  Keep the
    # SFD-selected integer ambiguity branch for demodulation; coherent tracking
    # contributes only to channel/reliability scoring.
    integer_start = math.floor(refined_start)
    sto_samples = float(refined_start - integer_start)
    score = float(max(sto_score, 0.0) * math.sqrt(max(coh_metric, 0.0) + 1e-30) + max(sfd_score_value, 0.0))
    return float(integer_start), sto_samples, float(seed_cfo), score, float(cto_samples)


def refine_start_cfo_coherent(
    samples: np.ndarray,
    start: float,
    cfg: LoRaConfig,
    *,
    cfo_min: float = -28.0,
    cfo_max: float = -18.0,
    radius_samples: float = 2048.0,
) -> tuple[float, float, np.ndarray, int, float, float, float]:
    """局部联合 start/CFO/h refine，目标函数是前导相干性。"""

    last = samples.shape[1] - (cfg.preamble_len + 4) * cfg.samples_per_symbol
    best_start = float(np.clip(start, 0.0, float(max(0, last))))
    best_cfo = 0.0
    best_channel = np.zeros(samples.shape[0], dtype=np.complex128)
    best_peak = 0
    best_power = 0.0
    best_metric = 0.0
    best_score = -1.0
    cache = PreambleFFTCache(samples, cfg)
    cfo_grid = np.arange(float(cfo_min), float(cfo_max) + 0.5, 1.0, dtype=np.float64)
    for step, radius in ((128.0, radius_samples), (16.0, 192.0), (2.0, 24.0), (1.0, 4.0)):
        center = best_start
        if best_score > 0.0 and step <= 64.0:
            cfo_center = float(round(best_cfo))
            trial_cfos = np.arange(max(cfo_min, cfo_center - 2.0), min(cfo_max, cfo_center + 2.0) + 0.5, 1.0)
        else:
            trial_cfos = cfo_grid
        for i in range(int(round(2.0 * radius / step)) + 1):
            trial_start = float(center - radius + i * step)
            if trial_start < 0.0 or trial_start > last:
                continue
            for cfo_trial in trial_cfos:
                score, cfo, channel, peak_bin, power, metric, _ = coherent_preamble_track_score(
                    samples,
                    trial_start,
                    float(cfo_trial),
                    cfg,
                    radius_bins=1,
                    eps_grid=11 if step > 8.0 else 21,
                    cache=cache,
                )
                if score > best_score:
                    best_score = float(score)
                    best_start = float(trial_start)
                    best_cfo = float(cfo)
                    best_channel = channel
                    best_peak = int(peak_bin)
                    best_power = float(power)
                    best_metric = float(metric)
    return best_start, best_cfo, best_channel, best_peak, best_power, best_score, best_metric


def pcube_sp_estimates(
    samples: np.ndarray,
    cfg: LoRaConfig,
    *,
    max_candidates: int,
    threshold: float,
    step_samples: int,
    min_sync_score: float,
    min_coherent_metric: float,
) -> list[dict]:
    """最终 SP 前端：检测并估计每个并发包的 start/CFO/h。"""

    x = apply_rf_calibration(samples)
    x = x - np.mean(x, axis=1, keepdims=True)
    stable_streams, _, _ = pca_project_streams(x, include_original=True)
    preamble_cache = PreambleFFTCache(x, cfg)
    last = x.shape[1] - (cfg.preamble_len + 4) * cfg.samples_per_symbol

    raw: list[tuple[float, float, float, int, float, float, int]] = []
    for start in range(0, max(0, last), int(step_samples)):
        for score, peak_bin, cfo, power, hits in stable_preamble_multi_tracks(x, start, cfg, streams=stable_streams):
            if score < threshold:
                continue
            sync = sync_word_score(x, start, cfo, cfg)
            sfd = sfd_score(x, start, cfo, cfg)
            if min_sync_score > 0.0 and sync * sfd < min_sync_score:
                continue
            confidence = float(score * math.sqrt(max(sync, 1.0)) * math.sqrt(max(sfd, 1.0)) * math.sqrt(max(hits, 1)))
            raw.append((confidence, float(start), float(cfo), int(peak_bin), float(power), float(sync), int(hits)))

    raw.sort(key=lambda row: row[0], reverse=True)
    selected: list[tuple[float, float, float, int, float, float, int]] = []
    for row in raw:
        _, start, *_ = row
        if any(abs(start - old[1]) < 4.0 * cfg.samples_per_symbol for old in selected):
            continue
        selected.append(row)
        if len(selected) >= max(30, int(max_candidates) * 2):
            break

    def refine_priority(row: tuple[float, float, float, int, float, float, int]) -> tuple[int, float, float, float]:
        confidence, _, cfo, _, _, sync, hits = row
        return (int(-30.0 <= float(cfo) <= -17.0), float(hits), float(confidence), float(sync))

    selected.sort(key=refine_priority, reverse=True)
    estimates: list[dict] = []
    coherent_refine_budget = max(6, int(max_candidates))
    coherent_refines_used = 0

    for u, (confidence, start, cfo, peak_bin, power, _sync, hits) in enumerate(selected):
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
                and abs(float(refined_start) - float(fixed_start)) <= 0.25 * cfg.samples_per_symbol
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
            final_cfo = float(coherent_cfo)
            final_power = float(max(final_power, coherent_power))

        # 低 metric 或明显不物理的 CFO 都必须进入 coherent refine。
        # 实测中强包重复窗口可能给出很高的前导相干分，但 CFO 会跳到
        # +几十/-几百 bin；这类候选若不 refine，会造成 start/h 匹配错误。
        nonphysical_cfo = final_cfo < -30.0 or final_cfo > -17.0
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
                radius_samples=2048.0 if refine_seed != float(start) else 1.5 * cfg.samples_per_symbol,
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
        # 兼容历史评估的整数 CFO 字段保留；正式 SP 链路使用连续 CFO 字段。
        continuous_cfo = float(final_cfo)
        final_cfo = float(math.floor(continuous_cfo + 0.5))
        estimates.append(
            {
                "packet_index": int(u),
                "start_sample": float(final_start),
                "cfo_bins": float(final_cfo),
                "continuous_cfo_bins": float(continuous_cfo),
                "sto_samples": float(joint_sto),
                "channel": complex_pairs(channel),
                "confidence": float(confidence),
                "sfd_confidence": float(sfd_score(x, int(round(float(final_start) + float(joint_sto))), final_cfo, cfg)),
                "ml_cfo_bins": float(final_cfo),
                "ml_continuous_cfo_bins": float(continuous_cfo),
                "ml_coherent_metric": float(channel_score),
                "peak_bin": int(local_peak),
                "power": float(final_power),
                "cto_samples": float(cto_samples),
                "pcube_track_hits": int(hits),
                "pcube_structure_score": float(struct_score),
                "pcube_used_refined": bool(use_refined),
                "pcube_fast_refine_enabled": bool(use_fast_refine),
                "pcube_coherent_score": float(coherent_score),
                "pcube_coherent_metric": float(coherent_metric),
                "pcube_coherent_hits": int(coherent_hits),
                "frontend_candidate_stage": "stable_pca",
                "pre_joint_start_sample": float(pre_joint_start),
                "pre_joint_cfo_bins": float(pre_joint_cfo),
                "joint_cfo_delta_bins": float(joint_cfo_delta),
                "joint_start_delta_samples": float(joint_start_delta),
                "joint_refine_accepted": bool(joint_accepted),
            }
        )
    def final_priority(est: dict) -> tuple[int, int, float]:
        cfo = float(est.get("continuous_cfo_bins", est.get("cfo_bins", 0.0)))
        physical_cfo = int(-30.0 <= cfo <= -17.0)
        hits = int(est.get("pcube_track_hits", 0))
        score = float(est.get("pcube_structure_score", 0.0)) * math.sqrt(max(float(est.get("confidence", 0.0)), 1.0))
        return physical_cfo, hits, score

    estimates.sort(key=final_priority, reverse=True)
    final_estimates: list[dict] = []
    for est in estimates:
        start = float(est["start_sample"]) + float(est.get("sto_samples", 0.0))
        if any(abs(start - (float(old["start_sample"]) + float(old.get("sto_samples", 0.0)))) < 4.0 * cfg.samples_per_symbol for old in final_estimates):
            continue
        final_estimates.append(est)
        if len(final_estimates) >= max(30, int(max_candidates)):
            break
    final_estimates.sort(key=lambda est: float(est["start_sample"]) + float(est.get("sto_samples", 0.0)))
    return final_estimates


def detected_estimates(
    samples: np.ndarray,
    cfg: LoRaConfig,
    *,
    max_candidates: int,
    threshold: float,
    step_samples: int,
    min_sync_score: float,
    min_coherent_metric: float,
    frontend: str,
) -> tuple[list[dict], list[SyncCandidate]]:
    """统一检测入口；最终只保留 pcube_sp。"""

    if frontend != "pcube_sp":
        raise ValueError("only frontend='pcube_sp' is kept in the final MRC/SP codebase")
    estimates = pcube_sp_estimates(
        samples,
        cfg,
        max_candidates=max_candidates,
        threshold=threshold,
        step_samples=step_samples,
        min_sync_score=min_sync_score,
        min_coherent_metric=min_coherent_metric,
    )
    candidates = [
        SyncCandidate(
            start_sample=float(est["start_sample"]),
            cfo_bins=float(est["cfo_bins"]),
            sto_samples=float(est.get("sto_samples", 0.0)),
            power=float(est.get("power", 0.0)),
            confidence=float(est["confidence"]),
            peak_bin=int(est.get("peak_bin", int(round(float(est["cfo_bins"]))) % cfg.m)),
            sfd_confidence=float(est["sfd_confidence"]),
        )
        for est in estimates
    ]
    return estimates, candidates
