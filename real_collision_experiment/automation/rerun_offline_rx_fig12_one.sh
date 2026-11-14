#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 SEQUENCE RETRY_LABEL" >&2
  echo "Example: $0 14 fig12_0203c411_retry1" >&2
  exit 2
fi

sequence="$1"
retry_label="$2"
if [[ ! "$sequence" =~ ^(11|12|13|14|15)$ ]]; then
  echo "SEQUENCE must be in 11..15 for the Fig. 12 campaign" >&2
  exit 2
fi
if [[ ! "$retry_label" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "RETRY_LABEL may contain only letters, digits, underscore, and hyphen" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
campaign="$repo_root/real_collision_experiment/paper_experiments/generated/fig9_10_fig12_phy5_d05_d075_r1_20s/campaign.json"
runs_root="$repo_root/real_collision_experiment/reruns/$retry_label"

python3 "$script_dir/offline_receiver_campaign.py" \
  --campaign "$campaign" \
  --repo-root "$repo_root" \
  --runs-root "$runs_root" \
  --start-sequence "$sequence" \
  --end-sequence "$sequence" \
  --slot-s 70 \
  --position-pause-s 20 \
  --capture-guard-s 5 \
  --rx-gain 20 \
  --sample-rate 750000 \
  --no-decode-first
