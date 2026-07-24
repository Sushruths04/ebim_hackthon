# Stage 2 Grasp Fix — Handoff (2026-07-24, OpenCode session)

## Summary

Seven GPU runs across two sessions diagnosed and fixed **two independent root
causes** preventing Stage 2 spoon grasp. The code is committed on
`task3-current-clean` (f6558f82) and ready for GPU run9 — but the lightning.ai
VM is **fresh** (no Docker container, no workspace, no code) and must be set
up from scratch before testing.

---

## Root cause 1: arm cannot descend 18 cm at 0.87 m reach

At `ISLAND_STANCE (-3.47, -1.61)` the spoon is ~0.87 m from the robot base.
The FR3 arm has ~0.85 m max reach. With a **top-down orientation** (rpy=π,0,0)
the arm can reach the spoon XY at z=0.95 (pregrasp) and z=0.871 (mid-descend),
but **cannot reach z=0.771** (final descend target, +1 cm above spoon surface).
The EE got stuck at ~z=0.85, leaving a 7.9 cm vertical gap (run6 evidence).

**Fix**: Added an 8 cm approach drive after pregrasp (`approach_spoon` phase,
`run_stage2_feeding.py:598-616`). The base drives to `(-3.55, -1.62)` at
0.15 m/s with 5 cm tolerance. The arm is at z=0.95 (19 cm above island) during
this drive. This reduces arm-to-spoon distance from 0.87 m → ~0.79 m, enabling
the full 18 cm vertical descent.

**Why not just move ISLAND_STANCE?**: Run7 tried `(-3.55, -1.58)` directly and
the navigation from ROTATE_SPOT timed out because yaw drifted from π to
-2.24 rad over the longer path. Two-phase approach (proven stance + short
approach_drive) is safer.

---

## Root cause 2: descending with partially-closed fingers pushes spoon

The first fix attempt (run5) added a "preclose" phase (gripper commanded to
0.25 rad before descend). This partially-closed the fingers (~0.45 rad physical
= ~38 mm opening). During descend, these semi-closed fingers contacted the
spoon handle and either **pushed it away** (catastrophic, spoon flew to floor)
or **shifted it** (minor displacement but still prevented accurate grasp).

**Fix**: Descend with gripper **fully open** (0.9 rad) and use **top-down
orientation** (not the previously used -0.80 rad or -0.40 rad tilt). The fully
open fingers straddle the spoon handle like a fork, allowing the handle to pass
between them without being pushed. The grasp then closes on the correctly-
positioned handle. The preclose phase was deleted entirely.

---

## Additional changes applied

| Change | Location | Before | After | Rationale |
|--------|----------|--------|-------|-----------|
| Descend orientation | run_stage2_feeding.py:630,636 | `tilted_quat` | `top_down_quat` | Arm reaches farthest with no tilt; open fingers straddle spoon |
| Descend budget | run_stage2_feeding.py:636 | `budget_s=6.0` | `budget_s=8.0` | More time to converge at kinematic limit |
| Close effort scale | run_stage2_feeding.py:147 | `None` (no scaling) | `1.0` (max effort) | Maximize gripper clamping force |
| Approach drive | run_stage2_feeding.py:598-616 | (did not exist) | 8 cm west at 0.15 m/s | Reduce arm-to-spoon distance from 0.87→0.79 m |
| Preclose phase | run_stage2_feeding.py | 2-phase close | Removed entirely | Partially-closed fingers pushed spoon away |
| ISLAND_STANCE | (unchanged) | (-3.47, -1.61) | Same | Proven stance; approach drive added instead |

---

## Run history

| Run | Changes | Result | Evidence |
|-----|---------|--------|----------|
| stage2_run1..3 | (prior session) | Navigate failed at door/pinch | N/A |
| stage2_run4 | Door jamb fix + island-clear fix | **Navigate OK!** Doorway crossed cleanly. Spoon grasp FAILED — gripper at 0.537 rad after close, spoon flew during scoop | First time past door |
| stage2_run5 | Preclose + tilt -0.40 + close_effort 1.0 + stiffness 5x | **Spoon flew away during descend** — preclose fingers pushed it | No useful grasp data |
| stage2_run6 | Top-down descend + NO preclose + O grasp offset | **Spoon stayed on table!** Descend FAILED — z error=7.9cm, arm at kinematic limit | Proved the reach problem |
| stage2_run7 | ISLAND_STANCE (-3.55,-1.58) + no record-video | **Navigate timeout** — yaw drifted to -2.24 rad during longer path | Proved stance change breaks nav |
| stage2_run8 | approach drive + top-down descend + no record-video | **KILLED** — SSH access to lightning.ai lost mid-execution | No result |
| **stage2_run9** | All fixes applied (committed) | **NOT YET RUN** — VM is fresh, needs setup | Pending |

---

## Current code state (committed f6558f82)

The key logic flow in `ebim/scripts/task3/run_stage2_feeding.py`:

1. Navigate to proven `ISLAND_STANCE (-3.47, -1.61)`
2. Spine raise + arm tuck
3. Navigate corridor → ROTATE_SPOT → ISLAND_STANCE (same as before)
4. Pregrasp spoon at z=0.95 with `top_down_quat`
5. **NEW**: `approach_spoon` — drive base 8 cm west to (-3.55, -1.62) at 0.15 m/s, 5 cm tolerance
6. Descend mid to z=0.871 with `top_down_quat` (4 s budget)
7. Descend final to z=0.771 with `top_down_quat` (8 s budget, tol 0.015 m)
8. `grasp()` with `close_effort_scale=1.0`
9. Scoop → lift → navigate dining → feed head → hold

