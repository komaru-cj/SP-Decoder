#!/usr/bin/env python3
"""Plan Fig. 9--12 real-collision runs and Windows PowerShell commands.

The Windows machine is an SSH orchestrator.  GNU Radio and the control B210
remain attached to the Ubuntu control host.  This planner never transmits RF;
it writes a machine-readable campaign, a CSV run sheet, and actual/dry-run
PowerShell scripts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL_DIR = ROOT / "real_collision_experiment" / "control_usrp"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from protocol import (  # noqa: E402
    DEFAULT_PHY_PROFILE_ID,
    PHY_PROFILES,
    TRAFFIC_DUTY_CYCLES,
    RunConfig,
    active_nodes_to_mask,
    expected_tx_schedule_ms,
    firmware_time_on_air_ms,
    lora_time_on_air_ms,
    phy_profile,
    recommended_receiver_sample_rate_hz,
    traffic_profile_id_from_duty,
    xorshift32,
)
from select_poisson_seeds import add_collision_orders, schedule_rows, seed_statistics  # noqa: E402


DEFAULT_SCALE_NODES = (3, 6, 9, 12, 15)
DEFAULT_SCALE_DUTY_CYCLES = (0.50, 0.75)
DEFAULT_PROXIMITY_SEPARATIONS_M = (0.02, 0.05, 0.10, 0.20, 0.30)
DEFAULT_FIG12_DUTY_CYCLE = 0.75
DEFAULT_FIG12_ROUNDS = 1
DEFAULT_RUN_ID_REVISION = 1


def parse_float_list(text: str) -> tuple[float, ...]:
    values = tuple(float(value.strip()) for value in text.split(",") if value.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def parse_int_list(text: str) -> tuple[int, ...]:
    values = tuple(int(value.strip()) for value in text.split(",") if value.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def load_slug(load: float) -> str:
    return f"g{load:g}".replace(".", "p")


def duty_slug(duty: float) -> str:
    return f"d{duty:g}".replace(".", "p")


def duty_encoding(duty: float, active_node_count: int) -> tuple[float, int]:
    """Validate a wire duty profile and return aggregate G plus CONFIG N."""
    traffic_profile_id_from_duty(duty)
    return round(float(duty) * active_node_count, 12), active_node_count


def float_text(value: float) -> str:
    return f"{value:g}"


def encode_run_id(nodes: int, duty_cycle: float, condition: int, repeat: int) -> int:
    """Encode NN/profile/condition/repeat into a readable uint32 run ID."""
    profile = traffic_profile_id_from_duty(duty_cycle)
    if not 1 <= nodes <= 15 or not 0 <= condition <= 0xFF or not 0 <= repeat <= 0xFF:
        raise ValueError("run-id components do not fit NN/profile/condition/repeat bytes")
    return (nodes << 24) | (profile << 16) | (condition << 8) | repeat


def encoded_repeat(round_index: int, revision: int) -> int:
    """Keep logical round 1 while avoiding collisions with archived run IDs."""
    if not 1 <= round_index <= 15 or not 0 <= revision <= 15:
        raise ValueError("round and run-id revision must each fit one nibble")
    return (revision << 4) | round_index


def scale_phy_profile_ids(args: argparse.Namespace) -> tuple[int, ...]:
    """Return the PHY profiles used by Fig. 9/10, preserving CLI order."""
    if args.scale_phy_profile_ids is None:
        return (args.phy_profile_id,)
    return tuple(args.scale_phy_profile_ids)


def scale_run_condition(
    *, phy_profile_id: int, duty_cycle: float, multi_phy: bool
) -> int:
    """Encode a collision-free condition byte for a scale run.

    Legacy single-PHY campaigns retain the old duty-percent byte.  In a
    multi-PHY campaign the high nibble identifies the PHY and the low nibble
    identifies the firmware traffic profile, so equal N/duty settings at two
    bandwidths cannot overwrite one another.
    """
    if not multi_phy:
        return int(round(100.0 * duty_cycle))
    return (phy_profile_id << 4) | traffic_profile_id_from_duty(duty_cycle)


def deterministic_seed(run_id: int, salt: int) -> int:
    value = xorshift32((run_id ^ salt) & 0xFFFFFFFF)
    return value if value != 0 else 1


@dataclass
class CampaignRun:
    sequence: int
    phase: str
    figure: str
    purpose: str
    run_id: int
    phy_profile_id: int
    spreading_factor: int
    bandwidth_hz: int
    active_nodes: list[int]
    offered_load: float
    traffic_profile_load: float
    firmware_active_node_count: int
    per_node_duty_cycle: float
    duration_s: float
    warmup_s: float
    node_tx_power_dbm: int
    global_seed: int
    payload_seed: int
    round_index: int | None
    layout: str
    tags: dict[str, str]
    expected_tx_count: int
    expected_aggregate_rate_pps: float
    expected_per_node_rate_pps: float
    predicted_packets_by_collision_order: dict[str, int]
    recommended_capture_s: int
    artifacts: dict[str, str]

    @property
    def run_hex(self) -> str:
        return f"0x{self.run_id:08X}"


def run_config(run: CampaignRun) -> RunConfig:
    return RunConfig(
        run_id=run.run_id,
        active_mask=active_nodes_to_mask(run.active_nodes),
        num_active_nodes=len(run.active_nodes),
        phy_profile_id=run.phy_profile_id,
        traffic_profile_id=traffic_profile_id_from_duty(run.per_node_duty_cycle),
        node_tx_power_dbm=run.node_tx_power_dbm,
        duration_ms=round(run.duration_s * 1000),
        warmup_ms=round(run.warmup_s * 1000),
        global_seed=run.global_seed,
        payload_seed=run.payload_seed,
    )


def make_run(
    *,
    sequence: int,
    phase: str,
    figure: str,
    purpose: str,
    run_id: int,
    active_nodes: list[int],
    per_node_duty_cycle: float,
    duration_s: float,
    warmup_s: float,
    node_tx_power_dbm: int,
    global_seed: int | None,
    payload_seed: int | None,
    round_index: int | None,
    layout: str,
    tags: dict[str, str],
    phy_profile_id: int,
) -> CampaignRun:
    traffic_profile_load, firmware_active_node_count = duty_encoding(
        per_node_duty_cycle, len(active_nodes)
    )
    offered_load = round(len(active_nodes) * float(per_node_duty_cycle), 12)
    data_phy = phy_profile(phy_profile_id)
    global_seed = deterministic_seed(run_id, 0xA5A55A5A) if global_seed is None else global_seed
    payload_seed = deterministic_seed(run_id, 0x13579BDF) if payload_seed is None else payload_seed
    temporary = CampaignRun(
        sequence=sequence,
        phase=phase,
        figure=figure,
        purpose=purpose,
        run_id=run_id,
        phy_profile_id=phy_profile_id,
        spreading_factor=data_phy["sf"],
        bandwidth_hz=data_phy["bandwidth_hz"],
        active_nodes=active_nodes,
        offered_load=offered_load,
        traffic_profile_load=traffic_profile_load,
        firmware_active_node_count=firmware_active_node_count,
        per_node_duty_cycle=float(per_node_duty_cycle),
        duration_s=duration_s,
        warmup_s=warmup_s,
        node_tx_power_dbm=node_tx_power_dbm,
        global_seed=global_seed & 0xFFFFFFFF,
        payload_seed=payload_seed & 0xFFFFFFFF,
        round_index=round_index,
        layout=layout,
        tags=tags,
        expected_tx_count=0,
        expected_aggregate_rate_pps=0.0,
        expected_per_node_rate_pps=0.0,
        predicted_packets_by_collision_order={},
        recommended_capture_s=0,
        artifacts={},
    )
    config = run_config(temporary)
    config.validate()
    rows = schedule_rows(config, active_nodes)
    add_collision_orders(rows)
    counts: dict[str, int] = {}
    for row in rows:
        key = str(int(row["collision_order"]))
        counts[key] = counts.get(key, 0) + 1
    expected_count = len(rows)
    run_name = f"run_{run_id:08x}"
    # The controller sends five CONFIG and five START frames before the 20 s
    # business interval.  Reserve 30 s for that lead-in, the allowed 10 s
    # cross-computer launch skew, and the tail so the business interval is not
    # truncated.  The offline receiver adds a separate 5 s capture guard.
    capture_s = math.ceil(duration_s + 30.0)
    temporary.expected_tx_count = expected_count
    temporary.expected_aggregate_rate_pps = expected_count / duration_s
    temporary.expected_per_node_rate_pps = expected_count / duration_s / len(active_nodes)
    temporary.predicted_packets_by_collision_order = counts
    temporary.recommended_capture_s = capture_s
    temporary.artifacts = {
        "control_manifest": f"control_manifests/{run_name}.json",
        "iq": f"runs/{run_name}/{run_name}.sc16",
        "iq_metadata": f"runs/{run_name}/{run_name}.sc16.json",
        "decoder_report": f"runs/{run_name}/six_methods.json",
        "field_record": f"runs/{run_name}/field_record.json",
    }
    return temporary


def top_runtime_seeds(
    *,
    count: int,
    search_count: int,
    duration_s: float,
    node_tx_power_dbm: int,
    run_id_revision: int,
) -> list[int]:
    selected: list[int] = []
    for repeat in range(1, count + 1):
        run_id = encode_run_id(
            15, 0.25, 0x0B, encoded_repeat(repeat, run_id_revision)
        )
        ranked: list[tuple[tuple[int, int, int], int]] = []
        for seed in range(1, max(search_count, count) + 1):
            config = RunConfig(
                run_id=run_id,
                active_mask=active_nodes_to_mask(list(range(1, 16))),
                num_active_nodes=15,
                phy_profile_id=DEFAULT_PHY_PROFILE_ID,
                traffic_profile_id=traffic_profile_id_from_duty(0.25),
                node_tx_power_dbm=node_tx_power_dbm,
                duration_ms=round(duration_s * 1000),
                warmup_ms=5_000,
                global_seed=seed,
                payload_seed=0x22222222,
            )
            stats = seed_statistics(config, list(range(1, 16)), {2, 4, 8})
            counts = stats["packets_by_collision_order"]
            coverage = sum(int(counts.get(str(order), 0) > 0) for order in (2, 4, 8))
            hits = sum(int(counts.get(str(order), 0)) for order in (2, 4, 8))
            minimum = min(int(counts.get(str(order), 0)) for order in (2, 4, 8))
            ranked.append(((coverage, minimum, hits), seed))
        ranked.sort(reverse=True)
        seed = next(seed for _, seed in ranked if seed not in selected)
        selected.append(seed)
    return selected


def build_campaign(args: argparse.Namespace) -> list[CampaignRun]:
    runs: list[CampaignRun] = []

    def add(**kwargs: object) -> None:
        runs.append(make_run(sequence=len(runs) + 1, **kwargs))

    aggregate_scale = False
    scale_values = args.scale_duty_cycles
    scale_phys = scale_phy_profile_ids(args)
    scale_conditions = [
        (phy_id, value, nodes, round_index)
        for phy_id in scale_phys
        for value in scale_values
        for nodes in args.scale_nodes
        for round_index in range(1, args.rounds + 1)
    ]
    # The first full-N run doubles as the one-time link gate.  Use the lowest
    # requested traffic setting so all 15 nodes are visible without making the bounded
    # prefix decode unnecessarily collision-dense.
    gate_condition = (scale_phys[0], min(scale_values), max(args.scale_nodes), 1)
    scale_conditions = [gate_condition] + [
        condition for condition in scale_conditions if condition != gate_condition
    ]
    for scale_phy_id, value, nodes, round_index in scale_conditions:
        duty = value
        profile_load, _ = duty_encoding(duty, nodes)
        data_phy = phy_profile(scale_phy_id)
        metric_group = duty_slug(duty)
        if len(scale_phys) > 1:
            metric_group += f"_bw{data_phy['bandwidth_hz'] // 1000}k"
        traffic_tags = {
            "traffic_semantics": "fixed_per_node_duty_cycle",
            "per_node_duty_cycle": float_text(duty),
            "effective_aggregate_offered_load": float_text(nodes * duty),
        }
        condition = scale_run_condition(
            phy_profile_id=scale_phy_id,
            duty_cycle=duty,
            multi_phy=len(scale_phys) > 1,
        )
        run_id = encode_run_id(
            nodes,
            duty,
            condition,
            encoded_repeat(round_index, args.run_id_revision),
        )
        add(
            phase="scale",
            figure="9,10",
            purpose="end_to_end_prr_and_throughput",
            run_id=run_id,
            active_nodes=list(range(1, nodes + 1)),
            per_node_duty_cycle=duty,
            duration_s=args.duration_s,
            warmup_s=args.warmup_s,
            node_tx_power_dbm=args.node_tx_power,
            global_seed=None,
            payload_seed=None,
            round_index=round_index,
            layout=args.scale_layout,
            tags={
                "campaign": args.campaign_id,
                "figure": "fig9_10",
                "metric_group": metric_group,
                "round": str(round_index),
                "run_id_revision": str(args.run_id_revision),
                "layout": args.scale_layout,
                "phy_profile_id": str(scale_phy_id),
                "spreading_factor": str(data_phy["sf"]),
                "bandwidth_hz": str(data_phy["bandwidth_hz"]),
                **traffic_tags,
            },
            phy_profile_id=scale_phy_id,
        )

    if args.include_fig11_air_runs:
        runtime_seeds = top_runtime_seeds(
            count=args.fig11_rounds,
            search_count=args.fig11_seed_search_count,
            duration_s=args.fig11_duration_s,
            node_tx_power_dbm=args.node_tx_power,
            run_id_revision=args.run_id_revision,
        )
        for round_index, seed in enumerate(runtime_seeds, start=1):
            run_id = encode_run_id(
                15,
                0.25,
                0x0B,
                encoded_repeat(round_index, args.run_id_revision),
            )
            add(
                phase="runtime_source",
                figure="11",
                purpose="decoder_runtime_collision_orders_2_4_8",
                run_id=run_id,
                active_nodes=list(range(1, 16)),
                per_node_duty_cycle=0.25,
                duration_s=args.fig11_duration_s,
                warmup_s=args.warmup_s,
                node_tx_power_dbm=args.node_tx_power,
                global_seed=seed,
                payload_seed=0x22222222,
                round_index=round_index,
                layout=args.scale_layout,
                tags={
                    "campaign": args.campaign_id,
                    "figure": "fig11",
                    "round": str(round_index),
                    "run_id_revision": str(args.run_id_revision),
                    "layout": args.scale_layout,
                    "target_collision_orders": "2_4_8",
                },
                phy_profile_id=args.phy_profile_id,
            )

    if len(set(args.fig12_separations_m)) != len(args.fig12_separations_m):
        raise ValueError("Fig. 12 node separations must be unique")
    for distance_index, separation in enumerate(args.fig12_separations_m, start=1):
        if separation <= 0 or args.fig12_node1_distance_m <= 0:
            raise ValueError("Fig. 12 distances must be positive")
        node2_distance = args.fig12_node1_distance_m + separation
        condition = 0xC0 + distance_index
        separation_label = ">20cm" if separation > 0.20 else f"{separation * 100:g}cm"
        common_tags = {
            "campaign": args.campaign_id,
            "figure": "fig12",
            "layout": args.fig12_layout,
            "bearing_deg": float_text(args.fig12_bearing_deg),
            "node1_distance_m": float_text(args.fig12_node1_distance_m),
            "node2_distance_m": float_text(node2_distance),
            "node_separation_m": float_text(separation),
            "node_separation_label": separation_label,
            "position_index": str(distance_index),
            "rx_antenna_spacing_m": float_text(args.fig12_rx_spacing_m),
        }
        for round_index in range(1, args.fig12_rounds + 1):
            duty = args.fig12_duty_cycle
            profile_load, _ = duty_encoding(duty, 2)
            traffic_tags = {
                "traffic_semantics": "fixed_per_node_duty_cycle",
                "per_node_duty_cycle": float_text(duty),
                "effective_aggregate_offered_load": float_text(2 * duty),
            }
            run_id = encode_run_id(
                2,
                duty,
                condition,
                encoded_repeat(round_index, args.run_id_revision),
            )
            add(
                phase="proximity_collision",
                figure="12",
                purpose="same_bearing_distance_prr",
                run_id=run_id,
                active_nodes=[1, 2],
                per_node_duty_cycle=duty,
                duration_s=args.duration_s,
                warmup_s=args.warmup_s,
                node_tx_power_dbm=args.node_tx_power,
                global_seed=None,
                payload_seed=None,
                round_index=round_index,
                layout=args.fig12_layout,
                tags={
                    **common_tags,
                    "mode": "two_node_collision",
                    "round": str(round_index),
                    "run_id_revision": str(args.run_id_revision),
                    **traffic_tags,
                    "round_semantics": "independent_replication_same_setting",
                },
                phy_profile_id=args.phy_profile_id,
            )

    run_ids = [run.run_id for run in runs]
    if len(run_ids) != len(set(run_ids)):
        raise AssertionError("campaign generated duplicate run IDs")
    return runs


def controller_arguments(run: CampaignRun, campaign_id: str, *, dry_run: bool) -> str:
    tags = " ".join(
        f"--experiment-tag '{key}={value}'" for key, value in sorted(run.tags.items())
    )
    dry = " --dry-run" if dry_run else ""
    return (
        f"--run-id {run.run_hex} "
        f"--active-nodes {','.join(str(node) for node in run.active_nodes)} "
        f"--phy-profile-id {run.phy_profile_id} "
        f"--per-node-duty-cycle {run.per_node_duty_cycle:g} "
        f"--duration-s {run.duration_s:g} --warmup-s {run.warmup_s:g} "
        f"--node-tx-power {run.node_tx_power_dbm} "
        f"--global-seed 0x{run.global_seed:08X} "
        f"--payload-seed 0x{run.payload_seed:08X} "
        f"--usrp-tx-gain $ControlTxGain "
        f"--device-args '$DeviceArgs' "
        f"--manifest-dir '$ManifestDir' {tags}{dry}"
    )


def powershell_text(
    runs: list[CampaignRun], args: argparse.Namespace, *, dry_run: bool
) -> str:
    title = "DRY RUN (no RF)" if dry_run else "REAL RF CAMPAIGN"
    lines = [
        "param(",
        f'    [string]$Controller = "{args.controller}",',
        f'    [string]$RemoteRoot = "{args.remote_root}",',
        f'    [string]$DeviceArgs = "{args.device_args}",',
        f"    [double]$ControlTxGain = {args.usrp_tx_gain:g}",
        ")",
        '$ErrorActionPreference = "Stop"',
        f'$CampaignId = "{args.campaign_id}"',
        '$ControllerScript = "$RemoteRoot/real_collision_experiment/control_usrp/usrp_run_controller.py"',
        '$ManifestDir = "$RemoteRoot/real_collision_experiment/run_manifests/$CampaignId"',
        f'Write-Host "{title}: $CampaignId ({len(runs)} runs)"',
        "",
    ]
    for script_index, run in enumerate(runs, start=1):
        run_name = f"run_{run.run_id:08x}"
        lines.extend(
            [
                f'# {run.sequence:03d}: Fig. {run.figure}; {run.purpose}',
                (
                    f'Write-Host "[{script_index}/{len(runs)}] seq={run.sequence} '
                    f'{run_name}; N={len(run.active_nodes)}; '
                    f'PHY={run.phy_profile_id} SF{run.spreading_factor}/BW{run.bandwidth_hz}; '
                    f'd={run.per_node_duty_cycle:g}; effective G={run.offered_load:g}; '
                    f'capture >= {run.recommended_capture_s}s"'
                ),
            ]
        )
        if not dry_run:
            lines.append(
                f'Read-Host "Arm RX for {run_name} first, then press Enter (Ctrl+C aborts)" | Out-Null'
            )
        arguments = controller_arguments(run, args.campaign_id, dry_run=dry_run)
        lines.extend(
            [
                f'$RemoteCommand = "python3 \'$ControllerScript\' {arguments}"',
                "ssh $Controller $RemoteCommand",
                f'if ($LASTEXITCODE -ne 0) {{ throw "Controller failed for {run_name}" }}',
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_outputs(runs: list[CampaignRun], args: argparse.Namespace) -> None:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    aggregate_scale = False
    scale_semantics = "fixed per-node duty cycle; effective aggregate offered load is N*d"
    scale_values = list(args.scale_duty_cycles)
    scale_phys = scale_phy_profile_ids(args)
    scale_phy_descriptions = [
        {
            "id": profile_id,
            **phy_profile(profile_id),
            "receiver_sample_rate_hz": recommended_receiver_sample_rate_hz(profile_id),
        }
        for profile_id in scale_phys
    ]
    traffic_semantics = {
        "scale_runs": scale_semantics,
        "scale_per_node_duty_cycles": scale_values,
        "traffic_profile_ids": {
            float_text(duty): traffic_profile_id_from_duty(duty)
            for duty in args.scale_duty_cycles
        },
        "encoding": {
            float_text(duty): {
                str(nodes): duty_encoding(duty, nodes)[0]
                for nodes in args.scale_nodes
            }
            for duty in args.scale_duty_cycles
        },
        "firmware_rule": "CONFIG numActiveNodes equals popcount(activeMask)",
    }
    campaign = {
        "schema": "sp_fig9_12_campaign_v1",
        "campaign_id": args.campaign_id,
        "run_id_revision": args.run_id_revision,
        "scale_phy_profiles": scale_phy_descriptions,
        "phy_profile": {
            "id": args.phy_profile_id,
            **phy_profile(args.phy_profile_id),
            "receiver_sample_rate_hz": recommended_receiver_sample_rate_hz(args.phy_profile_id),
        },
        "traffic_semantics": traffic_semantics,
        "decoder_mapping": {
            "standard_lorawan": "lorawan (shared SP fine sync; fixed physical Ch0 top-1 payload decisions)",
            "mrc": "mrc",
            "mrc_cic": "mrc_cic",
            "pcube": "pcube",
            "maloragw": "maloragw",
            "sp_decoder": "sp",
        },
        "fig11_timing_definition": (
            "default campaign uses offline constructed 2/4/6/8-packet collisions and needs no RF run; "
            "report per-detected-packet payload-decoder wall time with native detection/synchronization "
            "excluded, and separately report end-to-end SER using every method's native frontend with "
            "frontend misses counted as SER=1"
        ),
        "fig12_geometry": {
            "coordinate_system": "gateway midpoint is (0,0); bearing is counter-clockwise from +x",
            "bearing_deg": args.fig12_bearing_deg,
            "rx_antenna_spacing_m": args.fig12_rx_spacing_m,
            "node1_distance_m": args.fig12_node1_distance_m,
            "node_separations_m": list(args.fig12_separations_m),
            "node2_distances_m": [
                args.fig12_node1_distance_m + separation
                for separation in args.fig12_separations_m
            ],
            "schematic_only": True,
        },
        "required_transfer": [
            "control manifest JSON",
            "raw dual-channel .sc16 IQ",
            ".sc16.json capture metadata",
            "six-method decoder report JSON",
            "field record; Fig. 12 also needs photo and measured coordinates",
        ],
        "runs": [{**asdict(run), "run_id_hex": run.run_hex} for run in runs],
    }
    (args.out_dir / "campaign.json").write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    csv_fields = [
        "sequence", "phase", "figure", "purpose", "run_id_hex", "phy_profile_id",
        "spreading_factor", "bandwidth_hz", "active_nodes",
        "node_count", "per_node_duty_cycle", "offered_load",
        "traffic_profile_load", "firmware_active_node_count",
        "duration_s", "round_index", "layout",
        "global_seed_hex", "payload_seed_hex", "expected_tx_count",
        "expected_aggregate_rate_pps", "expected_per_node_rate_pps",
        "predicted_packets_by_collision_order", "recommended_capture_s",
        "control_manifest", "iq", "iq_metadata", "decoder_report", "field_record",
    ]
    with (args.out_dir / "run_sheet.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_fields)
        writer.writeheader()
        for run in runs:
            writer.writerow(
                {
                    "sequence": run.sequence,
                    "phase": run.phase,
                    "figure": run.figure,
                    "purpose": run.purpose,
                    "run_id_hex": run.run_hex,
                    "phy_profile_id": run.phy_profile_id,
                    "spreading_factor": run.spreading_factor,
                    "bandwidth_hz": run.bandwidth_hz,
                    "active_nodes": ",".join(str(node) for node in run.active_nodes),
                    "node_count": len(run.active_nodes),
                    "per_node_duty_cycle": run.per_node_duty_cycle,
                    "offered_load": run.offered_load,
                    "traffic_profile_load": run.traffic_profile_load,
                    "firmware_active_node_count": run.firmware_active_node_count,
                    "duration_s": run.duration_s,
                    "round_index": "" if run.round_index is None else run.round_index,
                    "layout": run.layout,
                    "global_seed_hex": f"0x{run.global_seed:08X}",
                    "payload_seed_hex": f"0x{run.payload_seed:08X}",
                    "expected_tx_count": run.expected_tx_count,
                    "expected_aggregate_rate_pps": f"{run.expected_aggregate_rate_pps:.6f}",
                    "expected_per_node_rate_pps": f"{run.expected_per_node_rate_pps:.6f}",
                    "predicted_packets_by_collision_order": json.dumps(
                        run.predicted_packets_by_collision_order, separators=(",", ":")
                    ),
                    "recommended_capture_s": run.recommended_capture_s,
                    **run.artifacts,
                }
            )

    index_fields = [
        "experiment", "x_value", "x_label", "report", "nodes", "offered_load",
        "seed", "power_gap_db", "weak_node", "layout", "notes",
    ]
    with (args.out_dir / "report_index_template.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=index_fields)
        writer.writeheader()
        for run in runs:
            if run.phase == "scale":
                metric_slug = (
                    load_slug(run.offered_load)
                    if aggregate_scale
                    else duty_slug(run.per_node_duty_cycle)
                )
                experiment = f"fig9_10_{metric_slug}"
                if len(scale_phys) > 1:
                    experiment += f"_bw{run.bandwidth_hz}"
                x_value = len(run.active_nodes)
                x_label = f"N={len(run.active_nodes)}"
            elif run.phase == "proximity_collision":
                experiment = "fig12_distance"
                x_value = run.tags["node_separation_m"]
                x_label = f"separation={run.tags['node_separation_m']}m"
            else:
                continue
            writer.writerow(
                {
                    "experiment": experiment,
                    "x_value": x_value,
                    "x_label": x_label,
                    "report": run.artifacts["decoder_report"],
                    "nodes": len(run.active_nodes),
                    "offered_load": run.offered_load,
                    "seed": f"0x{run.global_seed:08X}",
                    "power_gap_db": "",
                    "weak_node": 2 if run.phase == "proximity_collision" else "",
                    "layout": run.layout,
                    "notes": run.purpose,
                }
            )

    (args.out_dir / "run_campaign.ps1").write_text(
        powershell_text(runs, args, dry_run=False), encoding="utf-8"
    )
    (args.out_dir / "dry_run_campaign.ps1").write_text(
        powershell_text(runs, args, dry_run=True), encoding="utf-8"
    )
    for phase in sorted({run.phase for run in runs}):
        phase_runs = [run for run in runs if run.phase == phase]
        (args.out_dir / f"run_{phase}.ps1").write_text(
            powershell_text(phase_runs, args, dry_run=False), encoding="utf-8"
        )
        (args.out_dir / f"dry_run_{phase}.ps1").write_text(
            powershell_text(phase_runs, args, dry_run=True), encoding="utf-8"
        )

    scale_label = "per-node duty cycles"
    fig12_traffic = (
        f"per-node duty cycle d={float_text(args.fig12_duty_cycle)} "
        f"(aggregate G={float_text(2 * args.fig12_duty_cycle)})"
    )
    scale_phy_text = ", ".join(
        f"profile {item['id']} (SF{item['sf']}/BW{item['bandwidth_hz']})"
        for item in scale_phy_descriptions
    )
    scale_sample_rates = sorted(
        {int(item["receiver_sample_rate_hz"]) for item in scale_phy_descriptions}
    )
    notes = f"""# {args.campaign_id}\n\n
