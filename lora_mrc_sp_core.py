"""LoRa MRC/SP 接收核心函数。

本文件只保留最终实验链路需要的内容：
1. LoRa 基本参数、过采样 chirp、folded FFT 解调；
2. MRC 基线合并；
3. SP-Dechirp 所需的窗口补偿、前导信道估计和基础工具。

历史探索分支不再放在核心代码里。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class LoRaConfig:
    """当前 USRP 实验使用的固定 LoRa 配置。"""

    sf: int = 10
    bw_hz: float = 125_000.0
    sample_rate_hz: float = 1_000_000.0
    cr: int = 1
    preamble_len: int = 8
    sync_word: int = 0x12
    payload_len: int = 32
    crc_on: bool = True
    implicit_header: bool = True
    ldro: bool = False

    @property
    def m(self) -> int:
        return 1 << self.sf

    @property
    def osr(self) -> int:
        ratio = self.sample_rate_hz / self.bw_hz
        rounded = int(round(ratio))
        if abs(ratio - rounded) > 1e-9:
            raise ValueError("sample_rate_hz must be an integer multiple of bw_hz")
        return rounded

    @property
    def samples_per_symbol(self) -> int:
        return self.m * self.osr

    @property
    def payload_nibble_count(self) -> int:
        return 2 * self.payload_len + (4 if self.crc_on else 0)

    @property
    def payload_symbol_count(self) -> int:
        """按当前 implicit-header 配置计算 payload LoRa 符号数。"""

        cw_cnt = 0
        symbols = 0
        while cw_cnt < self.payload_nibble_count:
            reduced = (cw_cnt == 0) or self.ldro
            sf_app = self.sf - 2 if reduced else self.sf
            cw_len = 4 + (4 if cw_cnt < self.sf - 2 else self.cr)
            symbols += cw_len
            cw_cnt += sf_app
        return symbols

    @property
    def payload_start_symbols(self) -> float:
        # 标准 LoRa 帧结构：8 个 preamble + 2 个 sync + 2.25 个 SFD。
        return self.preamble_len + 4.25

    @property
    def frame_symbols(self) -> float:
        return self.payload_start_symbols + self.payload_symbol_count

    @property
    def frame_samples(self) -> int:
        return int(round(self.frame_symbols * self.samples_per_symbol))


@dataclass(frozen=True)
class SyncCandidate:
    """检测前端输出的一个候选包参数。"""

    start_sample: float
    cfo_bins: float
    sto_samples: float
    power: float
    confidence: float
    peak_bin: int
    sfd_confidence: float = 0.0
    candidate_list: tuple[tuple[float, float, float], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PreambleMLEstimate:
    """前导码联合估计结果。"""

    start_sample: float
    peak_bin: int
    cfo_bins: float
    fine_cfo_bins: float
    channel: np.ndarray
    coherent_metric: float
    phase_variance: float
    hit_count: int


@dataclass(frozen=True)
class BranchParameters:
    """MRC 分支参数。

    这里只使用 w0；其它字段保留为轻量占位，方便旧评估结果结构兼容。
    """

    w0: np.ndarray
    b: np.ndarray
    p0: complex
    rho: float
    phi: float
    mu: float
    noise_gain: float
    objective: float


@dataclass
class SymbolDecision:
    symbol_bin: int
    raw_symbol: int
    peak_power: float
    margin_db: float


@dataclass
class PhyDecodeResult:
    payload: bytes
    crc_ok: bool
    fec_errors: int
    corrected_codewords: int
    header_valid: bool
    decoded_nibbles: list[int]


@dataclass
class PacketDecodeResult:
    packet_index: int
    decisions: list[SymbolDecision]
    phy: PhyDecodeResult
    mean_margin_db: float
    min_margin_db: float


def signed_bin(bin_index: int, m: int) -> int:
    """把 FFT bin 转成带符号频偏 bin。"""

    b = int(bin_index) % m
    return b if b < m // 2 else b - m


def instantaneous_chirp(symbol: int, cfg: LoRaConfig, up: bool = True) -> np.ndarray:
    """生成与当前实测链路一致的过采样 LoRa chirp。"""

    if not up:
        return np.conj(instantaneous_chirp(symbol, cfg, up=True))
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    symbol = int(symbol) % cfg.m
    phase = (
        math.pi * n * n / (cfg.m * cfg.osr * cfg.osr)
        - math.pi * n / cfg.osr
        + 2.0 * math.pi * symbol * n / (cfg.m * cfg.osr)
    )
    fold = (cfg.m - symbol) * cfg.osr
    if symbol and fold < cfg.samples_per_symbol:
        phase[int(fold) :] -= 2.0 * math.pi * n[int(fold) :] / cfg.osr
    return np.exp(1j * phase).astype(np.complex64)


def fractional_read_1d(x: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """线性插值读取一维复数波形，用于分数采样 start。"""

    pos = np.asarray(positions, dtype=np.float64)
    lo = np.floor(pos).astype(np.int64)
    frac = pos - lo
    valid = (lo >= 0) & (lo + 1 < x.size)
    out = np.zeros(pos.shape, dtype=np.complex64)
    if np.any(valid):
        out[valid] = ((1.0 - frac[valid]) * x[lo[valid]] + frac[valid] * x[lo[valid] + 1]).astype(np.complex64)
    edge = pos == x.size - 1
    if np.any(edge):
        out[edge] = x[-1]
    return out


def fractional_read_2d(x: np.ndarray, start: float, length: int) -> np.ndarray:
    """从双天线 IQ 中按分数 start 读取一个窗口。"""

    positions = start + np.arange(length, dtype=np.float64)
    return np.vstack([fractional_read_1d(x[ch], positions) for ch in range(x.shape[0])])


def add_fractional_waveform(dst: np.ndarray, waveform: np.ndarray, start: float, gain: complex) -> None:
    """把 clean 包片段按分数 start 加到合成接收缓存中。"""

    lo = max(0, int(math.floor(start)) - 2)
    hi = min(dst.size, int(math.ceil(start + waveform.size)) + 2)
    if hi <= lo:
        return
    rel = np.arange(lo, hi, dtype=np.float64) - float(start)
    dst[lo:hi] += gain * fractional_read_1d(waveform, rel)


def apply_rf_calibration(samples: np.ndarray, correction: np.ndarray | None = None) -> np.ndarray:
    """双通道射频链校准入口；当前离线数据默认不额外校准。"""

    if correction is None:
        return np.asarray(samples, dtype=np.complex64)
    c = np.asarray(correction, dtype=np.complex64).reshape(-1)
    if c.size != samples.shape[0]:
        raise ValueError("RF correction vector length must match channel count")
    return (samples / c[:, None]).astype(np.complex64)


def pca_project_streams(samples: np.ndarray, *, include_original: bool = True) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MaLoRaGW-style PCA 投影，用于弱前导在多天线子空间中显现。"""

    x = np.asarray(samples, dtype=np.complex64)
    cov = (x @ x.conj().T) / max(1, x.shape[1])
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    projected = eigvecs.conj().T @ x
    streams = np.vstack([x, projected.astype(np.complex64)]) if include_original else projected.astype(np.complex64)
    return streams.astype(np.complex64), eigvecs, eigvals