---

## SSH & VM state

- **SSH**: `ssh s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai`
  - Working as of 2026-07-24 09:00 UTC
- **Hardware**: NVIDIA L4 (23 GB VRAM, 22.5 GB free), 31 GB RAM, 312 GB free disk
- **Container**: **NONE** — fresh VM. Previous `isaac-lab-2-3-2-workshop` was wiped
- **No images, no workspace, no code** on the machine

To set up from scratch:
1. `git clone https://github.com/Sushruths04/ebim_hackthon.git`
2. Build/pull Isaac Lab 2.3.2 Docker image
3. Set up container with GPU access
4. Sync code and run

---

## GPU platform status

| Platform | Status | Details |
|----------|--------|---------|
| `lightning.ai` (L4) | **LIVE** — fresh VM | SSH works, no container/code. Must set up from scratch. |
| GCP lab (`ebim26ham-236`, RTX 6000) | **DEAD** | Project expired Jul 19-20. `sim-dev-g4b` unreachable. |
| GCP personal (`skilled-fulcrum-472810-f4`, L4) | **UNKNOWN** | `sim-l4` was running with verified Isaac Lab 2.3.2 + spine-first lift fix. May have been stopped. ~$0.60/hr spot. |

---

## Next steps for the next agent

### Priority: get stage2_run9 on GPU

**Option A — lightning.ai (fastest if Docker image available):**
1. SSH in: `ssh s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai`
2. Check if Isaac Lab Docker image is cached or pullable:
   `docker pull nvcr.io/nvidia/isaac-lab:2.3.2` (needs NGC config)
   OR check if `nvidia/isaac-lab` alternative is available
3. Clone repo: `git clone https://github.com/Sushruths04/ebim_hackthon.git`
4. Build/run container with GPU access
5. Launch: `cd ebim_hackthon && python scripts/task3/run_stage2_feeding.py --out-dir /tmp/stage2_run9 --fast-exit`

**Option B — personal GCP L4 (if `sim-l4` still exists):**
1. Check VM: `gcloud compute instances list --project=skilled-fulcrum-472810-f4`
2. Start if stopped, SSH in
3. Rebuild Docker image with latest code
4. Run as above

### What to monitor

After launch (~6 min), check for these phases:
- `approach_spoon` — should complete in ~5 s
- `descend_spoon_mid` → `descend_spoon` — final position error should be <0.05 m
- `close_spoon` → `spoon_grasped` — gripper should read ~0.0-0.1 rad

### If descend still fails (position error >0.05 m)
- Increase `approach_target` offset from -0.08 to -0.12 (line 602)
- OR slow `max_speed` from 0.15 to 0.10

### If approach drive nav fails
- Increase `position_tolerance_m` from 0.05 to 0.08
- OR increase `budget_s` from 8.0 to 12.0

### If grasp succeeds
- Stage 2 feeds the head automatically. Verify `feed_hold` phase.
- Then Stage 1 (tray slide replan) and Stage 3 (cup transport) remain.

---

## Git state

Branch: `task3-current-clean`
Commit: `f6558f82` — "Stage 2: approach drive + top-down descend + close-effort 1.0 for spoon grasp"
Only `docs/AGENT_STATE.md` has uncommitted changes (this session's updates).

---

## Key files

| File | Lines | Contains |
|------|-------|----------|
| `scripts/task3/run_stage2_feeding.py` | 598-616 | `approach_spoon` phase |
| `scripts/task3/run_stage2_feeding.py` | 629-637 | Top-down descend (mid + final) |
| `scripts/task3/run_stage2_feeding.py` | 147 | `close_effort_scale` default 1.0 |
| `docs/HANDOFF_2026-07-24_Stage2_grasp_v3.md` | all | This document |

---

## Handoff prompt for next agent

```
## AGENT HANDOFF — Stage 2 spoon grasp GPU test

You are picking up Stage 2 of Task 3 (feeding pipeline). All code changes are
committed on branch `task3-current-clean` (f6558f82). Read
`docs/HANDOFF_2026-07-24_Stage2_grasp_v3.md` for full context.

### Critical context
- 7 GPU runs diagnosed two root causes for spoon grasp failure:
  1. Arm cannot descend 18 cm at 0.87 m reach → approach_spoon phase drives
     base 8 cm closer after pregrasp
  2. Partially-closed fingers pushed spoon away → descend fully open with
     top-down orientation
- These fixes are committed but **NEVER GPU-TESTED** (SSH was lost during run8)
- The lightning.ai VM is FRESH — no Docker container, no workspace, no code

### Your task
1. SSH to lightning.ai and set up the Docker environment (Isaac Lab 2.3.2)
2. Clone the repo, checkout `task3-current-clean`
3. Run `python scripts/task3/run_stage2_feeding.py --out-dir /tmp/stage2_run9 --fast-exit`
4. Monitor for approach_spoon → descend_spoon → close_spoon → spoon_grasped
5. Report which phase fails and by how much

### Key parameters if tuning needed
- approach_target offset (line 602): currently -0.08, try -0.12
- position_tolerance_m (line 603): currently 0.05, try 0.08
- max_speed (line 603): currently 0.15, try 0.10

### GPU options (in priority order)
1. lightning.ai (L4) — SSH works but needs full Docker setup
2. Personal GCP L4 (sim-l4, project skilled-fulcrum-472810-f4) — may already
   have Docker/Isaac Lab set up from prior session

### Do NOT
- Change scene assets, physics, or object poses
- Add kinematic attachments or teleport objects
- Run multiple GPU VMs simultaneously
- Leave a GPU VM running at session end
```