This plan contains {len(runs)} controller runs.  Run `dry_run_campaign.ps1` first; it
generates control manifests without a USRP.  The real script pauses before every
run so the dual-channel receiver can be armed first.\n\n
Fig. 9/10 data transmissions use {scale_phy_text}.
The profile-recommended receiver rates are {', '.join(str(value) for value in scale_sample_rates)} sample/s; the offline entry script may deliberately use one higher common rate. Fig. 9/10 use {scale_label}
{', '.join(float_text(v) for v in scale_values)}.  Traffic semantics: {scale_semantics}; the firmware
profile table contains every required G and CONFIG `numActiveNodes` always equals
the active-mask population.  Every run commands
the node radios to {args.node_tx_power:g} dBm.\n\n
Fig. 12 uses {fig12_traffic}.\n\n
For every Fig. 12 position, record the gateway antenna midpoint, both node
coordinates, antenna heights/orientations, measured bearing, tape-measured
distances, and a photograph.  Keep Node01 at {args.fig12_node1_distance_m:g} m and
place Node02 at separations
{', '.join(float_text(v) for v in args.fig12_separations_m)} m on the
same nominal {args.fig12_bearing_deg:g}-degree ray.  Treat these defaults as a
site-layout template and regenerate the campaign if the room cannot support them.\n\n
Copying only control manifests is insufficient for PRR or throughput.  Transfer
all files listed in `required_transfer` in `campaign.json`.\n"""
    (args.out_dir / "README.md").write_text(notes, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--campaign-id", default="fig9_10_fig12_phy5_d05_d075_r1_20s")
    parser.add_argument("--controller", default="control-user@CONTROL_PC_IP")
    parser.add_argument("--remote-root", default="/home/control/real_usrp_experiment")
    parser.add_argument("--device-args", default="serial=CONTROL_B210_SERIAL")
    parser.add_argument("--usrp-tx-gain", type=float, default=60.0)
    parser.add_argument("--node-tx-power", type=int, default=16)
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--warmup-s", type=float, default=2.0)
    parser.add_argument("--phy-profile-id", type=int, choices=sorted(PHY_PROFILES), default=5)
    parser.add_argument(
        "--scale-phy-profile-ids",
        type=parse_int_list,
        default=None,
        help=(
            "Comma-separated PHY profiles for Fig. 9/10; defaults to --phy-profile-id. "
            "Fig. 12 continues to use --phy-profile-id."
        ),
    )
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument(
        "--run-id-revision",
        type=int,
        default=DEFAULT_RUN_ID_REVISION,
        help="High nibble of the run-ID repeat byte; avoids archived run-ID collisions",
    )
    parser.add_argument("--scale-nodes", type=parse_int_list, default=DEFAULT_SCALE_NODES)
    parser.add_argument(
        "--scale-duty-cycles",
        type=parse_float_list,
        default=DEFAULT_SCALE_DUTY_CYCLES,
    )
    parser.add_argument(
        "--scale-offered-loads",
        type=parse_float_list,
        default=None,
        help="Deprecated and unsupported by duty-profile firmware",
    )
    parser.add_argument("--scale-layout", default="A")
    parser.add_argument("--fig11-rounds", type=int, default=3)
    parser.add_argument("--fig11-duration-s", type=float, default=20.0)
    parser.add_argument("--fig11-seed-search-count", type=int, default=500)
    parser.add_argument(
        "--include-fig11-air-runs",
        action="store_true",
        help="Also collect three N=15,G=3 RF runs; default Fig. 11 is offline only",
    )
    parser.add_argument("--fig12-layout", default="COLLINEAR_INDOOR")
    parser.add_argument("--fig12-bearing-deg", type=float, default=0.0)
    parser.add_argument("--fig12-rx-spacing-m", type=float, default=0.5)
    parser.add_argument("--fig12-node1-distance-m", type=float, default=2.0)
    parser.add_argument(
        "--fig12-separations-m",
        type=parse_float_list,
        default=DEFAULT_PROXIMITY_SEPARATIONS_M,
        help="Comma-separated Node01--Node02 separations along the same bearing",
    )
    parser.add_argument(
        "--fig12-duty-cycle",
        type=float,
        default=DEFAULT_FIG12_DUTY_CYCLE,
        help="Fixed per-node duty for every distance setting",
    )
    parser.add_argument(
        "--fig12-rounds",
        type=int,
        default=DEFAULT_FIG12_ROUNDS,
        help="Rounds per Fig. 12 position; use 0 to generate a Fig. 9/10-only campaign",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not 1 <= args.rounds <= 15:
        raise ValueError("Fig. 9/10 rounds must be in 1..15")
    if not 0 <= args.run_id_revision <= 15:
        raise ValueError("run-ID revision must be in 0..15")
    if args.include_fig11_air_runs and (
        args.fig11_rounds < 1 or args.fig11_seed_search_count < args.fig11_rounds
    ):
        raise ValueError("Fig. 11 seed search must cover every requested round")
    if args.duration_s <= 0 or args.fig11_duration_s <= 0:
        raise ValueError("durations must be positive")
    if args.fig12_rx_spacing_m <= 0:
        raise ValueError("Fig. 12 RX antenna spacing must be positive")
    if any(node not in (3, 6, 9, 12, 15) for node in args.scale_nodes):
        raise ValueError("Fig. 9/10 scale nodes must be selected from 3,6,9,12,15")
    if len(set(args.scale_nodes)) != len(args.scale_nodes):
        raise ValueError("scale node counts must be unique")
    scale_phys = scale_phy_profile_ids(args)
    if len(set(scale_phys)) != len(scale_phys):
        raise ValueError("Fig. 9/10 PHY profile IDs must be unique")
    if any(profile_id not in PHY_PROFILES for profile_id in scale_phys):
        raise ValueError(f"unknown Fig. 9/10 PHY profile; choose from {sorted(PHY_PROFILES)}")
    if args.scale_offered_loads is not None:
        raise ValueError(
            "--scale-offered-loads is incompatible with duty-profile firmware; "
            "use --scale-duty-cycles 0.25,0.5,0.75"
        )
    if len(set(args.scale_duty_cycles)) != len(args.scale_duty_cycles):
        raise ValueError("scale per-node duty cycles must be unique")
    for duty in args.scale_duty_cycles:
        for nodes in args.scale_nodes:
            duty_encoding(duty, nodes)
    if not 0 <= args.fig12_rounds <= 15:
        raise ValueError("Fig. 12 rounds must be in 0..15")
    duty_encoding(args.fig12_duty_cycle, 2)
    for text in (args.campaign_id, args.controller, args.remote_root, args.device_args):
        if "'" in text or '"' in text or "\n" in text:
            raise ValueError("campaign/SSH/path/device values may not contain quotes or newlines")


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)
    runs = build_campaign(args)
    write_outputs(runs, args)
    phases: dict[str, int] = {}
    for run in runs:
        phases[run.phase] = phases.get(run.phase, 0) + 1
    print(json.dumps({"out_dir": str(args.out_dir.resolve()), "run_count": len(runs), "by_phase": phases}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
