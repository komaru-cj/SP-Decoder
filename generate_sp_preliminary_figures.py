"""Generate preliminary SP-Dechirp motivation figures from real clean packets.

The script uses trace-driven collisions synthesized from
real_usrp_outputs/clean_pos_packets.npz.  It keeps the measured two-antenna
waveforms, CFO, channel imbalance, and hardware impairments, then applies oracle
start/CFO/channel for the motivation-only analysis in SP.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lora_mrc_sp_core import (
    LoRaConfig,
    fractional_read_2d,
    instantaneous_chirp,
    lora_symbol_fft,
)
from real_usrp_clean_packet_synth import load_extracted
from sp_detection_frontend import build_references


ROOT = Path(__file__).resolve().parent
CLEAN_PATH = ROOT / "real_usrp_outputs/clean_pos_packets.npz"
OUT_DIR = ROOT / "real_usrp_outputs/sp_paper_figures"


def complex_pairs_to_array(values: list[list[float]]) -> np.ndarray:
    return np.asarray([complex(r, i) for r, i in values], dtype=np.complex128)


def unit_channel(h: np.ndarray) -> np.ndarray:
    h = np.asarray(h, dtype=np.complex128).reshape(2)
    return h / math.sqrt(float(np.vdot(h, h).real))


def coherence2(a: np.ndarray, b: np.ndarray) -> float:
    aa = float(np.vdot(a, a).real)
    bb = float(np.vdot(b, b).real)
    return float(abs(np.vdot(a, b)) ** 2 / max(aa * bb, 1e-30))


def packet_power(packet: np.ndarray) -> float:
    return float(np.mean(np.abs(packet) ** 2))


def projected_spectra(
    window: np.ndarray,
    cfg: LoRaConfig,
    cfo_bins: float,
    channel: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    h = unit_channel(channel)
    b = np.asarray([-np.conj(h[1]), np.conj(h[0])], dtype=np.complex128)
    downchirp = instantaneous_chirp(0, cfg, up=False)
    n = np.arange(cfg.samples_per_symbol, dtype=np.float64)
    cfo = np.exp(-1j * 2.0 * math.pi * float(cfo_bins) * n / cfg.samples_per_symbol).astype(np.complex64)
    comp = np.asarray(window, dtype=np.complex64) * cfo[None, :]
    ant_spec = np.vstack([lora_symbol_fft(comp[ch] * downchirp, cfg) for ch in range(2)])
    p_spec = np.conj(h[0]) * ant_spec[0] + np.conj(h[1]) * ant_spec[1]
    q_spec = np.conj(b[0]) * ant_spec[0] + np.conj(b[1]) * ant_spec[1]
    return p_spec, q_spec


def synthesize_symbol_window_multi(
    packets: np.ndarray,
    refs: dict[int, object],
    cfg: LoRaConfig,
    target_idx: int,
    symbol_index: int,
    interferers: list[tuple[int, float, float]],
    *,
    noise_snr_db: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Synthesize one target-aligned payload symbol window with multiple interferers.

    Each interferer tuple is (packet_index, offset_symbols, sir_db), where SIR is
    target packet power over that interferer's scaled packet power.
    """

    t0 = int(round((cfg.payload_start_symbols + symbol_index) * cfg.samples_per_symbol))
    window = np.array(packets[target_idx, :, t0 : t0 + cfg.samples_per_symbol], dtype=np.complex64, copy=True)
    p_u = packet_power(packets[target_idx])
    for idx, offset_symbols, sir_db in interferers:
        p_v = packet_power(packets[idx])
        scale = math.sqrt(p_u / max(p_v, 1e-30) / (10.0 ** (float(sir_db) / 10.0)))
        rel = float(t0) - float(offset_symbols) * cfg.samples_per_symbol
        window += scale * fractional_read_2d(packets[idx], rel, cfg.samples_per_symbol)

    if math.isfinite(noise_snr_db):
        signal_power = float(np.mean(np.abs(window) ** 2))
        noise_power = signal_power / (10.0 ** (float(noise_snr_db) / 10.0))
        noise = (
            rng.normal(size=window.shape) + 1j * rng.normal(size=window.shape)
        ) * math.sqrt(noise_power / 2.0)
        window = (window + noise.astype(np.complex64)).astype(np.complex64)
    return window


