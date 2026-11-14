#!/usr/bin/env python3
"""Resubmission A/B/C: explicit-header simulation driven by measured h/CFO.

A/B isolate payload decisions at controlled synchronization; C runs the real
anonymous detector before the same decoders. Generated samples are never
described as simultaneous-air captures or as raw-IQ superposition.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/revision_abc_matplotlib")

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT, ROOT / "real_collision_experiment/node01_sp_receiver"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from compare.real_packet_decoders import PaperComparisonContext
from compare.CoRa.cora_detector import CoRaDetector
from compare.CoRa.tnb_bec import TnBBECDecoder
from evaluate_sp_dechirp_real_pos import attach_sp_reliability_and_lambda, channel_angle
from lora_mrc_sp_core import compensate_symbol_window, instantaneous_chirp, lora_symbol_fft
from real_collision_experiment.node01_sp_receiver.lora_phy_decode import decode_payload_from_symbol_bins
from real_collision_experiment.node01_sp_receiver.real_lora_config import RealCollisionLoRaConfig
from real_collision_experiment.node01_sp_receiver.sc16_io import dc_remove_and_whiten
from real_collision_experiment.node01_sp_receiver.sp_node01_receiver import decode_sp_stages
from real_collision_experiment.paper_experiments.build_fig11_trace_runtime import prepare_receiver_inputs
from real_collision_experiment.paper_experiments.simulate_sp_mechanisms import build_explicit_frame

SOURCE_AUDIT = ROOT / "real_collision_experiment/analysis/single_packet_angle_audit/summary.json"
SOURCE_CACHE = ROOT / "real_usrp_outputs/sp_v2_mechanism_figures/air_clean_packet_reference_cache.npz"
POSTERIOR = ROOT / "compare/CoRa/upstream/cora_v2/artifacts/python/models/dist.pkl"
DEFAULT_OUT = ROOT / "real_usrp_outputs/revision_abc"
METHODS = ("mrc", "mrc_cic", "mrc_cora", "pcube", "maloragw", "sp")
LABELS = dict(mrc="MRC", mrc_cic="MRC+CIC", mrc_cora="MRC+CoRa", pcube="PCube", maloragw="MaLoRaGW", sp="SP-Decoder")
SCHEMA = "measured_channel_explicit_abc_v1"


def write_json(path, value):
    def finite(item):
        if isinstance(item, dict):
            return {key: finite(v) for key, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [finite(v) for v in item]
        if isinstance(item, np.generic):
            return finite(item.item())
        if isinstance(item, float) and not math.isfinite(item):
            return "+inf" if item > 0 else "-inf" if item < 0 else None
        return item
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(finite(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def complex_pairs(values):
    return np.asarray([complex(*v) for v in values], dtype=np.complex128)


def pairs(values):
    return [[float(v.real), float(v.imag)] for v in values]


def angle_deg(a, b):
    return math.degrees(channel_angle(a, b))


def default_cfg():
    # Same BW/SF as the source spatial measurements and the existing formal
    # BW125 receiver rate; no bandwidth extrapolation of measured channels.
    return RealCollisionLoRaConfig(sf=10, bw_hz=125000, sample_rate_hz=750000)


def source_bank():
    audit = json.loads(SOURCE_AUDIT.read_text())
    with np.load(SOURCE_CACHE) as z:
        channels = np.asarray(z["full_channels"], dtype=np.complex128)
    channels /= np.linalg.norm(channels, axis=1, keepdims=True)
    records = []
    for row, channel in zip(audit["packets"], channels):
        records.append({**row, "channel_ri": pairs(channel)})
    return records


def revision_hash():
    digest = hashlib.sha256()
    files = [Path(__file__), SOURCE_AUDIT, SOURCE_CACHE, POSTERIOR]
    files += [ROOT / p for p in (
        "compare/mrc_input.py", "compare/real_packet_decoders.py",
        "compare/PCube/soft_grouping.py",
        "real_collision_experiment/paper_experiments/arrival_density.py",
        "compare/CoRa/cora_detector.py", "compare/CoRa/tnb_bec.py",
        "evaluate_sp_dechirp_real_pos.py",
        "sp_noise_competition.py", "lora_mrc_sp_core.py",
        "sp_reference_guard.py",
        "real_collision_experiment/node01_sp_receiver/lora_phy_decode.py",
        "real_collision_experiment/node01_sp_receiver/real_lora_config.py",
        "real_collision_experiment/node01_sp_receiver/sc16_io.py",
        "real_collision_experiment/paper_experiments/build_fig11_trace_runtime.py",
        "real_collision_experiment/node01_sp_receiver/real_sp_frontend.py",
        "real_collision_experiment/node01_sp_receiver/sp_node01_receiver.py",
        "real_collision_experiment/paper_experiments/simulate_sp_mechanisms.py",
    )]
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def source_pairs(bank, low, high):
    out = []
    for i, a in enumerate(bank):
        for j in range(i + 1, len(bank)):
            b = bank[j]
            if a["position"] == b["position"]:
                continue
            angle = angle_deg(complex_pairs(a["channel_ri"]), complex_pairs(b["channel_ri"]))
            if low <= angle < high:
                out.append((i, j))
    return out


def select_sources(bank, spec, rng):
    k = int(spec["k"])
    if "angle_low" in spec:
        available = source_pairs(bank, spec["angle_low"], spec["angle_high"])
        if not available:
            raise ValueError(f"no cross-position sources for {spec}")
        selected = list(available[int(rng.integers(len(available)))])
        if bool(rng.integers(2)):
            selected.reverse()
        return selected
    groups = defaultdict(list)
    for i, record in enumerate(bank):
        groups[record["position"]].append(i)
    # C fixes a reasonably separable spatial condition rather than crossing
    # the full small-angle matrix again. No decoder outcome enters sampling.
    for _ in range(500):
        keys = rng.choice(sorted(groups), k, replace=False)
        selected = [int(rng.choice(groups[str(key)])) for key in keys]
        if spec["family"] != "C" or k < 2:
            return selected
        minimum = min(angle_deg(complex_pairs(bank[i]["channel_ri"]), complex_pairs(bank[j]["channel_ri"])) for a, i in enumerate(selected) for j in selected[a + 1:])
        if minimum >= 10:
            return selected
    raise ValueError("cannot draw C sources with pairwise channel angle >=10 degrees")


def synthesize(spec, bank, cfg):
    rng = np.random.default_rng(int(spec["seed"]))
    selected = select_sources(bank, spec, rng)
    k = len(selected)
    if spec["family"] == "C":
        offsets = rng.uniform(0, float(spec["w_symbols"]), size=k)
    elif spec["family"] == "A":
        offsets = np.arange(k) * 1.37 + rng.uniform(0, .15, k)
    elif k == 2:
        offsets = np.asarray([0, .2])
    elif k == 1:
        offsets = np.zeros(1)
    else:
        offsets = np.arange(k) * 3.23 + rng.uniform(0, .15, k)
    starts = np.rint((3 + offsets) * cfg.samples_per_symbol).astype(int)
    length = int(max(starts) + cfg.frame_samples + 3 * cfg.samples_per_symbol)
    signal = np.zeros((2, length), dtype=np.complex64)
    truth = []
    for target, (source, start) in enumerate(zip(selected, starts)):
        record = bank[source]
        payload = rng.integers(0, 256, cfg.payload_len, dtype=np.uint8).tobytes()
        frame, bins = build_explicit_frame(payload, cfg)
        power = 1.0 if target == 0 else 10 ** (-float(spec.get("sir_db", 0)) / 10)
        if spec["family"] == "A":
            power = 10 ** (float(rng.uniform(-3, 3)) / 10)
        h = complex_pairs(record["channel_ri"]) * math.sqrt(2 * power)
        cfo = float(record["cfo_bins"])
        carrier = np.exp(2j * np.pi * cfo * np.arange(frame.size) / cfg.samples_per_symbol)
        # Random common phase changes no projective channel angle.
        h *= np.exp(2j * np.pi * rng.random())
        waveform = h[:, None] * (frame * carrier)[None, :]
        signal[:, start:start + frame.size] += waveform.astype(np.complex64)
        truth.append(dict(source_index=source, position=record["position"], source_label=record["label"], start_sample=float(start), offset_symbols=float(start / cfg.samples_per_symbol - 3), cfo_bins=cfo, power_per_channel=power, channel=pairs(h), payload_hex=payload.hex(), symbol_bins=bins))
    noise_power = 10 ** (-float(spec["snr_db"]) / 10)
    noise = (rng.normal(size=signal.shape) + 1j * rng.normal(size=signal.shape)) * math.sqrt(noise_power / 2)
    samples = signal + noise.astype(np.complex64)
    return samples, truth, noise_power


def controlled_inputs(samples, truth, cfg):
    # B is explicitly conditional on controlled timing/CFO. It still estimates
    # target references and lambda from the noisy overlapping preambles.
    white, whitener, sigma, cal = dc_remove_and_whiten(samples, noise_samples=2 * cfg.samples_per_symbol)
    dc = complex_pairs(cal["dc"])
    physical = samples - dc[:, None]
    estimates = [dict(start_sample=t["start_sample"], cfo_bins=t["cfo_bins"], continuous_cfo_bins=t["cfo_bins"], sto_samples=0., channel=[[0., 0.], [0., 0.]]) for t in truth]
    return physical, white, estimates, cfg.m * sigma, whitener, cal


def projected_decisions(samples, estimate, cfg, keep_spectra=False):
    h = complex_pairs(estimate.get("mrc_decision_channel_sp", estimate["channel_sp"]) if float(estimate["lambda_sp"]) == 0 else estimate["channel_sp"])
    a = h / max(np.linalg.norm(h), 1e-30)
    b = np.asarray([-np.conj(a[1]), np.conj(a[0])])
    down = instantaneous_chirp(0, cfg, up=False)
    p, q = [], []
    for j in range(cfg.payload_symbol_count):
        start = estimate["start_sample"] + (cfg.payload_start_symbols + j) * cfg.samples_per_symbol
        comp = compensate_symbol_window(samples, start, estimate["cfo_bins_sp"], cfg, sto_samples=estimate["sto_samples_sp"])
        spectra = np.vstack([lora_symbol_fft(row * down, cfg) for row in comp])
        p.append(abs(a.conj() @ spectra) ** 2)
        q.append(abs(b.conj() @ spectra) ** 2)
    support, orthogonal = np.asarray(p), np.asarray(q)
    score = support - float(estimate["lambda_sp"]) * orthogonal
    sp_bins = np.argmax(score, axis=1).tolist()
    mrc_bins = np.argmax(support, axis=1).tolist()
    return sp_bins, mrc_bins, (support, orthogonal, score) if keep_spectra else None


def assign_tracks(estimates, truth, cfg):
    # Time alone is ambiguous for W=0. Evaluation-only bipartite matching uses
    # time and CFO, never channel angle or decoded payload. The direction-error
    # statistic therefore cannot choose a conveniently matching reference.
    if not estimates:
        return {}
    cost = np.full((len(truth), len(estimates)), 1e6)
    for i, target in enumerate(truth):
        for j, estimate in enumerate(estimates):
            start = estimate["start_sample"] + estimate.get("sto_samples", 0.)
            cfo = estimate.get("continuous_cfo_bins", estimate["cfo_bins"])
            dt = abs(start - target["start_sample"]) / cfg.samples_per_symbol
            # A shifted CSS window changes apparent upchirp frequency by
            # delta_start/osr bins. Compare the equivalent physical CFO so a
            # one-chip start/CFO alias is not falsely scored as a missing track.
            df = abs(cfo - (start - target["start_sample"]) / cfg.osr - target["cfo_bins"])
            if dt <= .125 and df <= .75:
                cost[i, j] = dt / .125 + df / .75
    left, right = linear_sum_assignment(cost)
    return {int(i): int(j) for i, j in zip(left, right) if cost[i, j] < 1e5}


def evaluate(spec, bank, cfg, *, mechanism=False, noise_competition=None):
    started = time.perf_counter()
    samples, truth, noise_power = synthesize(spec, bank, cfg)
    frontend_started = time.perf_counter()
    if spec["family"] == "C":
        prepared = prepare_receiver_inputs(samples, cfg, max_candidates=24, candidates_per_window=16, threshold=3., cfo_min=-40., cfo_max=8., sp_scan_phase_count=8)
        physical, white = prepared["physical"], prepared["white"]
        estimates = prepared["estimates"]["mrc"]
        noise_sigma = prepared["noise_sigma2_fft"]
        # Recover the exact preprocessing coordinate for direction scoring.
        _, whitener, _, cal = dc_remove_and_whiten(samples, noise_samples=max(128, round(.75 * cfg.samples_per_symbol)))
        frontend_audit = prepared["native_diagnostics"]["sp_detection"]
        assignment = assign_tracks(estimates, truth, cfg)
    else:
        physical, white, estimates, noise_sigma, whitener, cal = controlled_inputs(samples, truth, cfg)
        frontend_audit = {"scope": "controlled_known_start_and_CFO; not end-to-end detection"}
        assignment = {i: i for i in range(len(truth))}
    frontend_seconds = time.perf_counter() - frontend_started
    lambda_started = time.perf_counter()
    if noise_competition is None:
        noise_competition = bool(spec.get("noise_competition", False))
    configured = attach_sp_reliability_and_lambda(white, estimates, cfg,
        noise_sigma2=noise_sigma, gamma=.05, max_lambda=None,
        noise_competition=noise_competition)
    lambda_seconds = time.perf_counter() - lambda_started
    methods = tuple(spec.get("methods", METHODS))
    decoded = {method: [] for method in methods}
    contexts = {}
    parameter_seconds = {}
    for method in methods:
        if method in ("sp", "mrc_cora"):
            continue
        t = time.perf_counter()
        contexts[method] = PaperComparisonContext(physical, estimates, cfg, frontend_method=method)
        parameter_seconds[method] = (time.perf_counter() - t) / max(1, len(estimates))
    detector = CoRaDetector(POSTERIOR) if "mrc_cora" in methods else None
    bec = TnBBECDecoder() if detector else None
    spectral_rows, mechanisms = [], []
    for index, (estimate, config) in enumerate(zip(estimates, configured)):
        t = time.perf_counter()
        sp_bins, ref_mrc_bins, spectra = projected_decisions(white, config, cfg, keep_spectra=mechanism)
        sp_phy = decode_payload_from_symbol_bins(sp_bins, cfg)
        sp_result = {"symbol_bins": sp_bins, "phy": {"phy_crc_ok": bool(sp_phy.phy_crc_ok), "payload_hex": sp_phy.payload.hex(), "status": sp_phy.status}}
        if "sp" in methods:
            # C uses the production cumulative synchronization/refinement path.
            if spec["family"] == "C":
                sp_result = next(r for r in decode_sp_stages(white, config, cfg, max_sync_trials=32) if r["method"] == "sp_sync_refine")
            sp_result["seconds"] = time.perf_counter() - t + lambda_seconds / max(1, len(estimates))
            sp_result["core_symbol_bins"] = sp_bins
            sp_result["reference_mrc_symbol_bins"] = ref_mrc_bins
            decoded["sp"].append(sp_result)
        for method in methods:
            if method == "sp":
                continue
            t = time.perf_counter()
            if method == "mrc_cora":
                symbols = detector.detect(physical, estimate, cfg)
                phy = bec.decode(symbols.symbol_bins, cfg)
                result = {"symbol_bins": symbols.symbol_bins, "phy": {"phy_crc_ok": bool(phy.phy_crc_ok), "payload_hex": phy.payload.hex(), "status": phy.status}, "mrc_weights": pairs(symbols.mrc_weights)}
            else:
                context = contexts[method]
                fn = {"mrc": context.decode_mrc, "mrc_cic": context.decode_cic, "pcube": context.decode_pcube, "maloragw": context.decode_maloragw}[method]
                result = fn(estimate)
            result["seconds"] = time.perf_counter() - t + parameter_seconds.get(method, 0.)
            decoded[method].append(result)
        if mechanism:
            mechanisms.append(spectra)
    focus = spec.get("focus", list(range(len(truth))))
    target_rows = []
    for i in focus:
        target = truth[i]
        j = assignment.get(i)
        config = configured[j] if j is not None else None
        actual = whitener @ complex_pairs(target["channel"])
        target_row = {"target_index": i, "source_index": target["source_index"], "position": target["position"], "track_established": j is not None, "matched_candidate": j, "direction_error_deg": angle_deg(complex_pairs(config["channel_sp"]), actual) if config else None, "lambda": float(config["lambda_sp"]) if config else None, "lambda_cap": float(config["lambda_cap_sp"]) if config else None, "theta_deg": math.degrees(config["theta_total"]) if config else None, "methods": {}}
        for method in methods:
            result = decoded[method][j] if j is not None else None
            # C end-to-end delivery is credited by unique exact payload identity
            # anywhere in the detected set, independent of evaluation matching.
            delivered = any(r["phy"]["phy_crc_ok"] and r["phy"]["payload_hex"] == target["payload_hex"] for r in decoded[method])
            if spec["family"] != "C":
                delivered = result is not None and result["phy"]["phy_crc_ok"] and result["phy"]["payload_hex"] == target["payload_hex"]
            bins = result["symbol_bins"] if result else []
            errors = sum(q >= len(bins) or bins[q] != b for q, b in enumerate(target["symbol_bins"]))
            target_row["methods"][method] = {"delivered": bool(delivered), "symbol_errors": int(errors), "symbol_count": len(target["symbol_bins"]), "ser": errors / len(target["symbol_bins"]), "status": result["phy"]["status"] if result else "not_established"}
        if "sp" in methods and j is not None:
            core = decoded["sp"][j]["core_symbol_bins"]
            ref_mrc = decoded["sp"][j]["reference_mrc_symbol_bins"]
            target_row["core_rescued_symbols"] = sum(m != b and s == b for m, s, b in zip(ref_mrc, core, target["symbol_bins"]))
            target_row["core_harmed_symbols"] = sum(m == b and s != b for m, s, b in zip(ref_mrc, core, target["symbol_bins"]))
        if mechanism and j is not None:
            support, orthogonal, score = mechanisms[j]
            for q, b in enumerate(target["symbol_bins"]):
                absolute_start = target["start_sample"] + (cfg.payload_start_symbols + q) * cfg.samples_per_symbol
                active = sum(t["start_sample"] < absolute_start + cfg.samples_per_symbol and t["start_sample"] + cfg.frame_samples > absolute_start for t in truth)
                row = dict(target=i, symbol=q, true_bin=b, mrc_bin=int(np.argmax(support[q])), sp_bin=int(np.argmax(score[q])), lambda_sp=float(config["lambda_sp"]), overlap_frames=int(active), rank_before=int(1 + np.count_nonzero(support[q] > support[q, b])), rank_after=int(1 + np.count_nonzero(score[q] > score[q, b])))
                spectral_rows.append(row)
        target_rows.append(target_row)
    physical_angle = angle_deg(complex_pairs(truth[0]["channel"]), complex_pairs(truth[1]["channel"])) if len(truth) >= 2 else None
    effective_angle = angle_deg(whitener @ complex_pairs(truth[0]["channel"]), whitener @ complex_pairs(truth[1]["channel"])) if len(truth) >= 2 else None
    output = dict(schema=SCHEMA, spec=spec, config=asdict(cfg), evidence="measured_channel_CFO_driven_explicit_waveform_simulation", generated_source_noise=False, source_records=[bank[t["source_index"]] for t in truth], truth=truth, frontend=frontend_audit, frontend_seconds=frontend_seconds, candidate_count=len(estimates), noise_variance_per_channel=noise_power, calibration=cal, physical_angle_deg=physical_angle, effective_whitened_angle_deg=effective_angle, targets=target_rows, decoder_work_s={m: sum(r["seconds"] for r in decoded[m]) for m in methods}, candidate_estimates=configured, elapsed_s=time.perf_counter() - started)
    if mechanism:
        output["mechanism_symbols"] = spectral_rows
    return output, (samples, mechanisms)


def job_key(spec):
    return f"{spec['family']}_{hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()[:16]}"


def run_job(spec, out, revision):
    path = Path(out) / "jobs" / (job_key(spec) + ".json")
    if path.exists():
        previous = json.loads(path.read_text())
        if previous.get("revision_hash") == revision:
            return str(path), True
    result, _ = evaluate(spec, source_bank(), default_cfg(), mechanism=spec["family"] == "A")
    result["revision_hash"] = revision
    write_json(path, result)
    return str(path), False


def specifications(mode, repeats, near_snr, seed):
    specs = []
    def add(**kwargs):
        paired_group = {k: v for k, v in kwargs.items() if k not in ("snr_db", "sir_db", "w_symbols")}
        group_seed = int(hashlib.sha256(json.dumps(paired_group, sort_keys=True).encode()).hexdigest()[:8], 16)
        for repeat in range(repeats):
            spec = {**kwargs, "repeat": repeat, "seed": (seed + group_seed + repeat * 104729) % (2**32 - 1)}
            specs.append(spec)
    if mode == "pilot":
        for snr in (-30., -27.5, -25., -22.5, -20., -17.5, -15., 0.):
            add(family="pilot", k=1, snr_db=snr, methods=["mrc", "sp"])
    if mode in ("A", "all"):
        add(family="A", k=7, snr_db=0.)
    if mode in ("B", "all"):
        for low, high in ((0., 10.), (10., 60.)):
            for snr in (-30., -25., -20., -10., 0., 10.):
                for sir in (-20., -10., 0., 10.):
                    add(family="B_grid", k=2, snr_db=snr, sir_db=sir, angle_low=low, angle_high=high, focus=[0])
        for low, high in ((0., 2.), (2., 5.), (5., 10.), (10., 20.), (20., 40.)):
            for snr in (near_snr, 0.):
                add(family="B_angle", k=2, snr_db=snr, sir_db=0., angle_low=low, angle_high=high)
        for k in (2, 4, 6, 8, 10):
            for snr in (near_snr, 0.):
                add(family="B_density", k=k, snr_db=snr, sir_db=0.)
    if mode in ("C", "all"):
        for k in (2, 4, 6):
            for width in (0., .1, .25, .5, 1., 2.):
                for snr in (near_snr, 0.):
                    add(family="C", k=k, w_symbols=width, snr_db=snr, methods=["mrc", "sp"])
    return specs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("pilot", "A", "B", "C", "all"), default="pilot")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repeats", type=int, default=16)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--near-snr", type=float, default=-25.)
    parser.add_argument("--seed", type=int, default=9452026)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.repeats < 1 or args.workers < 1:
        parser.error("repeats and workers must be positive")
    specs = specifications(args.mode, args.repeats, args.near_snr, args.seed)
    if args.limit:
        specs = specs[:args.limit]
    revision = revision_hash()
    write_json(args.out / f"manifest_{args.mode}.json", dict(schema=SCHEMA, revision_hash=revision, config=asdict(default_cfg()), evidence="measured_channel_CFO_driven_explicit_waveform_simulation", source_count=len(source_bank()), methods=LABELS, density_power_policy="equal per-packet received power; total interference increases with K", B_scope="known timing/CFO; preamble-estimated spatial reference and lambda", C_scope="anonymous production detection, reference estimation and SP core/refinement; all transmitted frames in denominator", arguments={**vars(args), "out": str(args.out)}, jobs=specs))
    began = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_job, spec, str(args.out), revision): spec for spec in specs}
        for count, future in enumerate(as_completed(futures), 1):
            spec = futures[future]
            path, cached = future.result()
            print(json.dumps(dict(done=count, total=len(specs), family=spec["family"], cached=cached, path=path, wall_s=round(time.perf_counter() - began, 2))), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
