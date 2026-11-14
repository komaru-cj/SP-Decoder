#!/usr/bin/env python3
"""Construct Fig.13 N=18/21/24 outdoor IQ captures from real source runs.

For every SF/BW group in the outdoor campaign, this script aligns the N=15
source capture to the N=3, N=6, or N=9 source capture at traffic begin, then
sums their raw two-channel sc16 samples.  The synthesized manifest preserves
the original packet identities through per-node source configuration records.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "real_collision_experiment"
MARGIN_BEFORE_S = 1.0
BUSINESS_DURATION_S = 20.0
MARGIN_AFTER_S = 5.0
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


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_name(run_id: int) -> str:
    return f"run_{int(run_id):08x}"


def run_manifest(runs_root: Path, name: str) -> dict:
    candidates = (runs_root / name / f"{name}.json", runs_root / "manifests" / f"{name}.json")
    for path in candidates:
        if path.exists():
            return load_json(path)
    raise FileNotFoundError(f"missing controller manifest for {name}; tried {list(candidates)}")


def source_traffic_start_s(runs_root: Path, reports_root: Path, name: str) -> tuple[float, str]:
    alignment_path = reports_root / f"{name}.business_alignment.json"
    if alignment_path.exists():
        return float(load_json(alignment_path)["traffic_start_s"]), "business_alignment_audit"

    # The strict decoder may not have been run yet.  The same energy-template
    # alignment used by it is sufficient to prepare a merged capture.
    from decode_fig9_10_12_middle5s import estimate_traffic_start_from_control_energy

    iq_path = runs_root / name / f"{name}.sc16"
    metadata_path = iq_path.with_suffix(iq_path.suffix + ".json")
    traffic_start_s, _ = estimate_traffic_start_from_control_energy(
        iq_path,
        load_json(metadata_path),
        run_manifest(runs_root, name),
        analysis_duration_s=5.0,
    )
    return float(traffic_start_s), "control_energy_template"


def metadata_rate(metadata: dict) -> float:
    actual = metadata.get("actual", {})
    requested = metadata.get("requested", {})
    rate = float(actual.get("rate_hz", requested.get("sample_rate_hz", 0.0)))
    if rate <= 0.0:
        raise ValueError("capture metadata has no positive sample rate")
    return rate


def aligned_sum(
    *,
    runs_root: Path,
    sources: list[tuple[str, float]],
    rate_hz: float,
) -> tuple[np.ndarray, dict]:
    sample_count = int(round(WINDOW_DURATION_S * rate_hz))
    accumulated = np.zeros((sample_count, 4), dtype=np.int32)
    source_diagnostics: dict[str, dict] = {}
    for name, traffic_start_s in sources:
        iq_path = runs_root / name / f"{name}.sc16"
        metadata = load_json(iq_path.with_suffix(iq_path.suffix + ".json"))
        source_rate = metadata_rate(metadata)
        if abs(source_rate - rate_hz) > 1.0:
            raise ValueError(f"{name}: sample rate {source_rate:g} != {rate_hz:g}")
        available = int(metadata.get("samples_per_channel", 0))
        if available <= 0:
            raise ValueError(f"{name}: metadata has no samples_per_channel")
        raw = np.memmap(iq_path, dtype="<i2", mode="r", shape=(available, 4))
        requested_start = int(round((traffic_start_s - MARGIN_BEFORE_S) * rate_hz))
        requested_end = int(
            round((traffic_start_s + BUSINESS_DURATION_S + MARGIN_AFTER_S) * rate_hz)
        )
        source_start = max(0, requested_start)
        source_end = min(available, requested_end)
        output_start = source_start - requested_start
        output_end = output_start + max(0, source_end - source_start)
        if source_end <= source_start or output_start < 0 or output_end > sample_count:
            raise ValueError(f"{name}: 26 s traffic-relative window is unavailable")
        accumulated[output_start:output_end] += raw[source_start:source_end].astype(np.int32)
        source_diagnostics[name] = {
            "traffic_start_s": float(traffic_start_s),
            "source_samples": [source_start, source_end],
            "merged_samples": [output_start, output_end],
        }
    high = accumulated > 32767
    low = accumulated < -32768
    saturated = int(np.count_nonzero(high) + np.count_nonzero(low))
    output = np.clip(accumulated, -32768, 32767).astype("<i2")
    source_diagnostics["saturation"] = {
        "sample_component_count": saturated,
        "fraction": saturated / max(1, accumulated.size),
    }
    return output, source_diagnostics


def source_config(manifest: dict) -> dict:
    config = manifest.get("config", {})
    return {key: int(config[key]) for key in RUN_CONFIG_KEYS if key in config}


def merged_run_id(*, phy_profile_id: int, node_count: int, revision: int) -> int:
    """Reserve the high-E range for offline-only Fig.13 summed captures."""
    if not 1 <= phy_profile_id <= 15 or not 16 <= node_count <= 24 or not 0 <= revision <= 15:
        raise ValueError("invalid merged-run identifier component")
    return 0xE0000000 | (int(phy_profile_id) << 20) | (int(node_count) << 12) | (int(revision) << 8)


def merged_manifest(
    *,
    base: dict,
    added: dict,
    target_nodes: int,
    merged_id: int,
) -> dict:
    base_config = base.get("config", {})
    added_config = added.get("config", {})
    base_schedules = base.get("expected_node_schedules", {})
    added_schedules = added.get("expected_node_schedules", {})
    if not isinstance(base_schedules, dict) or not isinstance(added_schedules, dict):
        raise ValueError("source manifest has no expected_node_schedules")
    base_run_id = int(base_config["run_id"])
    added_run_id = int(added_config["run_id"])
    added_count = target_nodes - 15
    schedules: dict[str, dict] = {}
    for node_id in range(1, 16):
        row = base_schedules.get(str(node_id))
        if not isinstance(row, dict):
            raise ValueError(f"N=15 source is missing node {node_id} schedule")
        schedules[str(node_id)] = {
            **row,
            "source_run_id": base_run_id,
            "source_node_id": node_id,
            "source_config": source_config(base),
        }
    for node_id in range(1, added_count + 1):
        row = added_schedules.get(str(node_id))
        if not isinstance(row, dict):
            raise ValueError(f"added source is missing node {node_id} schedule")
        schedules[str(15 + node_id)] = {
            **row,
            "source_run_id": added_run_id,
            "source_node_id": node_id,
            "source_config": source_config(added),
        }

    config = {
        key: int(base_config[key])
        for key in RUN_CONFIG_KEYS
        if key in base_config and key not in {"run_id", "active_mask", "num_active_nodes", "global_seed", "payload_seed"}
    }
    config.update(
        {
            "run_id": int(merged_id),
            "active_mask": (1 << target_nodes) - 1,
            "num_active_nodes": int(target_nodes),
            "global_seed": (int(merged_id) ^ 0xA5A55A5A) & 0xFFFFFFFF,
            "payload_seed": (int(merged_id) ^ 0x13579BDF) & 0xFFFFFFFF,
            "merged_source_run_ids": [base_run_id, added_run_id],
        }
    )
    traffic = dict(base.get("traffic", {}))
    duty = float(traffic.get("per_node_duty_cycle", 0.25))
    traffic.update(
        {
            "firmware_active_node_count": target_nodes,
            "profile_offered_load": target_nodes * duty,
            "effective_aggregate_offered_load": target_nodes * duty,
            "per_node_duty_cycle": duty,
        }
    )
    experiment = dict(base.get("experiment", {}))
    experiment.update(
        {
            "figure": "fig13",
            "simulated_merged": True,
            "merged_method": "aligned_traffic_relative_capture_summation",
            "merged_node_count": str(target_nodes),
            "merged_source_run_names": [run_name(base_run_id), run_name(added_run_id)],
        }
    )
    output = dict(base)
    output.update(
        {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "experiment": experiment,
            "config": config,
            "active_nodes": list(range(1, target_nodes + 1)),
            "active_node_count": target_nodes,
            "traffic": traffic,
            "expected_node_schedules": schedules,
            "merged_simulation": {
                "enabled": True,
                "semantics": "sum of two independently captured real IQ recordings aligned at traffic begin",
                "source_runs": [run_name(base_run_id), run_name(added_run_id)],
            },
        }
    )
    return output


def merged_metadata(base: dict, *, name: str, directory: Path, sample_count: int, rate_hz: float, sources: list[str]) -> dict:
    output = json.loads(json.dumps(base))
    requested = dict(output.get("requested", {}))
    requested["duration_s"] = sample_count / rate_hz
    output.update(
        {
            "output_file": str(directory / f"{name}.sc16"),
            "samples_per_channel": sample_count,
            "target_samples_per_channel": sample_count,
            "file_bytes": sample_count * 4 * np.dtype("<i2").itemsize,
            "requested": requested,
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "merged_simulation": {
                "enabled": True,
                "source_runs": sources,
                "method": "aligned_traffic_relative_capture_summation",
            },
        }
    )
    return output


def campaign_source_groups(campaign: dict) -> dict[tuple[int, int, int], dict[int, dict]]:
    groups: dict[tuple[int, int, int], dict[int, dict]] = {}
    for run in campaign.get("runs", []):
        if run.get("phase") != "fig13_scale_source" or str(run.get("figure")) != "fig13":
            continue
        profile = int(run["phy_profile_id"])
        sf = int(run["spreading_factor"])
        bandwidth = int(run["bandwidth_hz"])
        node_count = len(run["active_nodes"])
        groups.setdefault((profile, sf, bandwidth), {})[node_count] = run
    return groups


def build(args: argparse.Namespace) -> dict:
    campaign = load_json(args.campaign)
    if campaign.get("schema") != "sp_fig9_12_campaign_v1":
        raise ValueError("campaign is not compatible with the offline runner schema")
    groups = campaign_source_groups(campaign)
    if not groups:
        raise ValueError("campaign contains no Fig.13 source runs")
    traffic_start_map: dict[str, float] = {}
    results: dict[str, dict] = {}
    for (profile_id, sf, bandwidth), sources_by_n in sorted(groups.items()):
        required = {3, 6, 9, 15}
        missing = sorted(required - set(sources_by_n))
        if missing:
            raise ValueError(f"PHY {profile_id} SF{sf}/BW{bandwidth}: missing source N={missing}")
        base_name = run_name(int(sources_by_n[15]["run_id"]))
        base_manifest = run_manifest(args.runs, base_name)
        base_metadata = load_json(args.runs / base_name / f"{base_name}.sc16.json")
        rate_hz = metadata_rate(base_metadata)
        for target_nodes, added_nodes in ((18, 3), (21, 6), (24, 9)):
            added_name = run_name(int(sources_by_n[added_nodes]["run_id"]))
            added_manifest = run_manifest(args.runs, added_name)
            if int(added_manifest.get("radio", {}).get("bandwidth_hz", 0)) != bandwidth:
                raise ValueError(f"{base_name}/{added_name}: bandwidth mismatch")
            if int(added_manifest.get("radio", {}).get("spreading_factor", 0)) != sf:
                raise ValueError(f"{base_name}/{added_name}: spreading-factor mismatch")
            merged_id = merged_run_id(
                phy_profile_id=profile_id,
                node_count=target_nodes,
                revision=int(campaign.get("run_id_revision", 0)),
            )
            name = run_name(merged_id)
            directory = args.runs / name
            iq_path = directory / f"{name}.sc16"
            if iq_path.exists() and not args.force:
                traffic_start_map[name] = MARGIN_BEFORE_S
                results[name] = {"status": "existing", "node_count": target_nodes}
                continue
            base_start, base_alignment = source_traffic_start_s(args.runs, args.reports, base_name)
            added_start, added_alignment = source_traffic_start_s(args.runs, args.reports, added_name)
            samples, diagnostics = aligned_sum(
                runs_root=args.runs,
                sources=[(base_name, base_start), (added_name, added_start)],
                rate_hz=rate_hz,
            )
            directory.mkdir(parents=True, exist_ok=True)
            samples.tofile(iq_path)
            save_json(
                directory / f"{name}.json",
                merged_manifest(
                    base=base_manifest,
                    added=added_manifest,
                    target_nodes=target_nodes,
                    merged_id=merged_id,
                ),
            )
            save_json(
                directory / f"{name}.sc16.json",
                merged_metadata(
                    base_metadata,
                    name=name,
                    directory=directory,
                    sample_count=samples.shape[0],
                    rate_hz=rate_hz,
                    sources=[base_name, added_name],
                ),
            )
            traffic_start_map[name] = MARGIN_BEFORE_S
            results[name] = {
                "status": "built",
                "phy_profile_id": profile_id,
                "sf": sf,
                "bandwidth_hz": bandwidth,
                "node_count": target_nodes,
                "sources": [base_name, added_name],
                "source_alignment": {base_name: base_alignment, added_name: added_alignment},
                "saturation": diagnostics["saturation"],
            }
            print(
                f"BUILT_MERGED {name} SF{sf}/BW{bandwidth} N={target_nodes} "
                f"saturation={diagnostics['saturation']['fraction']:.3e}",
                flush=True,
            )
    save_json(args.traffic_start_map, traffic_start_map)
    return {"runs": results, "traffic_start_map": traffic_start_map}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--runs", type=Path, default=EXPERIMENT / "runs_outdoor")
    parser.add_argument("--reports", type=Path, default=EXPERIMENT / "analysis/outdoor_fig13_fig15/reports")
    parser.add_argument(
        "--traffic-start-map",
        type=Path,
        default=EXPERIMENT / "analysis/outdoor_fig13_fig15/reports/merged_traffic_starts.json",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.runs = args.runs.resolve()
    args.reports = args.reports.resolve()
    result = build(args)
    print(
        f"OUTDOOR_MERGE_DONE count={len(result['runs'])} map={args.traffic_start_map.resolve()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
