#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${REPO_ROOT:-$(cd -- "$script_dir/../../../.." && pwd)}"
campaign="$script_dir/campaign.json"
runs_root="${RUNS_ROOT:-$repo_root/real_collision_experiment/runs_outdoor}"

python3 "$repo_root/real_collision_experiment/automation/offline_receiver_campaign.py" \
  --campaign "$campaign" \
  --repo-root "$repo_root" \
  --runs-root "$runs_root" \
  --start-sequence 1 \
  --end-sequence 10 \
  --slot-s 75 \
  --position-pause-s 30 \
  --capture-guard-s 5 \
  --rx-gain 60 \
  --sample-rate 750000 \
  --continue-on-run-error \
  --no-decode-first
