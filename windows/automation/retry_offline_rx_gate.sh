#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
campaign="$repo_root/real_collision_experiment/paper_experiments/generated/fig9_10_fig12_phy5_d05_d075_r1_20s/campaign.json"
runs_root="${RUNS_ROOT:-$repo_root/real_collision_experiment/runs}"

python3 "$script_dir/retry_offline_gate.py" \
  --campaign "$campaign" \
  --repo-root "$repo_root" \
  --runs-root "$runs_root" \
  --gate-capture-seconds 3
