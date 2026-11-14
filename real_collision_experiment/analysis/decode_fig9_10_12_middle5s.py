#!/usr/bin/env python3
"""Decode the strictly aligned middle business seconds for Fig. 9--15.

The capture-file midpoint is not the traffic midpoint: repeated CONFIG/START
frames and the firmware arm/warm-up delay move the 20-second node business
interval later in the IQ file.  This driver aligns the controller event
template to RF energy, derives the full-IQ traffic origin, and evaluates the
strict centered 10 seconds of the business interval (for a 20-second run,
``[traffic_start + 5 s, traffic_start + 15 s]``).

With ``--build-merged`` the driver first synthesizes the simulated 18/21/24-node
runs by summing the real 15-node capture with the 3/6/9-node capture aligned at
their business traffic begins (see merge_fig9_10_runs.py), then decodes every
selected Fig. 9/10/12 run with the same strict-window receiver pipeline.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from formal_window import FORMAL_ANALYSIS_DURATION_S, formal_analysis_duration_s


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "real_collision_experiment"
AUTOMATION = EXPERIMENT / "automation"
if str(AUTOMATION) not in sys.path:
    sys.path.insert(0, str(AUTOMATION))

from receiver_campaign_server import formal_candidate_budgets  # noqa: E402


FORMAL_FINE_SYNC_SCHEMA = "fine_sync_anonymous_physical_v2"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def centered_window(metadata: dict, duration_s: float) -> tuple[float, float]:
    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    target = int(
        metadata.get(
            "target_samples_per_channel", metadata.get("samples_per_channel", 0)
        )
    )
    available = int(metadata.get("samples_per_channel", 0))
    if rate <= 0.0 or target <= 0 or available <= 0:
        raise ValueError("capture metadata has no usable rate/sample count")
    start_s = 0.5 * (float(target) / rate - float(duration_s))
    end_sample = round((start_s + duration_s) * rate)
    if start_s < 0.0 or end_sample > available:
        raise ValueError(
            f"capture does not contain target-centered {duration_s:g}s window: "
            f"available={available} required_end={end_sample}"
        )
    return float(start_s), float(duration_s)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sp-lambda-policy", choices=("pair_only_legacy", "pair_and_noise_max_v1", "pair_and_noise_two_packet_v1", "pair_and_noise_reference_guard_v2"),
                        default="pair_and_noise_reference_guard_v2")
    parser.add_argument("--runs", type=Path, default=EXPERIMENT / "runs")
    parser.add_argument(
        "--reports",
        type=Path,
        default=EXPERIMENT / "analysis/fig9_10_12_preview/reports",
    )
    parser.add_argument(
        "--window-map",
        type=Path,
        default=EXPERIMENT / "analysis/fig9_10_12_preview/evaluation_windows.json",
        help="Deprecated legacy capture-window map; strict business alignment ignores it",
    )
    parser.add_argument("--duration-s", type=float, default=FORMAL_ANALYSIS_DURATION_S)
    parser.add_argument(
        "--allow-window-duration-override",
        action="store_true",
        help=(
            "allow a noncanonical strict business-window duration for an explicit "
            "sensitivity/re-averaging run"
        ),
    )
    parser.add_argument(
        "--include-figure",
        action="append",
        default=None,
        help=(
            "Manifest experiment.figure values to decode. Repeat as needed. "
            "Defaults to the legacy fig9_10 and fig12 set."
        ),
    )
    parser.add_argument(
        "--spreading-factor",
        action="append",
        type=int,
        default=[],
        help="Only decode manifests with this spreading factor. Repeat as needed.",
    )
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--skip-comparison-decoders",
        action="store_true",
        help="write a shared-sync receiver report without the non-CoRa comparison decoders",
    )
    parser.add_argument(
        "--sp-sync-retry-policy",
        choices=("strict_header", "relaxed_structure"),
        default="strict_header",
        help=(
            "SP synchronization-retry admission policy passed to the receiver; "
            "relaxed_structure gives plausible preamble/SFD anchors a bounded "
            "additional start/CFO search."
        ),
    )
    parser.add_argument(
        "--sp-sync-relaxed-max-trials",
        type=int,
        default=8,
        help="Cumulative SP trial budget for relaxed-structure candidates.",
    )
    parser.add_argument(
        "--build-merged",
        action="store_true",
        help=(
            "Build the simulated 18/21/24-node runs (15-node capture summed with "
            "the 3/6/9-node capture) before decoding"
        ),
    )
    parser.add_argument(
        "--alignment-only",
        action="store_true",
        help="Audit strict business windows without running any decoder",
    )
    parser.add_argument(
        "--legacy-multi-track-frontend",
        action="store_true",
        help=(
            "Use the legacy per-seed multi-track preamble scan instead of the "
            "SPv2 Sec. 5.2 sliding downchirp/SFD frontend"
        ),
    )
    parser.add_argument(
        "--use-fine-sync",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Read per-run fine-synchronization hypotheses from "
            "analysis/fig9_10_12_preview/fine_sync/run_<id>.json when present; "
            "all decoders then share these start/STO/CFO/channel hypotheses"
        ),
    )
    parser.add_argument(
        "--require-fine-sync",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Require a matching global anonymous formal-window physical-candidate "
            "database "
            "for formal PRR-figure decoding. Alignment-only is exempt."
        ),
    )
    parser.add_argument(
        "--traffic-start-map",
        type=Path,
        default=None,
        help="Optional JSON mapping run name to full-IQ traffic-begin seconds",
    )
    return parser.parse_args()


def parse_utc_seconds(text: str) -> float:
    return datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()


def sc16_log_power(
    iq_path: Path,
    metadata: dict,
    *,
    block_s: float = 0.02,
) -> tuple[np.ndarray, float]:
    """Return robust two-channel log power on a short regular time grid."""

    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    samples = int(metadata.get("samples_per_channel", 0))
    if rate <= 0.0 or samples <= 0:
        raise ValueError("capture metadata has no usable rate/sample count")
    expected_bytes = samples * 4 * np.dtype("<i2").itemsize
    if iq_path.stat().st_size < expected_bytes:
        raise ValueError(
            f"IQ is shorter than metadata: bytes={iq_path.stat().st_size} "
            f"expected={expected_bytes}"
        )
    raw = np.memmap(iq_path, dtype="<i2", mode="r", shape=(samples, 4))
    block_samples = max(1, int(round(rate * float(block_s))))
    powers: list[float] = []
    for start in range(0, samples, block_samples):
        block = raw[start : min(samples, start + block_samples)].astype(np.float32)
        block -= np.mean(block, axis=0, keepdims=True)
        powers.append(float(np.mean(block * block)))
    array = np.asarray(powers, dtype=np.float64)
    floor = max(float(np.percentile(array, 5.0)), 1e-12)
    return np.log(np.maximum(array, floor)), float(block_s)


def estimate_traffic_start_from_control_energy(
    iq_path: Path,
    metadata: dict,
    manifest: dict,
    *,
    analysis_duration_s: float = FORMAL_ANALYSIS_DURATION_S,
) -> tuple[float, dict]:
    """Align manifest CONFIG/START enqueue times to their RF energy bursts.

    Event-versus-gap log-power contrast rejects a false match inside the later
    near-continuous node collision region.  No packet schedule, node identity,
    sequence, or decoded packet start participates in this alignment.
    """

    events: list[tuple[float, float, str]] = []
    relevant = [
        row
        for row in manifest.get("events", [])
        if row.get("type") in {"CONFIG_ENQUEUED", "START_ENQUEUED"}
        and row.get("utc")
    ]
    if not relevant or not manifest.get("expected_traffic_begin_utc"):
        raise ValueError(
            "manifest lacks controller events/expected_traffic_begin_utc; "
            "supply --traffic-start-map"
        )
    first_utc = parse_utc_seconds(relevant[0]["utc"])
    start_airtime = float(manifest.get("control", {}).get("start_airtime_s", 0.35))
    for row in relevant:
        kind = str(row["type"])
        duration = 0.50 if kind == "CONFIG_ENQUEUED" else max(0.25, start_airtime)
        events.append(
            (parse_utc_seconds(row["utc"]) - first_utc, duration, kind)
        )

    log_power, block_s = sc16_log_power(iq_path, metadata)
    span_s = max(offset + duration for offset, duration, _ in events) + 0.30
    template_blocks = int(math.ceil(span_s / block_s))
    if log_power.size <= template_blocks:
        raise ValueError("capture is too short to align the controller RF template")
    event_mask = np.zeros(template_blocks, dtype=bool)
    guard_mask = np.zeros(template_blocks, dtype=bool)
    event_slices: list[slice] = []
    for offset, duration, _ in events:
        start = max(0, int((offset + 0.02) / block_s))
        end = min(template_blocks, int((offset + duration - 0.02) / block_s))
        if end <= start:
            continue
        event_mask[start:end] = True
        event_slices.append(slice(start, end))
        guard_start = max(0, int((offset - 0.08) / block_s))
        guard_end = min(template_blocks, int((offset + duration + 0.08) / block_s))
        guard_mask[guard_start:guard_end] = True
    gap_mask = ~guard_mask
    if not np.any(event_mask) or not np.any(gap_mask):
        raise ValueError("controller RF template has no event/gap samples")

    scores = np.empty(log_power.size - template_blocks + 1, dtype=np.float64)
    business_duration_s = float(manifest.get("config", {}).get("duration_ms", 0)) / 1000.0
    available_s = float(metadata.get("samples_per_channel", 0)) / float(
        metadata.get("actual", {}).get(
            "rate_hz", metadata.get("requested", {}).get("sample_rate_hz", 1.0)
        )
    )
    traffic_offset_s = (
        parse_utc_seconds(manifest["expected_traffic_begin_utc"]) - first_utc
    )
    for shift in range(scores.size):
        candidate_traffic_start_s = shift * block_s + traffic_offset_s
        candidate_middle_start_s = candidate_traffic_start_s + 0.5 * (
            business_duration_s - float(analysis_duration_s)
        )
        if (
            business_duration_s <= 0.0
            or analysis_duration_s > business_duration_s
            or candidate_middle_start_s < 0.0
            or candidate_middle_start_s + float(analysis_duration_s) > available_s
        ):
            scores[shift] = -np.inf
            continue
        window = log_power[shift : shift + template_blocks]
        event_contrast = float(np.median(window[event_mask]) - np.median(window[gap_mask]))
        per_event = [float(np.median(window[item])) for item in event_slices]
        lower_event_contrast = float(
            np.percentile(per_event, 25.0) - np.median(window[gap_mask])
        )
        scores[shift] = event_contrast + 0.5 * lower_event_contrast
    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])
    if best_score < math.log(5.0):
        raise ValueError(
            f"controller RF template alignment is weak: score={best_score:.3f}; "
            "supply --traffic-start-map"
        )
    first_control_rf_s = best_index * block_s
    traffic_start_s = first_control_rf_s + traffic_offset_s
    separated = scores.copy()
    exclusion = max(1, int(round(1.0 / block_s)))
    separated[
        max(0, best_index - exclusion) : min(scores.size, best_index + exclusion + 1)
    ] = -np.inf
    runner_up = float(np.max(separated)) if np.any(np.isfinite(separated)) else -math.inf
    return float(traffic_start_s), {
        "source": "controller_event_template_aligned_to_sc16_energy",
        "traffic_start_s": float(traffic_start_s),
        "first_control_rf_start_s": float(first_control_rf_s),
        "block_s": float(block_s),
        "template_event_count": len(event_slices),
        "best_log_contrast_score": best_score,
        "runner_up_separated_log_contrast_score": runner_up,
        "iq_bytes": iq_path.stat().st_size,
        "metadata_updated_utc": metadata.get("updated_utc"),
    }


def middle_business_window(
    traffic_start_s: float,
    business_duration_s: float,
    analysis_duration_s: float,
) -> tuple[float, float]:
    if analysis_duration_s <= 0.0 or analysis_duration_s > business_duration_s:
        raise ValueError(
            "analysis duration must be positive and no longer than business duration"
        )
    return (
        float(traffic_start_s)
        + 0.5 * (float(business_duration_s) - float(analysis_duration_s)),
        float(analysis_duration_s),
    )


def manifest_paths(runs_root: Path) -> list[Path]:
    paths = {
        path.stem: path.resolve()
        for path in (runs_root / "manifests").glob("run_*.json")
    }
    for run_dir in runs_root.glob("run_*"):
        candidate = run_dir / f"{run_dir.name}.json"
        if candidate.exists():
            paths[candidate.stem] = candidate.resolve()
    return [paths[name] for name in sorted(paths)]


def validate_fine_sync_database(
    path: Path,
    *,
    run_name: str,
    analysis_start_s: float,
    duration_s: float,
) -> None:
    """Reject a database that cannot represent this exact business slice."""

    database = load_json(path)
    if database.get("schema") != FORMAL_FINE_SYNC_SCHEMA:
        raise ValueError(
            f"{run_name}: fine-sync database must be global anonymous v2; got "
            f"{database.get('schema')!r} at {path}"
        )
    if database.get("run_id") != run_name:
        raise ValueError(
            f"{run_name}: fine-sync database run_id is "
            f"{database.get('run_id')!r} at {path}"
        )
    window = database.get("window", {})
    database_start_s = float(window.get("analysis_start_s", math.nan))
    database_duration_s = float(window.get("duration_s", math.nan))
    if (
        not math.isfinite(database_start_s)
        or not math.isfinite(database_duration_s)
        or abs(database_start_s - analysis_start_s) > 1e-6
        or abs(database_duration_s - duration_s) > 1e-6
    ):
        raise ValueError(
            f"{run_name}: fine-sync database window "
            f"{database_start_s:g}+{database_duration_s:g}s does not match "
            f"decode window {analysis_start_s:g}+{duration_s:g}s"
        )
    packets = database.get("packets")
    if not isinstance(packets, list):
        raise ValueError(f"{run_name}: anonymous fine-sync packets is not a list")
    if any(
        row.get("node_id") is not None or row.get("sequence") is not None
        for row in packets
        if isinstance(row, dict)
    ):
        raise ValueError(f"{run_name}: anonymous fine-sync database contains identities")
    discovery = database.get("candidate_discovery", {})
    required_discovery = {
        "scope": "global_full_window",
        "manifest_schedule_exposed_to_detector": False,
        "node_timing_calibration": False,
        "planned_start_search_windows": False,
        "score_truncation": False,
    }
    invalid = {
        key: discovery.get(key)
        for key, expected in required_discovery.items()
        if discovery.get(key) != expected
    }
    if invalid:
        raise ValueError(
            f"{run_name}: fine-sync database violates global anonymous "
            f"discovery contract: {invalid}"
        )
    if discovery.get("candidate_overflow_policy") not in {
        "fail_closed_without_truncation",
        "retain_excess_candidates_without_truncation",
    }:
        raise ValueError(
            f"{run_name}: fine-sync database has an unknown candidate-overflow policy"
        )


def cfo_limit_bins(manifest: dict) -> int:
    radio = manifest.get("radio", {})
    sf = int(radio.get("spreading_factor", 10))
    bandwidth_hz = float(radio.get("bandwidth_hz", 125_000.0))
    # Hold the physical search span at 15.625 kHz: 128 bins at SF10/BW125,
    # 64 bins at BW250.  A fixed bin limit silently halves Hz coverage at BW125.
    return max(32, int(math.ceil(15_625.0 / (bandwidth_hz / (2**sf)))))


def main() -> int:
    args = parse_args()
    included_figures = set(
        args.include_figure
        or ("fig9_10", "fig11", "fig12", "fig13")
    )
    included_spreading_factors = set(args.spreading_factor)
    selected = {value.lower().removeprefix("run_") for value in args.run_id}
    if args.build_merged:
        from merge_fig9_10_runs import build_merged_runs  # noqa: E402

        merged_default_map = args.reports / "merged_traffic_starts.json"
        build_merged_runs(
            args.runs,
            args.reports,
            traffic_start_map_path=args.traffic_start_map or merged_default_map,
            force=False,
        )
    merged_map_candidates = []
    if args.traffic_start_map is not None:
        merged_map_candidates.append(args.traffic_start_map)
    merged_map_candidates.append(args.reports / "merged_traffic_starts.json")
    traffic_start_overrides: dict[str, float] = {}
    for candidate in merged_map_candidates:
        if candidate.exists():
            traffic_start_overrides.update(load_json(candidate))
    args.reports.mkdir(parents=True, exist_ok=True)
    completed = 0
    for manifest_path in manifest_paths(args.runs):
        manifest = load_json(manifest_path)
        figure = str(manifest.get("experiment", {}).get("figure"))
        if figure in {"fig14", "fig15"}:
            print(f"SKIP_EXCLUDED_FIGURE {manifest_path.stem} figure={figure}", flush=True)
            continue
        if figure not in included_figures:
            continue
        name = manifest_path.stem
        expected_duration_s = formal_analysis_duration_s(figure)
        if (
            not args.allow_window_duration_override
            and not math.isclose(args.duration_s, expected_duration_s, abs_tol=1e-9)
        ):
            raise SystemExit(
                f"{name}: {figure} requires --duration-s {expected_duration_s:g}"
            )
        spreading_factor = int(
            manifest.get("radio", {}).get(
                "spreading_factor", manifest.get("config", {}).get("sf", 0)
            )
            or 0
        )
        if included_spreading_factors and spreading_factor not in included_spreading_factors:
            continue
        if selected and name.removeprefix("run_").lower() not in selected:
            continue
        report_path = args.reports / f"{name}.json"
        if report_path.exists() and not args.overwrite and not args.alignment_only:
            if not args.skip_comparison_decoders:
                existing = load_json(report_path)
                if existing.get("comparison_baseline_revision") != "target_mrc_cic_v1":
                    raise ValueError(
                        f"{report_path}: contains legacy baselines; choose a new --reports "
                        "directory or use --overwrite to recompute MRC+CIC"
                    )
            if load_json(report_path).get("sp_lambda_policy", "pair_only_legacy") != args.sp_lambda_policy:
                raise ValueError(f"{report_path}: stale SP lambda policy; use a new --reports directory or --overwrite")
            print(f"SKIP_EXISTING {report_path}", flush=True)
            continue
        iq_path = args.runs / name / f"{name}.sc16"
        metadata_path = iq_path.with_suffix(iq_path.suffix + ".json")
        if not iq_path.exists() or not metadata_path.exists():
            print(f"SKIP_MISSING_IQ {name}", flush=True)
            continue
        metadata = load_json(metadata_path)
        business_duration_s = float(manifest.get("config", {}).get("duration_ms", 0)) / 1000.0
        if business_duration_s <= 0.0:
            business_duration_s = float(manifest.get("traffic", {}).get("duration_s", 0.0))
        if business_duration_s <= 0.0:
            raise ValueError(f"{name}: manifest has no positive business duration")
        if name in traffic_start_overrides:
            traffic_start_s = float(traffic_start_overrides[name])
            alignment = {
                "source": "traffic_start_map_override",
                "traffic_start_s": traffic_start_s,
                "iq_bytes": iq_path.stat().st_size,
                "metadata_updated_utc": metadata.get("updated_utc"),
            }
        else:
            if bool(manifest.get("experiment", {}).get("simulated_merged")):
                raise SystemExit(
                    f"{name}: simulated merged run has no traffic-start override; "
                    "run --build-merged or supply --traffic-start-map"
                )
            traffic_start_s, alignment = estimate_traffic_start_from_control_energy(
                iq_path,
                metadata,
                manifest,
                analysis_duration_s=args.duration_s,
            )
        start_s, duration_s = middle_business_window(
            traffic_start_s,
            business_duration_s,
            args.duration_s,
        )
        relative_business_window_start_s = start_s - traffic_start_s
        available_s = float(metadata.get("samples_per_channel", 0)) / float(
            metadata.get("actual", {}).get(
                "rate_hz", metadata.get("requested", {}).get("sample_rate_hz", 1.0)
            )
        )
        if start_s < 0.0 or start_s + duration_s > available_s:
            print(
                f"SKIP_WINDOW_OUTSIDE_CAPTURE {name} window={start_s:g}-"
                f"{start_s + duration_s:g}s available={available_s:g}s",
                flush=True,
            )
            continue
        expected_count = sum(
            int(row.get("tx_count", 0))
            for row in manifest.get("expected_node_schedules", {}).values()
        )
        run_budget = {
            "active_nodes": manifest.get("active_nodes", []),
            "expected_tx_count": expected_count,
        }
        global_limit, window_limit = formal_candidate_budgets(run_budget)
        cfo_limit = cfo_limit_bins(manifest)

        fine_sync_db = args.reports.parent / "fine_sync" / f"{name}.json"
        formal_shared_prr_figure = manifest.get("experiment", {}).get("figure") in {
            "fig9_10",
            "fig11",
            "fig12",
            "fig13",
            "fig14",
            "fig15",
        }

        def receiver_command(output: Path, *, skip_comparisons: bool) -> list[str]:
            command = [
                args.python_executable,
                str(EXPERIMENT / "node01_sp_receiver/sp_node01_receiver.py"),
                "--iq", str(iq_path),
                "--metadata", str(metadata_path),
                "--manifest", str(manifest_path),
                "--out", str(output),
                "--run-id", f"0x{int(manifest['config']['run_id']):08X}",
                "--capture-start-seconds", f"{start_s:.9f}",
                "--max-capture-seconds", f"{duration_s:.9f}",
                "--business-duration-s", f"{duration_s:.9f}",
                "--planned-business-window-start-ms",
                f"{relative_business_window_start_s * 1000.0:.9f}",
                "--planned-business-window-duration-ms",
                f"{duration_s * 1000.0:.9f}",
                "--threshold", "3",
                "--max-candidates", str(global_limit),
                "--frontend-candidates-per-window", str(window_limit),
                "--energy-min-ratio", "3",
                "--comparison-frontend-scope", "common",
                "--cfo-min", str(-cfo_limit),
                "--cfo-max", str(cfo_limit),
                "--sp-sync-retry-policy", args.sp_sync_retry_policy,
                "--sp-lambda-policy", args.sp_lambda_policy,
                "--sp-sync-relaxed-max-trials",
                str(args.sp_sync_relaxed_max_trials),
            ]
            if skip_comparisons:
                command.append("--skip-comparison-decoders")
            if not args.legacy_multi_track_frontend:
                command.append("--sliding-frontend")
            else:
                command.append("--no-sliding-frontend")
            if args.use_fine_sync and fine_sync_db.exists():
                command.extend(["--fine-sync-db", str(fine_sync_db)])
            return command

        command = receiver_command(
            report_path, skip_comparisons=args.skip_comparison_decoders
        )
        alignment.update(
            {
                "business_duration_s": float(business_duration_s),
                "analysis_duration_s": float(duration_s),
                "planned_business_window_start_ms": (
                    float(relative_business_window_start_s) * 1000.0
                ),
                "planned_business_window_duration_ms": float(duration_s) * 1000.0,
                "strict_middle_business_start_s": float(start_s),
                "strict_middle_business_end_s": float(start_s + duration_s),
            }
        )
        alignment_path = args.reports / f"{name}.business_alignment.json"
        alignment_path.write_text(
            json.dumps(alignment, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if args.alignment_only:
            print(
                f"BUSINESS_ALIGNMENT_ONLY {name} traffic_start={traffic_start_s:.3f}s "
                f"window={start_s:.3f}-{start_s + duration_s:.3f}s "
                f"audit={alignment_path}",
                flush=True,
            )
            completed += 1
            continue
        if args.require_fine_sync and formal_shared_prr_figure:
            if not args.use_fine_sync:
                raise SystemExit(
                    f"{name}: formal {manifest['experiment']['figure']} decoding "
                    "requires --use-fine-sync"
                )
            if not fine_sync_db.exists():
                raise SystemExit(
                    f"{name}: missing required fine-sync database {fine_sync_db}; "
                    "run build_fine_sync_database.py first"
                )
            validate_fine_sync_database(
                fine_sync_db,
                run_name=name,
                analysis_start_s=start_s,
                duration_s=duration_s,
            )
        print(
            f"DECODE_BUSINESS_MIDDLE{duration_s:g} {name} "
            f"traffic_start={traffic_start_s:.3f}s "
            f"window={start_s:.3f}-{start_s + duration_s:.3f}s "
            f"max_candidates={global_limit} per_window={window_limit} "
            f"cfo=±{cfo_limit} sync=global_anonymous_fine_sync",
            flush=True,
        )
        subprocess.run(command, cwd=ROOT, check=True)
        report = load_json(report_path)
        report.setdefault("input", {})["strict_middle_business_window"] = {
            "enabled": True,
            "traffic_start_s_from_full_iq": float(traffic_start_s),
            "business_duration_s": float(business_duration_s),
            "analysis_start_s_from_full_iq": float(start_s),
            "analysis_duration_s": float(duration_s),
            "alignment_source": alignment.get("source"),
            "alignment_audit": str(alignment_path.resolve()),
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        completed += 1
    print(
        f"BUSINESS_MIDDLE_DECODE_DONE duration={args.duration_s:g} "
        f"reports={completed} out={args.reports}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
