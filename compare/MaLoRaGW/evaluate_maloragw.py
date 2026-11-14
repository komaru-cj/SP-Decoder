"""MaLoRaGW uplink-adapted decoder on the shared real USRP data.

Implemented components from the paper:
- PCA-based packet detection/channel estimates are reused from the shared
  MaLoRaGW/PCube-inspired front-end;
- for payload decoding, the gateway selects K'=min(K,M) strongest users,
  constructs the paper's global ZF projection matrix, and classifies FFT peaks
  by time/frequency continuity plus channel-ratio features.

This reproduces the two-antenna uplink signal-projection path available on the
current hardware.  Downlink beamforming is not evaluated because the dataset is
uplink-only receive IQ.
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
    complex_from_pairs,
    evaluate_decoder,
    get_estimates,
    load_experiment,
    symbol_spectra,
    write_report,
)


_ALL_ESTIMATES: list[dict] = []


def _global_zf_rows(all_channels: list[np.ndarray], antenna_count: int) -> np.ndarray:
    """Paper-style U=(H^H H)^-1 H^H for K'=min(K,M) strongest users."""

    valid = [
        (i, np.asarray(h, dtype=np.complex128).reshape(antenna_count))
        for i, h in enumerate(all_channels)
        if float(np.vdot(h, h).real) > 0.0
    ]
    if not valid:
        return np.eye(antenna_count, dtype=np.complex128)
    valid.sort(key=lambda row: float(np.vdot(row[1], row[1]).real), reverse=True)
    selected = valid[: min(len(valid), antenna_count)]
    hmat = np.column_stack([h for _i, h in selected])
    try:
        return np.linalg.pinv(hmat)
    except np.linalg.LinAlgError:
        return np.eye(antenna_count, dtype=np.complex128)


def _repeat_penalty(samples, est, cfg, bin_index: int, q: int) -> float:
    """MaLoRaGW removes peaks repeated in consecutive target windows."""

    penalties: list[float] = []
    for dq in (-1, 1):
        qq = q + dq
        if qq < 0 or qq >= cfg.payload_symbol_count:
            continue
        s = float(est["start_sample"]) + (cfg.payload_start_symbols + qq) * cfg.samples_per_symbol
        spectra = symbol_spectra(
            samples,
            s,
            float(est["cfo_bins"]),
            cfg,
            sto_samples=float(est.get("sto_samples", 0.0)),
        )
        energy = np.sum(np.abs(spectra) ** 2, axis=0)
        floor = float(np.median(energy)) + 1e-30
        penalties.append(float(energy[int(bin_index) % cfg.m] / floor))
    return float(max(penalties)) if penalties else 0.0


def decode_maloragw(samples, truth, est, ref, cfg) -> list[int]:
    target_h = complex_from_pairs(est["channel"])
    channels = [complex_from_pairs(e["channel"]) for e in _ALL_ESTIMATES]
    zf_rows = _global_zf_rows(channels, samples.shape[0])
    target_ratio = target_h / (target_h[0] if abs(target_h[0]) > 1e-30 else 1.0 + 0.0j)
    decoded: list[int] = []
    for q in range(cfg.payload_symbol_count):
        symbol_start = float(est["start_sample"]) + (cfg.payload_start_symbols + q) * cfg.samples_per_symbol
        spectra = symbol_spectra(
            samples,
            symbol_start,
            float(est["cfo_bins"]),
            cfg,
            sto_samples=float(est.get("sto_samples", 0.0)),
        )
        energy = np.sum(np.abs(spectra) ** 2, axis=0)
        projected = zf_rows @ spectra
        zf_power = np.sum(np.abs(projected) ** 2, axis=0)

        # MaLoRaGW's peak clustering uses two features: time/frequency offset
        # and channel ratio.
        top_k = min(32, cfg.m)
        cand = np.argpartition(energy, -top_k)[-top_k:]
        floor = float(np.median(energy)) + 1e-30
        cand = cand[energy[cand] >= max(6.0 * floor, 0.01 * float(np.max(energy[cand])))]
        if cand.size == 0:
            cand = np.asarray([int(np.argmax(zf_power))], dtype=np.int64)
        ratios = np.vstack([
            spectra[0, cand] / np.where(np.abs(spectra[0, cand]) > 1e-30, spectra[0, cand], 1.0 + 0.0j),
            spectra[1, cand] / np.where(np.abs(spectra[0, cand]) > 1e-30, spectra[0, cand], 1.0 + 0.0j),
        ])
        ratio_dist = np.linalg.norm(ratios - target_ratio[:, None], axis=0)
        repeat = np.asarray([_repeat_penalty(samples, est, cfg, int(b), q) for b in cand], dtype=np.float64)
        score = zf_power[cand] / (1.0 + 4.0 * ratio_dist ** 2) / (1.0 + 0.08 * repeat)
        decoded.append(int(cand[int(np.argmax(score))]))
    return decoded


def main() -> None:
    global _ALL_ESTIMATES
    parser = base_arg_parser(__doc__ or "")
    args = parser.parse_args()
    samples, meta, cfg, refs = load_experiment(args)
    modes = get_estimates(args, samples, meta, cfg, refs)
    out_modes = {}
    for mode, estimates in modes.items():
        _ALL_ESTIMATES = estimates
        out_modes[mode] = evaluate_decoder("MaLoRaGW-ZF", args, samples, meta, cfg, refs, estimates, decode_maloragw)
    report = {
        "method": "MaLoRaGW-uplink-adapted",
        "paper": "MaLoRaGW: Multi-User MIMO Transmission for LoRa",
        "adaptation": "uplink only; downlink beamforming excluded for receive-only data",
        "input": str(args.synth),
        "modes": out_modes,
    }
    write_report(args, report)


if __name__ == "__main__":
    main()
