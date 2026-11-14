#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
campaign="$repo_root/real_collision_experiment/paper_experiments/generated/fig9_10_sf10_bw125_bw250_d025_r3_20s/campaign.json"
runs_root="${RUNS_ROOT:-$repo_root/real_collision_experiment/runs}"

python3 "$script_dir/offline_receiver_campaign.py" \
  --campaign "$campaign" \
  --repo-root "$repo_root" \
  --runs-root "$runs_root" \
  --start-sequence 1 \
  --end-sequence 1 \
  --slot-s 70 \
  --position-pause-s 20 \
  --capture-guard-s 5 \
  --gate-capture-seconds 3 \
  --rx-gain 20 \
  --sample-rate 750000 \
  --decode-first