def symbol_records_for_case(
    packets: np.ndarray,
    refs: dict[int, object],
    cfg: LoRaConfig,
    target_idx: int,
    interferer_idx: int,
    offset_symbols: float,
    sir_db: float,
) -> list[dict]:
    ref_u = refs[target_idx]
    h_u = complex_pairs_to_array(ref_u.channel)
    cfo_u = float(ref_u.cfo_bins)
    p_u = packet_power(packets[target_idx])
    p_v = packet_power(packets[interferer_idx])
    scale_v = math.sqrt(p_u / max(p_v, 1e-30) / (10.0 ** (sir_db / 10.0)))
    h_v = complex_pairs_to_array(refs[interferer_idx].channel) * scale_v
    rho = coherence2(h_u, h_v)
    rows: list[dict] = []
    for q, truth in enumerate(ref_u.symbol_bins):
        t0 = int(round((cfg.payload_start_symbols + q) * cfg.samples_per_symbol))
        target_window = packets[target_idx, :, t0 : t0 + cfg.samples_per_symbol]
        rel_interferer = float(t0) - float(offset_symbols) * cfg.samples_per_symbol
        interferer_window = fractional_read_2d(
            packets[interferer_idx], rel_interferer, cfg.samples_per_symbol
        )
        window = target_window + scale_v * interferer_window
        p_spec, q_spec = projected_spectra(window, cfg, cfo_u, h_u)
        support = np.abs(p_spec) ** 2
        contradiction = np.abs(q_spec) ** 2
        mrc_peak = int(np.argmax(support))
        truth = int(truth)
        eta_truth = float(contradiction[truth] / (support[truth] + contradiction[truth] + 1e-30))
        eta_mrc = float(contradiction[mrc_peak] / (support[mrc_peak] + contradiction[mrc_peak] + 1e-30))
        rows.append(
            {
                "target_idx": int(target_idx),
                "interferer_idx": int(interferer_idx),
                "symbol_index": int(q),
                "truth": truth,
                "mrc_peak": mrc_peak,
                "mrc_error": bool(mrc_peak != truth),
                "eta_truth": eta_truth,
                "eta_wrong": eta_mrc,
                "rho": float(rho),
                "sir_db": float(sir_db),
                "offset_symbols": float(offset_symbols),
                "support": support,
                "contradiction": contradiction,
            }
        )
    return rows


def choose_pairs_by_rho(refs: dict[int, object], max_per_bin: int = 12) -> list[tuple[int, int, float]]:
    channels = {idx: complex_pairs_to_array(ref.channel) for idx, ref in refs.items()}
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0001)]
    grouped: dict[int, list[tuple[int, int, float]]] = {i: [] for i in range(len(bins))}
    for i in sorted(channels):
        for j in sorted(channels):
            if i == j:
                continue
            rho = coherence2(channels[i], channels[j])
            for bidx, (lo, hi) in enumerate(bins):
                if lo <= rho < hi:
                    grouped[bidx].append((i, j, rho))
                    break
    rng = np.random.default_rng(20260716)
    selected: list[tuple[int, int, float]] = []
    for rows in grouped.values():
        rows = sorted(rows, key=lambda x: x[2])
        if len(rows) > max_per_bin:
            pick = rng.choice(len(rows), size=max_per_bin, replace=False)
            selected.extend(rows[int(p)] for p in pick)
        else:
            selected.extend(rows)
    return selected


