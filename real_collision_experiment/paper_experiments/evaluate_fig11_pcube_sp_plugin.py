#!/usr/bin/env python3
"""Evaluate PCube-clustered SP as a plug-in decoder on Fig. 11 scenes.

The cascade has one narrow, auditable interface.  PCube's preamble PDoA and
its per-symbol PDoA cluster provide an allowed FFT-bin set.  SP then scores
*only those bins* with its ordinary target/orthogonal projection and the
packet-level lambda that was fixed from preamble statistics before decoding.
The cascade never uses CRC, payload identity, manifest timing, or symbol truth
to form a cluster or select a bin.

The existing PCube and SP bars are recomputed from the immutable Fig. 11
per-candidate reports.  Hence the plug-in test adds only a third, cascaded
decoder; it cannot change the two source baselines.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECEIVER = ROOT / "real_collision_experiment" / "node01_sp_receiver"
ANALYSIS = ROOT / "real_collision_experiment" / "analysis"
for path in (ROOT, RECEIVER, ANALYSIS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_fig11_real_run_intervals import (  # noqa: E402
    FORMAL_ANALYSIS_DURATION_S,
    candidate_crc_identity,
    decoded_identity,
    infer_traffic_origin,
    load_json,
    manifest_paths,
    report_slice,
    scene_candidates,
)
from lora_mrc_sp_core import compensate_symbol_window, instantaneous_chirp, lora_symbol_fft  # noqa: E402
from lora_phy_decode import decode_payload_from_symbol_bins  # noqa: E402
from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import (  # noqa: E402
    dc_remove_and_whiten,
    load_capture,
)
from real_collision_experiment.node01_sp_receiver.sp_node01_receiver import (  # noqa: E402
    validate_payload,
)


METHODS = ("pcube", "sp_sync_refine", "pcube_sp")
METHOD_LABELS = {
    "pcube": "PCube",
    "sp_sync_refine": "SP-Decoder",
    "pcube_sp": "PCube+SP",
}
METHOD_COLORS = {
    "pcube": "#F4A261",
    "sp_sync_refine": "#159D8A",
    "pcube_sp": "#6C5CE7",
}
PCUBE_CLUSTER_RADIUS_RAD = 0.5
EPS = 1e-30


def parse_orders(text: str) -> tuple[int, ...]:
    values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    if not values or any(value < 2 for value in values):
        raise argparse.ArgumentTypeError("orders must be comma-separated integers >= 2")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root", type=Path, default=ROOT / "real_collision_experiment/runs"
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=ROOT / "real_collision_experiment/analysis/fig9_10_12_10s/reports",
    )
    parser.add_argument(
        "--intervals",
        type=Path,
        default=(
            ROOT
            / "real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes"
            / "fig11_real_collision_intervals.csv"
        ),
        help="The frozen Fig. 11 scene table whose PCube/SP values are retained.",
    )
    parser.add_argument(
        "--baseline-summary",
        type=Path,
        default=(
            ROOT
            / "real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes"
            / "fig11_real_decoder_time_ser_summary.csv"
        ),
        help="Frozen Fig. 11 summary used to verify PCube/SP replay equivalence.",
    )
    parser.add_argument(
        "--allow-baseline-mismatch",
        action="store_true",
        help=(
            "Write an explicitly exploratory result when the supplied reports no longer "
            "reproduce the frozen PCube/SP Fig. 11 values. Never use this mode for the paper."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "real_usrp_outputs/fig11_pcube_sp_plugin",
    )
    parser.add_argument("--orders", type=parse_orders, default=(2, 4, 8, 12, 16))
    parser.add_argument("--scenes-per-order", type=int, default=15)
    parser.add_argument("--sf", type=int, default=10)
    parser.add_argument("--bandwidth-hz", type=int, default=250_000)
    return parser.parse_args()


def method_row(candidate: dict, method: str) -> dict | None:
    return next(
        (row for row in candidate.get("methods", []) if row.get("method") == method),
        None,
    )


def complex_pairs(values: list[list[float]]) -> np.ndarray:
    return np.asarray(
        [complex(float(real), float(imag)) for real, imag in values],
        dtype=np.complex128,
    )


def local_peaks(power: np.ndarray) -> np.ndarray:
    """PCube's payload peak admission, including its conservative fallback."""

    values = np.asarray(power, dtype=np.float64)
    floor = float(np.median(values)) + EPS
    mask = (
        (values >= np.roll(values, 1))
        & (values >= np.roll(values, -1))
        & (values >= 6.0 * floor)
        & (values >= 0.01 * float(np.max(values)))
    )
    peaks = np.flatnonzero(mask)
    if peaks.size == 0:
        return np.asarray([int(np.argmax(values))], dtype=np.int64)
    if peaks.size > 64:
        peaks = peaks[np.argsort(values[peaks])[-64:]]
    return peaks.astype(np.int64, copy=False)