def lora_symbol_fft(mixed: np.ndarray, cfg: LoRaConfig) -> np.ndarray:
    """过采样 LoRa 的正确 M 点 FFT。

    当前 GNU Radio/USRP 实测波形在 dechirp 后应取固定 polyphase 分支；
    直接把 OSR 个采样相加会引入符号相关旁瓣。
    """

    chip_rate = np.asarray(mixed, dtype=np.complex128)[:: cfg.osr][: cfg.m]
    return np.fft.fft(chip_rate)


def dechirp_fft(window: np.ndarray, downchirp: np.ndarray, cfg: LoRaConfig) -> np.ndarray:
    return lora_symbol_fft(window * downchirp, cfg)


def dechirp_fft_dual(window: np.ndarray, downchirp: np.ndarray, cfg: LoRaConfig) -> np.ndarray:
    return np.vstack([dechirp_fft(window[ch], downchirp, cfg) for ch in range(window.shape[0])])


def peak_margin(spec: np.ndarray, peak: int) -> tuple[float, float]:
    """返回峰值功率和相对第二峰 margin(dB)。"""

    power = np.abs(spec) ** 2
    pk = float(power[int(peak)])
    other = np.delete(power, int(peak))
    second = float(np.max(other)) if other.size else 1e-30
    return pk, 10.0 * math.log10((pk + 1e-30) / (second + 1e-30))


