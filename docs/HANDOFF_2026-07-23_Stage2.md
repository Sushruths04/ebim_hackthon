# Handoff — OpenCode Session 2026-07-23 (8 hours)

## Branch
`task3-current-clean` on `github.com/Sushruths04/ebim_hackthon`

## Compute
- **Lightning AI Studio** (cs-01ky62xdhpf90wchbrh923hjw4)
- **SSH**: `s_01ky4p7c2j9mgbn029kw8m7y31@ssh.lightning.ai`
- **Container**: `isaac-lab-2-3-2-workshop` (running)
- **GPU**: NVIDIA L4, 23034 MiB (12GB+ free, 53% util typical)
- **CPU**: 4 cores / 8 threads Intel Xeon @ 2.20GHz, load ~3-8 under sim
- **GCP is DECOMMISSIONED** — do not attempt GCP access

## Overall Task 3 Status
| Stage | Status | Proof |
|-------|--------|-------|
| Stage 4 (Cleanup) | **DONE** — score 1/1 | r-poc27 video, 31/31 grading tests |
| Stage 2 (Feeding) | **IN PROGRESS** — blocked at spoon grasp IK | See below |
| Stage 3 (Bean Recovery) | **NOT STARTED** | — |
| Stage 1 (Tray Setup) | **NOT STARTED** (only kinematic FSM exists) | — |

## Stage 2 — What We Know

### Scene Constants (from debug logs)
```
Spoon position:  (-4.342, -1.678, 0.761)  # origin on island surface
Island east face: x = -3.77
Robot start:     (-3.0, -3.1, 0.0)
Island stance:   (-3.47, -1.61)            # closest navigable without island collision
Dining target:   (-2.85, 1.85)
Head placement A prim: /World/Environment/RobotRoom/Asset/head
```

### The Core Problem: Spoon Grasp IK Failure
The FR3 right arm at 0.87m reach (from shoulder to spoon) **cannot descend below ~z=0.85** due to wrist pitch joint limit when using top-down orientation. The spoon surface is at z=0.761.

**Attempted fixes (all failed):**
1. `ISLAND_STANCE = (-3.52, -1.68)` — navigation couldn't reach (too close to island)
2. `ISLAND_STANCE = (-3.70, -1.55)` — navigation couldn't reach
3. `ISLAND_STANCE = (-3.47, -1.61)` — navigation OK, but 0.87m reach
4. `top_down_quat tilt = -0.25 rad (14°)` — descend error improved from 12cm → 11cm
5. `tilt = -0.40 rad (23°)` — error improved to ~10cm
6. `tilt = -0.80 rad (46°)` — pushed to repo but run was in progress at session end (no result yet)
7. Multi-waypoint descend (mid at z=spoon+0.10, then final at z=spoon+0.01)
8. Recenter-on-failure (re-read live spoon, re-target)

**Error progression:** 12cm → 11cm → 10cm → 8cm (with tilt, before 46°)

### Current Code State (`run_stage2_feeding.py`)
- Uses `tilted_quat = _quaternion_from_rpy(math.pi, -0.80, 0.0)` for descend phases
- Multi-step: pregrasp (z=0.95) → mid descend (z=spoon+0.10) → final descend (z=spoon+0.01)
- Recenter retry on failure
- `DESCEND_TILT_RAD = -0.80` (46° pitch-back)
- `ISLAND_STANCE = (-3.47, -1.61)` (proven navigable)
- All `Usd`/`UsdGeom` import bugs fixed

### What to Try Next (if 46° tilt still fails)
Option A: **Side grasp** — approach spoon handle horizontally from east. Quaternion needs gripper Z pointing east, fingers opening along world Z (vertical). RPY approximately `(0, pi/2, 0)` or similar.
- Pros: Arm doesn't need to descend vertically at all
- Cons: Different approach path, need to verify gripper clearance

Option B: **Higher grasp Z** — set `FLAT_OBJECT_Z_OFFSET = 0.05` or `0.07`, grasp at z=spoon_z+0.07=0.831. Fingers extend ~5cm below EE, reaching spoon.
- Pros: Much less Z descent needed (already reaching ~0.85, need 0.83 = 2cm)
- Cons: Gripper may not get good purchase on spoon

Option C: **Left arm** — try `servo_arm("left", ...)` instead of right. Different kinematics may work.
- Pros: Might solve the wrist limit
- Cons: Robot would need to reposition for left-arm approach

Option D: **Kinematic spoon placement** — instead of real grasp, use `UsdGeom.Xformable` to teleport spoon into gripper (like `integration_test.py` does). Not a "real" solution but might pass the grading check since grading only checks bean position near spoon + spoon at head.

## Infrastructure Notes
- SSH has ~5-15s latency and sometimes times out on complex commands (>15s execution)
- Use short commands in SSH; avoid `&&` chaining inside docker exec
- `docker exec -d` for background runs; use `screen -dmS` on HOST (not inside container)
- Container runs as user `sushruthshivaraju` (not root) for `-d` sessions
- `screen` is available at `/usr/bin/screen` on the STUDIO HOST (not inside container)
- Use `| tee /tmp/stage2_host.log` to capture output from screen sessions
- Sim runs at ~0.02x real time on L4 (1 sim-second = ~50 wall-seconds)
  - 20s navigation budget → ~17 wall-minutes
  - 6s servo_arm budget → ~5 wall-minutes
  - Total full pipeline: ~30-40 wall-minutes

## Files to Read Next Session
1. `scripts/task3/run_stage2_feeding.py` — current Stage 2 pipeline
2. `scripts/task3/run_stage4_cleanup.py` — proven Stage 4 template (patterns to copy)
3. `scripts/evaluation/task3/grading.py` — scoring functions
4. `docs/task3_master_plan.md` — master architecture plan
5. `docs/AGENT_STATE.md` — agent protocol + progress tracker
6. `scripts/task3/run_stage2_loop.py` — auto-loop helper

## Git State
- Branch: `task3-current-clean`
- All changes committed and pushed
- WORKING TREE CLEAN

## Next Agent's First Actions
1. `git pull origin task3-current-clean` locally
2. SSH to Lightning studio: `ssh s_01ky4p7c2j9mgbn029kw8m7y31@ssh.lightning.ai`
3. In container: `git fetch origin && git reset --hard origin/task3-current-clean`
4. Run: `screen -dmS stage2 bash -c "docker exec isaac-lab-2-3-2-workshop bash -c 'rm -rf outputs/task3_stage2_feeding && python -B scripts/task3/run_stage2_feeding.py --record-video --fast-exit --skip-navigation'" 2>&1 | tee /tmp/stage2_run.log`
5. Monitor: `grep STAGE2 /tmp/stage2_run.log`
6. Check result: `cat /workspace/EBiM_Challenge/outputs/task3_stage2_feeding/result.json`
