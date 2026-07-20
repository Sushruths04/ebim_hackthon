# EBiM Task 3 — Complete Learning Guide

**Purpose:** Document everything the three AI agents (Claude, Codex, OpenCode) have built, how the system works, and how to learn from it.

**Last updated:** 2026-07-18

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture — How Everything Connects](#2-architecture)
3. [Agent Responsibilities](#3-agent-responsibilities)
4. [File-by-File Reference](#4-file-reference)
5. [What Each Phase Accomplished](#5-phase-history)
6. [Key Technical Decisions](#6-key-decisions)
7. [Lessons Learned](#7-lessons)
8. [Current Status](#8-current-status)
9. [How to Contribute](#9-how-to-contribute)

---

## 1. Project Overview

**Task:** A mobile dual-arm robot (Mobile FR3 Duo) performs a 4-stage kitchen-to-dining service cycle in Isaac Sim.

**Competition:** EBiM Benchmark — Assisted Living & Feeding. Deadline: Aug 3, 2026.

**Strategy:** Scripted autonomous controller (FSM), NOT a learned policy. The competition allows scripted controllers — "Full Autonomy" means no human at the keyboard, not "must use neural network."

**4 Stages:**
| Stage | Name | What Robot Does | Points |
|---|---|---|---|
| 1 | Table Setup | Move utensils from kitchen to dining seats | 4 |
| 2 | Feeding | Scoop beans, hold 3s near head | 4 |
| 3 | Bean Recovery | Pour beans into recycling bin | 4 |
| 4 | Cleanup | Return utensils to sink | 4 |

**Total: 16 points max. Ranking = highest stage → total → time.**

---

## 2. Architecture — How Everything Connects

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT SOURCES                             │
│  Keyboard Teleop │ Scripted FSM │ Learned Policy (Phase 7)  │
└────────┬─────────┴──────┬───────┴──────────┬───────────────┘
         │                │                  │
         v                v                  v
┌─────────────────────────────────────────────────────────────┐
│              TeleopCommand  (teleop_commands.py)             │
│  The universal command interface. ALL sources produce this.  │
│  Contains: base_twist, left/right PoseDelta, gripper deltas  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────────┐
│        CartesianTargetTracker  (teleop_targets.py)           │
│  Accumulates command deltas into persistent targets          │
│  Enforces workspace limits (position_min/max, gripper range) │
│  Frame transforms: world ↔ robot-base                       │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              v                     v
┌──────────────────────┐  ┌──────────────────────┐
│  DualArmController    │  │  TmrBaseAdapter       │
│  (arms.py)            │  │  (skills.py)          │
│  Lula IK solve        │  │  Body twist → wheel   │
│  reach/grasp/lift     │  │  targets              │
│  place/release        │  │  Heading hold         │
└──────────┬───────────┘  └──────────┬───────────┘
           │                         │
           v                         v
┌─────────────────────────────────────────────────────────────┐
│              Isaac Sim / Isaac Lab Runtime                    │
│  robot.set_joint_position_target() / set_joint_velocity_target() │
│  Physics: PhysX/Fabric, collision, contact                   │
└─────────────────────────────────────────────────────────────┘
```

### The Key Design Decision

**Everything plugs in at `TeleopCommand`.** This is the boundary the master plan mandates. The FSM, keyboard teleop, and any future learned policy ALL produce the same `TeleopCommand` object. This means:
- You can swap input sources without changing the robot control code
- The IK, composition, and runtime code is shared
- Testing is consistent across sources

---

## 3. Agent Responsibilities

### Claude (branch `main`)
**Role:** Primary GPU operator, architecture, integration

| What | How |
|---|---|
| Episode runner | `run_episode.py` — headless scene launch, video capture, grading |
| OmniGraph fix | `make_headless_robot_usd()` — wrapper USD layer deactivates controller graphs before composition |
| Video capture | Pull-based RGB annotator (replaced runaway BasicWriter that wrote 139k frames / 93 GB) |
| Navigation root cause | Discovered robot was pressing against wall (not a tuning problem) — fixed with door-aware routing |
| Arm transit pose | Measured in-sim: 1.88m → 0.74m width for doorway traversal |
| Master plan | 698-line architecture document any agent can execute from |

### Codex (branch `agent/codex-task3-grasp`)
**Role:** Manipulation / grasp-lift engineer

| What | How |
|---|---|
| `DualArmController` | `arms.py` — reach, grasp, lift, place via Lula IK + TeleopCommand |
| `NavigateTo` / `RotateTo` | `skills.py` — door-aware waypoint navigation, in-place rotation |
| `TmrBaseAdapter` | `skills.py` — body twist → TMR wheel targets, wheel damping fix (500) |
| Grasp verification | `verify_grasp_lift.py` — full pipeline: navigate → pregrasp → descend → close → lift → hold |
| Gripper fix | Corrected joint names: `left_gripper_joint` (not `left_fr3v2_finger_joint1`), convention 0.0=closed, 0.9=open |
| 18 grasp runs | Iterative calibration documented in AGENT_STATE.md |

### OpenCode (branch `agent/opencode-data`)
**Role:** Data tooling, verification helpers, Phase 7 prep

| What | How |
|---|---|
| `make_proof_bundle.py` | Assembles video + result.json + repro.txt into `proofs/<slug>/` |
| `batch_eval.py` | Phase 5: runs 3 heads × 5 seeds = 15 headless runs, produces summary table |
| `lerobot_recorder.py` | LeRobot v2 dataset recorder (HDF5/JSONL) |
| `teleop_record.py` | Keyboard teleop + LeRobot recording for demonstration collection |
| Unit tests | 10 tests for LeRobot recorder, all passing |

---

## 4. File-by-File Reference

### Core Runtime (`scripts/common/`)

#### `teleop_commands.py` — The Command Interface
```python
@dataclass(frozen=True)
class TeleopCommand:
    timestamp: float
    source: str              # "keyboard", "task3_autonomy.reach", etc.
    active: bool
    base_twist: Vector3      # (vx, vy, wz) body frame
    left_pose: PoseDelta     # incremental translation + rotation
    right_pose: PoseDelta
    left_gripper_delta: float
    right_gripper_delta: float
    spine_delta: float
```
**Why it matters:** This is the universal interface. Every input source produces this. The robot control code consumes this. Nothing else touches the robot directly.

#### `teleop_targets.py` — State Management
```python
class CartesianTargetTracker:
    """Accumulates command deltas into persistent arm targets."""
    
    def apply(self, command: TeleopCommand) -> TeleopTargets:
        # Position: additive (current + delta.translation)
        # Orientation: left-multiply (quat_from_rpy(delta.rotation) * current)
        # All values clamped to TargetLimits
```
**Key insight:** Position targets are in the **robot-base frame**. When the base moves, the arm targets move with it. This is why the FSM must either freeze arms during base motion or re-transform targets every tick.

#### `tmr_base_control.py` — Wheel Kinematics
```python
def compute_drive_targets(robot, steering_ids, vx, vy, wz, ...):
    # Diagonal TMR base: two independently-steered drive modules
    # Kinematic inversion: body twist → per-wheel steering angle + velocity
    
def compensate_yaw_rate(robot, vx, vy, wz_cmd, hold_yaw, ...):
    # PD heading hold during translation
    # Proportional + derivative correction maintains desired heading
```
**Critical fix:** Wheel drive damping was 5.0 (wheels at 7% of target). Changed to 500.0 via direct PhysX tensor write — the config path did NOT reach the simulation.

### Manipulation (`task3_autonomy/`)

#### `arms.py` — The Manipulation API
```python
class DualArmController:
    def reach(self, side, position, quat, *, step, dt, timeout_s):
        """Reach a world pose. Returns False on timeout."""
        # Reissues absolute target every tick (base drift compensation)
        
    def grasp(self, side, *, step, dt, settle_seconds):
        """Close gripper, settle, confirm object blocks closure."""
        # Uses gripper_holds_object() predicate
        
    def lift(self, side, dz, *, step, dt, timeout_s):
        """Raise end-effector by dz while holding attitude."""
        # Measures current pose, adds dz, calls reach()
        
    def command(self):
        """Solve IK and write joint targets."""
        # CartesianTargetTracker → Lula IK → compose_position_targets → robot
```

#### `skills.py` — FSM-Level Skills
```python
class NavigateTo:
    """Drive through door-aware waypoints to a target."""
    def compute(self, pose: Pose2D) -> tuple[float, float, bool]:
        # Returns (vx, vy, done) in body frame
        # Uses route_via_door() for wall avoidance
        
class RotateTo:
    """Rotate in place to absolute world yaw."""
    def compute(self, pose: Pose2D) -> tuple[float, bool]:
        # Returns (wz, done)
        
class TmrBaseAdapter:
    """Body twist → TMR wheel targets."""
    DRIVE_DAMPING = 500.0  # Must be written at runtime, not config
    
    def apply_twist(self, vx, vy, wz_cmd):
        # compensate_yaw_rate() + compute_drive_targets()
```

#### `navigation.py` — Pure Math (CPU-Testable)
```python
def route_via_door(start, target):
    """Generate waypoints crossing through the doorway."""
    # Door at x=-4.14, y=0.22
    # Kitchen lane at y=-0.37 (between partition and island)
    
def base_twist_toward(pose, target):
    """Proportional body-frame controller."""
    # Rotates world error by -yaw into body frame
    
def pose_reached(pose, target, tolerance_m=0.03, tolerance_rad=0.05):
    """Stop-condition check."""
```

### Scripts (`scripts/task3/`)

#### `run_episode.py` — The Foundation
```
What it does:
1. Seeds Python random for reproducibility
2. Builds the Task 3 scene (room + robot + objects)
3. Creates headless USD wrapper (deactivates OmniGraphs)
4. Runs the policy loop (idle or scripted)
5. Records video (pull-based annotator)
6. Grades stages 1/3/4
7. Prints EPISODE_RESULT JSON

Key functions:
- make_headless_robot_usd(): wrapper layer fix
- prepare_rigid_body_view_path(): nested rigid body cleanup
- _save_rgb_frame(): pull-based video capture
```

#### `verify_grasp_lift.py` — The Grasp Pipeline
```
Phase sequence:
0. Raise spine to 0.45m, tuck arms (TRANSIT_ARM_POSE)
1. Navigate: corridor_stop → rotate_spot → face west → stance
2. Pregrasp: right arm above cup at z=1.05
3. Descend: move to grasp height, close gripper
4. Lift: raise to z=1.10, hold 3 seconds

Key parameters:
- CUP_GRASP_XY = (-4.145, -1.75)
- GRASP_Z = 0.815
- LIFT_Z = 1.10
- FINAL_APPROACH_CONTACT_TOLERANCE_M = 0.10
```

### Evaluation (`scripts/evaluation/task3/`)

#### `grading.py` — Scoring Source of Truth
```python
# Regions (the FSM must place objects here)
TASK3_KITCHEN_AREA = Area2D(center_x=-4.2, center_y=-1.8, ...)
TASK3_DINING_AREA = Area2D(center_x=-2.85, center_y=1.9, ...)
TASK3_BEAN_RECOVERY_REGION = SphereRegion(center=Point3D(...), radius=0.2)
TASK3_SINK_REGION = SinkRegion(bounds=Bounds2D(...), tabletop_z=0.74699)

# Scoring functions
score_stage1_table_setup(positions)  # Count objects in dining area
feed_score(beans_left, hold_seconds, smooth)  # 0-4 points
bean_recovery_score(inside, total)  # Ratio-based 0-4 points
score_stage4_cleanup(bounds, z_values)  # Objects in sink region
```

---

## 5. What Each Phase Accomplished

### Phase 0 — Sync & Bootstrap
- Pushed merged local main to fork
- Created GPU budget log
- Submitted GCP quota requests (L4×2, A100×1)
- **Lesson:** GCP quota approval takes 24-48 hours — submit FIRST

### Phase 1 — Episode Runner
**Problem:** No way to verify behavior without a human watching.
**Solution:** `run_episode.py` — headless scene launch, video capture, grading.

**Blockers encountered:**
1. Robot USD's OmniGraphs crashed headless → Fix: wrapper USD layer (composition-time, not post-load)
2. BasicWriter ran away (139k frames / 93 GB) → Fix: pull-based RGB annotator
3. Results written after Kit shutdown (process killed) → Fix: persist before close()

**Proof:** `proofs/phase1-harness/` — 160 frames, seed-42 twice → bit-identical spawns.

### Phase 2 — Skill Primitives
**Problem:** Robot can't do anything autonomously.
**Solution:** Navigation + manipulation skills.

**Navigation discovery:**
- Robot was pressing against the dining/kitchen wall (not a controller problem)
- Door is 1.2m wide; robot with arms out is 1.88m → need transit tuck pose
- Measured in-sim: "pnn_j6_15_j4_30" pose = 0.74m width

**Grasp attempts (18 runs):**
- Runs 1-4: Basic bugs (imports, finger names, degrees/radians)
- Runs 5-7: Physics issues (timeout, weak spine, base drift)
- Runs 8-10: Alignment issues (cup sliding, offset errors)
- Runs 11-12: Convention fix (ChangingTek: 0.0=closed, 0.9=open)
- Runs 13-14: Base drift fix (active XY hold), cup rose 0.077m (just below gate)
- Run 15: **Mid-stroke pinch (0.435 rad)**, cup +0.069m
- Run 16: **Cup +0.105m (above gate!)** but slipped during hold
- Run 17: **Cup +0.134m peak, +0.098m final** — held but oscillating
- Run 18: Wrist target raised to 1.10m for settling margin

---

## 6. Key Technical Decisions

### 1. Pull-Based Video Capture
```
BAD:  BasicWriter (push-based) — writes on EVERY app update
      → 139k frames, 93 GB, disk full, process hung
      
GOOD: RGB Annotator (pull-based) — frame exists only when requested
      → Exactly 160 frames, clean GIF, no overflow
```
**Lesson:** In autonomous pipelines, pull-based fails closed, push-based fails open.

### 2. Composition-Time USD Fixes
```
BAD:  Post-load patching (deactivate graphs after import)
      → Kit already registered them, crash on sim.reset()
      
GOOD: Wrapper USD layer (set Graph.active=false BEFORE composition)
      → Kit never composes the graphs, no crash
```
**Lesson:** USD composition is a one-shot process. Fix before it runs, not after.

### 3. Wheel Damping at Runtime
```
BAD:  Set damping in robot_actuator_cfg_specs
      → Value did NOT reach PhysX (verified by probe)
      
GOOD: Write damping directly to PhysX via tensor API
      → 500.0 damping, wheels track 10 rad/s in 2s
```
**Lesson:** Some Isaac Lab config paths don't reach the simulation. Runtime tensor writes are the delivery mechanism.

### 4. Smallest-GPU-First Escalation
```
Modal serverless     → Failed (no Vulkan graphics stack)
Fractional g4 MIG    → Failed (CUDA↔Vulkan interop unsupported)
Full RTX PRO 6000    → Works (9.4s warm render)
Total escalation cost: ~1.5 EUR
```
**Lesson:** Evidence of *functional incapability* justifies escalation. Performance preference does not.

---

## 7. Lessons Learned

### For Robot Programming
1. **Measure the environment before planning through it** — the doorway was 1.2m, robot was 1.88m. Both the room and robot need to be measured.
2. **Verify actuators against targets** — wheels commanded to 10 rad/s reading back ~0 means obstruction, not gain problem.
3. **Pull-based data acquisition** — push-based recorders fail open (fill disk), pull-based fail closed.
4. **Composition-time fixes only** — post-load patching of USD prims/graphs cannot undo Kit's initialization.
5. **Active base hold during manipulation** — zero wheel velocity still allows floating drift from arm reaction forces.

### For Multi-Agent Projects
1. **Git is shared memory** — every agent reads AGENT_STATE.md first, updates it last.
2. **One GPU at a time** — hard rule, no exceptions.
3. **Branch ownership** — main = Claude, codex-packaging = Codex, opencode-data = OpenCode.
4. **Proof bundles are mandatory** — no checkbox without video + result.json + repro.txt.
5. **Push at every exit criterion** — unpushed work does not exist.

### For Competition Strategy
1. **Ranking = highest stage first** — completing Stage 4 (easiest) before Stage 2 (hardest) locks in ranking.
2. **Partial credit is fine** — bean recovery is ratio-scored, not all-or-nothing.
3. **Ship the scripted version first** — learned policy is Phase 7 (stretch, never blocks submission).
4. **Deadline is Aug 3** — submit early, iterate later.

---

## 8. Current Status

### Completed (Frozen)
| Phase | Proof | Tag |
|---|---|---|
| Phase 1: Episode runner | `proofs/phase1-harness/` | `v0.1-harness` |
| Phase 2: Navigation math | `proofs/phase2-navigation-math/` | — |
| Phase 2: Live navigation | `proofs/phase2-navigate-live/` | — |

### In Progress
| Phase | Status | Blocker |
|---|---|---|
| Phase 2: Grasp/lift | Run 18 pending (oscillation fix) | Need 8/10 pass rate |

### Not Started
| Phase | Depends On |
|---|---|
| Phase 3: Stage 1 FSM | Grasp gate passing |
| Phase 4: Stages 2-4 | Phase 3 |
| Phase 5: Batch eval | Phase 3+ |
| Phase 6: Submission | Phase 5 |
| Phase 7: Learned policy | After submission |

---

## 9. How to Contribute

### To fix the grasp (current blocker):
1. Read `docs/AGENT_STATE.md` — understand Run 15-18 findings
2. Tune parameters in `scripts/task3/verify_grasp_lift.py`:
   - `LIFT_Z` (currently 1.10)
   - `CUP_GRASP_Y_OFFSET` (currently 0.06)
   - Hold loop damping in the hold phase
3. Run on GPU VM: `python scripts/task3/verify_grasp_lift.py --skip-navigation --record-video`
4. If 8/10 passes: commit, tag `v0.1-skills`, update AGENT_STATE.md

### To build a new stage (Phase 3-4):
1. Read `scripts/evaluation/task3/grading.py` — understand scoring regions
2. Read `scripts/task3/verify_grasp_lift.py` — understand the phase pattern
3. Build the FSM: navigate → grasp → transport → place → release → retreat
4. Verify with `run_episode.py --policy scripted --record-video`
5. Score must be ≥ threshold per the master plan

### To collect teleoperation data (Phase 7):
1. SSH into GPU VM
2. Run: `python scripts/task3/teleop_record.py --episode-name demo_01 --livestream --public-ip 34.61.210.0`
3. Connect WebRTC client to `34.61.210.0`
4. Teleoperate the robot, press ESC to save
5. Download dataset: `gcloud compute scp ...`
