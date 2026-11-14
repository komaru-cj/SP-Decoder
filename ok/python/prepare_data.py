#!/usr/bin/env python3
"""Create local CSV-only inputs for every separated figure panel.

The source project stores some sidecars as JSON.  This preparer is the one
place where those JSON sidecars and measured-packet files are read; all panel
scripts subsequently read only ``ok/python/data/*.csv``.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data"
MECH = ROOT / "real_usrp_outputs/sp_v2_mechanism_figures"


def write_csv(name: str, fieldnames: list[str], values: list[dict]) -> None:
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(values)


def copy_csv(source: Path, name: str) -> None:
    shutil.copyfile(source, DATA / name)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def export_fig2a_and_fig2b() -> None:
    """Rebuild the 3 source spectra once and export editable numeric rows."""

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    source = load_module("ok_preliminary", ROOT / "generate_sp_preliminary_figures.py")
    packets, _ = source.load_extracted(source.CLEAN_PATH)
    cfg = source.LoRaConfig()
    refs = source.build_references(source.CLEAN_PATH, list(range(len(packets))), cfg)
    # Keep just the best two-packet record.  Retaining every 1024-bin spectrum
    # would consume hundreds of MB although Fig.2(a) needs only one example.
    seed_example: dict | None = None
    for target, interferer, _rho in source.choose_pairs_by_rho(refs, max_per_bin=4):
        for sir_db in (-5.0, -4.0, -3.0, -2.0, -1.0, 0.0):
            for offset in (0.0, 0.1, 0.25, 0.5, 0.9):
                for row in source.symbol_records_for_case(
                    packets, refs, cfg, target, interferer, offset, sir_db
                ):
                    if not row["mrc_error"]:
                        continue
                    support = row["support"]
                    contradiction = row["contradiction"]
                    truth = int(row["truth"])
                    for lam_value in np.linspace(0.05, 4.0, 80):
                        signed_value = support - float(lam_value) * contradiction
                        if int(np.argmax(signed_value)) != truth:
                            continue
                        margin_value = float(
                            signed_value[truth]
                            - np.max(np.delete(signed_value, truth))
                        )
                        score = margin_value * max(
                            float(row["eta_wrong"] - row["eta_truth"]), 0.0
                        )
                        if seed_example is None or score > seed_example["example_score"]:
                            seed_example = dict(row)
                            seed_example["lambda"] = float(lam_value)
                            seed_example["example_score"] = score
                        break
    if seed_example is None:
        raise RuntimeError("could not reconstruct the Fig.2(a) seed example")
    example = source.find_fig1_multinode_example(
        packets, refs, cfg, seed_example
    )
    support = np.asarray(example["support"], dtype=float)
    contradiction = np.asarray(example["contradiction"], dtype=float)
    lam = float(example["lambda"])
    signed = support - lam * contradiction
    wrong = int(example["mrc_peak"])
    truth = int(example["truth"])
    margin = signed[truth] - signed[wrong]
    support_db = source.relative_db(support)
    contradiction_db = source.relative_db(contradiction)
    normalized = (signed - signed[wrong]) / max(abs(margin), 1e-18)
    write_csv(
        "fig2a_spectra.csv",
        ["fft_bin", "target_spectrum_db", "orthogonal_spectrum_db", "signed_margin", "truth_bin", "wrong_bin", "lambda"],
        [
            {
                "fft_bin": index,
                "target_spectrum_db": value_a,
                "orthogonal_spectrum_db": value_b,
                "signed_margin": value_c,
                "truth_bin": truth,
                "wrong_bin": wrong,
                "lambda": lam,
            }
            for index, (value_a, value_b, value_c) in enumerate(
                zip(support_db, contradiction_db, normalized)
            )
        ],
    )

    compact = json.loads((ROOT / "real_usrp_outputs/sp_paper_figures/preliminary_records.json").read_text())
    errors = [
        {"group": "target bin", "eta": row["eta_truth"]}
        for row in compact
        if row["mrc_error"]
    ] + [
        {"group": "MRC wrong bin", "eta": row["eta_wrong"]}
        for row in compact
        if row["mrc_error"]
    ]
    write_csv("fig2b_spatial_inconsistency.csv", ["group", "eta"], errors)


def export_fig2d() -> None:
    copy_csv(MECH / "fig2d_competition_lower_bound_heatmap.csv", "fig2d_lower_heatmap.csv")
    copy_csv(MECH / "fig2d_target_reliability_upper_bound_heatmap.csv", "fig2d_upper_heatmap.csv")
    summary = json.loads((MECH / "fig2d_controlled_usable_interval_summary.json").read_text())
    lower = summary["lower_bound_condition"]
    upper = summary["upper_bound_condition"]
    write_csv(
        "fig2d_lower_boundary.csv",
        ["sir_db", "lambda_low"],
        [
            {"sir_db": row["sir_db"], "lambda_low": row["lambda_low"]}
            for row in lower["boundary_rows"]
        ],
    )
    write_csv(
        "fig2d_upper_boundary.csv",
        ["theta_u_deg", "lambda_high"],
        [
            {"theta_u_deg": row["theta_u_deg"], "lambda_high": row["lambda_high"]}
            for row in upper["boundary_rows"]
        ],
    )


def pair_risk(row: dict, lambdas: np.ndarray) -> np.ndarray:
    return (
        float(row["A_under"]) + lambdas * float(row["B_under"])
    ) / np.sqrt(
        np.maximum(float(row["C0"]) + lambdas**2 * float(row["C2"]), 1e-30)
    )


def export_fig5() -> None:
    """Regenerate the missing Fig.5 sidecar from its measured packet corpus."""

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    source = load_module(
        "ok_mechanism", ROOT / "real_collision_experiment/paper_experiments/generate_sp_v2_mechanism_figures.py"
    )
    stage = DATA / ".fig5_stage"
    stage.mkdir(exist_ok=True)
    spec = source.figure5_ten_competitor_risk(
        source.measured_context(ROOT / "real_usrp_outputs/clean_pos_packets.npz"),
        stage,
        gamma=0.05,
        lambda_max=4.0,
    )
    labels = spec["source_labels_target_first"]
    starts = spec["timeline_starts_symbols"]
    write_csv(
        "fig5_timeline.csv",
        ["packet_index", "source_label", "start_symbols", "is_target"],
        [
            {
                "packet_index": index,
                "source_label": label,
                "start_symbols": start,
                "is_target": int(index == spec["target_packet_index"]),
            }
            for index, (label, start) in enumerate(zip(labels, starts))
        ],
    )
    grid = np.linspace(0.0, float(spec["lambda_cap"]), 241)
    matrix = np.vstack([pair_risk(row, grid) for row in spec["pair_rows"]])
    active = np.argmin(matrix, axis=0)
    write_csv(
        "fig5_pair_risk.csv",
        ["lambda", "pair_index", "risk", "active_worst"],
        [
            {"lambda": lam, "pair_index": pair, "risk": matrix[pair, col], "active_worst": int(pair == active[col])}
            for col, lam in enumerate(grid)
            for pair in range(matrix.shape[0])
        ],
    )
    write_csv(
        "fig5_meta.csv",
        ["frame_symbols", "payload_start_symbols", "lambda_cap", "selected_lambda"],
        [{key: spec[key] for key in ("frame_symbols", "payload_start_symbols", "lambda_cap", "selected_lambda")}],
    )
    # ``figure5_ten_competitor_risk`` writes its historical JSON sidecar as a
    # by-product.  The local redraw project intentionally retains CSV only.
    shutil.rmtree(stage)


def export_fig7() -> None:
    config = json.loads((MECH / "fig7_configuration.json").read_text())
    scene = config["scene_record"]
    grid = np.linspace(0.0, float(scene["lambda_cap"]), 401)
    matrix = np.vstack([pair_risk(row, grid) for row in config["pair_rows"]])
    write_csv(
        "fig7_pair_curves.csv",
        ["lambda", "pair_index", "risk", "envelope"],
        [
            {"lambda": lam, "pair_index": pair, "risk": matrix[pair, col], "envelope": float(np.min(matrix[:, col]))}
            for col, lam in enumerate(grid)
            for pair in range(matrix.shape[0])
        ],
    )
    write_csv(
        "fig7_candidates.csv",
        ["lambda", "objective", "category", "sources"],
        config["candidate_points"],
    )
    write_csv(
        "fig7_meta.csv",
        ["lambda_cap", "finite_lambda", "finite_objective", "switch_lambdas"],
        [{
            "lambda_cap": scene["lambda_cap"],
            "finite_lambda": scene["finite_lambda"],
            "finite_objective": scene["finite_objective"],
            "switch_lambdas": ";".join(str(value) for value in config["envelope_switch_lambdas"]),
        }],
    )


def export_air() -> None:
    for source, name in (
        (MECH / "air_full_packet_channel_chirps.csv", "air_within_chirps.csv"),
        (MECH / "air_concurrent_channel_chirps.csv", "air_concurrent_chirps.csv"),
    ):
        copy_csv(source, name)
    summary = json.loads((MECH / "air_collision_ser_heatmap_summary.json").read_text())
    write_csv(
        "air_collision_ser_heatmap.csv",
        ["sir_db", "snr_db", "ser", "trial_count"],
        summary["cells"],
    )


def export_experiment_aggregates() -> None:
    copy_csv(MECH / "fig2c_trace_curve_suite.csv", "fig2c_packet_dependent.csv")
    copy_csv(MECH / "fig2c_trace_curve_suite_recovery.csv", "fig2c_fixed_lambda_prr.csv")
    copy_csv(
        ROOT / "real_usrp_outputs/sp_v2_paper_native_figures/candidate_winner_share.csv",
        "candidate_winner_share.csv",
    )
    copy_csv(
        ROOT / "real_collision_experiment/analysis/fig9_10_12_5s/fig9_10_12_preview_aggregate.csv",
        "fig9_10_12_aggregate.csv",
    )
    copy_csv(
        ROOT / "real_usrp_outputs/1fig11_real_run_intervals_2_4_8_12_16_scenes/fig11_real_decoder_time_ser_summary.csv",
        "fig11_summary.csv",
    )
    copy_csv(
        ROOT / "real_collision_experiment/analysis/outdoor_fig13_5s/fig13_prr.csv",
        "fig13_prr.csv",
    )


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    export_fig2a_and_fig2b()
    export_experiment_aggregates()
    export_fig2d()
    export_fig5()
    export_fig7()
    export_air()
    print(f"CSV inputs written to {DATA}")


if __name__ == "__main__":
    main()
