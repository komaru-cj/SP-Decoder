#!/usr/bin/env python3
"""Decode a bounded real capture with conservative strong-first SIC.

Only packets that already pass both PHY CRC and the experiment application CRC
are reconstructed and removed.  After each cancellation round the production
SP detector/synchronizer/decoder is run again on the residual IQ.  The source
capture is never modified.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "real_collision_experiment"
RECEIVER = EXPERIMENT / "node01_sp_receiver"
AUTOMATION = EXPERIMENT / "automation"
for directory in (ROOT, RECEIVER, AUTOMATION):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from real_collision_experiment.node01_sp_receiver.real_lora_config import (  # noqa: E402
    RealCollisionLoRaConfig,
)
from real_collision_experiment.node01_sp_receiver.sc16_io import (  # noqa: E402
    adc_clipping_statistics,
    load_capture,
)
from real_collision_experiment.paper_experiments.simulate_sp_mechanisms import (  # noqa: E402
    build_explicit_frame,
)
from receiver_campaign_server import formal_candidate_budgets  # noqa: E402


SP_METHOD_PRIORITY = {
    "sp_sync_refine": 4,
    "sp_core": 3,
    "sp_repair": 2,
    "sp": 1,
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def centered_window(metadata: dict, duration_s: float) -> float:
    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    target = int(metadata.get("target_samples_per_channel", metadata.get("samples_per_channel", 0)))
    available = int(metadata.get("samples_per_channel", 0))
    if rate <= 0.0 or target <= 0:
        raise ValueError("capture metadata has no usable rate/sample count")
    start_s = 0.5 * (target / rate - float(duration_s))
    required_end = round((start_s + duration_s) * rate)
    if start_s < 0.0 or required_end > available:
        raise ValueError(
            f"capture lacks centered {duration_s:g}s: available={available}, required_end={required_end}"
        )
    return float(start_s)


def identity_from_method(method: dict) -> tuple[int, int, int] | None:
    application = method.get("application", {})
    decoded = application.get("decoded")
    phy = method.get("phy", {})
    if not application.get("app_crc_ok") or not phy.get("phy_crc_ok") or not isinstance(decoded, dict):
        return None
    try:
        return int(decoded["run_id"]), int(decoded["node_id"]), int(decoded["sequence"])
    except (KeyError, TypeError, ValueError):
        return None


def decoded_proposals(report: dict, excluded: set[tuple[int, int, int]]) -> dict:
    grouped: dict[tuple[int, int, int], list[dict]] = {}
    for candidate in report.get("candidates", []):
        best_by_name: dict[str, dict] = {}
        for method in candidate.get("methods", []):
            name = str(method.get("method", ""))
            identity = identity_from_method(method)
            if name not in SP_METHOD_PRIORITY or identity is None or identity in excluded:
                continue
            old = best_by_name.get(name)
            if old is None or SP_METHOD_PRIORITY[name] > SP_METHOD_PRIORITY.get(str(old.get("method")), 0):
                best_by_name[name] = method
        if not best_by_name:
            continue
        method = max(best_by_name.values(), key=lambda row: SP_METHOD_PRIORITY[str(row["method"])])
        identity = identity_from_method(method)
        if identity is None:
            continue
        payload_hex = method.get("phy", {}).get("payload_hex")
        if not isinstance(payload_hex, str):
            continue
        grouped.setdefault(identity, []).append(
            {
                "candidate_id": int(candidate.get("candidate_id", -1)),
                "candidate_power": float(candidate.get("power", 0.0)),
                "start_sample": float(candidate["start_sample"])
                + float(method.get("sync_refine_start_delta_samples", 0.0) or 0.0),
                "cfo_bins": float(method.get("used_cfo_bins", candidate.get("continuous_cfo_bins", 0.0))),
                "method": str(method["method"]),
                "payload_hex": payload_hex,
            }
        )
    return grouped


def report_unique_identities(report: dict) -> set[tuple[int, int, int]]:
    identities: set[tuple[int, int, int]] = set()
    for row in report.get("unique_successes", []):
        try:
            identities.add((int(row["run_id"]), int(row["node_id"]), int(row["sequence"])))
        except (KeyError, TypeError, ValueError):
            continue
    return identities


def build_model(payload_hex: str, cfg: RealCollisionLoRaConfig, cfo_bins: float) -> np.ndarray:
    frame, _ = build_explicit_frame(bytes.fromhex(payload_hex), cfg)
    time = np.arange(frame.size, dtype=np.float64)
    carrier = np.exp(2j * np.pi * float(cfo_bins) * time / cfg.samples_per_symbol)
    return (frame * carrier).astype(np.complex64)


def fit_one(
    residual: np.ndarray,
    proposal: dict,
    cfg: RealCollisionLoRaConfig,
    *,
    start_radius: int,
    cfo_radius: float,
    cfo_step: float,
) -> dict | None:
    payload_hex = str(proposal["payload_hex"])
    frame, _ = build_explicit_frame(bytes.fromhex(payload_hex), cfg)
    length = int(frame.size)
    base_start = int(round(float(proposal["start_sample"])))
    start_values = range(base_start - start_radius, base_start + start_radius + 1)
    cfo_offsets = np.arange(-cfo_radius, cfo_radius + 0.5 * cfo_step, cfo_step)
    best: dict | None = None
    for start in start_values:
        if start < 0 or start + length > residual.shape[1]:
            continue
        segment = residual[:, start : start + length]
        local_energy = float(np.vdot(segment, segment).real)
        if local_energy <= 0.0:
            continue
        for offset in cfo_offsets:
            cfo = float(proposal["cfo_bins"]) + float(offset)
            model = build_model(payload_hex, cfg, cfo)
            model_energy = float(np.vdot(model, model).real)
            correlations = np.asarray([np.vdot(model, channel) for channel in segment])
            gains = correlations / max(model_energy, 1e-18)
            reduction = float(np.sum(np.abs(correlations) ** 2) / max(model_energy, 1e-18))
            fit_fraction = reduction / local_energy
            row = {
                **proposal,
                "start_sample": int(start),
                "cfo_bins": cfo,
                "frame_samples": length,
                "gains": gains,
                "local_energy_before": local_energy,
                "predicted_energy_reduction": reduction,
                "fit_fraction": float(fit_fraction),
                "model": model,
            }
            if best is None or row["predicted_energy_reduction"] > best["predicted_energy_reduction"]:
                best = row
    return best


def best_identity_fit(
    residual: np.ndarray,
    proposals: list[dict],
    cfg: RealCollisionLoRaConfig,
    args: argparse.Namespace,
) -> dict | None:
    fits = [
        fit_one(
            residual,
            proposal,
            cfg,
            start_radius=args.start_search_samples,
            cfo_radius=args.cfo_search_bins,
            cfo_step=args.cfo_search_step_bins,
        )
        for proposal in proposals
    ]
    valid = [row for row in fits if row is not None]
    return max(valid, key=lambda row: row["predicted_energy_reduction"], default=None)


def cancel_decoded_packets(
    residual: np.ndarray,
    grouped: dict,
    cfg: RealCollisionLoRaConfig,
    args: argparse.Namespace,
) -> tuple[list[dict], set[tuple[int, int, int]]]:
    initial: list[tuple[tuple[int, int, int], dict]] = []
    for identity, proposals in grouped.items():
        fit = best_identity_fit(residual, proposals, cfg, args)
        if fit is not None:
            initial.append((identity, fit))
    initial.sort(key=lambda item: item[1]["predicted_energy_reduction"], reverse=True)

    rows: list[dict] = []
    cancelled: set[tuple[int, int, int]] = set()
    for identity, _ in initial:
        fit = best_identity_fit(residual, grouped[identity], cfg, args)
        if fit is None or fit["fit_fraction"] < args.min_fit_fraction:
            continue
        start = int(fit["start_sample"])
        end = start + int(fit["frame_samples"])
        before = float(np.vdot(residual[:, start:end], residual[:, start:end]).real)
        for channel in range(residual.shape[0]):
            residual[channel, start:end] -= fit["gains"][channel] * fit["model"]
        after = float(np.vdot(residual[:, start:end], residual[:, start:end]).real)
        if not after < before:
            for channel in range(residual.shape[0]):
                residual[channel, start:end] += fit["gains"][channel] * fit["model"]
            continue
        cancelled.add(identity)
        rows.append(
            {
                "run_id": identity[0],
                "node_id": identity[1],
                "sequence": identity[2],
                "candidate_id": int(fit["candidate_id"]),
                "source_method": fit["method"],
                "start_sample": start,
                "cfo_bins": float(fit["cfo_bins"]),
                "fit_fraction": float(fit["fit_fraction"]),
                "local_energy_before": before,
                "local_energy_after": after,
                "measured_energy_reduction": before - after,
                "complex_gains": [
                    [float(value.real), float(value.imag)] for value in fit["gains"]
                ],
            }
        )
    return rows, cancelled


def write_sc16(path: Path, samples: np.ndarray) -> None:
    clipped = np.clip(np.asarray(samples), -0.999969482421875, 0.999969482421875)
    framed = np.empty((clipped.shape[1], clipped.shape[0], 2), dtype="<i2")
    framed[:, :, 0] = np.rint(clipped.real.T * 32768.0).astype("<i2")
    framed[:, :, 1] = np.rint(clipped.imag.T * 32768.0).astype("<i2")
    framed.tofile(path)


def residual_metadata(original: dict, samples: np.ndarray, rate: float, source: Path, round_index: int) -> dict:
    value = dict(original)
    value["status"] = "sic_residual"
    value["samples_per_channel"] = int(samples.shape[1])
    value["target_samples_per_channel"] = int(samples.shape[1])
    value["channel_count"] = int(samples.shape[0])
    value["actual"] = dict(value.get("actual", {}))
    value["actual"]["rate_hz"] = float(rate)
    value["overflow_count"] = 0
    value["timeout_count"] = 0
    value["clipping_count"] = adc_clipping_statistics(samples)["clipped_count"]
    value["sic"] = {
        "source_capture": str(source),
        "round": int(round_index),
        "note": "CRC-certified reconstructed packets removed; source capture unchanged",
    }
    return value


def run_decoder(
    args: argparse.Namespace,
    iq: Path,
    metadata: Path,
    manifest: Path,
    report: Path,
    run_id: int,
    max_candidates: int,
    per_window: int,
    *,
    capture_start_s: float,
) -> None:
    command = [
        args.python_executable,
        str(RECEIVER / "sp_node01_receiver.py"),
        "--iq", str(iq),
        "--metadata", str(metadata),
        "--manifest", str(manifest),
        "--out", str(report),
        "--run-id", f"0x{run_id:08X}",
        "--capture-start-seconds", f"{capture_start_s:g}",
        "--max-capture-seconds", f"{args.duration_s:g}",
        "--business-duration-s", f"{args.duration_s:g}",
        "--threshold", "3",
        "--max-candidates", str(max_candidates),
        "--frontend-candidates-per-window", str(per_window),
        "--energy-min-ratio", "3",
        "--comparison-frontend-scope", "common",
        "--cfo-min", f"{args.cfo_min:g}",
        "--cfo-max", f"{args.cfo_max:g}",
        "--skip-comparison-decoders",
    ]
    print(f"SIC_DECODE report={report.name} input={iq.name}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--duration-s", type=float, default=5.0)
    parser.add_argument("--start-s", type=float, default=None)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--min-fit-fraction", type=float, default=0.002)
    parser.add_argument("--start-search-samples", type=int, default=2)
    parser.add_argument("--cfo-search-bins", type=float, default=0.2)
    parser.add_argument("--cfo-search-step-bins", type=float, default=0.1)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Control manifest; defaults to RUN_DIR/RUN_NAME.json, then runs/manifests",
    )
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=None,
        help="Reuse an existing decoder report for round zero",
    )
    parser.add_argument("--output-subdir", default="sic_middle5")
    parser.add_argument("--cfo-min", type=float, default=-32.0)
    parser.add_argument("--cfo-max", type=float, default=32.0)
    parser.add_argument(
        "--frontend-candidates-per-window",
        type=int,
        default=None,
        help="Override the formal per-window proposal budget",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    name = run_dir.name
    iq = run_dir / f"{name}.sc16"
    metadata_path = iq.with_suffix(iq.suffix + ".json")
    if args.manifest is not None:
        manifest_path = args.manifest.resolve()
    elif (run_dir / f"{name}.json").exists():
        manifest_path = run_dir / f"{name}.json"
    else:
        manifest_path = run_dir.parent / "manifests" / f"{name}.json"
    for path in (iq, metadata_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"missing required input: {path}")

    metadata = load_json(metadata_path)
    manifest = load_json(manifest_path)
    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    start_s = centered_window(metadata, args.duration_s) if args.start_s is None else float(args.start_s)
    run_id = int(manifest["config"]["run_id"])
    expected_count = sum(
        int(row.get("tx_count", 0)) for row in manifest.get("expected_node_schedules", {}).values()
    )
    max_candidates, per_window = formal_candidate_budgets(
        {
            "active_nodes": manifest.get("active_nodes", []),
            "expected_tx_count": expected_count,
        }
    )
    if args.frontend_candidates_per_window is not None:
        per_window = max(1, int(args.frontend_candidates_per_window))
    radio = manifest.get("radio", {})
    cfg = RealCollisionLoRaConfig(
        sf=int(radio.get("spreading_factor", 10)),
        bw_hz=float(radio.get("bandwidth_hz", 250_000.0)),
        sample_rate_hz=rate,
        ldro=(2 ** int(radio.get("spreading_factor", 10)))
        / float(radio.get("bandwidth_hz", 250_000.0))
        >= 0.016,
    )

    output_dir = run_dir / str(args.output_subdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_report = (
        args.baseline_report.resolve()
        if args.baseline_report is not None
        else output_dir / "round_0_report.json"
    )
    if args.baseline_report is not None and not baseline_report.exists():
        raise SystemExit(f"missing baseline report: {baseline_report}")
    if args.baseline_report is None and (args.overwrite or not baseline_report.exists()):
        run_decoder(
            args,
            iq,
            metadata_path,
            manifest_path,
            baseline_report,
            run_id,
            max_candidates,
            per_window,
            capture_start_s=start_s,
        )

    capture = load_capture(
        iq,
        metadata_path,
        start_time_s=start_s,
        max_duration_s=args.duration_s,
    )
    residual = np.asarray(capture.samples, dtype=np.complex64).copy()
    all_decoded: set[tuple[int, int, int]] = set()
    all_report_successes: set[tuple[int, int, int]] = set()
    rounds: list[dict] = []
    current_report = baseline_report
    baseline_identities: set[tuple[int, int, int]] = set()
    baseline_report_identities: set[tuple[int, int, int]] = set()

    for round_index in range(args.max_rounds + 1):
        report = load_json(current_report)
        grouped_all = decoded_proposals(report, set())
        observed = set(grouped_all)
        report_observed = report_unique_identities(report)
        if round_index == 0:
            baseline_identities = set(observed)
            baseline_report_identities = set(report_observed)
        new_identities = observed - all_decoded
        new_report_identities = report_observed - all_report_successes
        grouped_new = {identity: grouped_all[identity] for identity in new_identities}
        print(
            f"SIC_ROUND {round_index} crc_unique={len(observed)} new={len(new_identities)}",
            flush=True,
        )
        if round_index >= args.max_rounds or not grouped_new:
            rounds.append(
                {
                    "round": round_index,
                    "report": str(current_report),
                    "crc_valid_identities": [list(value) for value in sorted(observed)],
                    "new_identities": [list(value) for value in sorted(new_identities)],
                    "report_application_valid_identities": [
                        list(value) for value in sorted(report_observed)
                    ],
                    "new_report_application_valid_identities": [
                        list(value) for value in sorted(new_report_identities)
                    ],
                    "cancelled": [],
                }
            )
            all_decoded.update(observed)
            all_report_successes.update(report_observed)
            break

        cancelled_rows, cancelled = cancel_decoded_packets(residual, grouped_new, cfg, args)
        all_decoded.update(observed)
        rounds.append(
            {
                "round": round_index,
                "report": str(current_report),
                "crc_valid_identities": [list(value) for value in sorted(observed)],
                "new_identities": [list(value) for value in sorted(new_identities)],
                "report_application_valid_identities": [
                    list(value) for value in sorted(report_observed)
                ],
                "new_report_application_valid_identities": [
                    list(value) for value in sorted(new_report_identities)
                ],
                "cancelled": cancelled_rows,
            }
        )
        all_report_successes.update(report_observed)
        print(
            f"SIC_CANCEL round={round_index} accepted={len(cancelled)} "
            f"rejected={len(grouped_new) - len(cancelled)}",
            flush=True,
        )
        if not cancelled:
            break

        residual_iq = output_dir / f"round_{round_index + 1}_residual.sc16"
        residual_meta = residual_iq.with_suffix(residual_iq.suffix + ".json")
        write_sc16(residual_iq, residual)
        save_json(
            residual_meta,
            residual_metadata(metadata, residual, rate, iq, round_index + 1),
        )
        current_report = output_dir / f"round_{round_index + 1}_report.json"
        if args.overwrite or not current_report.exists():
            run_decoder(
                args,
                residual_iq,
                residual_meta,
                manifest_path,
                current_report,
                run_id,
                max_candidates,
                per_window,
                capture_start_s=0.0,
            )
        else:
            print(f"SIC_REUSE_REPORT report={current_report.name}", flush=True)

    recovered = all_decoded - baseline_identities
    report_recovered = all_report_successes - baseline_report_identities
    report_only_without_phy_crc = all_report_successes - all_decoded
    summary = {
        "schema": "real_collision_strong_first_sic_v1",
        "source_iq": str(iq),
        "source_manifest": str(manifest_path),
        "source_capture_unchanged": True,
        "analysis_window": {
            "start_s": start_s,
            "duration_s": args.duration_s,
            "end_s": start_s + args.duration_s,
        },
        "phy": {
            "sf": cfg.sf,
            "bandwidth_hz": cfg.bw_hz,
            "sample_rate_hz": cfg.sample_rate_hz,
            "frame_samples": cfg.frame_samples,
        },
        "safety": {
            "crc_required_before_cancellation": True,
            "minimum_fit_fraction": args.min_fit_fraction,
            "energy_must_decrease": True,
            "manifest_payload_oracle_used": False,
        },
        "baseline_unique_count": len(baseline_identities),
        "sic_recovered_unique_count": len(recovered),
        "total_unique_count": len(all_decoded),
        "count_semantics": (
            "The three legacy *_unique_count fields are strict: both PHY CRC and "
            "application CRC must pass. Production report unique_success_count uses "
            "application CRC and is listed separately below."
        ),
        "baseline_report_application_valid_count": len(baseline_report_identities),
        "sic_report_application_valid_recovered_count": len(report_recovered),
        "total_report_application_valid_union_count": len(all_report_successes),
        "baseline_strict_dual_crc_count": len(baseline_identities),
        "sic_strict_dual_crc_recovered_count": len(recovered),
        "total_strict_dual_crc_union_count": len(all_decoded),
        "baseline_identities": [list(value) for value in sorted(baseline_identities)],
        "sic_recovered_identities": [list(value) for value in sorted(recovered)],
        "all_identities": [list(value) for value in sorted(all_decoded)],
        "sic_report_application_valid_recovered_identities": [
            list(value) for value in sorted(report_recovered)
        ],
        "application_valid_but_never_phy_crc_valid_identities": [
            list(value) for value in sorted(report_only_without_phy_crc)
        ],
        "nodes_seen": sorted({identity[1] for identity in all_decoded}),
        "rounds": rounds,
    }
    summary_path = output_dir / "sic_summary.json"
    save_json(summary_path, summary)
    print(
        f"SIC_DONE baseline={len(baseline_identities)} recovered={len(recovered)} "
        f"total={len(all_decoded)} summary={summary_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
