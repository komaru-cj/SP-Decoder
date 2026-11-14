"""Shared utilities for reproducing comparison baselines on the real USRP data.

The comparison scripts intentionally live under compare/* and do not modify the
SP-Dechirp receiver.  They reuse the same synthesized collision scenes,
reference symbols, and PCube-SP detector outputs so the legacy SER-threshold
diagnostic is measured on the same packets.  Formal PRR is produced only by
the real-capture receiver with standard FEC/CRC closure.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluate_sp_dechirp_real_pos import (  # noqa: E402
    oracle_estimates,
    packet_ser,
)
from lora_mrc_sp_core import (  # noqa: E402
    LoRaConfig,
    compensate_symbol_window,
    instantaneous_chirp,
    lora_symbol_fft,
)
from sp_detection_frontend import (  # noqa: E402
    build_references,
    channel_coherence,
    detected_estimates,
    load_scene,
    match_by_start,
)


DEFAULT_SYNTH = ROOT / "real_usrp_outputs/synth_sp_pos01to10_moderate_offset5_15_seed11.npz"
DEFAULT_CLEAN = ROOT / "real_usrp_outputs/clean_pos_packets.npz"


@dataclass(frozen=True)
class PacketEval:
    packet_index: int
    source_index: int
    source_label: str
    start_sample: float
    cfo_bins: float
    start_error_samples: float
    cfo_error_bins: float
    channel_coherence: float
    ser: float
    success: bool


def base_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--synth", default=str(DEFAULT_SYNTH), help="Synthesized collision .npz")
    parser.add_argument("--clean", default=str(DEFAULT_CLEAN), help="Clean packet reference .npz")
    parser.add_argument("--out", required=True, help="Output JSON report")
    parser.add_argument("--mode", choices=("oracle", "detected", "both"), default="both")
    parser.add_argument("--threshold", type=float, default=5.5)
    parser.add_argument("--step", type=int, default=4096)
    parser.add_argument("--max-candidates", type=int, default=14)
    parser.add_argument("--min-sync-score", type=float, default=1000.0)
    parser.add_argument("--min-coherent-metric", type=float, default=1000.0)
    parser.add_argument("--success-ser", type=float, default=0.20)
    parser.add_argument("--quiet", action="store_true")
    return parser


def complex_from_pairs(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(r, i) for r, i in values], dtype=np.complex128)


def load_experiment(args: argparse.Namespace) -> tuple[np.ndarray, dict, LoRaConfig, dict[int, object]]:
    samples, meta, cfg = load_scene(Path(args.synth))
    source_indices = [int(p["source_packet_index"]) for p in meta["packets"]]
    refs = build_references(Path(args.clean), source_indices, cfg)
    return samples, meta, cfg, refs


def get_estimates(
    args: argparse.Namespace,
    samples: np.ndarray,
    meta: dict,
    cfg: LoRaConfig,
    refs: dict[int, object],
) -> dict[str, list[dict]]:
    modes: dict[str, list[dict]] = {}
    if args.mode in ("oracle", "both"):
        modes["oracle"] = oracle_estimates(meta, refs)
    if args.mode in ("detected", "both"):
        est, _ = detected_estimates(
            samples,
            cfg,
            max_candidates=int(args.max_candidates),
            threshold=float(args.threshold),
            step_samples=int(args.step),
            min_sync_score=float(args.min_sync_score),
            min_coherent_metric=float(args.min_coherent_metric),
            frontend="pcube_sp",
        )
        modes["detected"] = est
    return modes


def symbol_spectra(
    samples: np.ndarray,
    symbol_start: float,
    cfo_bins: float,
    cfg: LoRaConfig,
    *,
    sto_samples: float = 0.0,
) -> np.ndarray:
    """Return two-antenna folded LoRa FFT spectra for one compensated symbol."""

    downchirp = instantaneous_chirp(0, cfg, up=False)
    comp = compensate_symbol_window(samples, symbol_start, cfo_bins, cfg, sto_samples=sto_samples)
    return np.vstack([lora_symbol_fft(comp[ch] * downchirp, cfg) for ch in range(comp.shape[0])])


def evaluate_decoder(
    name: str,
    args: argparse.Namespace,
    samples: np.ndarray,
    meta: dict,
    cfg: LoRaConfig,
    refs: dict[int, object],
    estimates: list[dict],
    decode_packet: Callable[[np.ndarray, dict, dict, object, LoRaConfig], list[int]],
) -> dict:
    truth_packets = meta["packets"]
    matched = match_by_start(estimates, truth_packets)
    evals: list[PacketEval] = []
    for u, (truth, est) in enumerate(zip(truth_packets, matched)):
        src = int(truth["source_packet_index"])
        ref = refs[src]
        label = str(truth.get("source_label", f"src{src}"))
        if est is None:
            evals.append(
                PacketEval(
                    packet_index=u,
                    source_index=src,
                    source_label=label,
                    start_sample=float("nan"),
                    cfo_bins=float("nan"),
                    start_error_samples=float("inf"),
                    cfo_error_bins=float("inf"),
                    channel_coherence=0.0,
                    ser=1.0,
                    success=False,
                )
            )
            continue
        decoded = decode_packet(samples, truth, est, ref, cfg)
        ser = packet_ser(decoded, ref.symbol_bins)
        h_est = complex_from_pairs(est["channel"])
        h_ref = complex_from_pairs(ref.channel)
        evals.append(
            PacketEval(
                packet_index=u,
                source_index=src,
                source_label=label,
                start_sample=float(est["start_sample"]),
                cfo_bins=float(est["cfo_bins"]),
                start_error_samples=float(est["start_sample"]) - float(truth["start_sample"]),
                cfo_error_bins=float(est["cfo_bins"]) - float(ref.cfo_bins),
                channel_coherence=channel_coherence(h_est, h_ref),
                ser=float(ser),
                success=bool(ser <= float(args.success_ser)),
            )
        )
    finite_start = [abs(e.start_error_samples) for e in evals if math.isfinite(e.start_error_samples)]
    finite_cfo = [abs(e.cfo_error_bins) for e in evals if math.isfinite(e.cfo_error_bins)]
    summary = {
        "decoder": name,
        "packet_count": len(evals),
        "symbol_count": len(evals) * cfg.payload_symbol_count,
        "ser": float(np.mean([e.ser for e in evals])) if evals else 1.0,
        # This legacy synthetic driver has no LoRa FEC/CRC closure.  Keep its
        # SER-threshold diagnostic explicitly separate from formal PRR.
        "ser_threshold_success_count": int(sum(e.success for e in evals)),
        "packet_count": len(evals),
        "success_ser_threshold_diagnostic": float(args.success_ser),
        "mean_abs_start_error_samples": float(np.mean(finite_start)) if finite_start else float("inf"),
        "mean_abs_cfo_convention_error_bins": float(np.mean(finite_cfo)) if finite_cfo else float("inf"),
    }
    return {"summary": summary, "packets": [asdict(e) for e in evals]}


def write_report(args: argparse.Namespace, report: dict) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    out.write_text(text, encoding="utf-8")
    if not args.quiet:
        print(text)