def circular_phase_distance(values: np.ndarray, reference: float) -> np.ndarray:
    return np.abs(np.angle(np.exp(1j * (np.asarray(values) - float(reference)))))


@dataclass
class Waveforms:
    white: np.ndarray
    physical_centered: np.ndarray
    cfg: RealCollisionLoRaConfig


def load_waveforms(report: dict) -> Waveforms:
    source = report["input"]
    slice_info = source["analysis_slice"]
    capture = load_capture(
        Path(source["iq"]),
        Path(source["metadata"]),
        start_time_s=float(slice_info["start_time_s"]),
        max_duration_s=float(slice_info["requested_duration_s"]),
    )
    # This exactly matches the formal receiver's default --noise-seconds 0:
    # dc_remove_and_whiten internally retains the first 128 samples.
    white, _, _, calibration = dc_remove_and_whiten(capture.samples, noise_samples=0)
    dc = np.asarray(
        [complex(float(real), float(imag)) for real, imag in calibration["dc"]],
        dtype=np.complex64,
    )
    physical_centered = np.asarray(capture.samples - dc[:, None], dtype=np.complex64)
    config = report["config"]
    cfg = RealCollisionLoRaConfig(
        sf=int(config["sf"]),
        bw_hz=float(config["bw_hz"]),
        sample_rate_hz=float(config["sample_rate_hz"]),
    )
    return Waveforms(white=white, physical_centered=physical_centered, cfg=cfg)


def spectra(
    samples: np.ndarray,
    *,
    start_sample: float,
    cfo_bins: float,
    sto_samples: float,
    cfg: RealCollisionLoRaConfig,
    symbol_index: int,
) -> np.ndarray:
    symbol_start = float(start_sample) + (
        float(cfg.payload_start_symbols) + int(symbol_index)
    ) * float(cfg.samples_per_symbol)
    window = compensate_symbol_window(
        samples, symbol_start, float(cfo_bins), cfg, sto_samples=float(sto_samples)
    )
    downchirp = instantaneous_chirp(0, cfg, up=False)
    return np.vstack([lora_symbol_fft(row * downchirp, cfg) for row in window])


