#!/usr/bin/env bash
# Run the repeatable EBiM Task 3 workflow inside a Lightning Studio.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$repo_root/docker/docker-compose.yaml"
env_file="$repo_root/docker/.env.base"
container="isaac-lab-2-3-2-workshop"

usage() {
    cat <<'EOF'
Usage: bash scripts/task3/lightning_workflow.sh <command>

Commands:
  bootstrap              Sync assets, validate the GPU, and start Isaac Lab.
  status                 Show GPU, container, commit, assets, and checkpoints.
  verify                 Run Task 3 grading and RL unit tests in Isaac Lab.
  train-kinematic-stage1 Run the fast, validated Stage 1 PPO curriculum.
  stop                   Stop Isaac Lab when this Lightning session is finished.

Before the first bootstrap on each Lightning account:
  docker login nvcr.io

The NGC API key is account secret material and is deliberately not stored here.
EOF
}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

cd "$repo_root"

compose() {
    HOST_UID="$(id -u)" HOST_GID="$(id -g)" docker compose \
        --env-file "$env_file" -f "$compose_file" "$@"
}

require_assets() {
    local asset
    for asset in assets/robot_room.usd assets/mobile_fr3_duo_v0_2.usd; do
        [ -f "$asset" ] || fail "Required Task 3 asset is missing: $asset"
    done
}

require_container() {
    docker inspect "$container" >/dev/null 2>&1 \
        || fail "Isaac Lab is not running. Run: bash scripts/task3/lightning_workflow.sh bootstrap"
}

bootstrap() {
    # This prepares persistent cache directories and checks the host GPU/runtime.
    bash scripts/task3/prepare_lightning_studio.sh
    require_assets
    compose --profile isaac-lab-2.3.2 up -d --build isaac-lab-2-3-2
    require_container
    printf '\nIsaac Lab is ready. Next command:\n'
    printf '  bash scripts/task3/lightning_workflow.sh verify\n'
}

status() {
    printf '%s\n' '--- Git ---'
    git log -1 --oneline
    git status --short
    printf '%s\n' '--- GPU ---'
    nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader
    printf '%s\n' '--- Container ---'
    docker ps --filter "name=$container" --format 'table {{.Names}}\t{{.Status}}'
    printf '%s\n' '--- Required assets ---'
    require_assets
    ls -lh assets/robot_room.usd assets/mobile_fr3_duo_v0_2.usd
    printf '%s\n' '--- Checkpoints ---'
    find models outputs/task3_rl -type f -name '*.pt' -printf '%p %k KB\n' 2>/dev/null || true
}

verify() {
    require_container
    docker exec "$container" bash -lc \
        'cd /workspace/EBiM_Challenge && python -B scripts/evaluation/task3/tests/test_grading.py && python -m unittest task3_rl.test_stage1 task3_rl.test_kinematic_stage1'
}

train_kinematic_stage1() {
    require_container
    docker exec "$container" bash -lc \
        'cd /workspace/EBiM_Challenge && python -m task3_rl.train_kinematic_stage1 --num-envs 2048 --iterations 500 --log-dir outputs/task3_rl/kinematic_stage1_l40s_500'
}

case "${1:-}" in
    bootstrap) bootstrap ;;
    status) status ;;
    verify) verify ;;
    train-kinematic-stage1) train_kinematic_stage1 ;;
    stop) compose --profile isaac-lab-2.3.2 stop isaac-lab-2-3-2 ;;
    --help|-h|help|'') usage ;;
    *) fail "Unknown command: $1" ;;
esac
