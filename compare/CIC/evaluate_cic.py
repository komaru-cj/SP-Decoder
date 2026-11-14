"""CIC reproduction on the shared real USRP collision scenes.

Implemented components from the paper:
- downchirp/SFD-style packet estimates are supplied by the shared detector;
- for each target symbol, sub-symbol boundaries are induced by all other
  detected packet starts modulo the target symbol period;
- CIC spectral intersection is the bin-wise minimum of normalized spectra over
  the optimal ICSS: full symbol plus each pair [0,tau_i] and [tau_i,N];
- Spectral Edge Difference (SED) chooses among surviving candidates.

On the two-channel dataset, fixed target MRC is applied before the CIC core.
Weights are estimated once from the physical preamble at the supplied sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "compare") not in sys.path:
    sys.path.insert(0, str(ROOT / "compare"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common_compare import (  # noqa: E402
    base_arg_parser,
    evaluate_decoder,
    load_experiment,
    write_report,
)
from evaluate_sp_dechirp_real_pos import oracle_estimates  # noqa: E402
from compare.mrc_input import target_mrc_weights  # noqa: E402
from lora_mrc_sp_core import (  # noqa: E402
    compensate_symbol_window,
    dechirp_fft_dual,
    fractional_read_2d,
    instantaneous_chirp,
    signed_bin,
)


_ALL_ESTIMATES: list[dict] = []


def _masked_spectrum(mixed: np.ndarray, cfg, lo: int, hi: int) -> np.ndarray:
    lo = max(0, int(lo))
    hi = min(int(hi), mixed.size)
    if hi <= lo:
        return np.zeros(cfg.m, dtype=np.float64)
    # Variable-duration sub-symbol spectrum: evaluate the DTFT on LoRa's M
    # symbol bins using only samples inside [lo, hi).  This preserves the wider
    # sinc main-lobe of short sections instead of treating every section as a
    # full-symbol demodulation.
    first_chip = int(np.ceil(lo / cfg.osr))
    last_chip = int(np.floor((hi - 1) / cfg.osr))
    if last_chip < first_chip:
        return np.zeros(cfg.m, dtype=np.float64)
    chip_idx = np.arange(first_chip, last_chip + 1, dtype=np.int64)
    values = np.asarray(mixed[chip_idx * cfg.osr], dtype=np.complex128)
    buf = np.zeros(cfg.m, dtype=np.complex128)
    buf[chip_idx % cfg.m] = values
    spec = np.fft.fft(buf)
    power = np.abs(spec) ** 2
    total = float(np.sum(power))
    if total <= 0.0:
        return np.zeros(cfg.m, dtype=np.float64)
    return power / total


def _cic_downchirp_estimates(samples: np.ndarray, cfg, args) -> list[dict]:
    """CIC Section 5.8: detect SFD downchirps first, then confirm preamble."""

    x = samples - np.mean(samples, axis=1, keepdims=True)
    upchirp = instantaneous_chirp(0, cfg, up=True)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    last = x.shape[1] - int((cfg.preamble_len + 4) * cfg.samples_per_symbol)
    raw: list[tuple[float, float, float, np.ndarray, float]] = []
    step = max(1, int(args.step))
    for start in range(0, max(0, last), step):
        start_f = float(start)
        sfd0 = start_f + (cfg.preamble_len + 2) * cfg.samples_per_symbol
        up_bins: list[float] = []
        sfd_bins: list[float] = []
        sfd_ratios: list[float] = []
        ok = True
        for p in range(2):
            s = sfd0 + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > x.shape[1]:
                ok = False
                break
            spec = dechirp_fft_dual(fractional_read_2d(x, s, cfg.samples_per_symbol), upchirp, cfg)
            energy = np.sum(np.abs(spec) ** 2, axis=0)
            b = int(np.argmax(energy))
            sfd_bins.append(float(signed_bin(b, cfg.m)))
            sfd_ratios.append(float(energy[b] / (np.median(energy) + 1e-30)))
        if not ok or not sfd_ratios or float(np.median(sfd_ratios)) < float(args.threshold):
            continue
        pre_ratios: list[float] = []
        pre_vectors: list[np.ndarray] = []
        for p in range(cfg.preamble_len):
            s = start_f + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > x.shape[1]:
                ok = False
                break
            spec = dechirp_fft_dual(fractional_read_2d(x, s, cfg.samples_per_symbol), downchirp, cfg)
            energy = np.sum(np.abs(spec) ** 2, axis=0)
            b = int(np.argmax(energy))
            up_bins.append(float(signed_bin(b, cfg.m)))
            pre_ratios.append(float(energy[b] / (np.median(energy) + 1e-30)))
            pre_vectors.append(spec[:, b])
        if not ok or len(up_bins) < cfg.preamble_len:
            continue
        z_up = float(np.median(up_bins))
        z_sfd = float(np.median(sfd_bins))
        cfo = 0.5 * (z_up + z_sfd)
        if cfo < -40.0 or cfo > -10.0:
            continue
        if float(np.median(pre_ratios)) < max(10.0, 0.5 * float(args.threshold)):
            continue
        cto_bins = 0.5 * (z_up - z_sfd)
        corrected_start = float(start_f - cto_bins * cfg.osr)
        cfo_comp = np.exp(-1j * 2.0 * np.pi * cfo * n / cfg.samples_per_symbol).astype(np.complex64)
        # Re-estimate channel at corrected start/CFO using preamble upchirps.
        vectors: list[np.ndarray] = []
        powers: list[float] = []
        for p in range(cfg.preamble_len):
            s = corrected_start + p * cfg.samples_per_symbol
            if s < 0 or s + cfg.samples_per_symbol > x.shape[1]:
                continue
            window = fractional_read_2d(x, s, cfg.samples_per_symbol) * cfo_comp[None, :]
            spec = dechirp_fft_dual(window, downchirp, cfg)
            energy = np.sum(np.abs(spec) ** 2, axis=0)
            local = np.asarray([(dk % cfg.m) for dk in range(-2, 3)], dtype=np.int64)
            b = int(local[int(np.argmax(energy[local]))])
            vectors.append(spec[:, b])
            powers.append(float(energy[b]))
        if not vectors:
            continue
        channel = np.mean(np.asarray(vectors, dtype=np.complex128), axis=0)
        confidence = float(np.sqrt(np.median(sfd_ratios)) * np.median(pre_ratios))
        raw.append((confidence, corrected_start, float(np.floor(cfo + 0.5)), channel, float(np.median(powers))))
    raw.sort(key=lambda row: row[0], reverse=True)
    selected: list[tuple[float, float, float, np.ndarray, float]] = []
    for row in raw:
        if any(abs(row[1] - old[1]) < 4.0 * cfg.samples_per_symbol for old in selected):
            continue
        selected.append(row)
        if len(selected) >= int(args.max_candidates):
            break
    selected.sort(key=lambda row: row[1])
    return [
        {
            "packet_index": i,
            "start_sample": float(start),
            "cfo_bins": float(cfo),
            "sto_samples": 0.0,
            "channel": [[float(np.real(v)), float(np.imag(v))] for v in channel],
            "confidence": float(conf),
            "power": float(power),
        }
        for i, (conf, start, cfo, channel, power) in enumerate(selected)
    ]


def _spectral_intersection(spectra: list[np.ndarray]) -> np.ndarray:
    if not spectra:
        raise ValueError("CIC needs at least one spectrum")
    out = np.asarray(spectra[0], dtype=np.float64).copy()
    for spec in spectra[1:]:
        out = np.minimum(out, np.asarray(spec, dtype=np.float64))
    return out


def _symbol_boundaries(target_symbol_start: float, target_est: dict, cfg) -> list[int]:
    n = cfg.samples_per_symbol
    boundaries: list[int] = []
    target_start = float(target_est["start_sample"])
    for est in _ALL_ESTIMATES:
        other_start = float(est["start_sample"])
        if abs(other_start - target_start) < 1e-6:
            continue
        rel = (other_start - target_symbol_start) % n
        if 2 * cfg.osr <= rel <= n - 2 * cfg.osr:
            boundaries.append(int(round(rel)))
    boundaries = sorted(set(boundaries))
    return boundaries


def _sed_scores(mixed: np.ndarray, cfg, candidates: np.ndarray) -> np.ndarray:
    n = cfg.samples_per_symbol
    half = n // 2
    eps = max(1, half // 10)
    left_specs = []
    right_specs = []
    for i in range(10):
        shift = i * eps
        left_specs.append(_masked_spectrum(mixed, cfg, shift, min(n, shift + half)))
        right_specs.append(_masked_spectrum(mixed, cfg, max(0, n - half - shift), n - shift))
    left = _spectral_intersection(left_specs)
    right = _spectral_intersection(right_specs)
    return np.abs(left[candidates] - right[candidates])


def _decode_one_symbol_cic(samples, target_est: dict, cfg, q: int, weights) -> tuple[int, float]:
    n = cfg.samples_per_symbol
    symbol_start = float(target_est["start_sample"]) + (cfg.payload_start_symbols + q) * n
    comp = compensate_symbol_window(
        samples,
        symbol_start,
        float(target_est["cfo_bins"]),
        cfg,
        sto_samples=float(target_est.get("sto_samples", 0.0)),
    )
    downchirp = instantaneous_chirp(0, cfg, up=False)
    mixed = (weights @ comp) * downchirp
    boundaries = _symbol_boundaries(symbol_start, target_est, cfg)
    spectra = [_masked_spectrum(mixed, cfg, 0, n)]
    for tau in boundaries:
        spectra.append(_masked_spectrum(mixed, cfg, 0, tau))
        spectra.append(_masked_spectrum(mixed, cfg, tau, n))
    inter = _spectral_intersection(spectra)
    full_spec = _masked_spectrum(mixed, cfg, 0, n)
    k = min(12, cfg.m)
    candidates = np.argpartition(inter, -k)[-k:]
    # Paper CIC detects peaks after spectral intersection and also uses received
    # power as an auxiliary feature.  Keep only candidates that are visible both
    # in the intersection and in the full-symbol spectrum.
    inter_floor = float(np.median(inter)) + 1e-30
    full_floor = float(np.median(full_spec)) + 1e-30
    visible = candidates[
        (inter[candidates] >= max(4.0 * inter_floor, 0.25 * float(np.max(inter[candidates]))))
        & (full_spec[candidates] >= max(4.0 * full_floor, 0.02 * float(np.max(full_spec))))
    ]
    if visible.size:
        candidates = visible
    sed = _sed_scores(mixed, cfg, candidates)
    # CIC first detects peaks on spectral intersection, then uses SED to break
    # ambiguity among real candidates.  In measured spectra, pure low-energy
    # noise bins can have tiny SED, so we only let SED reorder candidates whose
    # intersection energy is close to the strongest surviving peak.
    peak_energy = float(np.max(inter[candidates]))
    strong = candidates[inter[candidates] >= 0.60 * max(peak_energy, 1e-30)]
    if strong.size == 0:
        peak = int(candidates[int(np.argmax(inter[candidates]))])
        sorted_energy = np.sort(inter[candidates])
        margin = float(sorted_energy[-1] / max(sorted_energy[-2], 1e-30)) if sorted_energy.size > 1 else 1.0
        return peak, margin
    strong_sed = _sed_scores(mixed, cfg, strong)
    order = np.lexsort((-inter[strong], strong_sed))
    peak = int(strong[int(order[0])])
    sorted_energy = np.sort(inter[candidates])
    margin = float(sorted_energy[-1] / max(sorted_energy[-2], 1e-30)) if sorted_energy.size > 1 else 1.0
    return peak, margin


def decode_cic(samples, truth, est, ref, cfg) -> list[int]:
    weights, _source = target_mrc_weights(samples, est, cfg)
    # The same target-conditioned linear projection is used for every symbol.
    # Combining before dechirping and after it are equivalent here.
    decoded: list[int] = []
    for q in range(cfg.payload_symbol_count):
        symbol, _margin = _decode_one_symbol_cic(samples, est, cfg, q, weights)
        decoded.append(int(symbol))
    return decoded


def main() -> None:
    global _ALL_ESTIMATES
    parser = base_arg_parser(__doc__ or "")
    args = parser.parse_args()
    samples, meta, cfg, refs = load_experiment(args)
    modes: dict[str, list[dict]] = {}
    if args.mode in ("oracle", "both"):
        modes["oracle"] = oracle_estimates(meta, refs)
    if args.mode in ("detected", "both"):
        modes["detected"] = _cic_downchirp_estimates(samples, cfg, args)
    out_modes = {}
    for mode, estimates in modes.items():
        _ALL_ESTIMATES = estimates
        out_modes[mode] = evaluate_decoder("MRC+CIC", args, samples, meta, cfg, refs, estimates, decode_cic)
    report = {
        "method": "mrc_cic",
        "method_label": "MRC+CIC",
        "paper": "Concurrent Interference Cancellation: Decoding Multi-Packet Collisions in LoRa",
        "adaptation": "symbol SER/PRR; fixed target physical-preamble MRC followed by CIC",
        "input": str(args.synth),
        "modes": out_modes,
    }
    write_report(args, report)


if __name__ == "__main__":
    main()
