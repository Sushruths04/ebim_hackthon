#!/usr/bin/env bash
# One-shot bring-up for a brand new Lightning Studio: clone -> submodules/LFS ->
# persistent cache dirs -> build + start the Isaac Lab 2.3.2 container.
#
# Prereqs (one-time, per machine, not scriptable from outside a repo):
#   1. This studio's SSH key is registered (Lightning's own setup script does
#      this: paste the iwr/curl one-liner from the studio's SSH page).
#   2. `docker login nvcr.io` has been run once on this Lightning account.
#
# Usage (on the studio, in an empty directory):
#   curl -fsSL https://raw.githubusercontent.com/Sushruths04/ebim_hackthon/task3-current-clean/scripts/task3/bootstrap_new_studio.sh | bash

set -euo pipefail

REPO_URL="https://github.com/Sushruths04/ebim_hackthon.git"
BRANCH="task3-current-clean"
TARGET_DIR="${1:-EBiM_Challenge}"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

command -v git >/dev/null || fail "git is required"
command -v docker >/dev/null || fail "docker is required"
command -v nvidia-smi >/dev/null || fail "No NVIDIA GPU visible. Switch this Studio to a GPU machine first."

if ! git lfs version >/dev/null 2>&1; then
    fail "Git LFS is required. Install it, then rerun."
fi
git lfs install --skip-repo

if [ -d "$TARGET_DIR/.git" ]; then
    printf 'Repo already present at %s; pulling latest %s.\n' "$TARGET_DIR" "$BRANCH"
    git -C "$TARGET_DIR" fetch origin "$BRANCH"
    git -C "$TARGET_DIR" checkout "$BRANCH"
    git -C "$TARGET_DIR" reset --hard "origin/$BRANCH"
else
    git clone -b "$BRANCH" "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"

bash scripts/task3/prepare_lightning_studio.sh

docker_config="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
if [ ! -f "$docker_config" ] || ! grep -q '"nvcr.io"' "$docker_config"; then
    printf '\nNot yet authenticated to nvcr.io on this account. Run:\n'
    printf '  docker login nvcr.io   (username: $oauthtoken, password: your NGC API key)\n'
    printf 'then re-run this script.\n'
    exit 2
fi

bash scripts/task3/lightning_workflow.sh bootstrap

cat <<EOF

Bootstrap complete. Repo at: $(pwd)
Container: isaac-lab-2-3-2-workshop (docker ps to confirm)

Next:
  bash scripts/task3/lightning_workflow.sh verify
EOF
