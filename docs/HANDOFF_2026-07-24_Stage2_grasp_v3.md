# Stage 2 Grasp Fix — Handoff (2026-07-24)

## Problem

The spoon grasp has never succeeded. Two distinct root causes were identified
and addressed across sequential GPU runs on `lightning.ai`:

### Root cause 1: arm cannot descend 18 cm at 0.87 m reach

At ISLAND_STANCE `(-3.47, -1.61)` the spoon is ~0.87 m from the robot base.
The FR3 arm has ~0.85 m max reach. With a **top-down orientation**
(rpy=π,0,0) the arm can reach the spoon XY at z=0.95 (pregrasp) and
z=0.871 (mid-descend), but **cannot reach z=0.771** (final descend target
+1 cm above spoon surface). The EE got stuck at ~z=0.85, leaving a 7.9 cm
vertical gap. Result: the gripper fingers close on air, the spoon stays on
the table, but the grasp fails.

**Fix**: Added an 8 cm approach drive after pregrasp (`approach_spoon`
phase, lines 598-616). The base drives to `(-3.55, -1.62)` at 0.15 m/s with
a relaxed 5 cm tolerance. The arm is at z=0.95 (19 cm above island) during
this drive, so clearance is safe. This reduces the arm-to-spoon distance
from 0.87 m → ~0.79 m, enabling the full 18 cm vertical descent.

**NOTE**: A previous attempt to move ISLAND_STANCE directly to `(-3.55, -1.58)`
caused the navigation to timeout (yaw drifted from π to -2.24 rad during
the longer path from ROTATE_SPOT). The two-phase approach (navigate to
proven stance, then short approach drive) avoids this.

### Root cause 2: descending with partially-closed fingers pushes spoon

The first fix attempt added a "preclose" phase (gripper commanded to
0.25 rad before descend). This partially-closed the fingers (~0.45 rad
physical = ~38 mm opening). During descend, these semi-closed fingers
contacted the spoon handle and either **pushed it away** (catastrophic,
spoon flew to floor) or **shifted it** (minor displacement but still
prevented accurate grasp).

**Fix**: Descend with gripper **fully open** (0.9 rad) and use
**top-down orientation** (not the previously used -0.80 rad or -0.40 rad
tilt). The fully open fingers straddle the spoon handle like a fork,
allowing the handle to pass between them without being pushed. The grasp
then closes on the correctly-positioned handle.

### Additional changes

| Change | File | Line | Before | After |
|--------|------|------|--------|-------|
| Descend orientation | run_stage2_feeding.py | 630,636 | tilted_quat | top_down_quat |
| Descend budget | run_stage2_feeding.py | 636 | budget_s=6.0 | budget_s=8.0 |
| Close effort scale | run_stage2_feeding.py | 147 | None (no scaling) | 1.0 (max effort) |
| DESCEND_TILT_RAD | run_stage2_feeding.py | 59-61 | -0.80 (46°) | -0.40 (23°) (still set but unused — descended with top_down_quat) |

## Run history

| Run | Changes | Result |
|-----|---------|--------|
| stage2_run1..3 | (prior session) | Navigate failed at door/pinch |
| stage2_run4 | Door jamb fix + island-clear fix | Navigate OK, spoon grasp FAILED (gripper at 0.537 rad after close, spoon flew away during scoop) |
| stage2_run5 | Preclose + tilt -0.40 + close_effort 1.0 + stiffness 5x | Spoon flew away during descend (preclose fingers pushed it) |
| stage2_run6 | Top-down descend + NO preclose + O grasp offset | Spoon stayed on table! Descend failed (z error=7.9cm, arm at kinematic limit) |
| stage2_run7 | ISLAND_STANCE (-3.55,-1.58) + no record-video | Navigate timeout (yaw drifted to -2.24 rad) |
| stage2_run8 | **Current state**: approach drive + top-down descend | **NOT YET RUN** — SSH access lost |

## Current code state

The code at `ebim/scripts/task3/run_stage2_feeding.py` has all fixes applied
and is ready for GPU testing. The key logic flow:

1. Navigate to proven ISLAND_STANCE `(-3.47, -1.61)`
2. Spine raise + arm tuck
3. Navigate corridor → rotate → island (same as before)
4. Pregrasp spoon at z=0.95 with top_down_quat
5. **NEW**: `approach_spoon` — drive base 8 cm west to `(-3.55, -1.62)` at 0.15 m/s, 5 cm tolerance
6. Descend mid to z=0.871 with top_down_quat
7. Descend final to z=0.771 with top_down_quat (8 s budget)
8. `grasp()` with close_effort_scale=1.0
9. Scoop → lift → navigate dining → feed head → hold

## Next steps for the next agent

1. **SSH to lightning.ai** and verify the code on remote:
   ```
   ssh s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai
   ```
   The key may need re-authorization.

2. **Sync files to docker container**:
   ```
   Get-Content -Path "ebim/scripts/task3/run_stage2_feeding.py" -Raw | ssh ... "docker exec -i isaac-lab-2-3-2-workshop bash -c 'cat > /workspace/EBiM_Challenge/scripts/task3/run_stage2_feeding.py'"
   ```

3. **Kill any existing run**:
   ```
   ssh ... "docker exec isaac-lab-2-3-2-workshop pkill -f run_stage2_feeding"
   ```

4. **Launch run** (without --record-video for speed):
   ```
   ssh ... "docker exec -d isaac-lab-2-3-2-workshop bash -c 'cd /workspace/EBiM_Challenge && python scripts/task3/run_stage2_feeding.py --out-dir /tmp/stage2_run9 --fast-exit > /tmp/stage2_run9.log 2>&1; echo EXIT_CODE=\$? >> /tmp/stage2_run9.log'"
   ```

5. **Monitor**: check log after ~6 min for `descend_spoon` and `close_spoon`
   phases:
   ```
   ssh ... "docker exec isaac-lab-2-3-2-workshop grep 'STAGE2DBG' /tmp/stage2_run9.log | grep -E 'descend_spoon|close_spoon|spoon_grasped' -i"
   ```

6. **If descend still fails** (position error >0.05 m): the approach drive
   (`approach_target`) may need a larger offset (try -0.12 instead of -0.08)
   or a slower speed.

7. **If grasp succeeds**: Stage 2 feeds the head automatically. Verify
   `feed_hold` phase passes. Then move on to Stage 1 (tray slide) or
   Stage 3 (cup transport).

## Git state

Only `ebim/scripts/task3/run_stage2_feeding.py` is modified (staged but
uncommitted). The `ebim/task1_isaacsim/.../joint_drive_config.yaml` was
modified then reverted (no net change). Commit before handing off:
```
git -C ebim add -A && git -C ebim commit -m "Stage 2: approach drive + top-down descend for spoon grasp"
```
