#!/bin/sh
# Reliability test: 10 trials of skip-nav + spine-first lift
cd /workspace/EBiM_Challenge/_worktrees/task3-tray-fix || exit 1
for i in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== TRIAL $i ==="
  python scripts/task3/fixed_grasp_lift.py \
    --skip-navigation \
    --min-lift-m 0.02 \
    --hold-seconds 1.0 \
    --out-dir "/tmp/fixed_reliability_r${i}" \
    --fast-exit 2>&1 | grep "GRASP_RESULT"
  echo "EXIT_CODE=$?"
done
echo "=== ALL DONE ==="