def save_fig(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{name}.png", dpi=220)
    fig.savefig(OUT_DIR / f"{name}.svg")
    plt.close(fig)


def relative_db(power: np.ndarray) -> np.ndarray:
    power = np.asarray(power, dtype=np.float64)
    return 10.0 * np.log10((power + 1e-18) / (float(np.max(power)) + 1e-18))


def signed_log_score(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    scale = float(np.median(np.abs(values)) + 1e-18)
    return np.sign(values) * 10.0 * np.log10(1.0 + np.abs(values) / scale)


def plot_fig1(example: dict) -> None:
    support = example["support"]
    contradiction = example["contradiction"]
    truth = int(example["truth"])
    wrong = int(example["mrc_peak"])
    best_lam = float(example["lambda"])
    signed = support - best_lam * contradiction
    xs = np.arange(support.size)
    support_db = relative_db(support)
    contradiction_db = relative_db(contradiction)
    signed_margin = float(signed[truth] - signed[wrong])
    signed_margin_norm = (signed - signed[wrong]) / (abs(signed_margin) + 1e-18)
    fig, axes = plt.subplots(3, 1, figsize=(8.8, 6.4), sharex=True)
    panels = [
        (
            support_db,
            r"Target-direction spectrum $|P_u[k]|^2$ (dB)",
        ),
        (
            contradiction_db,
            r"Target-orthogonal spectrum $|Q_u[k]|^2$ (dB)",
        ),
        (
            signed_margin_norm,
            rf"Signed margin from $|P_u[k]|^2-\lambda |Q_u[k]|^2$, $\lambda={best_lam:.2f}$",
        ),
    ]
    for ax, (data, title) in zip(axes, panels):
        ax.plot(xs, data, lw=1.1, color="#234f8f")
        ax.scatter([truth, wrong], [data[truth], data[wrong]], s=18, zorder=4, color=["#1b9e77", "#d95f02"])
        ax.axvline(truth, color="#1b9e77", ls="--", lw=1.4, label="target bin")
        ax.axvline(wrong, color="#d95f02", ls=":", lw=1.8, label="MRC wrong bin")
        ax.set_title(title, loc="left", fontsize=9.2, pad=6)
        ax.set_xlim(0, support.size - 1)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("relative\npower (dB)")
    axes[1].set_ylabel("relative\npower (dB)")
    axes[2].set_ylabel("normalized\nmargin")
    axes[0].set_ylim(-68.0, 8.0)
    axes[1].set_ylim(-68.0, 8.0)
    axes[2].axhline(0.0, color="0.25", lw=0.8, alpha=0.55)
    signed_lim = max(1.25, float(np.percentile(np.abs(signed_margin_norm), 99.0)) * 1.08)
    axes[2].set_ylim(-0.25 * signed_lim, signed_lim)
    axes[-1].set_xlabel("LoRa FFT bin")
    axes[0].legend(loc="upper right", ncol=2, fontsize=8)
    fig.suptitle(
        "A multi-packet real-trace collision where target-orthogonal evidence rejects the MRC peak",
        fontsize=10.5,
    )
    save_fig(fig, "fig1_sp_core_observation")


def plot_fig2(records: list[dict]) -> dict:
    sir_levels = [-5.0, -4.0, -3.0, -2.0, -1.0, 0.0]
    rho_edges = np.asarray([0.0, 0.2, 0.6, 0.8, 1.0001])
    heat = np.full((len(sir_levels), len(rho_edges) - 1), np.nan)
    counts = np.zeros_like(heat)
    for si, sir in enumerate(sir_levels):
        for bi in range(len(rho_edges) - 1):
            vals = [
                row["mrc_error"]
                for row in records
                if abs(float(row["sir_db"]) - sir) < 1e-9
                and rho_edges[bi] <= float(row["rho"]) < rho_edges[bi + 1]
            ]
            if vals:
                heat[si, bi] = float(np.mean(vals))
                counts[si, bi] = len(vals)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    im = ax.imshow(heat, origin="lower", aspect="auto", vmin=0.0, vmax=1.0, cmap="magma")
    ax.set_xticks(np.arange(len(rho_edges) - 1))
    ax.set_xticklabels([f"{rho_edges[i]:.1f}-{rho_edges[i+1]:.1f}" for i in range(len(rho_edges) - 1)])
    ax.set_yticks(np.arange(len(sir_levels)))
    ax.set_yticklabels([f"{x:.0f}" for x in sir_levels])
    ax.set_xlabel(r"channel coherence $\rho$")
    ax.set_ylabel("SIR (dB)")
    ax.set_title("MRC symbol error rate under oracle synchronization and channel")
    for si in range(len(sir_levels)):
        for bi in range(len(rho_edges) - 1):
            if np.isfinite(heat[si, bi]):
                ax.text(bi, si, f"{heat[si, bi]:.2f}", ha="center", va="center", color="white", fontsize=8)
    fig.colorbar(im, ax=ax, label="MRC SER")
    save_fig(fig, "fig2_mrc_failure_heatmap")
    return {
        "sir_levels": sir_levels,
        "rho_edges": rho_edges.tolist(),
        "mrc_ser": heat.tolist(),
        "counts": counts.astype(int).tolist(),
    }


def plot_fig3(error_rows: list[dict]) -> dict:
    eta_truth = np.asarray([row["eta_truth"] for row in error_rows], dtype=np.float64)
    eta_wrong = np.asarray([row["eta_wrong"] for row in error_rows], dtype=np.float64)
    floor = 1e-5
    eta_truth_plot = np.maximum(eta_truth, floor)
    eta_wrong_plot = np.maximum(eta_wrong, floor)
    rng = np.random.default_rng(20260718)
    max_points = min(900, len(error_rows))
    truth_pick = rng.choice(len(eta_truth_plot), size=max_points, replace=False)
    wrong_pick = rng.choice(len(eta_wrong_plot), size=max_points, replace=False)
    fig, ax = plt.subplots(figsize=(7.8, 6.0))
    parts = ax.violinplot(
        [eta_truth_plot, eta_wrong_plot],
        positions=[1, 2],
        vert=False,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for body, color in zip(parts["bodies"], ["#1b9e77", "#d95f02"]):
        body.set_facecolor(color)
        body.set_edgecolor("none")
        body.set_alpha(0.22)
    ax.boxplot(
        [eta_truth_plot, eta_wrong_plot],
        positions=[1, 2],
        vert=False,
        widths=0.26,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "white", "edgecolor": "0.25", "linewidth": 1.0},
        medianprops={"color": "black", "linewidth": 1.4},
        whiskerprops={"color": "0.25"},
        capprops={"color": "0.25"},
    )
    ax.scatter(
        eta_truth_plot[truth_pick],
        1.0 + rng.normal(scale=0.035, size=max_points),
        s=5,
        color="#1b9e77",
        alpha=0.22,
        linewidths=0,
    )
    ax.scatter(
        eta_wrong_plot[wrong_pick],
        2.0 + rng.normal(scale=0.035, size=max_points),
        s=5,
        color="#d95f02",
        alpha=0.22,
        linewidths=0,
    )
    med_truth = float(np.median(eta_truth))
    med_wrong = float(np.median(eta_wrong))
    ax.axvline(med_truth, color="#1b9e77", ls="--", lw=1.0)
    ax.axvline(med_wrong, color="#d95f02", ls="--", lw=1.0)
    ax.text(med_truth, 0.62, f"median {med_truth:.4f}", color="#1b9e77", fontsize=8, ha="left")
    ax.text(med_wrong, 2.34, f"median {med_wrong:.3f}", color="#d95f02", fontsize=8, ha="left")
    ax.set_xscale("log")
    ax.set_xlim(floor, 1.0)
    ax.set_yticks([1, 2])
    ax.set_yticklabels(["target bin", "MRC wrong bin"])
    ax.set_xlabel(r"spatial inconsistency $\eta$ (target-orthogonal energy ratio, log scale)")
    ax.set_title("MRC wrong peaks contain much stronger target-orthogonal evidence")
    ax.grid(axis="x", alpha=0.25, which="both")
    save_fig(fig, "fig3_eta_distribution")
    return {
        "mrc_error_symbol_count": int(len(error_rows)),
        "eta_truth_median": med_truth,
        "eta_wrong_median": med_wrong,
        "eta_median_ratio_wrong_over_truth": float(med_wrong / max(med_truth, 1e-12)),
    }


def find_fig1_example(records: list[dict]) -> dict:
    best: dict | None = None
    for row in records:
        if not row["mrc_error"]:
            continue
        support = row["support"]
        contradiction = row["contradiction"]
        truth = int(row["truth"])
        for lam in np.linspace(0.05, 4.0, 80):
            signed = support - float(lam) * contradiction
            if int(np.argmax(signed)) != truth:
                continue
            margin = float(signed[truth] - np.max(np.delete(signed, truth)))
            gain = float(row["eta_wrong"] - row["eta_truth"])
            score = margin * max(gain, 0.0)
            if best is None or score > best["example_score"]:
                best = dict(row)
                best["lambda"] = float(lam)
                best["example_score"] = score
            break
    if best is None:
        raise RuntimeError("could not find a real MRC-error symbol repaired by signed spectrum")
    return best


def find_fig1_multinode_example(
    packets: np.ndarray,
    refs: dict[int, object],
    cfg: LoRaConfig,
    seed_example: dict,
) -> dict:
    """Search a visually rich multi-packet collision for Fig. 1."""

    rng = np.random.default_rng(20260717)
    indices = np.arange(len(packets))
    best: dict | None = None
    target_idx = int(seed_example["target_idx"])
    base_interferer = int(seed_example["interferer_idx"])
    symbol_index = int(seed_example["symbol_index"])
    base_offset = float(seed_example["offset_symbols"])
    base_sir = float(seed_example["sir_db"])
    offset_pool = np.asarray([0.18, 0.37, 0.72, 1.35, 2.65, 4.40, 7.25, 10.60], dtype=np.float64)
    sir_pool = np.asarray([-5.0, -4.0, -3.0, -2.0, -1.0, 1.0], dtype=np.float64)
    lam_grid = np.linspace(0.05, 1.60, 64)
    pool = indices[(indices != target_idx) & (indices != base_interferer)]
    for _ in range(520):
        extra_ids = [int(x) for x in rng.choice(pool, size=3, replace=False)]
        offsets = rng.choice(offset_pool, size=len(extra_ids), replace=False)
        sirs = rng.choice(sir_pool, size=len(extra_ids), replace=True)
        interferers = [(base_interferer, base_offset, base_sir)]
        interferers.extend(zip(extra_ids, offsets.tolist(), sirs.tolist()))
        window = synthesize_symbol_window_multi(
            packets,
            refs,
            cfg,
            target_idx,
            symbol_index,
            interferers,
            noise_snr_db=24.0,
            rng=rng,
        )
        ref_u = refs[target_idx]
        h_u = complex_pairs_to_array(ref_u.channel)
        p_spec, q_spec = projected_spectra(window, cfg, float(ref_u.cfo_bins), h_u)
        support = np.abs(p_spec) ** 2
        contradiction = np.abs(q_spec) ** 2
        truth = int(ref_u.symbol_bins[symbol_index])
        mrc_peak = int(np.argmax(support))
        if mrc_peak == truth:
            continue
        eta_truth = float(contradiction[truth] / (support[truth] + contradiction[truth] + 1e-30))
        eta_wrong = float(contradiction[mrc_peak] / (support[mrc_peak] + contradiction[mrc_peak] + 1e-30))
        if eta_wrong <= eta_truth + 0.03:
            continue
        for lam in lam_grid:
            signed = support - float(lam) * contradiction
            sp_peak = int(np.argmax(signed))
            if sp_peak != truth:
                continue
            margin = float(signed[truth] - np.max(np.delete(signed, truth)))
            if margin <= 0.0:
                continue
            p_db = relative_db(support)
            q_db = relative_db(contradiction)
            support_peaks = int(np.sum(p_db > -24.0))
            contradiction_peaks = int(np.sum(q_db > -24.0))
            roughness = float(np.std(p_db[p_db > -55.0]) + 0.5 * np.std(q_db[q_db > -55.0]))
            score = 12.0 * (eta_wrong - eta_truth) + 0.04 * support_peaks + 0.04 * contradiction_peaks + 0.03 * roughness + 0.002 * margin
            if best is None or score > best["example_score"]:
                best = {
                    "target_idx": int(target_idx),
                    "interferers": [
                        {"packet_index": int(i), "offset_symbols": float(o), "sir_db": float(s)}
                        for i, o, s in interferers
                    ],
                    "symbol_index": int(symbol_index),
                    "truth": int(truth),
                    "mrc_peak": int(mrc_peak),
                    "sp_peak": int(sp_peak),
                    "eta_truth": eta_truth,
                    "eta_wrong": eta_wrong,
                    "lambda": float(lam),
                    "support": support,
                    "contradiction": contradiction,
                    "example_score": float(score),
                    "support_bins_above_minus24db": support_peaks,
                    "contradiction_bins_above_minus24db": contradiction_peaks,
                    "noise_snr_db": 24.0,
                }
            break
    if best is None:
        fallback = dict(seed_example)
        fallback["sp_peak"] = int(seed_example["truth"])
        fallback["interferers"] = [
            {
                "packet_index": int(seed_example["interferer_idx"]),
                "offset_symbols": float(seed_example["offset_symbols"]),
                "sir_db": float(seed_example["sir_db"]),
            }
        ]
        fallback["noise_snr_db"] = float("inf")
        return fallback
    return best


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = LoRaConfig()
    packets, _ = load_extracted(CLEAN_PATH)
    refs = build_references(CLEAN_PATH, list(range(len(packets))), cfg)
    pairs = choose_pairs_by_rho(refs, max_per_bin=4)
    offsets = [0.0, 0.1, 0.25, 0.5, 0.9]
    sir_levels = [-5.0, -4.0, -3.0, -2.0, -1.0, 0.0]
    all_records: list[dict] = []
    compact_records: list[dict] = []
    for target_idx, interferer_idx, rho in pairs:
        for sir_db in sir_levels:
            for off in offsets:
                rows = symbol_records_for_case(
                    packets, refs, cfg, target_idx, interferer_idx, off, sir_db
                )
                all_records.extend(rows)
                for row in rows:
                    compact_records.append(
                        {
                            k: v
                            for k, v in row.items()
                            if k not in {"support", "contradiction"}
                        }
                    )

    error_rows = [row for row in all_records if row["mrc_error"]]
    if not error_rows:
        raise RuntimeError("MRC produced no errors in the preliminary sweep")
    two_packet_example = find_fig1_example(all_records)
    example = find_fig1_multinode_example(packets, refs, cfg, two_packet_example)
    plot_fig1(example)
    fig2 = plot_fig2(all_records)
    fig3 = plot_fig3(error_rows)
    summary = {
        "clean_path": str(CLEAN_PATH.relative_to(ROOT)),
        "output_dir": str(OUT_DIR.relative_to(ROOT)),
        "sf": cfg.sf,
        "bw_hz": cfg.bw_hz,
        "sample_rate_hz": cfg.sample_rate_hz,
        "payload_symbol_count": cfg.payload_symbol_count,
        "pair_count": len(pairs),
        "offset_symbols": offsets,
        "sir_db": sir_levels,
        "total_symbol_observations": len(all_records),
        "mrc_error_symbol_count": len(error_rows),
        "mrc_ser_overall": float(np.mean([row["mrc_error"] for row in all_records])),
        "fig1_example": {
            k: v
            for k, v in example.items()
            if k not in {"support", "contradiction"}
        },
        "fig2": fig2,
        "fig3": fig3,
        "records_json": "preliminary_records.json",
    }
    with (OUT_DIR / "preliminary_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with (OUT_DIR / "preliminary_records.json").open("w", encoding="utf-8") as f:
        json.dump(compact_records, f, ensure_ascii=False)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