def noncoherent_preamble_score(
    samples: np.ndarray,
    start: int,
    cfg: LoRaConfig,
    *,
    preamble_windows: int | None = None,
) -> tuple[float, int, float, float]:
    """clean 包提取用的非相干前导评分。"""

    preamble_windows = cfg.preamble_len if preamble_windows is None else preamble_windows
    downchirp = instantaneous_chirp(0, cfg, up=False)
    peak_bins: list[int] = []
    ratios: list[float] = []
    peak_powers: list[float] = []
    for p in range(preamble_windows):
        s = start + p * cfg.samples_per_symbol
        if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
            return 0.0, 0, 0.0, 0.0
        spec = dechirp_fft_dual(samples[:, s : s + cfg.samples_per_symbol], downchirp, cfg)
        energy = np.sum(np.abs(spec) ** 2, axis=0)
        peak = int(np.argmax(energy))
        peak_bins.append(peak)
        peak_powers.append(float(energy[peak]))
        ratios.append(float(energy[peak] / (float(np.median(energy)) + 1e-30)))
    signed = np.asarray([signed_bin(b, cfg.m) for b in peak_bins], dtype=np.float64)
    consistency = math.exp(-float(np.std(signed)) / 2.0)
    score = float(np.median(ratios) * consistency)
    return score, int(np.median(peak_bins)), float(np.median(signed)), float(np.median(peak_powers))


def estimate_preamble_ml_cfo_channel(
    samples: np.ndarray,
    start_sample: float,
    cfg: LoRaConfig,
    *,
    center_bin: int | None = None,
    bin_radius: int = 96,
    fine_cfo_grid: int = 33,
) -> PreambleMLEstimate:
    """用重复 upchirp 的相干性估计前导 CFO 和双天线信道。"""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    start = int(round(start_sample))
    spectra: list[np.ndarray] = []
    for p in range(cfg.preamble_len):
        s = start + p * cfg.samples_per_symbol
        if s < 0 or s + cfg.samples_per_symbol > samples.shape[1]:
            continue
        spectra.append(dechirp_fft_dual(samples[:, s : s + cfg.samples_per_symbol], downchirp, cfg))
    if not spectra:
        return PreambleMLEstimate(start_sample, 0, 0.0, 0.0, np.zeros(samples.shape[0], dtype=np.complex128), 0.0, float("inf"), 0)
    spec = np.asarray(spectra, dtype=np.complex128)
    energy_bins = np.median(np.sum(np.abs(spec) ** 2, axis=1), axis=0)
    center = int(np.argmax(energy_bins)) if center_bin is None else int(center_bin) % cfg.m
    bins = np.asarray([(center + dk) % cfg.m for dk in range(-bin_radius, bin_radius + 1)], dtype=np.int64)
    eps_grid = np.linspace(-0.5, 0.5, fine_cfo_grid)
    chirp_index = np.arange(spec.shape[0], dtype=np.float64)
    best_metric = -1.0
    best_phase_var = float("inf")
    best_bin = center
    best_eps = 0.0
    best_channel = np.zeros(samples.shape[0], dtype=np.complex128)
    for b in bins:
        vectors = spec[:, :, b]
        denom = float(np.sum(np.abs(vectors) ** 2)) + 1e-30
        for eps in eps_grid:
            aligned = vectors * np.exp(-1j * 2.0 * math.pi * float(eps) * chirp_index)[:, None]
            channel = np.mean(aligned, axis=0)
            coherent = float(np.vdot(np.sum(aligned, axis=0), np.sum(aligned, axis=0)).real / denom)
            phases = np.unwrap(np.angle(aligned @ np.conj(channel)))
            phase_var = float(np.var(phases)) if phases.size else float("inf")
            metric = coherent / (1.0 + phase_var)
            if metric > best_metric:
                best_metric = metric
                best_phase_var = phase_var
                best_bin = int(b)
                best_eps = float(eps)
                best_channel = channel
    signed = float(signed_bin(best_bin, cfg.m))
    return PreambleMLEstimate(
        start_sample=float(start_sample),
        peak_bin=best_bin,
        cfo_bins=signed + best_eps,
        fine_cfo_bins=best_eps,
        channel=best_channel,
        coherent_metric=float(best_metric),
        phase_variance=float(best_phase_var),
        hit_count=len(spectra),
    )


