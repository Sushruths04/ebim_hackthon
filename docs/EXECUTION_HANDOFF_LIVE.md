# TASK 3 — LIVE EXECUTION HANDOFF (read this FIRST, every session)

> **Purpose:** the single "where are we / what's next" file. ANY agent (Sonnet,
> OpenCode, Codex, Opus) reads this first and updates it last, every session, so
> work survives a session ending abruptly (5-hour limit, crash, handoff to a
> different agent). If a session ends mid-task, the next agent continues from the
> `NEXT TASK` block below with zero context loss.
>
> **Authoritative plan:** `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`
> **Your operating rules:** `docs/SONNET_EXECUTION_PROMPT_task3.md`
> **Objective truth:** organizer rules at https://ebim-benchmark.github.io/competition.html
> (NOT `grading.py` — that's a dev smoke-test only).

---

## HOW TO USE THIS FILE (protocol — do not skip)

1. On session start: read this whole file, then the master plan, then the
   execution prompt. Confirm the branch + last commit below match the repo.
2. Work the `NEXT TASK`. One hypothesis, one change, one run.
3. On EVERY meaningful step (a code change committed, a GPU run finished, a gate
   passed/failed): update the `PROGRESS LOG` (append one dated line) and the
   `NEXT TASK` / `CURRENT STATE` blocks. Commit + push this file with your work.
4. If you hit an ESCALATE condition (see the prompt), fill the `⚠ NEEDS OPUS`
   block, commit+push, and tell the human to bring it to Opus. Do NOT keep
   guessing.

---

## CURRENT STATE  (update every session)

- **Branch:** `task3-current-clean`
- **Last commit:** `197f20f5` (T2: IsaacWorld wired against
  verify_grasp_lift.py primitives + simulation_app fix; NOT gate-passing yet
  — see ⚠ NEEDS OPUS below).
- **Overall:** 0/4 stages have a real-rules GPU proof bundle. T0/T1 (CPU)
  done. T2 (GPU wiring) implemented and GPU-exercised, but blocked: the
  reference "proven 10/10" cup grasp (`verify_grasp_lift.py` defaults) does
  NOT currently reproduce a real hold on this Lightning L4/container, even
  unmodified. See escalation block.
- **Environment:** Lightning AI L4 only (GCP BANNED). SSH string THIS
  SESSION: `s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai` (verified live).
  VM repo `/teamspace/studios/this_studio/EBiM_Challenge` == container
  `/workspace/EBiM_Challenge` (bind mount). Container `isaac-lab-2-3-2-workshop`
  was already up this session; GPU confirmed on host AND in container
  (`NVIDIA L4, 23034 MiB`). Container stopped at end of this session (see
  PROGRESS LOG) — restart with
  `bash scripts/task3/lightning_workflow.sh bootstrap` before continuing.
- **VM branch divergence (resolved this session):** the VM's
  `task3-current-clean` had a completely different, older commit history
  (pre-pivot tray-drag/Stage-2 lineage, tip `38040c0`) that was never pushed
  anywhere and did NOT contain the T0/T1 `task3_pipeline` package at all.
  Backed it up non-destructively to local branch
  `backup/vm-pretpivot-2026-07-24` on the VM (could not push to origin from
  the VM -- no git credentials there, read-only fetch works fine), then
  `git reset --hard origin/task3-current-clean` to bring the VM to the
  authoritative history. If a future session needs that old Stage-2 tuning
  work, it is preserved at that VM-local branch.
- **Resolved:** the seat-discovery unknown from T0 is closed — see
  `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md` §5.1 "DISCOVERY TASK 1.0 —
  RESOLVED" and `task3_pipeline/seats.py`.

## STAGE 1 STATUS

Stage 1 CPU side COMPLETE. GPU side (T2): `world_isaac.py` fully implemented
per the wiring map, GPU-exercised on the real L4, but the grasp chain does
not yet pass the honest verifier -- root cause traced to the REFERENCE
primitive itself (`verify_grasp_lift.py` defaults), not (as far as evidence
shows) new bugs in `world_isaac.py`. See ⚠ NEEDS OPUS.

## NEXT TASK  (the ONE thing to do next)

**→ Pending Opus decision (see ⚠ NEEDS OPUS below).** Do NOT keep
GPU-guessing grid parameters until that block is resolved -- 2 grid-adjacent
attempts on the unmodified reference script already made things worse, not
better (see evidence). Likely next paths once Opus decides: (a) re-tune the
cup grasp fresh on this exact environment via a bounded, logged grid sweep
(not ad hoc), treating the historical "10/10" numbers as no-longer-load-bearing;
(b) investigate GPU/driver/Isaac-Sim-build differences vs whatever produced
the historical proof; or (c) something else Opus specifies.

_After T2 is actually gated, continue down master plan §7 build order:
perception, then Stage 1+4 end-to-end._

## PROGRESS LOG  (append one line per step, newest at bottom)

- 2026-07-24 — Opus — plan + prompt + this handoff written to `docs/`. Execution not started. NEXT: T0.
- 2026-07-24 — Sonnet — T0 done (commit `1d1ab632`): committed the untracked
  `task3_pipeline/` package to git; added `task3_pipeline/seats.py` (seat-target
  interface, mocked pending T1); retargeted `config.py` (`STAGE1_OBJECTS` -> 4
  real objects, no tray; `DINING_AREA` now documented as smoke-test-only
  fallback; added `GRASP_HELD_MAX_DIST_M`); rewrote `stages.py::plan_stage1`
  (per-object navigate/reach/grasp/carry to assigned seats, no tray, no
  single dining-drop) and `plan_stage4` (honest per-utensil grasp+place into
  the sink, dropped "SCORER EXPLOIT" framing); made
  `outcomes.py::classify_grasp` honest (closed-cage-on-empty-object now
  WEAK_GRASP, not SUCCESS, unless `object_follows_ee`/`object_ee_dist_m`
  proves a real hold); updated `world.py` MockWorld to match (honest grasp
  metrics, generalized `carry_object_to`, 4-object `score_stage`). CPU tests:
  `python -m pytest task3_pipeline/tests -q` -> 11 passed. `ruff check
  task3_pipeline` -> 68 pre-existing/residual style findings (E501 line-length,
  import-sort, a couple `UP037`/`F401`) — almost all in files not touched this
  session (`memory.py`, `policy.py`, `orchestrator.py`, `world_isaac.py`,
  `skills.py`) or on pre-existing lines in touched files; the new code
  authored this session (`seats.py`, the new/changed lines in `stages.py`)
  was cleaned to pass ruff. Did NOT `git mv` any tray-drag file — the
  `verify_grasp_lift.py` proof + import-coupling constraint made a physical
  archive out of scope; instead added a top-of-file deprecation docstring to
  `scripts/task3/probe_tray_slide.py` only (no executable change). NEXT: T1.
- 2026-07-24 — Sonnet — T1 done (CPU-only, no GPU needed): resolved the T0
  "6 seats" unknown by direct inspection — `robot_room.usd` has no separate
  seat/chair geometry, and neither `grading.py` nor the organizers'
  `integration_test.py::run_stage1` scores by seat (both score the dining
  rectangle only). Rewrote `task3_pipeline/seats.py`: removed the invented
  `MOCK_SEATS`; added `TABLE_SEAT_POSITIONS` copied from the real
  `TASK3_HEAD_PLACEMENTS` (9 named A-I placements,
  `scripts/scenes/scene_robot_room_keyboard.py`); `assigned_seats()` now
  deterministically selects distinct real seats (default A/C/G, or a seeded
  sample). `SeatTarget`/`object_to_seat()` shape unchanged, so
  `stages.py::plan_stage1` required no edits. Added 3 new tests to
  `task3_pipeline/tests/test_pipeline.py` that load
  `scripts/evaluation/task3/grading.py` by file path (it has zero Isaac
  imports) and assert every assigned seat AND every Stage-1
  object->seat-target mapping classifies as `"dining"` via
  `classify_table_area` — i.e. objects placed at seat targets pass the only
  real scorer that ships, validated entirely on CPU.
  `python -m pytest task3_pipeline/tests -q` -> 14 passed (11 previously
  green + 3 new). Updated
  `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md` §5.1 to replace the
  blocking-discovery-task text with the resolved finding. NEXT: T2.
- 2026-07-24 — Sonnet (T2 session) — SSH verified live
  (`s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai`), host + container
  `nvidia-smi` both show the L4. Found VM's `task3-current-clean` had
  diverged to an old, never-pushed tray-drag/Stage-2 lineage (tip `38040c0`,
  no `task3_pipeline` package at all) — backed it up to VM-local branch
  `backup/vm-pretpivot-2026-07-24`, pushed local `3be4cbc5` to origin (first
  push of this branch), then `git reset --hard origin/task3-current-clean`
  on the VM. Implemented `task3_pipeline/world_isaac.py` in full (commit
  `ee0659dd`): `__init__`/`reset` build the real Isaac scene (mirrors
  `verify_grasp_lift.py`'s Phase 0 spine-raise + transit tuck);
  `navigate_to`/`reach`/`grasp`/`lift`/`hold`/`place`/`carry_object_to`
  wired to `DualArmController`/`TmrBaseAdapter`; `reach()` implements the
  §4 stance-first reach fix by recomputing the base stance from the
  object's LIVE pose each call using the `STANCE - cup_position` offset
  that made the proven grasp work (not a hardcoded per-episode value);
  `grasp()` uses `verify_grasp_lift.object_follows_end_effector` for the
  honest hold check. Added `scripts/task3/run_world_isaac_grasp.py` harness
  (navigate/reach->grasp->lift->hold on one object, `--skip-navigation` for
  fast iteration). First GPU run crashed (`simulation_app=None` passed to
  scene composition, which calls `app.update()`) — fixed (commit
  `197f20f5`), re-ran: GPU gate passed (`cuda:0`, no llvmpipe), but the
  grasp did not hold (`weak_grasp`, object_ee_dist_m 0.127 m; lift
  `ik_fail`). Ran a control experiment on the UNMODIFIED
  `scripts/task3/verify_grasp_lift.py --skip-navigation` (the referenced
  "proven 10/10" script, zero code changes) 3x (plain `python -B`, twice;
  once via the official `/workspace/isaaclab/isaaclab.sh -p` launcher used
  by `run_grasp_reliability_batch.py`) — all 3 runs bit-identical
  (deterministic) and ALL FAIL: `gripper_position_rad: 0.2402`,
  `cup_lift_m: 0.0`, `object_to_ee_m: 0.339`, `passed: false`. Tried the
  next `GRASP_GRID` value (`--cup-grasp-y-offset 0.0` instead of default
  `0.06`) on the same unmodified script: WORSE (cup shoved 25cm off the
  counter, `gripper_position_rad: 0.7528`, `cup_lift_m: 0.0301`,
  `passed: false`). Diffed every file in the execution path
  (`verify_grasp_lift.py`, `task3_autonomy/{arms,skills,navigation}.py`,
  `scripts/common/{dual_arm_lula,teleop_targets,teleop_commands,
  tmr_base_control,path_utils}.py`, `scripts/scenes/scene_robot_room_keyboard.py`
  `configure_robot_room_stage` path, `assets/robot_room.usd`,
  `assets/mobile_fr3_duo_v0_2.usd`) against commit `cf372031` ("Complete Day
  1 grasp reliability proof", 2026-07-18, the commit that produced
  `proofs/phase2-grasp-reliability/run18_result.json`, `passed: true`,
  `cup_lift_m: 0.1087`) — every file is either byte-identical or its only
  changes are in code paths this script provably does not execute (verified
  by tracing `route_via_door`'s early-return branch and
  `_run_keyboard_control_app` vs what `verify_grasp_lift.py` actually
  calls). No code/asset explanation found for the regression. Escalating —
  see ⚠ NEEDS OPUS. `world_isaac.py`'s OWN correctness relative to
  `verify_grasp_lift.py` cannot be fully judged until the reference script
  itself reproduces, since right now neither does. Container stopped this
  session; VM/container state otherwise as described above.

## ⚠ NEEDS OPUS  (2026-07-24, T2 session)

**Symptom:** the master plan's foundational assumption — that
`scripts/task3/verify_grasp_lift.py` reproduces the "proven 10/10" cup
grasp — does not currently hold on the live Lightning L4 (container
`isaac-lab-2-3-2-workshop`, image `isaac-lab-2.3.2:ebim2026`, repo at
commit `197f20f5`). This blocks judging whether my new
`task3_pipeline/world_isaac.py` (T2 deliverable) is itself correct, since
the reference primitive it wraps does not currently succeed either.

**Evidence (all pasted from this session, nothing from memory):**

1. My own `IsaacWorld` grasp chain (`scripts/task3/run_world_isaac_grasp.py
   --object-name cup --skip-navigation`), after fixing a `simulation_app`
   plumbing bug (commit `197f20f5`):
   ```
   WORLD_ISAAC_DBG {'phase': 'descend', 'ok': True, 'strict_reach': False, 'position_error_m': 0.0922, 'target': [-4.145, -1.693, 0.815]}
   WORLD_ISAAC_DBG {'phase': 'close', 'ok': False, 'gripper_position_rad': 0.0019, 'object_ee_dist_m': 0.127, 'object_follows_ee': False}
   WORLD_ISAAC_DBG {'phase': 'lift', 'ok': False, 'object_rise_m': 0.0}
   "grasp": {"outcome": "weak_grasp", "diagnosis": "gripper closed (0.002 rad) but object not held (dist 0.127 m) -- likely empty"}
   "lift": {"outcome": "ik_fail", "diagnosis": "ik failure during lift (fling risk)"}
   ```
2. Control: the UNMODIFIED reference script, `python -B
   scripts/task3/verify_grasp_lift.py --object-name cup --skip-navigation
   --fast-exit`, run twice, bit-identical both times (fully deterministic
   in this environment):
   ```
   GRASP_RESULT {"cup_lift_m": 0.0, "cup_start": [-4.1849,-1.7527,0.747], "cup_end": [-4.233,-1.792,0.747], "final_phase": "hold", "passed": false, ...}
   phase close: gripper_position_rad: 0.2402
   phase hold:  object_to_ee_m: 0.3394, lifted_m: 0.0, held_s: 0.0
   ```
3. Same control, run via the OFFICIAL launcher used by the frozen
   reliability batch script (`/workspace/isaaclab/isaaclab.sh -p
   scripts/task3/verify_grasp_lift.py --skip-navigation --fast-exit`,
   exactly matching `run_grasp_reliability_batch.py`'s own subprocess
   command): **bit-identical to #2** (rules out the launcher wrapper as the
   cause).
4. Tried the next `config.GRASP_GRID` value on the same unmodified script
   (`--cup-grasp-y-offset 0.0`, grid's alternative to the failing default
   `0.06`): worse, not better —
   ```
   GRASP_RESULT {"cup_lift_m": 0.0301, "cup_start": [-4.1849,-1.7527,0.747], "cup_end": [-3.9326,-1.8654,0.7771], "passed": false, ...}
   phase close: gripper_position_rad: 0.7528  (cup shoved ~25cm off the counter during descend/close)
   ```
5. Diffed EVERY file in the execution path against commit `cf372031`
   ("Complete Day 1 grasp reliability proof", 2026-07-18 — the commit that
   produced `proofs/phase2-grasp-reliability/run18_result.json`, itself
   `passed: true, cup_lift_m: 0.1087`, and whose `repro.txt` documents the
   exact zero-override CLI used): `verify_grasp_lift.py`'s top constants
   (`STANCE`, `CUP_GRASP_XY`, `CUP_RIM_X_OFFSET`, `CUP_GRASP_Y_OFFSET`,
   `PREGRASP_Z`, `GRASP_Z`, `GRASP_HEIGHT_ABOVE_CUP_ORIGIN`,
   `TRAVEL_SPINE_M`) are byte-identical; `scripts/common/{dual_arm_lula,
   teleop_targets, teleop_commands, tmr_base_control, path_utils}.py` have
   ZERO diff; `task3_autonomy/skills.py` has ZERO diff;
   `task3_autonomy/arms.py`'s diff is purely additive new methods (no
   changed logic in `grasp`/`reach`/`lift`/`command`);
   `task3_autonomy/navigation.py`'s only logic change (an island-clear
   waypoint) is inside a branch this exact route
   (`ROTATE_SPOT`->`STANCE`, both south of the door) provably never enters
   (`route_via_door`'s `start_north == target_north` early return fires
   first); `scripts/scenes/scene_robot_room_keyboard.py`'s diff is entirely
   inside `run_keyboard_control`/`_run_keyboard_control_app`/argparse, none
   of which `verify_grasp_lift.py` calls (it calls
   `configure_robot_room_stage`/`configure_keyboard_control_stage`
   directly, unchanged); `assets/robot_room.usd` and
   `assets/mobile_fr3_duo_v0_2.usd` are byte-identical (`git diff --stat`
   empty). **No code or asset change explains the regression.**

