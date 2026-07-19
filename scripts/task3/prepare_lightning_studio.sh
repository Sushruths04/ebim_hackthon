#!/usr/bin/env bash
# Prepare a Linux Lightning Studio for the EBiM Task 3 Docker runtime.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

mode="gpu"
case "${1:-}" in
    "") ;;
    --cpu-setup) mode="cpu" ;;
    --help|-h)
        cat <<'EOF'
Usage: scripts/task3/prepare_lightning_studio.sh [--cpu-setup]

Without arguments, validates the NVIDIA Docker runtime and prepares the Isaac
cache directories. Use --cpu-setup on a CPU-only Lightning Studio to sync the
repository and large assets before switching the Studio to a GPU.
EOF
        exit 0
        ;;
    *)
        printf 'ERROR: Unknown option: %s\n' "$1" >&2
        exit 2
        ;;
esac

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null || fail "git is required"

if ! git lfs version >/dev/null 2>&1; then
    fail "Git LFS is required. Install it, then rerun this script."
fi

git submodule update --init --recursive
git lfs pull

if [ "$mode" = "cpu" ]; then
    cat <<'EOF'

CPU setup completed: source files, submodules, and Git LFS assets are ready.
Do not build the Isaac image on this CPU instance. Switch this same Studio to
an NVIDIA GPU, then run this script again without --cpu-setup.
EOF
    exit 0
fi

command -v docker >/dev/null || fail "Docker is required by the EBiM runtime"
docker compose version >/dev/null || fail "Docker Compose v2 is required"

if ! command -v nvidia-smi >/dev/null; then
    fail "No NVIDIA GPU is visible. Switch the Lightning Studio to an NVIDIA GPU before running Isaac Sim."
fi

nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

if ! docker info --format '{{json .Runtimes}}' | grep -q 'nvidia'; then
    fail "Docker does not expose the NVIDIA runtime. Verify GPU-container support in this Studio."
fi

export HOST_UID="$(id -u)"
export HOST_GID="$(id -g)"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export DISPLAY="${DISPLAY:-:0}"

touch "$XAUTHORITY"
mkdir -p /tmp/.X11-unix

# The upstream validator always inspects running containers, even in
# --prepare-dirs mode. Create its documented persistent layout directly so
# pre-build setup remains valid on a fresh Lightning Studio.
cache_root="${HOME}/docker/ebim-challenge"
mkdir -p \
    "$cache_root/isaac-sim-5.1.0/cache/main/ov" \
    "$cache_root/isaac-sim-5.1.0/cache/main/warp" \
    "$cache_root/isaac-sim-5.1.0/cache/computecache" \
    "$cache_root/isaac-sim-5.1.0/config" \
    "$cache_root/isaac-sim-5.1.0/data/documents" \
    "$cache_root/isaac-sim-5.1.0/data/Kit" \
    "$cache_root/isaac-sim-5.1.0/logs" \
    "$cache_root/isaac-sim-5.1.0/pkg" \
    "$cache_root/isaac-sim-6.0.0/cache/main/ov" \
    "$cache_root/isaac-sim-6.0.0/cache/main/warp" \
    "$cache_root/isaac-sim-6.0.0/cache/computecache" \
    "$cache_root/isaac-sim-6.0.0/config" \
    "$cache_root/isaac-sim-6.0.0/data/documents" \
    "$cache_root/isaac-sim-6.0.0/data/Kit" \
    "$cache_root/isaac-sim-6.0.0/logs" \
    "$cache_root/isaac-sim-6.0.0/pkg" \
    "$cache_root/isaac-lab-2.3.2/cache/kit" \
    "$cache_root/isaac-lab-2.3.2/cache/ov" \
    "$cache_root/isaac-lab-2.3.2/cache/pip" \
    "$cache_root/isaac-lab-2.3.2/cache/glcache" \
    "$cache_root/isaac-lab-2.3.2/cache/computecache" \
    "$cache_root/isaac-lab-2.3.2/data" \
    "$cache_root/isaac-lab-2.3.2/documents" \
    "$cache_root/isaac-lab-2.3.2/logs"

printf 'Prepared persistent Isaac cache directories under %s\n' "$cache_root"

cat <<EOF

Lightning Studio preflight completed.

Next, authenticate to NVIDIA NGC in this Studio:
  docker login nvcr.io

Use username '\$oauthtoken' and an NGC API key as the password. Build the
Isaac Sim runtime for the first headless scene check:
  docker compose --env-file docker/.env.base -f docker/docker-compose.yaml \\
    --profile isaac-sim-5.1.0 build isaac-sim-5-1-0

Task 3 headless scene smoke run:
  docker compose --env-file docker/.env.base -f docker/docker-compose.yaml \\
    --profile isaac-sim-5.1.0 up -d
  docker exec -it isaac-sim-5-1-0-workshop bash -lc \\
    'cd /workspace/EBiM_Challenge && python scripts/scenes/scene_robot_room_keyboard.py \\
      --task task3 --headless --no-keyboard-control --autoplay'

The smoke run validates scene composition. It is not a controller test, visual
remote-teleoperation workflow, or autonomous Task 3 submission.
EOF