def pcube_clustered_sp(
    waveforms: Waveforms,
    candidate: dict,
    pcube: dict,
    *,
    run_id: int,
    active_nodes: set[int],
    accepted_run_ids: set[int],
) -> dict:
    """Pass PCube PDoA clusters to an otherwise unchanged SP decision rule."""

    diagnostics = pcube.get("paper_diagnostics", {})
    target_pdoa = diagnostics.get("target_pdoa_rad")
    if target_pdoa is None:
        raise ValueError("PCube row has no preamble PDoA cluster anchor")
    frontend = diagnostics.get("frontend_policy", {})
    sp_start = float(candidate["start_sample"])
    sp_cfo = float(candidate.get("continuous_cfo_bins", candidate["cfo_bins"]))
    sp_sto = float(candidate.get("sto_samples", 0.0))
    # PCube may make its documented bounded preamble/SFD local refinement.
    # The recorded deltas expose the resulting pre-payload cluster geometry.
    pcube_start = sp_start + float(frontend.get("paper_refinement_start_delta_samples") or 0.0)
    pcube_cfo = sp_cfo + float(frontend.get("paper_refinement_cfo_delta_bins") or 0.0)
    channel = complex_pairs(candidate["channel_sp"])
    norm = math.sqrt(float(np.vdot(channel, channel).real))
    if channel.size != 2 or norm <= EPS:
        raise ValueError("SP target channel must be a nonzero two-Rx vector")
    target = channel / norm
    orthogonal = np.asarray(
        [-np.conj(target[1]), np.conj(target[0])], dtype=np.complex128
    )
    lam = float(candidate.get("lambda_sp", 0.0))
    bins: list[int] = []
    margins: list[float] = []
    cluster_sizes: list[int] = []
    fallback_count = 0
    started = time.perf_counter_ns()
    for symbol_index in range(int(waveforms.cfg.payload_symbol_count)):
        pcube_spectra = spectra(
            waveforms.physical_centered,
            start_sample=pcube_start,
            cfo_bins=pcube_cfo,
            sto_samples=0.0,
            cfg=waveforms.cfg,
            symbol_index=symbol_index,
        )
        energy = np.sum(np.abs(pcube_spectra) ** 2, axis=0)
        candidates = local_peaks(energy)
        pair_phase = np.angle(
            pcube_spectra[0, candidates] * np.conj(pcube_spectra[1, candidates])
        )
        phase_distance = circular_phase_distance(pair_phase, float(target_pdoa))
        allowed = candidates[phase_distance <= PCUBE_CLUSTER_RADIUS_RAD]
        if allowed.size == 0:
            allowed = np.asarray(
                [int(candidates[int(np.argmin(phase_distance))])], dtype=np.int64
            )
            fallback_count += 1
        cluster_sizes.append(int(allowed.size))

        sp_spectra = spectra(
            waveforms.white,
            start_sample=sp_start,
            cfo_bins=sp_cfo,
            sto_samples=sp_sto,
            cfg=waveforms.cfg,
            symbol_index=symbol_index,
        )
        projected = np.conj(target) @ sp_spectra[:2]
        residual = np.conj(orthogonal) @ sp_spectra[:2]
        score = (np.abs(projected) ** 2 - lam * np.abs(residual) ** 2).real
        local = int(np.argmax(score[allowed]))
        chosen = int(allowed[local])
        bins.append(chosen)
        remaining = np.delete(score[allowed], local)
        margins.append(
            float(score[chosen] - np.max(remaining)) if remaining.size else float(score[chosen])
        )

    phy = decode_payload_from_symbol_bins(bins, waveforms.cfg)
    payload = bytes(phy.payload)
    decoded, app_ok, status = validate_payload(
        payload,
        run_id=int(run_id),
        active_nodes=active_nodes,
        accepted_run_ids=accepted_run_ids,
    )
    return {
        "method": "pcube_sp",
        "symbol_bins": [int(value) for value in bins],
        "mean_symbol_margin": float(np.mean(margins)) if margins else 0.0,
        "lambda_sp": lam,
        "phy": {
            "payload_hex": payload.hex(),
            "phy_crc_ok": bool(phy.phy_crc_ok),
            "corrected_codewords": int(phy.corrected_codewords),
            "uncorrected_codewords": int(phy.uncorrected_codewords),
            "header_nibbles": [int(value) for value in phy.header_nibbles],
            "status": phy.status,
        },
        "application": {
            "app_crc_ok": bool(app_ok),
            "status": status,
            "decoded": (
                {
                    "run_id": int(decoded.run_id),
                    "node_id": int(decoded.node_id),
                    "sequence": int(decoded.sequence),
                }
                if decoded is not None
                else None
            ),
        },
        "decode_elapsed_ms": (time.perf_counter_ns() - started) / 1_000_000.0,
        "paper_diagnostics": {
            "cascade_interface": "PCube PDoA cluster bins -> SP fixed-lambda score",
            "pcube_target_pdoa_rad": float(target_pdoa),
            "pcube_cluster_radius_rad": PCUBE_CLUSTER_RADIUS_RAD,
            "pcube_local_start_delta_samples": float(
                frontend.get("paper_refinement_start_delta_samples") or 0.0
            ),
            "pcube_local_cfo_delta_bins": float(
                frontend.get("paper_refinement_cfo_delta_bins") or 0.0
            ),
            "mean_pcube_cluster_bin_count": float(np.mean(cluster_sizes)),
            "pcube_empty_cluster_fallback_count": int(fallback_count),
            "sp_lambda_source": "original pre-payload packet-level configuration",
            "crc_or_truth_used_for_cluster_or_bin_selection": False,
        },
    }


