#!/usr/bin/env python3
"""Merge real Fig. 9/10 captures into simulated 18/21/24-node runs.

The collected Fig. 9/10 runs cover N=3/6/9/12/15 at both 125 kHz and 250 kHz.
This module overlays the 15-node capture with an independently recorded
3/6/9-node capture to synthesize an N=18/21/24 run:

* Both captures are re-aligned so their business traffic begins coincide;
* the two dual-channel complex-int16 signals are summed sample by sample
  (saturated to int16), so every packet waveform, CFO, channel direction,
  power relation and noise floor comes from a real recording;
* a merged manifest keeps node ids 1..15 from the 15-node run and renumbers
  the added run's nodes to 16..18 / 16..21 / 16..24, while recording the
  source run id / node id / source config per node so the receiver can
  re-derive the exact transmitted payload and identity.

The generated runs live in ``<runs>/run_<merged_id>`` next to the source runs
and are decoded by the same strict middle-business-window driver.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from formal_window import FORMAL_ANALYSIS_DURATION_S


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "real_collision_experiment"
DEFAULT_RUNS = EXPERIMENT / "runs"
DEFAULT_REPORTS = EXPERIMENT / "analysis" / "fig9_10_12_preview" / "reports"

# (merged node count, 15-node source run, added source run)
MERGED_PLAN = (
    (18, "run_0f012131", "run_03012131"),
    (21, "run_0f012131", "run_06012131"),
    (24, "run_0f012131", "run_09012131"),
    (18, "run_0f015131", "run_03015131"),
    (21, "run_0f015131", "run_06015131"),
    (24, "run_0f015131", "run_09015131"),
)

MARGIN_BEFORE_S = 1.0
MARGIN_AFTER_S = 5.0
BUSINESS_DURATION_S = 20.0
WINDOW_DURATION_S = MARGIN_BEFORE_S + BUSINESS_DURATION_S + MARGIN_AFTER_S

RUN_CONFIG_KEYS = (
    "run_id",
    "active_mask",
    "num_active_nodes",
    "phy_profile_id",
    "traffic_profile_id",
    "node_tx_power_dbm",
    "duration_ms",
    "warmup_ms",
    "global_seed",
    "payload_seed",
    "flags",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_for_run(runs_root: Path, run_name: str) -> dict:
    run_dir = runs_root / run_name
    candidates = [
        run_dir / f"{run_name}.json",
        runs_root / "manifests" / f"{run_name}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return load_json(candidate)
    raise FileNotFoundError(f"no manifest for {run_name} (tried {candidates})")


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def merged_run_name(node_count: int, bandwidth_hz: int) -> str:
    suffix = "21" if int(bandwidth_hz) == 125_000 else "51"
    return f"run_{node_count:02x}01{suffix}31"


def merged_run_id(node_count: int, bandwidth_hz: int) -> int:
    return int(merged_run_name(node_count, bandwidth_hz).removeprefix("run_"), 16)


def traffic_start_s_for_run(
    runs_root: Path,
    run_name: str,
    reports_root: Path,
) -> tuple[float, dict]:
    """Return the strict RF-aligned traffic-begin second of a source run."""

    alignment = reports_root / f"{run_name}.business_alignment.json"
    if alignment.exists():
        audit = load_json(alignment)
        return float(audit["traffic_start_s"]), {
            "source": "business_alignment_audit",
            "path": str(alignment),
        }
    from decode_fig9_10_12_middle5s import (  # lazy to avoid circular import
        estimate_traffic_start_from_control_energy,
    )

    run_dir = runs_root / run_name
    iq_path = run_dir / f"{run_name}.sc16"
    metadata = load_json(iq_path.with_suffix(iq_path.suffix + ".json"))
    manifest = load_json(run_dir / f"{run_name}.json")
    traffic_start_s, audit = estimate_traffic_start_from_control_energy(
        iq_path,
        metadata,
        manifest_for_run(runs_root, run_name),
        analysis_duration_s=FORMAL_ANALYSIS_DURATION_S,
    )
    return float(traffic_start_s), audit


def merged_samples(
    runs_root: Path,
    sources: list[tuple[str, float]],
    *,
    rate_hz: float,
) -> tuple[np.ndarray, dict]:
    """Sum the aligned traffic-relative windows of two captures (saturated)."""

    total_samples = int(round(WINDOW_DURATION_S * rate_hz))
    merged = np.zeros((total_samples, 4), dtype=np.int32)
    diagnostics: dict[str, dict] = {}
    for run_name, traffic_start_s in sources:
        run_dir = runs_root / run_name
        iq_path = run_dir / f"{run_name}.sc16"
        metadata = load_json(iq_path.with_suffix(iq_path.suffix + ".json"))
        actual = metadata.get("actual", {})
        requested = metadata.get("requested", {})
        source_rate = float(
            actual.get("rate_hz", requested.get("sample_rate_hz", rate_hz))
        )
        if abs(source_rate - rate_hz) > 1.0:
            raise ValueError(
                f"{run_name}: source rate {source_rate:g} != merged rate {rate_hz:g}"
            )
        samples_per_channel = int(metadata.get("samples_per_channel", 0))
        raw = np.memmap(iq_path, dtype="<i2", mode="r", shape=(samples_per_channel, 4))
        start_sample = max(0, int(round((traffic_start_s - MARGIN_BEFORE_S) * rate_hz)))
        end_sample = min(
            samples_per_channel,
            int(round((traffic_start_s + BUSINESS_DURATION_S + MARGIN_AFTER_S) * rate_hz)),
        )
        segment = raw[start_sample:end_sample].astype(np.int32)
        merged_start = int(round((traffic_start_s - MARGIN_BEFORE_S) * rate_hz))
        segment_start = merged_start - start_sample
        stop = min(total_samples, segment_start + segment.shape[0])
        if segment_start < 0 or stop <= segment_start:
            raise ValueError(
                f"{run_name}: traffic window does not intersect merged span "
                f"(traffic_start={traffic_start_s:g})"
            )
        merged[segment_start:stop] += segment[: stop - segment_start]
        diagnostics[run_name] = {
            "traffic_start_s": float(traffic_start_s),
            "source_window_samples": [start_sample, end_sample],
            "merged_slice": [segment_start, stop],
            "source_available_after_traffic_s": (
                float(samples_per_channel) / rate_hz - traffic_start_s
            ),
        }
    clipped = merged > 32767
    under = merged < -32768
    clipped_count = int(np.count_nonzero(clipped))
    underflow_count = int(np.count_nonzero(under))
    out = np.clip(merged, -32768, 32767).astype(np.int16)
    diagnostics["saturation"] = {
        "clipped_count_total": clipped_count,
        "underflow_count_total": underflow_count,
        "saturated_fraction": float(
            (clipped_count + underflow_count) / max(1, merged.size)
        ),
    }
    return out, diagnostics


def source_config_dict(manifest: dict) -> dict:
    cfg = manifest.get("config", {})
    return {key: int(cfg[key]) for key in RUN_CONFIG_KEYS if key in cfg}


def build_merged_manifest(
    base_manifest: dict,
    added_manifest: dict,
    *,
    node_count: int,
    bandwidth_hz: int,
) -> dict:
    """Create the merged manifest with per-node source identity/config."""

    run_name = merged_run_name(node_count, bandwidth_hz)
    run_id = merged_run_id(node_count, bandwidth_hz)
    base_config = base_manifest.get("config", {})
    added_config = added_manifest.get("config", {})
    base_schedules = base_manifest.get("expected_node_schedules", {})
    added_schedules = added_manifest.get("expected_node_schedules", {})
    base_run_id = int(base_config.get("run_id", 0))
    added_run_id = int(added_config.get("run_id", 0))
    base_source = source_config_dict(base_manifest)
    added_source = source_config_dict(added_manifest)

    schedules: dict[str, dict] = {}
    for node_id in range(1, 16):
        source_schedule = base_schedules.get(str(node_id), {})
        if not isinstance(source_schedule, dict):
            raise ValueError(f"{run_name}: base run missing schedule for node {node_id}")
        schedules[str(node_id)] = {
            **source_schedule,
            "source_run_id": base_run_id,
            "source_node_id": node_id,
            "source_config": base_source,
        }
    added_node_count = node_count - 15
    for index in range(added_node_count):
        source_node_id = index + 1
        merged_node_id = 15 + source_node_id
        source_schedule = added_schedules.get(str(source_node_id), {})
        if not isinstance(source_schedule, dict):
            raise ValueError(
                f"{run_name}: added run missing schedule for node {source_node_id}"
            )
        schedules[str(merged_node_id)] = {
            **source_schedule,
            "source_run_id": added_run_id,
            "source_node_id": source_node_id,
            "source_config": added_source,
        }

    experiment = dict(base_manifest.get("experiment", {}))
    experiment.update(
        {
            "simulated_merged": True,
            "merged_method": "aligned_traffic_relative_capture_summation",
            "merged_source_runs": [
                base_manifest.get("config", {}).get("run_id"),
                added_manifest.get("config", {}).get("run_id"),
            ],
            "merged_source_run_names": [
                f"run_{base_run_id:08x}",
                f"run_{added_run_id:08x}",
            ],
        }
    )

    config = {
        key: int(value)
        for key, value in base_config.items()
        if key
        in {
            "phy_profile_id",
            "traffic_profile_id",
            "node_tx_power_dbm",
            "duration_ms",
            "warmup_ms",
            "flags",
            "sf",
            "bandwidth_hz",
        }
    }
    config.update(
        {
            "run_id": run_id,
            "active_mask": (1 << node_count) - 1,
            "num_active_nodes": node_count,
            "global_seed": (run_id * 0x9E3779B9) & 0xFFFFFFFF,
            "payload_seed": (run_id * 0x85EBCA6B) & 0xFFFFFFFF,
            "offered_load": round(0.25 * node_count, 4),
            "per_node_duty_cycle": 0.25,
            "bandwidth_hz": bandwidth_hz,
            "merged_source_run_ids": [base_run_id, added_run_id],
        }
    )

    traffic = dict(base_manifest.get("traffic", {}))
    traffic.update(
        {
            "firmware_active_node_count": node_count,
            "profile_offered_load": round(0.25 * node_count, 4),
            "effective_aggregate_offered_load": round(0.25 * node_count, 4),
        }
    )

    merged = dict(base_manifest)
    merged.update(
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "experiment": experiment,
            "config": config,
            "active_nodes": list(range(1, node_count + 1)),
            "active_node_count": node_count,
            "traffic": traffic,
            "expected_node_schedules": schedules,
            "merged_simulation": {
                "enabled": True,
                "semantics": (
                    "sum of two real captures aligned at business traffic begin; "
                    "payload identities preserved via per-node source config"
                ),
                "source_runs": [f"run_{base_run_id:08x}", f"run_{added_run_id:08x}"],
            },
        }
    )
    return merged


def build_merged_metadata(
    base_metadata: dict,
    *,
    run_name: str,
    merged_dir: Path,
    samples_per_channel: int,
    rate_hz: float,
    sources: list[str],
) -> dict:
    metadata = json.loads(json.dumps(base_metadata))
    duration_s = samples_per_channel / rate_hz
    requested = dict(metadata.get("requested", {}))
    requested["duration_s"] = float(duration_s)
    metadata.update(
        {
            "output_file": str(merged_dir / f"{run_name}.sc16"),
            "samples_per_channel": int(samples_per_channel),
            "target_samples_per_channel": int(samples_per_channel),
            "file_bytes": int(samples_per_channel) * 4 * np.dtype("<i2").itemsize,
            "requested": requested,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "merged_simulation": {
                "enabled": True,
                "source_runs": sources,
                "method": "aligned_traffic_relative_capture_summation",
                "duration_s": float(duration_s),
            },
        }
    )
    return metadata


def build_merged_runs(
    runs_root: Path,
    reports_root: Path,
    *,
    traffic_start_map_path: Path | None = None,
    force: bool = False,
) -> dict:
    """Generate all merged runs; return per-run provenance and the map."""

    runs_root = Path(runs_root)
    reports_root = Path(reports_root)
    traffic_map: dict[str, float] = {}
    results: dict[str, dict] = {}
    for node_count, base_name, added_name in MERGED_PLAN:
        base_manifest = manifest_for_run(runs_root, base_name)
        added_manifest = manifest_for_run(runs_root, added_name)
        bandwidth_hz = int(base_manifest.get("radio", {}).get("bandwidth_hz", 0))
        if bandwidth_hz != int(added_manifest.get("radio", {}).get("bandwidth_hz", 0)):
            raise ValueError(
                f"{base_name}/{added_name}: bandwidth mismatch for merged run"
            )
        run_name = merged_run_name(node_count, bandwidth_hz)
        run_dir = runs_root / run_name
        iq_path = run_dir / f"{run_name}.sc16"
        if iq_path.exists() and not force:
            print(f"SKIP_EXISTING_MERGED {run_name} {iq_path}", flush=True)
            traffic_map[run_name] = MARGIN_BEFORE_S
            results[run_name] = {"status": "existing"}
            continue
        base_start, base_audit = traffic_start_s_for_run(
            runs_root, base_name, reports_root
        )
        added_start, added_audit = traffic_start_s_for_run(
            runs_root, added_name, reports_root
        )
        metadata = load_json(runs_root / base_name / f"{base_name}.sc16.json")
        actual = metadata.get("actual", {})
        requested = metadata.get("requested", {})
        rate_hz = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
        if rate_hz <= 0.0:
            raise ValueError(f"{base_name}: metadata has no usable sample rate")
        samples, diagnostics = merged_samples(
            runs_root,
            [(base_name, base_start), (added_name, added_start)],
            rate_hz=rate_hz,
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        samples.tofile(iq_path)
        manifest = build_merged_manifest(
            base_manifest,
            added_manifest,
            node_count=node_count,
            bandwidth_hz=bandwidth_hz,
        )
        save_json(run_dir / f"{run_name}.json", manifest)
        merged_metadata = build_merged_metadata(
            metadata,
            run_name=run_name,
            merged_dir=run_dir,
            samples_per_channel=samples.shape[0],
            rate_hz=rate_hz,
            sources=[base_name, added_name],
        )
        save_json(run_dir / f"{run_name}.sc16.json", merged_metadata)
        traffic_map[run_name] = MARGIN_BEFORE_S
        results[run_name] = {
            "status": "built",
            "node_count": node_count,
            "bandwidth_hz": bandwidth_hz,
            "samples_per_channel": int(samples.shape[0]),
            "duration_s": float(samples.shape[0] / rate_hz),
            "traffic_start_s_in_merged": MARGIN_BEFORE_S,
            "sources": [base_name, added_name],
            "traffic_start_s": {
                base_name: base_start,
                added_name: added_start,
            },
            "alignment_sources": {
                base_name: base_audit.get("source"),
                added_name: added_audit.get("source"),
            },
            "saturation": diagnostics.get("saturation"),
            "iq_bytes": iq_path.stat().st_size,
        }
        print(
            f"BUILT_MERGED {run_name} N={node_count} bw={bandwidth_hz} "
            f"samples={samples.shape[0]} sat_frac="
            f"{diagnostics.get('saturation', {}).get('saturated_fraction', 0.0):.3e}",
            flush=True,
        )
    if traffic_start_map_path is not None:
        save_json(traffic_start_map_path, traffic_map)
    return {"runs": results, "traffic_start_map": traffic_map}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument(
        "--traffic-start-map",
        type=Path,
        default=DEFAULT_REPORTS / "merged_traffic_starts.json",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_merged_runs(
        args.runs,
        args.reports,
        traffic_start_map_path=args.traffic_start_map,
        force=args.force,
    )
    print(
        f"MERGED_RUNS_DONE count={len(result['runs'])} "
        f"map={args.traffic_start_map.resolve()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