**Hypotheses considered and why not (yet) actionable:**
- Launcher/env difference (`isaaclab.sh` vs `python -B`) — ruled out (#3,
  bit-identical).
- Wrong/stale grasp-offset default — tested the grid's own alternative
  (#4) and it is strictly worse (bigger miss, cup knocked further), so
  this isn't a simple "the offset needs to move a little" fix; a
  from-scratch bounded re-tune (not blind guessing) would be needed.
- Code regression somewhere in the dependency chain — exhaustively diffed
  and ruled out (#5). The only remaining untested variable is the
  Isaac-Sim/PhysX/driver *build* itself differing from whatever produced
  the 2026-07-18 proof (this container's Isaac Lab 2.3.2 image, CUDA
  driver 580.159.03, PhysX version) — I have no way to check what the
  07-18 environment's exact versions were from inside this repo.

**The architecture question for Opus:** given the reference "proven 10/10"
primitive does not currently reproduce with its own documented zero-override
repro command, on the exact commit that produced the proof, via 2 different
launch methods — how should T2 proceed?
  (a) Treat the historical 10/10 numbers as no longer load-bearing and
      re-tune the cup grasp fresh on THIS environment via a bounded,
      logged `GRASP_GRID` sweep (my `world_isaac.reach()`/`grasp()` already
      expose `grasp_y_offset`/`grasp_height_above_origin_m`/
      `approach_stance` as params for exactly this), accepting a new
      empirical baseline instead of the old one;
  (b) investigate whether a different Isaac Sim/Lab build or GPU
      driver would restore the original numbers (would need a supervisory
      decision since it's outside my ability to change the container image
      unilaterally); or
  (c) something else.
I have NOT touched `task3_pipeline/world_isaac.py`'s grasp geometry beyond
what's described in the T2 instructions (reusing `verify_grasp_lift.py`'s
constants as-is) pending this decision, since changing untested constants
further would just be guess #4 on the same symptom.

## DONE / FROZEN  (stages with a real-rules proof bundle — never rework)

- _(none yet)_
