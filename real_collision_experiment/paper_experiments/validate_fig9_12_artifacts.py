#!/usr/bin/env python3
"""Validate copied Fig. 9--12 manifests, IQ metadata, and decoder reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


REQUIRED_METHODS = ("ch0", "mrc", "mrc_cic", "pcube", "maloragw", "sp_sync_refine")


def find_artifact(root: Path, relative: str) -> tuple[Path, str | None]:
    expected = root / relative
    if expected.exists():
        return expected, None
    matches = list(root.rglob(Path(relative).name)) if root.exists() else []
    if len(matches) == 1:
        return matches[0], f"found outside planned relative path: {matches[0]}"
    if len(matches) > 1:
        return expected, f"ambiguous filename; found {len(matches)} copies"
    return expected, None


def read_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON root is not an object: {path}")
        return {}
    return value


def validate_control(run: dict, manifest: dict, errors: list[str]) -> None:
    config = manifest.get("config", {})
    expected = {
        "run_id": int(run["run_id"]),
        "num_active_nodes": len(run["active_nodes"]),
        "offered_load": float(
            run.get("traffic_profile_load", run["offered_load"])
        ),
        "duration_ms": round(float(run["duration_s"]) * 1000),
        "warmup_ms": round(float(run["warmup_s"]) * 1000),
        "global_seed": int(run["global_seed"]),
        "payload_seed": int(run["payload_seed"]),
    }
    for key, wanted in expected.items():
        actual = config.get(key)
        if actual != wanted:
            errors.append(f"control config {key}: expected {wanted!r}, got {actual!r}")
    if manifest.get("active_nodes") != run["active_nodes"]:
        errors.append("control active_nodes does not match campaign")
    traffic = manifest.get("traffic", {})
    for key, wanted in (
        ("per_node_duty_cycle", run.get("per_node_duty_cycle")),
        ("effective_aggregate_offered_load", run.get("offered_load")),
    ):
        if wanted is not None and not math.isclose(
            float(traffic.get(key, float("nan"))),
            float(wanted),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            errors.append(
                f"control traffic {key}: expected {wanted!r}, got {traffic.get(key)!r}"
            )
    tags = manifest.get("experiment", {})
    for key, wanted in run.get("tags", {}).items():
        if tags.get(key) != wanted:
            errors.append(f"control experiment tag {key}: expected {wanted!r}, got {tags.get(key)!r}")


def validate_iq_metadata(run: dict, metadata: dict, iq_path: Path, errors: list[str], warnings: list[str]) -> None:
    if metadata.get("run_id") != int(run["run_id"]):
        errors.append("IQ metadata run_id does not match campaign")
    if metadata.get("status") not in (None, "done"):
        errors.append(f"IQ capture status is {metadata.get('status')!r}, not 'done'")
    for key in ("overflow_count", "timeout_count"):
        if key not in metadata:
            warnings.append(f"IQ metadata does not expose {key}; inspect receiver console")
        elif int(metadata[key]) != 0:
            errors.append(f"IQ metadata {key}={metadata[key]}")
    clipping = metadata.get("clipping_count", metadata.get("clipped_count"))
    if clipping is None:
        warnings.append("IQ metadata does not expose clipping_count; decoder report must check ADC clipping")
    elif any(int(value) != 0 for value in clipping):
        errors.append(f"IQ clipping is non-zero: {clipping}")
    file_bytes = metadata.get("file_bytes")
    if iq_path.exists() and file_bytes is not None and iq_path.stat().st_size != int(file_bytes):
        errors.append(
            f"IQ size {iq_path.stat().st_size} does not match metadata file_bytes {file_bytes}"
        )
    samples = metadata.get("samples_per_channel")
    target = metadata.get("target_samples_per_channel")
    if samples is not None and target is not None and int(samples) != int(target):
        errors.append(f"IQ samples_per_channel {samples} != target {target}")


def validate_report(run: dict, report: dict, errors: list[str], warnings: list[str]) -> None:
    if report.get("run_id") != int(run["run_id"]):
        errors.append("decoder report run_id does not match campaign")
    capture_warnings = report.get("capture_warnings", [])
    if capture_warnings:
        errors.append(f"decoder report has {len(capture_warnings)} capture warning(s)")
    observed_nodes = {
        int(row["node_id"])
        for row in report.get("unique_protocol_valid_before_filters", [])
        if isinstance(row, dict) and "node_id" in row
    }
    zero_observed = sorted(
        set(int(node) for node in run.get("active_nodes", [])) - observed_nodes
    )
    if zero_observed:
        warnings.append(
            "NODE_OUTAGE_REVIEW_REQUIRED: active nodes with zero protocol-valid packets "
            f"{zero_observed}; do not silently exclude or impute them. Keep metrics "
            "unchanged unless field evidence marks the entire run invalid and it is rerun."
        )
    planned = report.get("planned_crc_delivery_and_tps", {})
    if not planned.get("has_planned_denominator"):
        errors.append("decoder report lacks a planned end-to-end denominator")
    method_rows = planned.get("by_method", {})
    for method in REQUIRED_METHODS:
        row = method_rows.get(method)
        if not isinstance(row, dict):
            errors.append(f"decoder report is missing method {method}")
            continue
        for metric in ("planned_crc_delivery_ratio", "tps_business_s"):
            if row.get(metric) is None:
                errors.append(f"decoder report method {method} is missing {metric}")
        if row.get("payload_goodput_kbps") is None and row.get("tps_business_s") is not None:
            warnings.append(
                f"decoder report method {method} predates payload_goodput_kbps; "
                "analysis will convert tps_business_s using the fixed 20-byte payload"
            )
    if run["phase"] == "runtime_source":
        order_rows = report.get("planned_collision_recovery", {}).get(
            "collision_order_by_identity", []
        )
        observed = {int(row["collision_order"]) for row in order_rows if "collision_order" in row}
        missing = {2, 4, 8} - observed
        if missing:
            warnings.append(f"runtime report lacks planned collision orders {sorted(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Inventory an incomplete transfer without treating missing files as fatal",
    )
    args = parser.parse_args()

    campaign = json.loads(args.campaign.read_text(encoding="utf-8"))
    results: list[dict] = []
    for run in campaign.get("runs", []):
        errors: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []
        resolved: dict[str, str] = {}
        paths: dict[str, Path] = {}
        for kind, relative in run.get("artifacts", {}).items():
            path, note = find_artifact(args.artifact_root, relative)
            paths[kind] = path
            resolved[kind] = str(path)
            if note:
                warnings.append(f"{kind}: {note}")
            if not path.exists():
                missing.append(kind)
        if paths.get("control_manifest", Path("/")).exists():
            validate_control(run, read_json(paths["control_manifest"], errors), errors)
        if paths.get("iq_metadata", Path("/")).exists():
            metadata = read_json(paths["iq_metadata"], errors)
            validate_iq_metadata(run, metadata, paths.get("iq", Path("/missing")), errors, warnings)
        if paths.get("decoder_report", Path("/")).exists():
            validate_report(run, read_json(paths["decoder_report"], errors), errors, warnings)
        if missing and not args.allow_missing:
            errors.append("missing required artifacts: " + ", ".join(missing))
        results.append(
            {
                "sequence": run["sequence"],
                "run_id_hex": run["run_id_hex"],
                "phase": run["phase"],
                "status": "invalid" if errors else ("incomplete" if missing else "valid"),
                "missing": missing,
                "errors": errors,
                "warnings": warnings,
                "resolved": resolved,
            }
        )

    counts = {
        status: sum(row["status"] == status for row in results)
        for status in ("valid", "incomplete", "invalid")
    }
    output = {
        "schema": "sp_fig9_12_artifact_validation_v1",
        "campaign_id": campaign.get("campaign_id"),
        "artifact_root": str(args.artifact_root.resolve()),
        "counts": counts,
        "runs": results,
    }
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if counts["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
