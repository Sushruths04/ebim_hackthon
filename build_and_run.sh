#!/bin/bash
set -euo pipefail

sudo docker rm -f $(sudo docker ps -aq) 2>/dev/null || true

cd /workspace/EBiM_Challenge
sudo docker build --network=host -t ebim-task3:local . 2>&1 | tail -5

echo "=== Testing python ==="
sudo docker run --rm ebim-task3:local python --version 2>&1

echo "=== Starting skip-nav test ==="
sudo docker run -d --gpus all --network host -v /workspace/EBiM_Challenge/outputs:/workspace/EBiM_Challenge/outputs ebim-task3:local python scripts/task3/run_stage4_cleanup.py --object-name cup --arm-side right --approach-stance east --skip-navigation --pickup-only --record-video --fast-exit
echo "=== Container started ==="