def collect_scenes(args: argparse.Namespace) -> tuple[list[dict], list[dict]]:
    """Load the exact 75 collision groups used by the displayed Fig. 11.

    The present 5-second report directories were generated after Fig. 11.
    Reconstructing scenes from them would silently alter the 2-packet subset.
    The frozen interval table instead binds this plug-in evaluation to the
    same 10-second reports and scene rows that produced the supplied figure.
    """

    manifests = {path.stem: load_json(path) for path in manifest_paths(args.runs_root)}
    by_order: dict[int, list[dict]] = defaultdict(list)
    skipped: list[dict] = []
    with args.intervals.open("r", encoding="utf-8", newline="") as stream:
        interval_rows = list(csv.DictReader(stream))
    for interval in interval_rows:
        order = int(interval["collision_order"])
        if order not in args.orders:
            continue
        run_name = str(interval["run"])
        manifest = manifests.get(run_name)
        if manifest is None:
            skipped.append({"run": run_name, "reason": "manifest_missing"})
            continue
        radio = manifest.get("radio", {})
        config = manifest.get("config", {})
        sf = int(radio.get("spreading_factor", config.get("sf", 0)) or 0)
        bandwidth_hz = int(radio.get("bandwidth_hz", config.get("bandwidth_hz", 0)) or 0)
        if sf != int(args.sf) or bandwidth_hz != int(args.bandwidth_hz):
            skipped.append({"run": run_name, "reason": "PHY_mismatch"})
            continue
        report_path = args.reports / f"{run_name}.json"
        if not report_path.exists():
            skipped.append({"run": run_name, "reason": "report_missing"})
            continue
        report = load_json(report_path)
        if report.get("decoder", {}).get("comparison_frontend_scope") != "common":
            skipped.append({"run": run_name, "reason": "not_common_frontend"})
            continue
        try:
            report_start_s, _ = report_slice(report)
        except ValueError as exc:
            skipped.append({"run": run_name, "reason": str(exc)})
            continue
        config = report.get("config", {})
        cfg = RealCollisionLoRaConfig(
            sf=int(config["sf"]),
            bw_hz=float(config["bw_hz"]),
            sample_rate_hz=float(config["sample_rate_hz"]),
        )
        identities = tuple(
            sorted(
                tuple(int(value) for value in token.split(":", 1))
                for token in str(interval["collision_group_identities"]).split(";")
                if token
            )
        )
        by_order[order].append(
            {
                "scene_index": int(interval["scene_index"]),
                "run_name": run_name,
                "manifest": manifest,
                "report": report,
                "collision_order": order,
                "active_identities": identities,
                "segment_start_slice_s": float(interval["full_capture_start_s"]) - report_start_s,
                "segment_end_slice_s": float(interval["full_capture_end_s"]) - report_start_s,
                "frame_s": float(cfg.frame_samples) / float(cfg.sample_rate_hz),
            }
        )
    selected: list[dict] = []
    for order in args.orders:
        rows = sorted(by_order[order], key=lambda row: int(row["scene_index"]))
        if len(rows) < args.scenes_per_order:
            raise RuntimeError(f"order {order}: only {len(rows)} scenes; need {args.scenes_per_order}")
        selected.extend(rows[: args.scenes_per_order])
    return selected, skipped


