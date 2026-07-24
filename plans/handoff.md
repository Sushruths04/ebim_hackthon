# TASK 3 — MASTER HANDOFF (read this FIRST, every session, any agent)

> **This is THE living handoff. A fresh Claude / Codex / OpenCode session with
> ZERO other context must be able to continue the work from this file alone.**
> It is intentionally long and dense. Do not trim it. Read it top to bottom
> before touching anything.
>
> **Canonical.** This file supersedes `docs/EXECUTION_HANDOFF_LIVE.md` (kept only
> as a pointer). The full plan is `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`.
> Objective truth = the organizer prose rules at
> https://ebim-benchmark.github.io/competition.html (NOT `grading.py`, which the
> organizers themselves label a dev smoke-test).

---

## 0. THE PROCESS EVERY SESSION MUST FOLLOW (permanent, non-negotiable)

**This process is mandatory for EVERY agent (Claude, Codex, OpenCode) on EVERY
session. It is also recorded in `AGENTS.md`. Follow it or work is lost.**

**On session START:**
1. Read this whole file (`plans/handoff.md`), then
   `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`.
2. `git pull` on branch `task3-current-clean`. Confirm the "Last commit" in §2
   matches `git rev-parse HEAD`. If not, you are out of date — pull.
3. Look at §5 "WHAT TO DO NEXT" and start the FIRST unchecked ordered step.
   Announce which step you are on.

**While working:**
4. ONE hypothesis → ONE change → ONE run. Never stack changes.
5. **Never claim a result you did not just observe.** Paste the actual
   `result.json` line / log excerpt / frame you opened THIS session. If you did
   not run it this turn, you may not state its outcome. (This is the #1 rule —
   this project has repeatedly been burned by agents inventing run results.)
6. A phase printing `"ok": true` is NOT proof anything was held. Verify with
   measured evidence (gripper angle + object-follows-end-effector + object rose).

**On session END (assume you may not get another turn — you can be cut off
mid-task by a usage limit at any moment):**
7. Update this file: §2 CURRENT STATE (new commit hash, what changed), §4 add any
   new failed attempt WITH the evidence and why it failed, §5 re-order/refresh
   WHAT TO DO NEXT so the next agent starts correctly.
8. `git add -A && git commit && git push origin task3-current-clean`. **Unpushed
   work does not exist for the next session.**
9. If you started the GPU container, STOP it at a real pause
   (`bash scripts/task3/lightning_workflow.sh stop`) — no idle GPU billing.

