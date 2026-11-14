#!/usr/bin/env python3
"""Generate the outdoor Fig. 13 and Fig. 15 RF capture campaign.

The generated campaign is consumed unchanged by the existing offline receiver
and controller runners.  Each node transmits for 20 s, while every downstream
decoder is required to use the centered formal business window.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTROL_DIR = ROOT / "real_collision_experiment" / "control_usrp"
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from protocol import (  # noqa: E402
    PHY_PROFILES,
    TRAFFIC_DUTY_CYCLES,
    RunConfig,
    active_nodes_to_mask,
    expected_tx_schedule_ms,
    phy_profile,
    recommended_receiver_sample_rate_hz,
    traffic_profile_id_from_duty,
    xorshift32,
)
from real_collision_experiment.analysis.formal_window import (  # noqa: E402
    FORMAL_ANALYSIS_DURATION_S,
)


FIG13_PHY_PROFILE_IDS = (4, 5)  # SF8/SF10, both BW250 kHz.
FIG13_CAPTURE_NODES = (3, 6, 9, 12, 15)
FIG15_B_DISTANCES_M = (20.0, 40.0, 60.0, 80.0, 100.0, 150.0, 200.0)
FIG13_PER_NODE_DUTY_CYCLE = 0.25
FIG15_PER_NODE_DUTY_CYCLE = 0.75
BUSINESS_DURATION_S = 20.0
MIDDLE_DECODE_DURATION_S = FORMAL_ANALYSIS_DURATION_S
RECOMMENDED_CAPTURE_S = 50
RX_CAPTURE_GUARD_S = 5
DEFAULT_SLOT_S = 75.0
DEFAULT_POSITION_PAUSE_S = 30.0


def encoded_repeat(round_index: int, revision: int) -> int:
    if not 1 <= round_index <= 15 or not 0 <= revision <= 15:
        raise ValueError("round and revision must fit one nibble each")
    return (revision << 4) | round_index


def encode_run_id(
    nodes: int,
    condition: int,
    revision: int,
    per_node_duty_cycle: float,
) -> int:
    profile = traffic_profile_id_from_duty(per_node_duty_cycle)
    if not 1 <= nodes <= 15 or not 0 <= condition <= 0xFF:
        raise ValueError("run-ID node count or condition is out of range")
    return (nodes << 24) | (profile << 16) | (condition << 8) | encoded_repeat(1, revision)


def deterministic_seed(run_id: int, salt: int) -> int:
    value = xorshift32((int(run_id) ^ int(salt)) & 0xFFFFFFFF)
    return value if value else 1


def text(value: float) -> str:
    return f"{float(value):g}"


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
    round_index: int
    layout: str
    tags: dict[str, str]
    expected_tx_count: int
    expected_aggregate_rate_pps: float
    expected_per_node_rate_pps: float
    recommended_capture_s: int
    artifacts: dict[str, str]

    @property
    def run_hex(self) -> str:
        return f"0x{self.run_id:08X}"


def make_run(
    *,
    sequence: int,
    phase: str,
    figure: str,
    purpose: str,
    run_id: int,
    active_nodes: list[int],
    per_node_duty_cycle: float,
    phy_profile_id: int,
    node_tx_power_dbm: int,
    layout: str,
    tags: dict[str, str],
) -> CampaignRun:
    config = RunConfig(
        run_id=run_id,
        active_mask=active_nodes_to_mask(active_nodes),
        num_active_nodes=len(active_nodes),
        phy_profile_id=phy_profile_id,
        traffic_profile_id=traffic_profile_id_from_duty(per_node_duty_cycle),
        node_tx_power_dbm=node_tx_power_dbm,
        duration_ms=round(BUSINESS_DURATION_S * 1000),
        warmup_ms=2_000,
        global_seed=deterministic_seed(run_id, 0xA5A55A5A),
        payload_seed=deterministic_seed(run_id, 0x13579BDF),
    )
    config.validate()
    profile = phy_profile(phy_profile_id)
    schedules = [expected_tx_schedule_ms(config, node_id) for node_id in active_nodes]
    expected_count = sum(len(row) for row in schedules)
    name = f"run_{run_id:08x}"
    return CampaignRun(
        sequence=sequence,
        phase=phase,
        figure=figure,
        purpose=purpose,
        run_id=run_id,
        phy_profile_id=phy_profile_id,
        spreading_factor=int(profile["sf"]),
        bandwidth_hz=int(profile["bandwidth_hz"]),
        active_nodes=list(active_nodes),
        offered_load=float(config.offered_load),
        traffic_profile_load=float(config.offered_load),
        firmware_active_node_count=len(active_nodes),
        per_node_duty_cycle=per_node_duty_cycle,
        duration_s=BUSINESS_DURATION_S,
        warmup_s=2.0,
        node_tx_power_dbm=node_tx_power_dbm,
        global_seed=int(config.global_seed),
        payload_seed=int(config.payload_seed),
        round_index=1,
        layout=layout,
        tags=dict(tags),
        expected_tx_count=expected_count,
        expected_aggregate_rate_pps=expected_count / BUSINESS_DURATION_S,
        expected_per_node_rate_pps=expected_count / BUSINESS_DURATION_S / len(active_nodes),
        recommended_capture_s=RECOMMENDED_CAPTURE_S,
        artifacts={
            "control_manifest": f"run_manifests/{name}.json",
            "iq": f"runs/{name}/{name}.sc16",
            "iq_metadata": f"runs/{name}/{name}.sc16.json",
            "decoder_report": f"reports/{name}.json",
            "field_record": f"runs/{name}/field_record.json",
        },
    )


def build_campaign(args: argparse.Namespace) -> list[CampaignRun]:
    runs: list[CampaignRun] = []

    def add(**kwargs: object) -> None:
        runs.append(make_run(sequence=len(runs) + 1, **kwargs))

    for profile_id in args.fig13_phy_profile_ids:
        profile = phy_profile(profile_id)
        merge_group = f"sf{profile['sf']}_bw{profile['bandwidth_hz'] // 1000}k"
        for node_count in args.fig13_nodes:
            # In multi-PHY scale campaigns, the high condition nibble denotes PHY;
            # the low nibble denotes the fixed 25% traffic profile.
            condition = (int(profile_id) << 4) | traffic_profile_id_from_duty(
                FIG13_PER_NODE_DUTY_CYCLE
            )
            run_id = encode_run_id(
                node_count,
                condition,
                args.run_id_revision,
                FIG13_PER_NODE_DUTY_CYCLE,
            )
            add(
                phase="fig13_scale_source",
                figure="fig13",
                purpose="outdoor_decoder_prr_by_sf_source_capture",
                run_id=run_id,
                active_nodes=list(range(1, node_count + 1)),
                per_node_duty_cycle=FIG13_PER_NODE_DUTY_CYCLE,
                phy_profile_id=profile_id,
                node_tx_power_dbm=args.node_tx_power,
                layout=args.fig13_layout,
                tags={
                    "campaign": args.campaign_id,
                    "figure": "fig13",
                    "metric": "decoder_prr_by_sf",
                    "merge_group": merge_group,
                    "merge_source": "true",
                    "spreading_factor": str(profile["sf"]),
                    "bandwidth_hz": str(profile["bandwidth_hz"]),
                    "physical_node_count": str(node_count),
                    "per_node_duty_cycle": text(FIG13_PER_NODE_DUTY_CYCLE),
                    "business_duration_s": text(BUSINESS_DURATION_S),
                    "decode_window": f"middle_{MIDDLE_DECODE_DURATION_S:g}s",
                    "layout": args.fig13_layout,
                },
            )

    for position_index, distance_m in enumerate(args.fig15_b_distances_m, start=1):
        for mode_index, (mode, active_nodes, purpose) in enumerate(
            (
                ("ab_simultaneous", [1, 2], "near_far_ab_simultaneous_prr"),
                ("b_only", [2], "near_far_b_only_baseline_prr"),
            )
        ):
            condition = 0xD0 + 2 * (position_index - 1) + mode_index
            run_id = encode_run_id(
                len(active_nodes),
                condition,
                args.run_id_revision,
                args.fig15_per_node_duty_cycle,
            )
            add(
                phase="fig15_near_far",
                figure="fig15",
                purpose=purpose,
                run_id=run_id,
                active_nodes=active_nodes,
                per_node_duty_cycle=args.fig15_per_node_duty_cycle,
                phy_profile_id=args.fig15_phy_profile_id,
                node_tx_power_dbm=args.node_tx_power,
                layout=args.fig15_layout,
                tags={
                    "campaign": args.campaign_id,
                    "figure": "fig15",
                    "metric": "near_far_prr",
                    "position_index": str(position_index),
                    "node_a_distance_m": text(args.node_a_distance_m),
                    "node_b_distance_m": text(distance_m),
                    "mode": mode,
                    "per_node_duty_cycle": text(args.fig15_per_node_duty_cycle),
                    "business_duration_s": text(BUSINESS_DURATION_S),
                    "decode_window": "middle_5s",
                    "layout": args.fig15_layout,
                },
            )

    run_ids = [run.run_id for run in runs]
    if len(run_ids) != len(set(run_ids)):
        raise AssertionError("campaign generated duplicate run IDs")
    return runs


def campaign_payload(runs: list[CampaignRun], args: argparse.Namespace) -> dict:
    return {
        # Keep the established schema for the existing offline runners.
        "schema": "sp_fig9_12_campaign_v1",
        "campaign_id": args.campaign_id,
        "run_id_revision": args.run_id_revision,
        "experiment_scope": {
            "environment": "outdoor",
            "fig13": {
                "sf_values": [phy_profile(profile_id)["sf"] for profile_id in args.fig13_phy_profile_ids],
                "bandwidth_hz": 250_000,
                "physical_node_counts": list(args.fig13_nodes),
                "per_node_duty_cycle": FIG13_PER_NODE_DUTY_CYCLE,
                "synthetic_node_counts": [18, 21, 24],
                "merge_definition": (
                    "aligned summation of an N=15 real capture and an independently "
                    "recorded N=3/6/9 real capture from the same PHY"
                ),
            },
            "fig14": {
                "source": "physical Fig.13 SF8/BW250 N=3 source report",
                "snr_bins_db": ["<-30", "[-30,-10)", "[-10,10)", ">=10"],
                "noise_definition": "added complex Gaussian noise with source measured two-RX covariance",
            },
            "fig15": {
                "node_a_distance_m": args.node_a_distance_m,
                "node_b_distances_m": list(args.fig15_b_distances_m),
                "modes": ["ab_simultaneous", "b_only"],
                "active_nodes_by_mode": {
                    "ab_simultaneous": [1, 2],
                    "b_only": [2],
                },
                "per_node_duty_cycle": args.fig15_per_node_duty_cycle,
                "position_pause_s": args.position_pause_s,
            },
            "business_duration_s": BUSINESS_DURATION_S,
            "formal_decode_window": (
                f"[traffic_start + {(BUSINESS_DURATION_S - MIDDLE_DECODE_DURATION_S) / 2:g} s, "
                f"traffic_start + {(BUSINESS_DURATION_S + MIDDLE_DECODE_DURATION_S) / 2:g} s]"
            ),
        },
        "decoder_mapping": {
            "lorawan": "LoRaWAN Ch0 baseline",
            "mrc": "two-RX MRC",
            "mrc_cic": "MRC+CIC",
            "pcube": "PCube",
            "maloragw": "MaLoRaGW",
            "sp": "SP decoder",
        },
        "required_transfer": [
            "control manifest JSON",
            "raw dual-channel .sc16 IQ",
            ".sc16.json capture metadata",
            "field record with coordinates, antenna heights, orientation, and weather/site notes",
        ],
        "runs": [{**asdict(run), "run_id_hex": run.run_hex} for run in runs],
    }


def write_run_sheet(runs: list[CampaignRun], destination: Path) -> None:
    fields = [
        "sequence", "phase", "figure", "purpose", "run_id_hex", "phy_profile_id",
        "spreading_factor", "bandwidth_hz", "active_nodes", "node_count",
        "per_node_duty_cycle", "offered_load", "duration_s", "warmup_s",
        "expected_tx_count", "recommended_capture_s", "layout", "tags",
        "control_manifest", "iq", "iq_metadata", "decoder_report", "field_record",
    ]
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
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
                    "active_nodes": ",".join(map(str, run.active_nodes)),
                    "node_count": len(run.active_nodes),
                    "per_node_duty_cycle": run.per_node_duty_cycle,
                    "offered_load": run.offered_load,
                    "duration_s": run.duration_s,
                    "warmup_s": run.warmup_s,
                    "expected_tx_count": run.expected_tx_count,
                    "recommended_capture_s": run.recommended_capture_s,
                    "layout": run.layout,
                    "tags": json.dumps(run.tags, ensure_ascii=False, separators=(",", ":")),
                    **run.artifacts,
                }
            )


def bash_runner_text(
    *,
    label: str,
    start_sequence: int,
    end_sequence: int,
    args: argparse.Namespace,
) -> str:
    return f'''#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${{BASH_SOURCE[0]}}")" && pwd)"
repo_root="${{REPO_ROOT:-$(cd -- "$script_dir/../../../.." && pwd)}}"
campaign="$script_dir/campaign.json"
runs_root="${{RUNS_ROOT:-$repo_root/real_collision_experiment/runs_outdoor}}"

python3 "$repo_root/real_collision_experiment/automation/offline_receiver_campaign.py" \\
  --campaign "$campaign" \\
  --repo-root "$repo_root" \\
  --runs-root "$runs_root" \\
  --start-sequence {start_sequence} \\
  --end-sequence {end_sequence} \\
  --slot-s {args.slot_s:g} \\
  --position-pause-s {args.position_pause_s:g} \\
  --capture-guard-s {RX_CAPTURE_GUARD_S:g} \\
  --rx-gain {args.rx_gain:g} \\
  --sample-rate 750000 \\
  --continue-on-run-error \\
  --no-decode-first
'''


def powershell_runner_text(
    *,
    label: str,
    start_sequence: int,
    end_sequence: int,
    args: argparse.Namespace,
) -> str:
    return f'''param(
    [string]$PythonExecutable = "python",
    [double]$ControlTxGain = {args.control_tx_gain:g}
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\\..\\..\\..")).Path
$Campaign = Join-Path $ScriptDir "campaign.json"
$ManifestDir = Join-Path $RepoRoot "real_collision_experiment\\run_manifests\\{args.campaign_id}_offline"
$Controller = Join-Path $RepoRoot "real_collision_experiment\\automation\\offline_controller_campaign.py"

& $PythonExecutable $Controller `
    --campaign $Campaign `
    --repo-root $RepoRoot `
    --manifest-dir $ManifestDir `
    --start-sequence {start_sequence} `
    --end-sequence {end_sequence} `
    --slot-s {args.slot_s:g} `
    --position-pause-s {args.position_pause_s:g} `
    --pre-config-delay-s 5 `
    --continue-on-run-error `
    --control-tx-gain $ControlTxGain
if ($LASTEXITCODE -ne 0) {{
    throw "Offline {label} controller campaign failed with exit code $LASTEXITCODE"
}}
'''


def readme_text(runs: list[CampaignRun], args: argparse.Namespace) -> str:
    fig13_count = sum(run.figure == "fig13" for run in runs)
    fig15_count = sum(run.figure == "fig15" for run in runs)
    return f'''# {args.campaign_id}

Outdoor capture plan: {fig13_count} Fig.13 source runs and {fig15_count} Fig.15 runs. Every
node sends business traffic for 20 s. Fig.13 uses 25% per-node duty, while Fig.15
uses {args.fig15_per_node_duty_cycle * 100:g}% per-node duty. A capture requests 50 s and the RX runner adds a 5 s guard. Formal decoding uses only the traffic-relative
middle {MIDDLE_DECODE_DURATION_S:g} s: `[traffic_start + {(BUSINESS_DURATION_S - MIDDLE_DECODE_DURATION_S) / 2:g} s, traffic_start + {(BUSINESS_DURATION_S + MIDDLE_DECODE_DURATION_S) / 2:g} s]`.

## Fig.13

Physical source captures use SF=8/10/12, BW=250 kHz (PHY profiles 4/5/6), and
N=3/6/9/12/15. The later N=18/21/24 points are not RF runs: for each PHY, merge
the aligned N=15 capture with N=3/6/9 respectively. This preserves real waveforms,
channels, CFOs and noise while correctly recording source packet identities.

## Fig.15

Node A is fixed at {args.node_a_distance_m:g} m from the gateway. Node B positions are
{', '.join(text(value) for value in args.fig15_b_distances_m)} m. The provided distance list has
{len(args.fig15_b_distances_m)} positions, so this plan uses those seven positions. At every position it
first captures `ab_simultaneous`, then `b_only`; both runs share the same position index.
`ab_simultaneous` activates Node01 and Node02 (`active_nodes=[1,2]`), whereas `b_only`
activates only Node02 (`active_nodes=[2]`). Thus the seven positions produce 14 runs.
There is a {args.position_pause_s:g} s `POSITION_BREAK` only before the next position, not between
the two modes at one position.

## Capture

On the Ubuntu RX machine, start the matching script first. Start the Windows control
script when RX prints its start prompt, within 10 s.

```bash
bash run_fig13_receiver.sh
bash run_fig15_receiver.sh
```

```powershell
& .\\run_fig13_controller.ps1 -PythonExecutable "D:\\mysoft2\\radioconda\\python.exe" -ControlTxGain {args.control_tx_gain:g}
& .\\run_fig15_controller.ps1 -PythonExecutable "D:\\mysoft2\\radioconda\\python.exe" -ControlTxGain {args.control_tx_gain:g}
```

The shared slot is {args.slot_s:g} s. Both runners record failures and retain the fixed schedule;
rerun only listed failed run IDs with a new output directory/manifest label.

## Strict Decode And Merge

After copying controller manifests beside their matching IQ directories, use this
order for every formal PRR source: strict-window alignment, v2 fine-sync database
construction and audit, then formal decode. D is the certified anonymous physical
candidate set; all Fig.13--15 PRR values are `CRC-valid decoded candidates / D`.
The detector never receives packet schedules, node IDs, or sequences. Replace
`RUNS_ROOT` when the RX data are
stored outside the default path.

```bash
RUNS_ROOT="$PWD/real_collision_experiment/runs_outdoor"
REPORTS="$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15/reports"
python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s {MIDDLE_DECODE_DURATION_S:g} \\
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 --alignment-only

python3 real_collision_experiment/analysis/build_fine_sync_database.py \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" \\
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \\
  --out-dir "$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15"

for database in "$PWD"/real_collision_experiment/analysis/outdoor_fig13_fig15/fine_sync/run_*.json; do
  python3 real_collision_experiment/analysis/audit_fine_sync_database.py "$database" || exit 1
done

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s {MIDDLE_DECODE_DURATION_S:g} \\
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10

python3 real_collision_experiment/analysis/merge_outdoor_scale_runs.py \\
  --campaign "$PWD/real_collision_experiment/paper_experiments/generated/{args.campaign_id}/campaign.json" \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" \\
  --traffic-start-map "$REPORTS/merged_traffic_starts.json"

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s {MIDDLE_DECODE_DURATION_S:g} \\
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \\
  --traffic-start-map "$REPORTS/merged_traffic_starts.json" \\
  --alignment-only --overwrite

python3 real_collision_experiment/analysis/build_fine_sync_database.py \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" \\
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \\
  --out-dir "$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15" \\
  --run-id e0412600 --run-id e0415600 --run-id e0418600 \\
  --run-id e0512600 --run-id e0515600 --run-id e0518600 \\
  --run-id e0612600 --run-id e0615600 --run-id e0618600

for database in "$PWD"/real_collision_experiment/analysis/outdoor_fig13_fig15/fine_sync/run_e*.json; do
  python3 real_collision_experiment/analysis/audit_fine_sync_database.py "$database" || exit 1
done

python3 real_collision_experiment/analysis/decode_fig9_10_12_middle10s.py \\
  --runs "$RUNS_ROOT" --reports "$REPORTS" --duration-s {MIDDLE_DECODE_DURATION_S:g} \\
  --include-figure fig13 --spreading-factor 8 --spreading-factor 10 \\
  --traffic-start-map "$REPORTS/merged_traffic_starts.json" \\
  --overwrite \\
  --run-id e0412600 --run-id e0415600 --run-id e0418600 \\
  --run-id e0512600 --run-id e0515600 --run-id e0518600 \\
  --run-id e0612600 --run-id e0615600 --run-id e0618600
```

Decode Fig.15 separately with the same three phases: run the driver with
`--include-figure fig15 --alignment-only`, build/audit its v2 databases, then rerun
without `--alignment-only`. Since CRC-failed anonymous candidates have no valid node
identity, Fig.15 reports `ab_simultaneous` and `b_only` traffic-mode PRR rather than
inventing per-node D subsets.

## Fig.14 AWGN

Fig.14 uses only the physical Fig.13 SF8/BW250 N=3 source report. The driver reads
its certified v2 fine-sync database, adds covariance-matched noise, and accepts
points by measured median preamble-SNR bin: `<-30`, `[-30,-10)`, `[-10,10)`, or
`>=10` dB. It is a decoder PRR measurement on fixed shared D targets, not a
low-SNR detector-recall result. Existing v2 AWGN caches are rejected; pass
`--overwrite` when rebuilding.

```bash
python3 real_collision_experiment/node01_sp_receiver/run_fig14_snr_sweep.py \\
  --reports "$REPORTS" \\
  --out-dir "$PWD/real_collision_experiment/analysis/outdoor_fig13_fig15/fig14_awgn" \\
  --overwrite
```
'''


def write_outputs(runs: list[CampaignRun], args: argparse.Namespace) -> None:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = campaign_payload(runs, args)
    (args.out_dir / "campaign.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_run_sheet(runs, args.out_dir / "run_sheet.csv")
    fig13_end = sum(run.figure == "fig13" for run in runs)
    fig15_start = fig13_end + 1
    fig15_end = len(runs)
    (args.out_dir / "run_fig13_receiver.sh").write_text(
        bash_runner_text(
            label="Fig.13", start_sequence=1, end_sequence=fig13_end, args=args
        ),
        encoding="utf-8",
    )
    (args.out_dir / "run_fig15_receiver.sh").write_text(
        bash_runner_text(
            label="Fig.15", start_sequence=fig15_start, end_sequence=fig15_end, args=args
        ),
        encoding="utf-8",
    )
    (args.out_dir / "run_fig13_controller.ps1").write_text(
        powershell_runner_text(
            label="Fig.13", start_sequence=1, end_sequence=fig13_end, args=args
        ),
        encoding="utf-8",
    )
    (args.out_dir / "run_fig15_controller.ps1").write_text(
        powershell_runner_text(
            label="Fig.15", start_sequence=fig15_start, end_sequence=fig15_end, args=args
        ),
        encoding="utf-8",
    )
    (args.out_dir / "README.md").write_text(readme_text(runs, args), encoding="utf-8")


def parse_int_list(value: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return values


def parse_float_list(value: str) -> tuple[float, ...]:
    values = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one number is required")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--campaign-id", default="fig13_fig15_outdoor_sf8_sf10_sf12_bw250_d025_r6_20s"
    )
    parser.add_argument("--run-id-revision", type=int, default=6)
    parser.add_argument("--node-tx-power", type=int, default=16)
    parser.add_argument("--control-tx-gain", type=float, default=60.0)
    parser.add_argument("--rx-gain", type=float, default=60.0)
    parser.add_argument("--slot-s", type=float, default=DEFAULT_SLOT_S)
    parser.add_argument("--position-pause-s", type=float, default=DEFAULT_POSITION_PAUSE_S)
    parser.add_argument("--fig13-phy-profile-ids", type=parse_int_list, default=FIG13_PHY_PROFILE_IDS)
    parser.add_argument("--fig13-nodes", type=parse_int_list, default=FIG13_CAPTURE_NODES)
    parser.add_argument("--fig13-layout", default="OUTDOOR_SCALE")
    parser.add_argument("--fig15-phy-profile-id", type=int, default=6)
    parser.add_argument(
        "--fig15-per-node-duty-cycle",
        type=float,
        choices=TRAFFIC_DUTY_CYCLES,
        default=FIG15_PER_NODE_DUTY_CYCLE,
    )
    parser.add_argument("--fig15-layout", default="OUTDOOR_NEAR_FAR")
    parser.add_argument("--node-a-distance-m", type=float, default=80.0)
    parser.add_argument("--fig15-b-distances-m", type=parse_float_list, default=FIG15_B_DISTANCES_M)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not 0 <= args.run_id_revision <= 15:
        raise ValueError("--run-id-revision must be in 0..15")
    if args.node_tx_power < -4 or args.node_tx_power > 20:
        raise ValueError("--node-tx-power must be in -4..20 dBm")
    if args.slot_s < RECOMMENDED_CAPTURE_S + RX_CAPTURE_GUARD_S + 10.0:
        raise ValueError("--slot-s needs at least 10 s beyond 50 s capture plus 5 s guard")
    if args.position_pause_s < 30.0:
        raise ValueError("--position-pause-s must be at least 30 s for Fig.15")
    if tuple(args.fig13_phy_profile_ids) != FIG13_PHY_PROFILE_IDS:
        raise ValueError("Fig.13 requires PHY profiles 4,5: SF8/SF10 at BW250 kHz")
    if tuple(args.fig13_nodes) != FIG13_CAPTURE_NODES:
        raise ValueError("Fig.13 source captures must be N=3,6,9,12,15")
    if args.fig15_phy_profile_id != 6:
        raise ValueError("Fig.15 requires PHY profile 6: SF12/BW250 kHz")
    if any(profile_id not in PHY_PROFILES for profile_id in args.fig13_phy_profile_ids):
        raise ValueError("unknown Fig.13 PHY profile")
    if args.node_a_distance_m <= 0.0 or any(value <= 0.0 for value in args.fig15_b_distances_m):
        raise ValueError("all gateway distances must be positive")
    if len(set(args.fig15_b_distances_m)) != len(args.fig15_b_distances_m):
        raise ValueError("Fig.15 B distances must be unique")
    for value in (args.campaign_id, args.fig13_layout, args.fig15_layout):
        if not value or any(character in value for character in "\r\n\"'"):
            raise ValueError("campaign and layout values may not be empty or contain quotes/newlines")


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)
    runs = build_campaign(args)
    write_outputs(runs, args)
    by_figure: dict[str, int] = {}
    for run in runs:
        by_figure[run.figure] = by_figure.get(run.figure, 0) + 1
    print(
        json.dumps(
            {
                "out_dir": str(args.out_dir.resolve()),
                "run_count": len(runs),
                "by_figure": by_figure,
                "fig15_position_count": len(args.fig15_b_distances_m),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