def cascade_rows(scenes: list[dict]) -> list[dict]:
    rows: list[dict] = []
    by_run: dict[str, list[dict]] = defaultdict(list)
    for scene in scenes:
        by_run[scene["run_name"]].append(scene)
    for run_name, run_scenes in sorted(by_run.items()):
        report = run_scenes[0]["report"]
        waveforms = load_waveforms(report)
        manifest = run_scenes[0]["manifest"]
        run_id = int(manifest["config"]["run_id"])
        active_nodes = {int(value) for value in manifest.get("active_nodes", [])}
        accepted = {run_id}
        accepted.update(int(value) for value in manifest.get("config", {}).get("merged_source_run_ids", []))
        needed: dict[int, dict] = {}
        for scene in run_scenes:
            for candidate in scene_candidates(
                report,
                start_slice_s=float(scene["segment_start_slice_s"]),
                end_slice_s=float(scene["segment_end_slice_s"]),
                frame_s=float(scene["frame_s"]),
            ):
                needed[int(candidate["candidate_id"])] = candidate
        cascade: dict[int, dict] = {}
        for candidate_id, candidate in sorted(needed.items()):
            pcube = method_row(candidate, "pcube")
            if pcube is None:
                continue
            cascade[candidate_id] = pcube_clustered_sp(
                waveforms,
                candidate,
                pcube,
                run_id=run_id,
                active_nodes=active_nodes,
                accepted_run_ids=accepted,
            )
        for scene in run_scenes:
            candidates = scene_candidates(
                report,
                start_slice_s=float(scene["segment_start_slice_s"]),
                end_slice_s=float(scene["segment_end_slice_s"]),
                frame_s=float(scene["frame_s"]),
            )
            denominator = min(len(scene["active_identities"]), len(candidates))
            for method in METHODS:
                if method == "pcube_sp":
                    decoded = {
                        decoded_identity(cascade.get(int(candidate["candidate_id"])))
                        for candidate in candidates
                    }
                else:
                    decoded = {decoded_identity(method_row(candidate, method)) for candidate in candidates}
                decoded.discard(None)
                rows.append(
                    {
                        "run": run_name,
                        "collision_order": int(scene["collision_order"]),
                        "method": method,
                        "method_label": METHOD_LABELS[method],
                        "planned_packet_count": len(scene["active_identities"]),
                        "fine_sync_detected_packet_count": len(candidates),
                        "prr_denominator_packet_count": denominator,
                        "decoded_packet_count": len(decoded),
                        "prr": float(len(decoded)) / denominator if denominator else math.nan,
                        "cascade_candidate_count": len(cascade) if method == "pcube_sp" else None,
                    }
                )
    return rows


def summarize(rows: list[dict], orders: tuple[int, ...]) -> list[dict]:
    summary: list[dict] = []
    for order in orders:
        for method in METHODS:
            selected = [row for row in rows if row["collision_order"] == order and row["method"] == method]
            numerator = sum(int(row["decoded_packet_count"]) for row in selected)
            denominator = sum(int(row["prr_denominator_packet_count"]) for row in selected)
            summary.append(
                {
                    "collision_order": order,
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "collision_scene_count": len(selected),
                    "decoded_packet_count": numerator,
                    "prr_denominator_packet_count": denominator,
                    "prr": float(numerator) / denominator if denominator else math.nan,
                }
            )
    return summary


