#!/usr/bin/env bash
set -euo pipefail

repo_root=/workspace/EBiM_Challenge
runner="$repo_root/scripts/task3/run_episode.py"
seed="${TASK3_SEED:-0}"
head_placement="${TASK3_HEAD_PLACEMENT:-a}"
policy="${TASK3_POLICY:-scripted}"
max_seconds="${TASK3_MAX_SECONDS:-120}"

if [[ "${1:-}" == "bash" || "${1:-}" == "shell" ]]; then
  exec /bin/bash
fi

if [[ $# -gt 0 ]]; then
  # Use Isaac Sim's python.sh for python/python3 calls so CARB environment
  # (CARB_APP_PATH, ISAAC_PATH, etc.) is set up correctly.
  if [[ "$1" == "python" || "$1" == "python3" ]]; then
    shift
    exec /isaac-sim/python.sh "$@"
  fi
  exec "$@"
fi

if [[ -x /workspace/isaaclab/isaaclab.sh ]]; then
  exec /workspace/isaaclab/isaaclab.sh -p "$runner" \
    --seed "$seed" \
    --head-placement "$head_placement" \
    --policy "$policy" \
    --max-seconds "$max_seconds" \
    --out-dir "$repo_root/outputs/task3_episodes"
fi

exec python3 "$runner" \
  --seed "$seed" \
  --head-placement "$head_placement" \
  --policy "$policy" \
  --max-seconds "$max_seconds" \
  --out-dir "$repo_root/outputs/task3_episodes"