**If you get STUCK (3 fixes fail on the same symptom, or a design decision this
file doesn't cover):** do NOT guess a 4th time. Write the blocker into §6 NEEDS
OPUS with the evidence, commit+push, and stop. The human brings it to an Opus
session for a decision.

---

## 1. THE GOAL — what we are solving and why

**Main objective:** a fully autonomous, standard-physics FSM that completes as
many of the 4 Task 3 ("Assisted Living") stages as possible, each verified by the
REAL organizer rules, submitted by the Phase I deadline. Ranking = highest
completed stage → total score → time. So: **always advance, take partial credit,
never hang.**

**Deadlines (verified live from the competition page):**
- Phase I (simulation) submission: **Aug 10, 2026 (AoE)**.
- Phase II (real hardware, 7 cameras, NO privileged state): **Sep 10, 2026**.
  Phase II is WHY we build a perception layer now — anything relying only on
  privileged PhysX poses dies at Phase II.

**The 4 stages (real prose rules — the ONLY authoritative spec):**
1. **Table Setup** — carry **plate, cup, bowl-with-beans, spoon** (4 objects,
   **NO tray**) from the kitchen to **3 of 6 randomly-assigned seats**. Objects
   start stacked on a plate in the kitchen. (4 pts)
2. **Feeding** — **bimanual**: one arm holds the spoon, one steadies the bowl;
   scoop beans, hold at the head **≥ 3 s**, return the beans. (4 pts)
3. **Bean Recovery** — empty beans into the recycling bin, scored by recovered
   ratio (≥0.8→2, ≥0.9→3, =1.0→4). (4 pts)
4. **Cleanup** — return all four utensils to the marked sink region. (4 pts)

**Safety = HARD FAIL:** peak head/face force (ISO/TS 15066) + watchdog. Stage 2
approach speed/standoff is the safety lever — approach the head slowly, stop short.

**Architecture (decided, do not re-litigate):** one scripted orchestrator reads a
world state and calls modular skills — most scripted, learned models ONLY for the
two hard skills (grasp, scoop) and ONLY if scripted stays <70% after auto-retry.
Perception is pretrained (no training). An auto-verifier + bounded-retry + JSON
memory replaces the human manually watching runs. **RL/PPO is NOT needed. A VLA
(e.g. MolmoAct 2) is a Phase-II / thesis asset, NOT for the Aug 10 sprint
(embodiment mismatch — our robot is a Mobile FR3 Duo — plus it needs
embodiment-matched fine-tune data we don't have yet).**

---

## 2. CURRENT STATE — what's done, what's in progress (detail)

- **Branch:** `task3-current-clean`. **Last commit: `3311a0b3`** (pushed to
  origin `github.com/Sushruths04/ebim_hackthon`). Confirm with `git rev-parse HEAD`.
  (This section was stale — it said `3fb6ddc8` but HEAD was already 6 commits
  ahead: `319419c7`/`0eb76f4d` LEVER 1 recenter code, `a2105f70` LEVER 2
  `grasp_base_hold_kp` param, `3311a0b3` LEVER 3 CLI args. That prior session
  ended after writing the code but WITHOUT running/verifying any of it on GPU
  and WITHOUT updating this file — a violation of §0 rule 7/8. Corrected now.)
- **Overall: 0 of 4 stages have a real GPU proof bundle.** The blocker is the
  grasp (see §4). Everything below the grasp (navigate/place/carry) is
  comparatively easy once grasp holds.
- **2026-07-24 session (this one) found the VM in a bad state on connect:**
  5 concurrent `run_world_isaac_grasp.py` processes were all running at once
  inside the container (started 19:41–20:29, one pair being exact duplicates
  of the same base-param command, plus kp=8 and kp=12 variants) — a clear
  violation of the "ONE run at a time" rule from a prior session that
  launched them and got cut off before waiting for results or cleaning up.
  Worse: they were ALL writing to the same default `--out-dir`
  (`outputs/task3_world_isaac_grasp/result.json`), so the one result.json
  found on disk was a race with unknown provenance (couldn't tell which run
  produced it — it has no kp field in its output) and 5-way GPU contention
  meant none of them are trustworthy anyway (`nvidia-smi` showed only 6% util
  after 30-92 min of "running"). **Killed all 5** (had to kill via
  `docker exec ... kill -9` with container-local PIDs, not host PIDs — host
  PIDs get "operation not permitted" since procs run as root inside the
  container). GPU confirmed clean (0%/0MiB) after kill. Relaunched ONE clean
  Lever-1 test with a dedicated `--out-dir` (`..._lever1_clean`) so this
  doesn't happen again. **Lesson for future sessions: always check
  `ps aux`/`docker exec ... ps aux` for stragglers before launching a new
  run, and always pass a unique `--out-dir` per run.**

**DONE:**
- **T0 (CPU, commit `1d1ab632`):** committed the `task3_pipeline/` orchestration
  package into git; retargeted Stage 1 off the dead tray objective to the 4 real
  objects; retargeted Stage 4 off the "scorer exploit" to an honest grasp+place;
  made `task3_pipeline/outcomes.py::classify_grasp` HONEST (a grasp is SUCCESS
  only if the object actually follows the end-effector — closes the recurring
  "gripper closed on empty air" false-positive). 11 CPU tests green.
- **T1 (CPU, commit `3be4cbc5`):** resolved the "where are the seats" unknown.
  FINDING: there is NO separate seat/chair geometry in `assets/robot_room.usd`,
  and BOTH the organizers' `grading.py` and their `integration_test.py::run_stage1`
  score objects landing in the dining RECTANGLE, not per-seat. The real seating
  positions ARE in code as `TASK3_HEAD_PLACEMENTS` (9 tabletop points A–I,
  z=0.74659) in `scripts/scenes/scene_robot_room_keyboard.py`. Decision: seat
  targets = those real coordinates (see `task3_pipeline/seats.py`); placing the 4
  objects at distinct A–I points passes the only scorer that exists AND
  approximates the prose "distinct seats". 14 CPU tests green. **Do NOT go hunting
  for seat prims — they do not exist.**
- **Stage 1 CPU side is therefore COMPLETE** (plan + targets + honest verifier +
  local scorer validation all green).

**IN PROGRESS — T2 (GPU wiring, commits `ee0659dd` + `197f20f5`):**
- `task3_pipeline/world_isaac.py` is fully implemented per its own wiring-map
  docstrings (reset/navigate/reach/grasp/lift/hold/place/carry wired to
  `DualArmController` + `TmrBaseAdapter` + `verify_grasp_lift.py` geometry;
  `reach()` implements the stance-first reach idea; `grasp()` uses
  `verify_grasp_lift.object_follows_end_effector` for the honest hold check).
- A GPU harness exists: `scripts/task3/run_world_isaac_grasp.py`.
- The GPU environment is confirmed working (see §7): SSH live, container up, L4
  visible, `cuda:0`, no CPU fallback.
- **BLOCKER:** the grasp does not achieve a real hold on the Lightning L4. This is
  NOT (as far as exhaustive diffing shows) a bug in the new code — the
  historically "proven 10/10" reference grasp (`verify_grasp_lift.py`) itself does
  not reproduce on this hardware. Full detail in §4.

**Uncommitted/untracked:** several `scratch_frames_*/` dirs (local only, ignore —
do not commit them). The tray-drag files were intentionally NOT archived to
`old/` yet (import coupling — see §4); only a deprecation note was added to
`scripts/task3/probe_tray_slide.py`.

---

## 3. FILES BEING TOUCHED — exact paths and roles

**The orchestration "brain" (KEEP — adopt as-is, do not rewrite):**
- `task3_pipeline/orchestrator.py` — `Task3Pipeline`, sequences stages, emits
  `EPISODE_RESULT`.
- `task3_pipeline/chained_fsm.py`? → actually `task3_autonomy/chained_fsm.py` —
  fail-closed stage 1→2→3→4 sequencer.
- `task3_pipeline/skills.py` — `SelfCorrectingSkill`: execute → verify → retry →
  record. THIS is the auto-verifier loop that replaces manual tuning.
- `task3_pipeline/policy.py` — diagnosis-driven retry (an IK_FAIL flips stance
  before touching offsets).
- `task3_pipeline/memory.py` — JSON param/failure memory (`outputs/task3_pipeline/param_memory.json`).
- `task3_pipeline/outcomes.py` — the verifier/classifiers. `classify_grasp` is
  now honest (requires `object_follows_ee`/`object_ee_dist_m`).

**Retargeted to real rules (DONE, don't revert):**
- `task3_pipeline/config.py` — `STAGE1_OBJECTS = ("plate2","cup","bowl2","spoon2")`,
  no tray; grasp GRIDS; verifier thresholds (incl. `GRASP_HELD_MAX_DIST_M`).
- `task3_pipeline/stages.py` — `plan_stage1` (per-object → assigned seats),
  `plan_stage4` (honest utensil place).
- `task3_pipeline/seats.py` — seat targets from real `TASK3_HEAD_PLACEMENTS`.
- `task3_pipeline/world.py` — `MockWorld` (CPU-only test double). NOTE: never
  use MockWorld numbers as evidence of real progress — it is a fake world.

**⇦ THE FILE CURRENTLY BEING EDITED / the active work:**
- **`task3_pipeline/world_isaac.py`** — the REAL robot adapter. This is where T2
  work happens. Its `grasp()` / `reach()` expose `grasp_y_offset`,
  `grasp_height_above_origin_m`, `approach_stance` params for tuning.
- **`scripts/task3/run_world_isaac_grasp.py`** — the GPU harness that exercises
  world_isaac's grasp chain on one object. Run THIS to test grasp changes.

**The proven-grasp reference (reuse its geometry, do NOT edit it):**
- `scripts/task3/verify_grasp_lift.py` — constants: `STANCE=(-3.32,-1.72)`,
  `CUP_GRASP_XY=(-4.145,-1.75)`, `CUP_RIM_X_OFFSET=0.04`, `CUP_GRASP_Y_OFFSET=0.06`,
  `PREGRASP_Z=1.05`, `GRASP_Z=0.815`, `GRASP_HEIGHT_ABOVE_CUP_ORIGIN=0.068`,
  `LIFT_Z=1.10`, `TRAVEL_SPINE_M=0.45`. Function `object_follows_end_effector()`
  is the hold-check primitive.
- `scripts/common/dual_arm_lula.py` — `_solve_arm` returns previous joints on IK
  failure (arm silently freezes — relevant to fling/IK_FAIL behavior).
- `task3_autonomy/{navigation,skills,arms,rotations}.py` — nav/arm primitives.

**Scorers / scene:**
- `scripts/evaluation/task3/grading.py` — DEV smoke-test scorer only (dining
  rectangle). Not the official scorer.
- `scripts/scenes/scene_robot_room_keyboard.py` — builds the scene;
  `TASK3_HEAD_PLACEMENTS` (A–I), `/World/Scene/eval_camera` (RGB+Depth+Semantic,
  for the future perception layer).

**Proof of the historical grasp (READ but don't trust blindly):**
- `proofs/phase2-grasp-reliability/{run18_result.json, repro.txt, batch_summary.json, grasp_lift.gif}`.

---

## 4. WHAT HAS BEEN TRIED AND FAILED (specific, with WHY)

### 4.1 THE CURRENT BLOCKER — the "proven 10/10" cup grasp does not reproduce on the L4
- **What:** ran the UNMODIFIED `scripts/task3/verify_grasp_lift.py --skip-navigation`
  (the exact script behind the "10/10" claim) on the current Lightning L4 /
  container `isaac-lab-2.3.2:ebim2026`, on the EXACT commit `cf372031` that
  produced the archived proof `run18_result.json` (`passed:true, cup_lift 0.1087,
  gripper 0.076`).
- **Result:** deterministic FAIL, bit-identical across 3 runs (2× plain `python -B`,
  1× via the official `isaaclab.sh -p` launcher): `gripper_position_rad: 0.2402`,
  `cup_lift_m: 0.0`, `object_to_ee_m: 0.339`, `passed:false`.
- **The new `world_isaac.py` grasp chain** shows the same class of failure:
  descend `position_error 0.0922, strict_reach:False`; close `gripper 0.002,
  object_ee_dist 0.127, object_follows_ee False → weak_grasp`; lift `ik_fail`.
- **WHY it fails (root cause, evidence-based):** the archived pass was
  **knife-edge**. Its own telemetry shows the descend landed with a **7 cm error**
  (`position_error_m: 0.0701, strict_reach:False`) which nudged the cup ~5 cm, and
  it STILL caged at 0.076 essentially by luck. On the L4, PhysX contact-rich
  behavior differs just enough that the descend pushes the cup OFF the finger
  axis, so the gripper closes loose (0.24) on nothing and the lift finds no object.
  This is consistent with this project's entire documented history of grasp
  fragility (loose grips 0.24–0.6, "cup slips"). **The "10/10" was not robust.**
- **Ruled out (so it is NOT these):**
  - Wrong CLI args — the proof's `repro.txt` documents a zero-override command;
    matched it.
  - Launcher difference (`isaaclab.sh` vs `python`) — bit-identical, ruled out.
  - The grid's alternative offset (`--cup-grasp-y-offset 0.0`) — tried, made it
    WORSE (cup shoved 25 cm off the counter, gripper 0.7528). So it is not a
    "nudge the offset a little" fix.
  - A code/asset regression — EXHAUSTIVELY diffed every file in the execution
    path against `cf372031`: all byte-identical or changes provably unreachable by
    this code path. No code explanation.
- **Only remaining untested variable:** the Isaac Sim / PhysX / GPU-driver BUILD
  differs from whatever produced the 2026-07-18 proof (current: Isaac Lab 2.3.2,
  driver 580.159.03, L4). This is likely the real cause but cannot be checked from
  inside the repo.
- **Opus verdict (decision already made):** STOP trying to reproduce the old
  proof. It is not a robust, transferable foundation. The grasp must be
  ESTABLISHED fresh on THIS hardware. That is the real critical-path work; the
  auto-verifier + retry grid exist for exactly this. Proceed per §5.

### 4.2 Reachability reality (important constraint for §5)
The base at `STANCE=(-3.32,-1.72)` already sits ~0.05 m off the island east face
(`verify_grasp_lift.py` docstring). You likely CANNOT get the island cup to <0.80 m
reach without base-vs-island collision. So for the island cup, make the grasp
robust AT the achievable ~0.82 m reach via close-accuracy (§5 levers 1–3), NOT by
driving the base closer.

### 4.4 LEVER 1 (recenter on live cup pose) — TESTED CLEAN, FAILED, reproducible
- **Run:** `python -B scripts/task3/run_world_isaac_grasp.py --object-name cup
  --skip-navigation --out-dir outputs/task3_world_isaac_grasp_lever1_clean`, single
  process, GPU confirmed clean before launch (0%/0MiB), GPU gate passed
  (`Using device: cuda:0`, no llvmpipe/software-rasterizer hits in
  `outputs/lever1_clean.log`). `wall_time_seconds: 222.06`.
- **Result (`result.json`, real, opened this session):** `passed: false`.
  - `descend`: `position_error_m 0.0944`, `strict_reach: false` — already ~9.4cm
    short, biased in **-Y** (`ee_dy_m: -0.072`).
  - `recenter` (the Lever-1 fix itself): `ok: false`, `recenter_pos_err_m: 0.0761`
    — re-solving IK against the LIVE cup pose barely helped (9.4cm → 7.6cm) and
    still missed by 7.6cm against a 0.015m tolerance / 4s timeout.
    `target=[-4.097,-1.754,0.829]` vs `ee_after=[-4.117,-1.808,0.879]` — off in
    both Y and Z, i.e. the arm did not converge, not "closed on a target that
    was itself wrong."
  - `close`: `gripper_position_rad -0.0` (fully closed — closed on empty air),
    `object_ee_dist_m 0.1251`, `object_follows_ee: false` → `weak_grasp`.
  - `lift`: `object_rise_m 0.0` → `miss`.
  - **Reproducibility:** this is near-identical to the (contaminated,
    provenance-unknown) result found on session start — `recenter_pos_err_m`
    0.0768 there vs 0.0761 here. Same failure mode twice → this is a real,
    deterministic finding, not noise.
- **Interpretation:** the fix in Lever 1 (recompute target from live pose) is
  necessary but not sufficient — it is not a *stale-target* problem, it is an
  **IK/reach convergence** problem: `arms.reach()` cannot get the end effector
  within tolerance of the (correct, live) target at all, consistently missing
  by ~7-9cm in the same -Y-biased direction both before and after recentering.
  This matches §4.2's standing concern that the island-cup reach may sit right
  at/beyond the arm's workspace limit for this base stance. **Lever 2
  (stiffen descend / reduce cup displacement) targets a different failure mode
  (cup slipping) and is unlikely to fix an IK-convergence shortfall — but per
  process we test it anyway, one change at a time, before escalating.**
- **New finding (§5 step 4, captured this session):** container's actual
  running Isaac Sim is **`5.1.0-rc.19+release.26219.9c81211b.gl`** (from
  `/workspace/isaaclab/_isaac_sim/VERSION` and boot log
  `Isaac-Sim/5.1/user.config.json`), inside image `isaac-lab-2.3.2:ebim2026`.
  This container was created ~12h before this session (i.e. NOT the same
  container instance that produced the 07-18 proof). The historical proof's
  `repro.txt` does not pin an Isaac Sim version, so we cannot directly compare,
  but a 2.3.2-branded Isaac Lab image running a 5.1 **release-candidate** Isaac
  Sim internally is unusual and consistent with §4.1's suspected
  build-mismatch cause of the IK/contact-geometry drift. Cannot fix from
  inside the repo (would need a different/pinned image) — noting as
  supporting evidence for §6 if levers exhaust.
- **Also confirmed independently (session hygiene):** the VM was found with 5
  concurrent unmanaged runs left by a prior session (see §2) — that prior
  session's own frozen `repro.txt` for the reference batch script explicitly
  warns "never run a second copy on the single GPU," so this was a known rule
  that got violated, not an unknown risk.

### 4.3 Earlier deferrals (context, not failures)
- Tray-drag files were NOT physically archived to `old/` — `run_stage2_feeding.py`,
  `task3_autonomy/recording.py`, and 2 tests import from them; a blind `git mv`
  would break Stage 2. Deferred until those imports are severed. Deprecation note
  added to `scripts/task3/probe_tray_slide.py` only.
- The VM's `task3-current-clean` had diverged to an OLD pre-pivot history (no
  `task3_pipeline` package); it was backed up to VM-local branch
  `backup/vm-pretpivot-2026-07-24` and reset to `origin/task3-current-clean`.

---

## 5. WHAT TO DO NEXT — ordered steps

**GOAL of this phase: establish a cup grasp that ACTUALLY HOLDS on the Lightning
L4, reproduced on ≥3 seeds, verified by the honest verifier (real held + lifted,
not `ok:true`).** Test with:
`python scripts/task3/run_world_isaac_grasp.py --object-name cup --skip-navigation`
(or the equivalent via `isaaclab.sh -p`). Read the REAL result.json/frames each run.

Do these IN ORDER, ONE change per GPU run. Hard cap ~8 GPU runs total, then
re-escalate (§6) if no robust hold.

1. **[LEVER 1 — highest probability] Re-center on the LIVE cup pose right before
   close.** After the descend, re-read the cup's ACTUAL PhysX pose and set the
   close/grasp target to it (use `verify_grasp_lift.cup_grasp_target` on the live
   pose), so the fingers close where the cup actually IS, not where it was
   pre-descend. This is a known project technique ("recenter_live_cup", historical
   r13). GATE: gripper closes toward ~0.076–0.15 AND cup rises ≥0.05 m,
   reproduced 3×.
2. **[LEVER 2] Minimize cup displacement during descend.** Stiffen the base hold
   during descend (`GRASP_GRID base_hold_kp`: try 8, then 12) and/or slow the
   descend so contact is gentler. Target descend `position_error < 0.03 m` and cup
   moved < 2 cm before close.
3. **[LEVER 3] Sweep the remaining grasp knobs** one per run: `grasp_y_offset`,
   `grasp_height_above_origin_m`. Honest verifier is the gate every time.
4. **Also capture** the container's exact Isaac Sim version string and log it here
   (rules out / confirms a version regression vs the 07-18 proof).
5. **If levers 1–3 fail within the cap → re-escalate (§6).** Opus fallbacks to
   weigh then: (a) pretrained grasp model [Contact-GraspNet / AnyGrasp] as the
   `[L]` fallback the plan anticipates; (b) a top-down cage close instead of
   side-rim; (c) gripper effort/force-limit tuning; (d) grasp objects at their
   Stage-1 KITCHEN location (where the geometry may differ from the island cup)
   rather than the island cup.

**Once a robust grasp exists** (this unblocks everything): continue master plan
§7 — wire the grasp into `plan_stage1`'s per-object loop, get Stage 1 end-to-end
(navigate→grasp→carry→place at a seat, real scorer), tag a submittable build, then
Stage 4, then Stage 2/3, then perception.

---

## 6. ⚠ NEEDS OPUS (fill when stuck; the human brings this to an Opus session)

- _(currently empty — the grasp escalation was answered: see §4.1 verdict + §5.
  The next escalation goes here if levers 1–5 in §5 are exhausted.)_
- When filling: paste the exact symptom, the hypotheses already tried WITH their
  pasted evidence, and the specific decision you need. Do NOT keep guessing.

---

## 7. ENVIRONMENT — exact working setup (verify live, don't assume)

- **GPU venue: Lightning AI ONLY. GCP is HARD-BANNED (no budget).** Ignore any
  `gcloud` instructions in older docs.
- **SSH:** `s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai` — **this string CHANGES
  across Lightning Studio restarts.** Verify live with `ssh <string> nvidia-smi`
  before trusting it. If it fails, the human must supply the current string from
  their Lightning Studio (they can paste it or run `! ssh ...`).
- **Repo on VM:** `~/EBiM_Challenge` = `/teamspace/studios/this_studio/EBiM_Challenge`,
  branch `task3-current-clean`. The container bind-mounts it at
  `/workspace/EBiM_Challenge`. Ignore `/home/zeus/ebim_hackthon` (stale).
- **Container:** `isaac-lab-2-3-2-workshop`, image `isaac-lab-2.3.2:ebim2026`.
  Bring up: `bash scripts/task3/lightning_workflow.sh bootstrap`. Stop:
  `bash scripts/task3/lightning_workflow.sh stop`.
- **GPU:** 1× NVIDIA L4, 23 GB.
- **MANDATORY GPU GATE before trusting ANY run** (this project got burned by
  silent CPU fallback): `nvidia-smi` on host AND `docker exec
  isaac-lab-2-3-2-workshop nvidia-smi`; grep the run log for `llvmpipe` /
  `software rasterizer` / `No device could be created` (ANY hit = discard the run);
  confirm `cuda:0` in the Isaac boot log; confirm GPU util goes nonzero once
  physics starts.
- **Fast iteration:** `--skip-navigation` drives straight to the work stance
  (~half the wall-clock of full navigation). Use it for all grasp iteration.
- **Perception (future):** camera prim `/World/Scene/eval_camera` already exists.
  VLM (Qwen2-VL) lives in `~/vlm_venv` on the VM host (NOT in the container).

---

## 8. IF YOU HIT A USAGE LIMIT MID-TASK — how to continue with ANOTHER agent

Any agent (including Opus) can be cut off by a usage limit at any moment. The
whole point of this file is that another agent can pick up WITHOUT redoing or
deviating. To continue:

1. **Nothing is lost that was committed.** The new agent runs `git pull` on
   `task3-current-clean` and reads THIS file. §2/§4/§5 tell it exactly where
   things stand and what to do next.
2. **Give the new agent (Claude / Codex / OpenCode) this one-line bootstrap** as
   its first message:
   > "Read `plans/handoff.md` in full, then `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`.
   > Follow the process in §0. Continue from the first unchecked step in §5. Do all
   > work yourself; update `plans/handoff.md` and commit+push after every step;
   > escalate to §6 instead of guessing. Never claim a run result you didn't just
   > observe — paste the real evidence."
3. **If the interrupted agent had UNCOMMITTED work** (rare, since the process says
   commit often): the new agent checks `git status`, reviews the diff, and either
   commits it (if sound) or discards it — it does NOT blindly build on top.
4. **To avoid deviation:** the new agent must NOT invent a new plan. The plan is
   fixed (this file + the master plan). Its job is to execute §5, not redesign.
   If it thinks the plan is wrong, it writes that into §6 NEEDS OPUS and stops —
   it does not act on a unilateral redesign.
5. **Opus is for clarification/decisions only** (when §6 is filled). Sonnet /
   Codex / OpenCode do all the coding/testing/running. This keeps cost down.

---

## 9. NON-NEGOTIABLE RULES (why this project stays credible)
1. Every claim about a run backed by a pasted result.json/log/frame opened THIS
   session. Never from memory.
2. One hypothesis, one change, one run. 3 fails on one symptom → §6, don't guess.
3. GPU gate before trusting any run (§7).
4. `"ok": true` ≠ a real hold. Verify with measured evidence.
5. Commit + push after every meaningful result. Update THIS file. Unpushed = lost.
6. Standard physics only — no kinematic attach, no asset edits, no teleport in the
   graded path.
7. No hardcoded per-episode values in the graded path (seats/objects read from
   state each episode).
8. Stop the GPU container at pauses. Lightning only; GCP banned.
9. Archive superseded work to `old/` (don't delete) once safe to.

---

## 10. DONE / FROZEN (real GPU proof bundles — never rework without owner request)
- _(none yet)_
