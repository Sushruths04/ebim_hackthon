# EBiM Task 3 — Master Execution Plan (2026-07-16)

**This document is self-contained.** It is written so that any engineer or AI
session (including a fresh Claude/Sonnet session with zero conversation
context) can execute the project from here. Read it top to bottom once, then
work the TODO checklist at the end.

---

## 1. Mission

Win points on **EBiM Task 3 (Assisted Living & Feeding)**: a mobile dual-arm
FR3 Duo robot performs a 4-stage kitchen-to-dining service cycle in Isaac Sim.

**Official rules** (verified 2026-07-16 from
https://ebim-benchmark.github.io/competition.html#tasks):

- 4 stages × 4 points = **16 points max**. Bean Recovery (Stage 3) is scored
  by recovered-bean ratio.
- Ranking tie-breaks: **highest completed stage → total score → completion
  time**.
- **"Full Autonomy only"** — the submitted solution must execute without
  human input. The rules do NOT require a learned/neural policy. Scripted
  autonomous controllers are permissible.
- Safety gates: peak head/face contact force (ISO/TS 15066) and watchdog
  interventions are hard failures.
- Submission: **public GitHub repo + Dockerfile + README with execution
  instructions**. Source disclosure optional; weights may be linked
  externally.
- **Phase I (simulation) deadline: Aug 3, 2026.** Real-robot windows:
  Aug 10–19 and Aug 20–31, 2026.

**Today is July 16 → 18 days to the simulation deadline.**

## 2. Core Strategy (READ THIS BEFORE CODING ANYTHING)

### Primary track — Scripted Autonomous Controller (the point-scorer)

Build a **finite-state-machine (FSM) controller** that reads privileged
simulator state (object poses from PhysX/Fabric APIs) and drives the robot
through all 4 stages using the IK / base-control stack that ALREADY EXISTS in
this repo. This is:

- Legal (autonomous ≠ learned).
- The proven approach: scripted FSMs over privileged state are the standard
  strong baseline in manipulation competitions (see Real Robot Challenge
  winners, arXiv:2109.15233).
- The only approach guaranteed to produce a submittable, point-scoring
  artifact within 18 days — the binding constraint is engineering time, not
  compute (see §4 budget).
- **Solves the no-teleoperation constraint**: nothing in this track ever
  needs a human at a keyboard.

### Secondary track (stretch, only after primary is submitted) — Learned policy

The scripted controller doubles as a **demonstration generator**. Record its
successful rollouts as a LeRobot dataset, then fine-tune a small open VLA
(SmolVLA first; GR00T N1.5/1.6 or pi0/openpi if budget allows) via behavior
cloning. Do this ONLY if the primary track is finished and packaged.

### What we explicitly DE-PRIORITIZE

- Building a physical Isaac Lab PPO environment (arms + grasping + collisions
  as an RL env). It's the slowest path to points. The existing kinematic PPO
  work (`task3_rl/`) already validated the training pipeline; keep it as
  evidence, don't extend it before the FSM works.
- Vision/perception. Use privileged state. The competition scores task
  completion in sim; nothing published requires onboard perception for
  Phase I. (Re-verify on the competition page before submission.)
- Keyboard/GELLO teleoperation. Not needed anywhere in this plan.

## 3. Current Status Inventory (verified 2026-07-16)

Repository: fork `github.com/Sushruths04/ebim_hackthon` of
`github.com/EBiM-Benchmark/benchmark`. Local checkout at
`D:\Mini Thesis\EBIM HAckthon\EBiM-benchmark` has full upstream history plus
the Lightning AI work merged in (commit "Merge Task 3 Lightning workflow").

### Working and verified

| Component | Location | Evidence |
|---|---|---|
| Task 3 room + robot assets | `assets/robot_room.usd`, `assets/mobile_fr3_duo_v0_2.usd` | loads; Stage 1 integration test 5/5 |
| Scene launcher (spawn presets, 300 beans, head placement a–i) | `scripts/scenes/scene_robot_room_keyboard.py --task task3` | runs on L40S |
| Grading for all 4 stages | `scripts/evaluation/task3/grading.py` + `tests/test_grading.py` | "7 task3 all grading tests passed" |
| Live grading integration tests | `scripts/evaluation/task3/integration_test.py` | headless: stage1 5/5, stage2 4/4, stage3 4/4, stage4 5/5 (these move prims kinematically — they validate GRADING, they are NOT autonomous runs) |
| Dual-arm Lula IK (per-arm, robot-base frame targets) | wired inside `scene_robot_room_keyboard.py`; config in `scripts/config/task3_teleop/` | drives arms in interactive runs |
| Mobile base control helpers | `scripts/common/tmr_base_control.py` | drives base in interactive runs |
| `TeleopCommand` boundary | `scripts/common/` (simulator-independent command dataclass; accepts per-arm Cartesian targets OR direct 7-joint tuples, gripper, base twist) | documented in README; THIS is where the FSM plugs in |
| RSL-RL PPO pipeline end-to-end | `task3_rl/` (kinematic Stage 1 env, training script, unit tests) | 500-iter L40S run, checkpoints in `models/` |
| Lightning AI workflow automation | `scripts/task3/lightning_workflow.sh` (bootstrap/status/verify/train/stop) | used on L40S studio |
| LeRobot recording reference | `DEMO/record.py` + README section | from upstream; not yet used for task3 |

### Not built yet (this plan builds it)

- Any autonomous robot behavior (all past runs were keyboard-teleoperated or
  kinematic prim motion).
- Skill primitives (navigate, reach, grasp, lift, place, scoop, pour).
- The Stage 1–4 FSM.
- Episode runner with seeding, logging, video recording, and grading hookup.
- Dockerfile + submission README.
- Any learned policy on the real physics.

### Known asset gaps (non-blocking)

- `assets/ikea_knock_box.glb` and `assets/ikea_scale.glb` missing (optional
  props; room loads without them).
- Startup USD `visuals` warnings and NGX/ROS warnings — cosmetic.

## 4. Compute & Budget Plan

**Total budget (updated 2026-07-16): ≈ 1,170 EUR** — Google Cloud ~1,000 EUR,
Modal ~100 EUR, Lightning AI ~70 EUR. Compute is NOT the bottleneck anymore;
engineering time is. Budget generously, parallelize, but never leave idle
GPUs running.

### Hardware constraint you MUST respect

Isaac Sim **rendering requires RT cores**. On GCP that means **L4 GPUs (g2
instance family)** — A100/H100 have no RT cores and cannot do the RTX
rendering needed for cameras/video. Rule of thumb:

- Isaac Sim / Isaac Lab episodes (with camera recording) → **L4 (GCP g2) or
  L40S (Lightning)**.
- Pure PyTorch training (VLA fine-tune, BC) → **A100 (GCP/Modal)**; no Isaac
  needed there.

### Allocation

| Resource | Role | Sizing / cost |
|---|---|---|
| **GCP g2-standard-16 (1×L4, 24 GB) — "SIM-DEV"** | Primary Isaac dev/run box: FSM development, episode runs, verification | ≈ $1.2–1.4/hr on-demand (≈ $0.6/hr spot). Even 300 hours ≈ 400 EUR — well within budget. |
| **GCP g2 second instance — "SIM-EVAL"** (spin up from a disk image of SIM-DEV) | Parallel batch work: evaluation matrices, demo-dataset generation, while SIM-DEV develops the next stage | Spot instances; start in Phase 3+. |
| **GCP a2 (1×A100 40/80 GB)** | Phase 7 VLA fine-tuning (GR00T / pi0 LoRA) | ≈ $3–4/hr; a 10 k-step LoRA run ≈ 6–7 h ≈ 25 EUR. |
| **Modal (~100 EUR)** | Containerized training jobs: SmolVLA fine-tune, dataset post-processing, TensorBoard-style eval sweeps | **CONFIGURED**: workspace `mitvho09` (https://modal.com/apps/mitvho09/main), CLI authenticated on the local Windows terminal, verified 2026-07-16 with zero running apps. Serverless = zero idle cost, but see hard rule 2 below. NOT for Isaac Sim. |
| **Lightning AI (~70 EUR, L40S)** | Already-configured fallback + quick interactive debugging (caches/workflow exist) | Use until GCP quota lands, then switch primary work to GCP. |
| Local Windows machine | git, code review, plan tracking, USD inspection | No GPU sim work here. |

### GCP setup (manual, DO THIS FIRST — quota approval can take 24–48 h)

1. Create project, enable billing + Compute Engine API.
2. **Request GPU quota**: `NVIDIA_L4` (2) and `NVIDIA_A100` (1) in one region
   (e.g., `us-central1` or `europe-west4`), plus matching
   `GPUS_ALL_REGIONS ≥ 3`.
3. Create a 200 GB+ boot disk VM (Ubuntu 22.04), install NVIDIA driver,
   Docker, NVIDIA Container Toolkit, `docker login nvcr.io`.
4. Clone the fork, run `lightning_workflow.sh bootstrap` equivalents (the
   compose stack is host-agnostic Linux + Docker; no X11 needed for headless).
5. **Snapshot the disk once Isaac runs** — every later VM (SIM-EVAL, replacements)
   boots from this image in minutes instead of re-downloading ~30 GB of
   Isaac images/caches.
6. Set a **billing alert at 250/500/750 EUR** and use spot instances for
   batch work (episode generation restarts cleanly; the runner is seeded).

### Budget rules (HARD RULES — non-negotiable, set by the project owner)

1. **Start on the SMALLEST GPU that could plausibly work; escalate only on
   measured evidence** (OOM error, or a measured throughput number that
   makes the deadline impossible). NEVER pick a bigger GPU "to be safe" or
   on gut feeling. Escalation ladder:
   - Generic PyTorch / dataset work: CPU → T4 → A10G/L4 → A100-40GB → A100-80GB.
   - Isaac Sim (RT cores required): L4 first; L40S only if L4 is measurably
     insufficient (log the evidence in `docs/gpu_budget_log.md` before
     switching).
   - VLA fine-tuning: try LoRA on A10G/L4 with gradient accumulation before
     ANY A100 request; A100 only when the model provably doesn't fit.
2. **Modal: stop the app whenever work pauses.** At the end of every working
   session (and before any break): `modal app stop <app-name>` / `modal app
   list` must show nothing running. Prefer batch `modal run` jobs that exit
   on completion over long-lived `modal deploy` / `modal serve` apps; set
   `timeout=` and `scaledown_window` (idle timeout) low on every function so
   a forgotten container kills itself. Never leave a Modal app running
   unattended overnight.
3. **GCP: stop/delete instances at session end** (`gcloud compute instances
   stop`); idle GPUs are the #1 waste. Use spot instances for all batch work.
4. Develop and debug **headless**; recorded video is the debugging GUI.
5. Write and unit-test all FSM/skill code locally/CPU first; GPUs execute
   and verify only.
6. Log spend per session in `docs/gpu_budget_log.md` (date, platform,
   machine/GPU type, hours, EUR, outcome — and, when escalating GPU size,
   the evidence that forced it).
7. Reserve **≥ 100 EUR** for final-week evaluation matrices + submission
   dry-runs.
8. Budget is a ceiling, not a target: the cheapest configuration that meets
   the phase's exit criterion is the correct one.

## 5. Architecture of the Autonomous Controller

```
                    ┌────────────────────────────────────┐
                    │  Episode Runner (headless-capable)  │
                    │  seed, head placement, logging,     │
                    │  video recorder, grading hookup     │
                    └────────────────┬───────────────────┘
                                     │
                    ┌────────────────▼───────────────────┐
                    │  Task 3 FSM (stages 1→4)            │
                    │  preconditions / postconditions /   │
                    │  timeouts / retry budgets / e-stop  │
                    └────────────────┬───────────────────┘
                                     │ calls
                    ┌────────────────▼───────────────────┐
                    │  Skill primitives                   │
                    │  navigate_to(x,y,yaw)               │
                    │  reach(arm, pose)  grasp(arm)       │
                    │  lift(arm, dz)     place(arm, pose) │
                    │  scoop(arm)        hold(secs)       │
                    │  pour(arm, target)                  │
                    └────────────────┬───────────────────┘
                                     │ emits
                    ┌────────────────▼───────────────────┐
                    │  TeleopCommand stream (existing     │
                    │  boundary: Cartesian targets → Lula │
                    │  IK, gripper bools, base twist)     │
                    └────────────────┬───────────────────┘
                                     │
                    ┌────────────────▼───────────────────┐
                    │  Existing runtime adapter →         │
                    │  Isaac Lab articulation targets     │
                    └────────────────────────────────────┘
```

Key implementation facts:

- **Plug in at `TeleopCommand`.** The repo README explicitly says future
  autonomous sources belong "upstream of the simulator-independent
  TeleopCommand boundary." The FSM is exactly such a source. Do not fork the
  IK/composition/runtime code — reuse it.
- **State reading:** with PhysX Fabric enabled, do NOT read moving body poses
  from USD attributes (they go stale). Use PhysX / Fabric-aware / tensor APIs
  (the repo README warns about this; the integration tests and
  `task3_rl/live_stage1_smoke.py` show working pose-reading patterns).
- **Cartesian targets live in the robot-base frame** and are carried along
  when the base moves (existing behavior). Skills must account for this:
  freeze arm targets during base motion, or command in world frame and
  re-transform each tick.
- **Grasp reality check:** rigid-body grippers on thin utensils are
  physics-fragile. Acceptable mitigations, in order of preference:
  (a) tune gripper force/friction/contact offsets;
  (b) grasp the TRAY (large, graspable) and let utensils ride on it —
      Stage 1 only requires objects to reach the dining area;
  (c) as last resort for a stage, use a kinematic attach (fixed joint created
      on gripper-contact) — check competition FAQ/Discord whether this is
      allowed before relying on it in the submission.
- **Known coordinates** (from repo, use as initial FSM waypoints):
  - Robot task3 spawn: `(-4.6, 2.7, 0.0)`, yaw −90°.
  - Bowl/beans: `(-4.3, -1.467, 0.754)`.
  - Kinematic Stage-1 curriculum used start `(-4.282, -1.618)` (kitchen tray
    area) with workspace x∈[−5.25,−1.75], y∈[−2.50,2.75] — the dining goal
    is encoded in `task3_rl/stage1.py` (`Stage1TaskCfg.goal_xy`).
  - Head placements: presets `a`–`i` via `--head-placement`.
  - Sink region: `assets/sink_boundary.usdc`; grading defines the exact
    regions — read `scripts/evaluation/task3/grading.py` FIRST and treat its
    region definitions as the source of truth for all FSM target positions.

## 6. Phased Plan with Verification Gates

Every phase has an **exit criterion**. Do not start the next phase until the
current one's criterion is met and logged. After ANY change, re-run the fast
grading tests (`python -B scripts/evaluation/task3/tests/test_grading.py`)
plus the phase's own verification.

### Phase 0 — Sync & bootstrap (Day 0, ~1 GPU-hour)

0. **Immediately (manual, 15 min): submit the GCP GPU quota requests** from
   §4 — approval latency (24–48 h) is the only thing that can delay the
   compute plan. Also register the team on the competition page if not done.
1. On the local Windows machine: push the merged local `main` to the fork.
   The fork's old unrelated history will be replaced — it is fully contained
   in the local merge commit, nothing is lost:
   ```bash
   cd "D:/Mini Thesis/EBIM HAckthon/EBiM-benchmark"
   git push origin main --force-with-lease
   ```
2. On a Lightning GPU studio (L40S):
   ```bash
   cd /teamspace/studios/this_studio
   git clone --recurse-submodules https://github.com/Sushruths04/ebim_hackthon.git EBiM-benchmark
   cd EBiM-benchmark
   docker login nvcr.io        # NGC key from the Lightning account secrets
   bash scripts/task3/lightning_workflow.sh bootstrap
   bash scripts/task3/lightning_workflow.sh verify
   ```
   (If the studio already has the repo, `git pull` + re-run verify.)
3. Create `docs/gpu_budget_log.md` and log this session.

**Exit criterion:** `verify` passes (grading tests + RL unit tests) on the
GPU studio from the pushed fork.

### Phase 1 — Headless episode runner + video recorder (Days 1–2, ~3 GPU-hours)

Build `scripts/task3/run_episode.py`:

- Launches the task3 scene headless (reuse `scene_robot_room_keyboard.py`
  composition code as a library, or subprocess it with flags — prefer
  refactoring the scene build into an importable function).
- Args: `--seed`, `--head-placement {a..i,random}`, `--policy
  {idle,scripted}`, `--max-seconds`, `--record-video`, `--out-dir`.
- Deterministic reset: fixed seed → identical object poses. Log every episode
  as JSON: seed, head placement, git commit, asset hashes, per-stage grading
  result, wall time.
- Off-screen RGB camera recording to MP4/frames per episode (extend
  `scripts/task3/capture_static_view.py` which already does off-screen RGB;
  `scripts/task3/record_robot_demo.py` from the Lightning session may
  already do most of this — READ IT FIRST).
- After the episode, call the stage grading functions and print one
  `EPISODE_RESULT` JSON line (mirror the `STAGE_RESULT` convention in
  `integration_test.py`).

**Why this first:** with no human watching (user is away) and headless GPU
sessions, recorded video + JSON results are the ONLY feedback loop. Every
later phase depends on it.

**Exit criterion:** `run_episode.py --policy idle --record-video` produces a
video + `EPISODE_RESULT` JSON with grading executed (score will be 0 — fine),
twice with the same seed giving identical object spawn poses.

### Phase 2 — Skill primitives (Days 2–5, ~8 GPU-hours)

Create `scripts/task3/skills/` (or `task3_autonomy/` package):

1. `navigate_to(x, y, yaw)` — closed-loop base motion using
   `tmr_base_control` helpers + live base pose; stop tolerance ~3 cm / 3°.
   Includes a static waypoint router to avoid the wall/partition (the
   integration tests route "y before x" — copy that idea).
2. `reach(arm, world_pose)` — transform to robot-base frame, feed Cartesian
   target through TeleopCommand, wait until end-effector within tolerance or
   timeout. Reuse existing per-arm Lula IK.
3. `grasp(arm)` / `release(arm)` — gripper close/open + contact/width check
   to confirm hold.
4. `lift(arm, dz)`, `place(arm, world_pose)` — compositions of `reach`.
5. Each skill: explicit timeout, success predicate, and failure return (never
   hang). Unit-test the pure-math parts (frame transforms, tolerances)
   locally without Isaac.

Verification scripts (each is a tiny `run_episode`-based scenario):
- `verify_navigate.py`: drive kitchen → dining → kitchen; assert final pose.
- `verify_grasp_lift.py`: **THE critical de-risking test** — navigate to the
  tray, grasp it (or the cup first: easier geometry), lift 10 cm, hold 3 s,
  assert the object's z rose and stayed; record video.

**Exit criterion:** `verify_grasp_lift.py` succeeds ≥ 8/10 seeded runs with
video evidence. If rigid grasping proves unstable after ~2 days of tuning,
switch to mitigation (b)/(c) from §5 and move on — do not stall here.

### Phase 3 — Stage 1 autonomous completion (Days 5–7, ~6 GPU-hours)

FSM for Stage 1 (Table Setup): navigate to kitchen pickup zone → grasp tray
(utensils riding on it) → transport to dining area (waypoint route) → place
at the seat targets defined by `grading.py` → release → retreat.

- Read Stage 1's exact scoring predicate in `grading.py` and place objects to
  satisfy IT, not your intuition.
- Retry budget: e.g., 2 re-grasp attempts; on exhaustion, proceed (partial
  points beat a hang).

**Exit criterion:** `run_episode.py --policy scripted --stage 1` scores
≥ 4/5 on ≥ 7/10 runs across seeds and ≥ 3 head placements. **This is the
first real point on the board — commit, push, and tag it (`v0.1-stage1`).**

### Phase 4 — Stages 2–4 (Days 7–12, ~10 GPU-hours)

Order by expected difficulty (do 4 before 2–3 if beans prove hard —
remember ranking = highest stage completed FIRST, so a run that completes
stages 1→4 with weak bean scores may still need every stage attempted in
sequence; check whether stages must be sequential in the official rules).

- **Stage 2 (Feeding):** right arm scoops beans (spoon path: enter bowl at
  ~30–45° pitch, drag through bean pile, level out, lift), left arm steadies
  bowl; move spoon to a pose ~20 cm in front of the head (the integration
  test's stage-2 geometry documents the exact target), hold ≥ 3 s
  (watch the head-force safety gate: approach slowly, stop short), return
  beans to bowl. Bean-on-spoon physics will need iteration: tune spoon
  friction/contact offsets; a deeper scoop path retains more beans.
- **Stage 3 (Bean Recovery):** transport bowl to recycling container, tilt/
  pour. Scored by ratio → maximize but don't perfect. Pour slowly, low
  height, funnel position from `grading.py`'s recovery-sphere definition.
- **Stage 4 (Cleanup):** navigate utensils back to the sink region
  (`sink_boundary.usdc`); pure pick-place, easiest of the three — consider
  implementing it right after Stage 1 to lock in "highest stage" ranking.

**Exit criterion per stage:** ≥ 3/4 points on ≥ 6/10 seeded runs, video
recorded. Tag each (`v0.1-stageN`).

### Phase 5 — Full-run robustness + speed (Days 12–15, parallel on SIM-EVAL)

- Chain 1→2→3→4 in one episode; fix inter-stage state carryover (arm poses,
  gripper state, remembered object poses).
- Evaluation matrix (budget now allows a real one): all 9 head placements ×
  10 seeds = **90 headless runs** on the SIM-EVAL spot instance, launched as
  one batch script. Store the JSON results table in `docs/eval_results.md`.
- Run the matrix **continuously from Phase 3 onward** (nightly batches on
  SIM-EVAL): every stage merge gets a fresh matrix, so regressions surface
  within a day instead of at the end.
- Optimize completion time ONLY where free (higher base speed on straight
  segments; skip unnecessary settles) — time is the LAST tie-break.

**Exit criterion:** median total score across the 90-run matrix, documented;
no run hangs or crashes (watchdog-clean).

### Phase 6 — Submission packaging (Days 14–16, ~3 GPU-hours) — DO NOT LEAVE TO THE LAST DAY

- `Dockerfile` that reproduces the run: FROM the Isaac Lab image used by the
  compose stack, copy repo, entrypoint = one deterministic full-run command.
- Rewrite fork README top section: what this is, exact execution command,
  expected output, hardware requirements, link to result videos.
- Public repo check (it already is), registration (team name + contact
  email) per the competition page.
- Dry-run the Dockerfile on a fresh Lightning studio (fresh account caches =
  honest test of the instructions).
- Submit BEFORE Aug 1 to leave a 2-day buffer for form/portal problems.

**Exit criterion:** a teammate-free, from-scratch `docker build && docker
run` produces a graded full episode. Submission confirmed.

### Phase 7 (funded stretch — start once Phase 3 is done, in PARALLEL) — Learned policy

With the ~1,170 EUR budget this track is now funded and can run in parallel
on separate machines from Phase 4 onward (scripted FSM work never waits for
it, and it never blocks the submission):

1. Add `--record-lerobot` to `run_episode.py`: dump obs (joint states,
   base pose, gripper, 2–4 camera streams) + actions (TeleopCommand stream)
   per step, LeRobot v2 dataset format (upstream `DEMO/record.py` +
   lerobot_ros2 guide show the schema).
2. Batch-generate **500–1,000 successful scripted episodes** with randomized
   seeds/head placements on the SIM-EVAL L4 spot instance (≈ automated
   MimicGen-style data generation, except the source demos are scripted —
   no teleop needed at any point). Start with Stage-1-only episodes as soon
   as Phase 3 lands; extend to full runs later. Store the dataset in a GCS
   bucket.
3. Fine-tune BOTH of these (budget covers it; compare honestly):
   - **SmolVLA (~450 M, LeRobot-native)** — first: trains in hours on a
     Modal A10G/A100 job (~10–20 EUR); native LeRobot dataset support;
     fastest signal on whether BC-from-scripted-demos works at all.
   - **GR00T N1.5/N1.6** (NVIDIA) or **pi0/openpi LoRA** — on a GCP A100;
     ≈ 6–7 h / 10 k steps ≈ 25 EUR per run; 2–3 runs with different data
     mixes are affordable. GR00T fits the Isaac ecosystem; pi0's flow
     matching gives the smoothest contact-rich trajectories.
4. Evaluate every checkpoint through the SAME `run_episode.py` harness
   (`--policy learned --checkpoint ...`) on the L4 sim machines — a learned
   policy is only as good as its harness score.
5. Optional second iteration (DAgger-style): collect the learned policy's
   failure episodes, generate scripted corrections for those states, retrain.
6. Submit the learned policy ONLY if it beats the scripted FSM on the
   Phase 5 matrix. Either way the dataset + fine-tunes are thesis/portfolio
   material.

## 7. Automation Rules (user is away; no teleop ever)

- Every capability must be runnable as a single headless command with JSON +
  video output. If a step "needs someone to watch the GUI," redesign it.
- Long GPU runs: launch with `nohup ... &` or tmux, write progress to a log
  file, and ALWAYS auto-stop the container/instance at the end of the script
  so an unattended run can't burn credits overnight.
- Commit + push to the fork at every exit criterion. The fork is the source
  of truth; local Windows, Lightning studios, and GCP VMs are all disposable
  clones.

### 7.1 Complete list of manual steps (there is NO teleoperation or keyboard control anywhere in this plan)

Everything the human must do, total. All are admin tasks doable in minutes
from any laptop; none involve controlling the robot:

| # | Manual step | When | Time |
|---|---|---|---|
| 1 | GCP: create project, enable billing, **request L4×2 + A100×1 GPU quota** | Day 0 (approval takes 24–48 h) | 15 min |
| 2 | Create NGC API key; `docker login nvcr.io` on each new machine/image | Once per machine (baked into the disk snapshot after the first) | 5 min |
| 3 | Competition **registration** (team name + contact email) | Day 0 | 5 min |
| 4 | Set GCP billing alerts (250/500/750 EUR) | Day 0 | 5 min |
| 5 | Review recorded episode videos (async QA — recommended, not required) | Whenever convenient | minutes |
| 6 | Approve the go/no-go on any physics shortcut (e.g., kinematic attach) after checking Discord/FAQ legality | Phase 2–4, only if needed | 10 min |
| 7 | **Submission form** on the competition portal | By Aug 1 | 15 min |

Every robot behavior — navigation, grasping, feeding, pouring, cleanup, demo
recording for the learned track — is scripted and headless. The keyboard
teleop code in the repo remains unused by this plan.

### 7.2 Definition of Done — the visual-proof protocol (MANDATORY for every task)

The project owner reviews progress asynchronously via visual proof, and a
task must NEVER need to be reopened. Therefore **no checklist item may be
marked done without a proof bundle**, and once proven, a task is frozen.

Every completed task produces a proof bundle in `proofs/<phase>-<task-slug>/`
(committed to the repo, or in the GCS bucket with a committed link file if
videos are large):

1. **Video** (`proof.mp4` or frames) — the off-screen recording of the
   verification run showing the behavior working. This is non-negotiable for
   anything the robot does; for pure-code tasks (e.g., frame-math unit
   tests), a terminal transcript file is the equivalent.
2. **Result JSON** (`result.json`) — the `EPISODE_RESULT`/test output with
   score, seed, head placement, git commit hash, date.
3. **Repro command** (`repro.txt`) — the exact one-line command that
   regenerates the proof from that commit.
4. **A one-line entry appended to `docs/eval_results.md`**: task, date,
   commit, score, link to the proof bundle.

Completion rules:

- The TODO checkbox in §10 may only be ticked in the same commit that adds
  the proof bundle. Tick + tag (`v0.1-<task>`), push.
- **Freeze rule:** once ticked, a task is only ever touched again if the
  nightly regression matrix (Phase 5 batches) shows it broke — and then the
  fix must produce a NEW proof bundle. Never "improve" a frozen task
  speculatively.
- **Regression guard:** the SIM-EVAL nightly batch re-runs the verification
  scenario of every frozen task (they are all seeded one-liners, so this is
  cheap). A frozen task that fails its own repro command = highest-priority
  bug the next morning.
- Executor sessions (Claude/Sonnet) must SEND the video/result to the owner
  at each task completion (SendUserFile or a pushed link) — the owner should
  be able to see progress from a phone without asking.

## 8. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Rigid-gripper grasping unstable on utensils | HIGH | Grasp tray not utensils (Stage 1/4); tune contacts; kinematic-attach fallback (verify legality) |
| Bean scooping/pouring physics fails | HIGH | Partial credit is fine (ratio-scored); tune spoon contact offsets; deep-scoop path; do Stage 4 before 2–3 |
| GCP GPU quota not approved in time | MEDIUM | Request Day 0; Lightning L40S covers Phases 0–2 meanwhile; Modal for any training |
| Wrong GPU type rented (A100 for Isaac Sim → no RTX rendering) | MEDIUM | Hard rule in §4: Isaac = L4/L40S only; A100 = PyTorch training only |
| Budget overrun from idle instances | LOW (was MEDIUM) | Billing alerts, spot instances, stop-on-exit in every batch script, spend log |
| Head-force safety gate trips in Stage 2 | MEDIUM | Slow approach, stop ≥ safety margin from head, cap arm speed near head |
| `TeleopCommand` boundary needs plumbing to accept a programmatic source | MEDIUM | It was designed for this (README); if blocked, drive the same functions the keyboard handler calls |
| Fabric stale-pose bug corrupts state reading | MEDIUM | Only PhysX/tensor APIs for dynamic poses (never USD xforms while playing) |
| Competition portal/rules surprises | LOW | Re-read competition page + Discord weekly; submit by Aug 1 |
| Fork force-push loses something | LOW | The old fork history is fully merged locally already; local reflog is a second safety net |

## 9. Model & Training Cheat-Sheet (for Phase 7 only)

| Model | Size | Why / when | Where to train |
|---|---|---|---|
| SmolVLA | ~0.45 B | LeRobot-native, cheapest fine-tune, good for single-task BC | Lightning L40S or Modal A10G, few hours |
| GR00T N1.5/N1.6 | ~2–3 B | Strongest open results on manipulation; NVIDIA/Isaac ecosystem fit | Modal/GCP A100 |
| pi0 / openpi (+pi0.5) | ~3 B | Flow matching → smoothest contact-rich trajectories; LoRA ≈ 6–7 h/10 k steps | Modal/GCP A100 |
| OpenVLA(-OFT) | 7 B | Only if abundant compute appears | GCP A100-80GB |

Training recipe (any of the above): behavior cloning on 100–300 scripted-
success episodes → evaluate in harness → (optional) DAgger-style round:
collect failures, add scripted corrections, retrain. Skip RL fine-tuning
unless everything else is done — PPO on the physical scene is out of budget.

## 10. Detailed TODO Checklist

### Phase 0 — Sync & bootstrap
- [x] GCP project + billing + L4×2/A100×1 quota request — submitted
      2026-07-16 17:33 UTC via `gcloud alpha quotas preferences create`
      (project `gen-lang-client-0186028838`, billing already enabled):
      `NVIDIA-L4-GPUS-per-project-region` (2, us-central1, preference id
      `ebim-l4-us-central1`), `NVIDIA-A100-GPUS-per-project-region` (1,
      us-central1, `ebim-a100-us-central1`), `GPUS-ALL-REGIONS-per-project`
      (3, `ebim-gpus-all-regions`). All three show `grantedValue: 0`
      (pending review) as of submission — check with `gcloud alpha quotas
      preferences list --service=compute.googleapis.com
      --project=gen-lang-client-0186028838`. Approval still takes 24-48h.
- [ ] **(Manual)** Set GCP billing alerts (250/500/750 EUR) — not
      submittable via CLI in a way that's safe to do unattended (alert
      recipients/thresholds are a judgment call); still needs you.
- [ ] **(Manual)** Competition registration (team name + email) — status not verifiable by the executor session; confirm done
- [x] Push merged local main to fork — pushed as a clean single-commit
      snapshot (`9cc7088`) instead of full history: the fork's old history
      contained unrecoverable Git LFS objects (dead upstream
      `amp_for_hardware` quadruped meshes) that blocked a full-history
      force-push. Prior fork state backed up at `backup/pre-sync-2026-07-16`.
      Local `main` keeps its full real history untouched. (2026-07-16)
- [ ] Lightning GPU studio: clone/pull fork, `docker login nvcr.io` —
      **BLOCKED**: `ssh lightning-p4` returns `Permission denied (publickey)`,
      studio appears stopped. Needs restart from the Lightning web console.
- [ ] `lightning_workflow.sh bootstrap` then `verify` — all tests pass
- [x] Create `docs/gpu_budget_log.md`, log session hours (2026-07-16)
- [ ] Once quota lands: build SIM-DEV GCP VM (L4, driver, Docker, NGC, repo, Isaac up) and **snapshot the disk**
- [ ] Re-run `verify` on SIM-DEV; it becomes the primary machine (Lightning = fallback)

### Phase 1 — Episode runner
- [x] Read `scripts/task3/record_robot_demo.py` and `capture_static_view.py`
      (2026-07-16) — finding: the scene-build composition functions
      (`configure_keyboard_control_stage`, `configure_robot_room_stage`,
      `make_control_scene_cfg`) are ALREADY importable/reusable exactly as
      `record_robot_demo.py` uses them; no refactor of
      `scene_robot_room_keyboard.py` was needed.
- [x] Refactor task3 scene build into an importable function (keep CLI
      intact) — not needed, see finding above; CLI untouched.
- [ ] **AUTHORED, NOT YET RUN** `scripts/task3/run_episode.py`: seed, head
      placement, policy=idle, max time, off-screen video, grading hookup →
      `EPISODE_RESULT` JSON — written 2026-07-16 against the documented
      APIs but never executed (no live Isaac Sim GPU access this session:
      Lightning studio SSH down, GCP quota not granted). Known unverified
      risk: `isaacsim.core.prims.RigidPrim` construction/`initialize()`
      requirements are version-dependent and unconfirmed. Do NOT tick the
      remaining Phase 1 boxes below until this has actually run.
- [ ] Deterministic reset verified (same seed → same spawn poses, 2 runs)
- [ ] Off-screen video recording per episode
- [ ] Grading hookup → one `EPISODE_RESULT` JSON line per run
- [ ] Commit + push (`v0.1-harness`)

### Phase 2 — Skills
- [ ] Read `scripts/evaluation/task3/grading.py` fully; extract all region/
      target coordinates into a `task3_autonomy/constants.py`
- [ ] `navigate_to()` + waypoint router (y-before-x wall avoidance)
- [ ] `verify_navigate.py` passes (kitchen↔dining, ±3 cm/3°)
- [ ] `reach()` via TeleopCommand→Lula IK, world-frame wrapper
- [ ] `grasp()`/`release()` with hold-confirmation predicate
- [ ] `lift()`, `place()`
- [ ] Local unit tests for frame math (no Isaac needed)
- [ ] `verify_grasp_lift.py` ≥ 8/10 with video — **critical gate**
- [ ] If grasping unstable after 2 days: adopt mitigation (b)/(c), document it
- [ ] Commit + push (`v0.1-skills`)

### Phase 3 — Stage 1
- [ ] Stage 1 FSM (pickup → transport → place → release → retreat)
- [ ] Retry budget + timeouts on every FSM state
- [ ] ≥ 4/5 pts on ≥ 7/10 runs, ≥ 3 head placements, videos saved
- [ ] Commit + push + tag `v0.1-stage1`

### Phase 4 — Stages 2–4
- [ ] Stage 4 FSM (utensils → sink) — do early, it locks in ranking
- [ ] Stage 2 FSM (scoop, bimanual steady, 3 s hold at head, return beans)
- [ ] Stage 2 safety: capped approach speed near head
- [ ] Stage 3 FSM (bowl → recycling container, slow pour)
- [ ] Each stage ≥ 3/4 pts on ≥ 6/10 runs, tagged

### Phase 5 — Full-run robustness
- [ ] Spin up SIM-EVAL (spot, from snapshot); nightly eval batches from Phase 3 onward
- [ ] Chained 1→2→3→4 single-episode run
- [ ] 90-run matrix (9 head placements × 10 seeds), results in `docs/eval_results.md`
- [ ] Zero hangs/crashes; watchdog-clean
- [ ] Cheap speed optimizations only

### Phase 6 — Submission
- [ ] Dockerfile (Isaac Lab base image, one-command entrypoint)
- [ ] Fork README: execution instructions + expected output + videos
- [ ] Dry run of the Dockerfile on a FRESH GCP VM (not the snapshot — honest test)
- [ ] **(Manual)** Submit on the portal by **Aug 1** (2-day buffer)

### Phase 7 — Learned policy (parallel from Phase 3; never blocks submission)
- [ ] `--record-lerobot` flag on run_episode
- [ ] 500–1,000 successful scripted episodes on SIM-EVAL → GCS bucket
- [ ] SmolVLA fine-tune on Modal; eval through same harness
- [ ] GR00T N1.5/1.6 or pi0 LoRA fine-tune on GCP A100; eval through same harness
- [ ] Optional DAgger round on failure states
- [ ] Only swap into the submission if it beats the FSM on the Phase 5 matrix

## 11. Sources

- EBiM competition rules: https://ebim-benchmark.github.io/competition.html#tasks
- Scripted-FSM baselines in manipulation competitions: https://arxiv.org/pdf/2109.15233 (Real Robot Challenge), https://arxiv.org/pdf/2110.06192
- Privileged-state policy learning: https://arxiv.org/html/2502.15442v1
- Isaac Lab Mimic / SkillGen (automated demo generation): https://isaac-sim.github.io/IsaacLab/main/source/overview/imitation-learning/teleop_imitation.html , https://isaac-sim.github.io/IsaacLab/main/source/overview/imitation-learning/skillgen.html
- VLA model landscape 2026: https://www.roboticscenter.ai/tools/vla-models-comparison , https://www.roboticscenter.ai/vla-models/best-2026 , https://github.com/ShashwatPatil/VLA_model_comparision/blob/master/vla_model_comparison.md
- GR00T N1: https://arxiv.org/pdf/2503.14734 ; openpi: https://www.openpi.net/english.html
