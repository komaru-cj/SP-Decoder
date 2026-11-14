#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
campaign="$repo_root/real_collision_experiment/paper_experiments/generated/fig9_10_fig12_phy5_d05_d075_r1_20s/campaign.json"

arguments=(
  "$script_dir/receiver_campaign_server.py"
  --campaign "$campaign"
  --listen-host 0.0.0.0
  --port 39091
  --repo-root "$repo_root"
  --runs-root "$repo_root/real_collision_experiment/runs"
  --rx-gain 20
  --sample-rate 750000
  --start-sequence "${START_SEQUENCE:-1}"
)
if [[ -n "${END_SEQUENCE:-}" ]]; then
  arguments+=(--end-sequence "$END_SEQUENCE")
fi
if [[ "${DECODE_FIRST:-1}" == "1" ]]; then
  arguments+=(--decode-first)
else
  arguments+=(--no-decode-first)
fi

python3 "${arguments[@]}"