def target_orthogonal_basis(channel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """构造目标方向 a 和其正交方向 b。SP 在这两个投影上做差分判决。"""

    h = np.asarray(channel, dtype=np.complex128).reshape(2)
    norm = math.sqrt(float(np.vdot(h, h).real))
    if norm <= 0.0:
        raise ValueError("channel vector must be nonzero")
    a = h / norm
    b = np.asarray([-np.conj(a[1]), np.conj(a[0])], dtype=np.complex128)
    return a, b


def fixed_mrc_branch_parameters(channel: np.ndarray) -> BranchParameters:
    """MRC 基线：沿目标信道方向做相干合并。"""

    a, b = target_orthogonal_basis(channel)
    return BranchParameters(w0=a, b=b, p0=1.0 + 0.0j, rho=0.0, phi=0.0, mu=0.0, noise_gain=1.0, objective=0.0)


def compensate_symbol_window(
    samples: np.ndarray,
    symbol_start: float,
    cfo_bins: float,
    cfg: LoRaConfig,
    *,
    sto_samples: float = 0.0,
) -> np.ndarray:
    """读取 payload 符号窗口，并补偿接收端估计出的 CFO。"""

    window = fractional_read_2d(samples, float(symbol_start) + float(sto_samples), cfg.samples_per_symbol)
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    cfo = np.exp(-1j * 2.0 * math.pi * float(cfo_bins) * n / cfg.samples_per_symbol).astype(np.complex64)
    return window * cfo[None, :]


def combine_branch_symbol(compensated: np.ndarray, params: BranchParameters, cfg: LoRaConfig) -> tuple[np.ndarray, np.ndarray]:
    """对一个已补偿符号做 MRC 合并并 FFT。"""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    mixed = compensated * downchirp[None, :]
    spectra = np.vstack([lora_symbol_fft(mixed[ch], cfg) for ch in range(compensated.shape[0])])
    combined = np.conj(params.w0) @ spectra
    return combined, spectra


def gray_demap(symbol: int, cfg: LoRaConfig) -> int:
    """LoRa Gray demap；评估 SER 时主要使用 symbol_bin。"""

    out = int(symbol)
    shift = 1
    while shift < 32:
        out ^= out >> shift
        shift <<= 1
    return (out + 1) % cfg.m


def decode_packet_branch(
    samples: np.ndarray,
    packet_index: int,
    start_sample: float,
    cfo_bins: float,
    params: BranchParameters,
    cfg: LoRaConfig,
    *,
    sto_samples: float = 0.0,
) -> PacketDecodeResult:
    """MRC 包级 payload 解调。

    这里输出每个 payload 符号的 FFT top-1 bin；PHY payload/CRC 不参与当前
    MRC/SP 的 SER/PRR 评估，因此只保留空的 PHY 占位结果。
    """

    decisions: list[SymbolDecision] = []
    for q in range(cfg.payload_symbol_count):
        symbol_start = start_sample + (cfg.payload_start_symbols + q) * cfg.samples_per_symbol
        compensated = compensate_symbol_window(samples, symbol_start, cfo_bins, cfg, sto_samples=sto_samples)
        spectrum, _ = combine_branch_symbol(compensated, params, cfg)
        peak = int(np.argmax(np.abs(spectrum) ** 2))
        peak_power, margin_db = peak_margin(spectrum, peak)
        decisions.append(
            SymbolDecision(
                symbol_bin=peak,
                raw_symbol=gray_demap(peak, cfg),
                peak_power=peak_power,
                margin_db=margin_db,
            )
        )
    margins = [d.margin_db for d in decisions]
    return PacketDecodeResult(
        packet_index=int(packet_index),
        decisions=decisions,
        phy=PhyDecodeResult(payload=b"", crc_ok=False, fec_errors=0, corrected_codewords=0, header_valid=True, decoded_nibbles=[]),
        mean_margin_db=float(np.mean(margins)) if margins else 0.0,
        min_margin_db=float(np.min(margins)) if margins else 0.0,
    )