def baseline_mismatches(
    summary: list[dict], baseline_path: Path, orders: tuple[int, ...]
) -> list[str]:
    """Reject a cascade bar if its two source bars are not the frozen Fig. 11."""

    with baseline_path.open("r", encoding="utf-8", newline="") as stream:
        frozen_rows = list(csv.DictReader(stream))
    frozen = {
        (int(row["collision_order"]), str(row["method"])): float(row["prr_mean"])
        for row in frozen_rows
        if str(row.get("method")) in {"pcube", "sp_sync_refine"}
    }
    replayed = {
        (int(row["collision_order"]), str(row["method"])): float(row["prr"])
        for row in summary
        if str(row.get("method")) in {"pcube", "sp_sync_refine"}
    }
    mismatches: list[str] = []
    for order in orders:
        for method in ("pcube", "sp_sync_refine"):
            key = (int(order), method)
            expected = frozen.get(key)
            actual = replayed.get(key)
            if expected is None or actual is None or abs(expected - actual) > 1e-12:
                mismatches.append(
                    f"order={order} method={method} frozen={expected} replayed={actual}"
                )
    return mismatches


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot(summary: list[dict], orders: tuple[int, ...], output: Path) -> None:
    x = np.arange(len(orders), dtype=np.float64)
    width = 0.23
    figure, axis = plt.subplots(figsize=(7.4, 3.8), constrained_layout=True)
    for method_index, method in enumerate(METHODS):
        lookup = {
            int(row["collision_order"]): float(row["prr"])
            for row in summary
            if row["method"] == method
        }
        values = np.asarray([lookup[order] for order in orders])
        bars = axis.bar(
            x + (method_index - 1) * width,
            values,
            width,
            color=METHOD_COLORS[method],
            label=METHOD_LABELS[method],
        )
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                value + 0.018,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    axis.set_xticks(x, [str(order) for order in orders])
    axis.set_xlabel("Packets in the target collision group")
    axis.set_ylabel("PRR (unique decoded / min(planned, detected))")
    axis.set_ylim(0.0, 1.12)
    axis.grid(axis="y", color="#d9d9d9", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.legend(ncol=3, fontsize=9, frameon=True, loc="upper center")
    for suffix in ("png", "pdf"):
        figure.savefig(output.with_suffix(f".{suffix}"), dpi=240)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    if args.scenes_per_order < 1:
        raise ValueError("scenes-per-order must be positive")
    scenes, skipped = collect_scenes(args)
    rows = cascade_rows(scenes)
    summary = summarize(rows, args.orders)
    mismatches = baseline_mismatches(summary, args.baseline_summary, args.orders)
    if mismatches and not args.allow_baseline_mismatch:
        raise RuntimeError(
            "the current per-candidate reports do not reproduce the frozen Fig. 11 "
            "PCube/SP bars; refusing to mix data versions. Restore the archived reports "
            "or rerun all three methods on one candidate database. Differences: "
            + "; ".join(mismatches)
        )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "fig11_pcube_sp_plugin_raw.csv", rows)
    write_csv(args.out_dir / "fig11_pcube_sp_plugin_summary.csv", summary)
    plot(summary, args.orders, args.out_dir / "fig11_pcube_sp_plugin_prr")
    audit = {
        "schema": "fig11_pcube_sp_plugin_v1",
        "orders": list(args.orders),
        "scenes_per_order": int(args.scenes_per_order),
        "cascade": {
            "pcube_output": "PDoA-clustered payload FFT-bin set",
            "pcube_cluster_radius_rad": PCUBE_CLUSTER_RADIUS_RAD,
            "sp_input": "PCube cluster bin set plus original pre-payload SP channel and lambda",
            "sp_lambda_source": "existing Fig.11 packet-level configuration before payload",
            "crc_truth_manifest_used_for_cluster_or_bin_selection": False,
        },
        "baseline_policy": "PCube and SP values are re-aggregated from the unchanged Fig.11 reports",
        "baseline_replay_mismatches": mismatches,
        "exploratory_baseline_mismatch_override": bool(args.allow_baseline_mismatch),
        "skipped_runs": skipped,
        "summary": summary,
    }
    (args.out_dir / "fig11_pcube_sp_plugin_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"FIG11_PCUBE_SP_DONE scenes={len(scenes)} out={args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
