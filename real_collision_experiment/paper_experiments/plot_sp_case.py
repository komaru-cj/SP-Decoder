#!/usr/bin/env python3
"""Plot one real MRC-failure/SP-success signed-spectrum case."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/sp_matplotlib")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluate_sp_dechirp_real_pos import sp_projected_spectra  # noqa: E402
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import load_capture  # noqa: E402


def complex_vector(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(real, imag) for real, imag in values], dtype=np.complex128)


def complex_matrix(values: list[list[list[float]]]) -> np.ndarray:
    return np.asarray(
        [[complex(real, imag) for real, imag in row] for row in values],
        dtype=np.complex128,
    )


def method(candidate: dict, name: str) -> dict:
    return next(row for row in candidate.get("methods", []) if row.get("method") == name)


def app_success(row: dict) -> bool:
    return bool(row.get("application", {}).get("app_crc_ok", False))


def choose_case(candidates: list[dict], requested_id: int | None) -> tuple[dict, int]:
    pool = candidates
    if requested_id is not None:
        pool = [row for row in candidates if int(row.get("candidate_id", -1)) == requested_id]
    for candidate in pool:
        try:
            mrc = method(candidate, "mrc")
            sp = method(candidate, "sp_sync_refine")
        except StopIteration:
            continue
        if app_success(sp) and not app_success(mrc):
            for index, (mrc_bin, sp_bin) in enumerate(
                zip(mrc.get("symbol_bins", []), sp.get("symbol_bins", []))
            ):
                if int(mrc_bin) != int(sp_bin):
                    return candidate, index
    raise ValueError("no candidate satisfies MRC failure + SP success with a differing symbol")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate-id", type=int, default=None)
    parser.add_argument("--symbol-index", type=int, default=None)
    parser.add_argument("--bins-around-peak", type=int, default=24)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    candidate, automatic_symbol = choose_case(report.get("candidates", []), args.candidate_id)
    symbol_index = automatic_symbol if args.symbol_index is None else args.symbol_index
    mrc = method(candidate, "mrc")
    sp = method(candidate, "sp_sync_refine")

    input_row = report["input"]
    capture = load_capture(Path(input_row["iq"]), Path(input_row["metadata"]))
    cfg = RealCollisionLoRaConfig(sample_rate_hz=float(report["config"]["sample_rate_hz"]))
    start = (
        float(candidate["start_sample"])
        + float(candidate.get("sto_samples_sp", candidate.get("sto_samples", 0.0)))
        + float(sp.get("sync_refine_start_delta_samples", 0.0))
    )
    cfo = float(sp.get("used_cfo_bins", candidate.get("continuous_cfo_bins", candidate["cfo_bins"])))
    channel = complex_vector(candidate["channel_sp"])
    calibration = report["calibration"]
    dc = complex_vector(calibration["dc"])
    whitener = complex_matrix(calibration["whitener"])
    segment_begin = max(0, int(np.floor(start)) - cfg.samples_per_symbol)
    segment_end = min(
        capture.samples.shape[1],
        int(
            np.ceil(
                start
                + (cfg.payload_start_symbols + cfg.payload_symbol_count + 1)
                * cfg.samples_per_symbol
            )
        ),
    )
    centered = capture.samples[:, segment_begin:segment_end] - dc[:, None]
    white = (whitener @ centered).astype(np.complex64)
    p_spec, q_spec = sp_projected_spectra(
        white,
        start - segment_begin,
        cfo,
        0.0,
        channel,
        cfg,
        symbol_index,
    )
    lam = float(candidate.get("lambda_sp", sp.get("lambda_sp", 0.0)))
    p_power = np.abs(p_spec) ** 2
    q_penalty = lam * np.abs(q_spec) ** 2
    signed = p_power - q_penalty
    scale = max(float(np.max(p_power)), 1e-12)
    p_power /= scale
    q_penalty /= scale
    signed /= scale

    truth_bin = int(sp["symbol_bins"][symbol_index])
    wrong_bin = int(mrc["symbol_bins"][symbol_index])
    wrong_offset = ((wrong_bin - truth_bin + cfg.m // 2) % cfg.m) - cfg.m // 2
    # Always include both the CRC-closed SP bin and the wrong MRC winner.
    radius = min(cfg.m // 2, max(2, int(args.bins_around_peak), abs(wrong_offset) + 8))
    offsets = np.arange(-radius, radius + 1)
    indices = (truth_bin + offsets) % cfg.m

    fig, axes = plt.subplots(3, 1, figsize=(7.0, 6.2), sharex=True)
    rows = (
        (p_power, r"MRC evidence $|P[k]|^2$"),
        (q_penalty, r"orthogonal penalty $\lambda|Q[k]|^2$"),
        (signed, r"SP signed score $D[k]$"),
    )
    for axis, (values, title) in zip(axes, rows):
        axis.plot(offsets, values[indices], linewidth=1.3)
        axis.axvline(0, color="tab:green", linestyle="--", label="SP/CRC bin")
        if -radius <= wrong_offset <= radius:
            axis.axvline(wrong_offset, color="tab:red", linestyle=":", label="MRC bin")
        axis.set_ylabel("normalized")
        axis.set_title(title)
        axis.grid(alpha=0.25)
    axes[-1].set_xlabel(f"FFT-bin offset from decoded target bin {truth_bin}")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right")
    fig.suptitle(
        f"candidate {candidate['candidate_id']}, payload symbol {symbol_index}, "
        f"$\\lambda$={lam:.3f}"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    plt.close(fig)

    sidecar = {
        "source_report": str(args.report),
        "candidate_id": int(candidate["candidate_id"]),
        "symbol_index": int(symbol_index),
        "sp_crc_closed": app_success(sp),
        "mrc_crc_closed": app_success(mrc),
        "sp_bin": truth_bin,
        "mrc_bin": wrong_bin,
        "lambda_sp": lam,
        "output_figure": str(args.out),
    }
    args.out.with_suffix(args.out.suffix + ".json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(sidecar, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
