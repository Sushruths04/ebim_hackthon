# SONNET / OPENCODE EXECUTION PROMPT — Task 3 (paste this verbatim)

> Paste everything between the lines below as the agent's task. It is written to
> keep the agent working autonomously, one gated task at a time, without
> hallucinating or drifting from the organizer rules.

---

You are executing the Task 3 build for the EBiM robotics competition. Work
autonomously and continuously — do not stop and ask the human between tasks
unless a STOP condition below is hit.

**READ THESE FIRST, IN THIS ORDER, EVERY SESSION:**
1. `docs/EXECUTION_HANDOFF_LIVE.md` — the live "where are we / what's next" file.
   It tells you the current state and the ONE next task. Start from its
   `NEXT TASK` block.
2. `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md` — the authoritative plan.
   Every decision, target, and gate comes from here + the organizer rules at
   `https://ebim-benchmark.github.io/competition.html`. If any older doc in
   `docs/` contradicts it, the master plan wins.
3. Before coding: `scripts/task3/verify_grasp_lift.py` (the proven grasp you
   must reuse), `task3_pipeline/world_isaac.py` (the wiring map you must
   implement), `task3_pipeline/{orchestrator,skills,policy,memory}.py` (the
   brain you must keep).

**DOCUMENTATION IS MANDATORY (so work survives an abrupt session end):** after
EVERY meaningful step — a committed code change, a finished GPU run, a gate
passed or failed — you MUST append one dated line to the `PROGRESS LOG` in
`docs/EXECUTION_HANDOFF_LIVE.md` and update its `CURRENT STATE` + `NEXT TASK`
blocks, then commit + push that file WITH your work. Also append your one-line
result to `docs/AGENT_STATE.md` as this project already requires. If your session
ends mid-task, the next agent must be able to continue purely from
`EXECUTION_HANDOFF_LIVE.md` — write it for that reader.

**MISSION:** deliver a fully autonomous, standard-physics FSM that completes as
many of the 4 stages as possible, each verified by the REAL organizer rules (NOT
`grading.py`, which is only a dev smoke-test), by Aug 10. Ranking = highest stage
reached → score → time, so always advance; take partial credit, never hang.

**HOW TO WORK (the loop, repeat until the plan's Definition of Done or a STOP):**
1. Pick the NEXT unfinished task from the master plan's §7 build order (respect
   the order; each has a GATE that must be true before advancing). Announce which
   task + which plan section you are on.
2. Make ONE change addressing ONE hypothesis. Never stack changes.
3. Validate: CPU tests + ruff + py_compile for logic; for anything touching the
   robot, run on GPU (Lightning L4 only — GCP is BANNED) AFTER passing the GPU
   gate (host+container `nvidia-smi`, grep log for `llvmpipe`/`software
   rasterizer` = discard, confirm `cuda:0` + nonzero util).
4. Read the REAL evidence yourself (`result.json`, log, frames). A phase is
   SUCCESS only with measured proof (grasp: `gripper_rad ≤ 0.20` AND
   object-follows-EE AND object rose). `"ok": true` alone proves nothing.
5. Commit + push after every meaningful result (pass or fail) with a one-line
   `AGENT_STATE.md` update. Check for another agent's uncommitted work first;
   reconcile, don't overwrite.
6. If the change failed, apply the plan's retry/geometry logic (§4) — ONE new
   hypothesis — and loop. If 3 fixes fail on the same symptom without narrowing
   it, STOP and write the architecture question to `AGENT_STATE.md`.

**FIRST TASKS, IN ORDER (do not skip; each ends at its gate):**
- T0: `git mv` the tray-drag work to `old/task3_tray_drag_ABANDONED_2026-07-24/`
  (§2.2 — archive, do NOT delete). Commit `task3_pipeline/` into git (it is
  currently untracked). Retarget `stages.py` + `config.py` off the tray/rectangle
  objective to the real rules (§2.3). Make `outcomes.classify` honest (§6).
  GATE: CPU tests green; no tray/dining-rectangle logic in the active path.
- T1 (§5.1 Task 1.0): locate the 6 seat targets in `robot_room.usd` + the
  per-episode assignment mechanism; write `task3_pipeline/seats.py`.
  GATE: teleport a test object to a seat target → the REAL-rules Stage-1 scorer
  accepts it. (Teleport is allowed in this unit test only, never in the graded run.)
- T2 (§4 Phase A): implement `world_isaac.py` navigate/reach/grasp/lift against
  the proven primitives with the <0.80 m reach guarantee (stance-first; reuse
  `verify_grasp_lift.py` geometry). GATE: GPU grasp `position_error ≤ 0.05`, no
  IK_FAIL, object held (verified), on ≥3 seeds.
- Then continue down §7.

**HARD RULES (from §8 — violating these has burned this project before):**
standard physics only (no kinematic attach / asset edits / teleport in graded
run); no hardcoded per-episode values (seats are randomized — read them each
episode); one hypothesis/one change/one run; every claim backed by evidence you
opened this turn; stop the GPU container at pauses (no idle spend).

**ESCALATE TO OPUS ONLY WHEN GENUINELY STUCK (this keeps the human's cost down —
you are the primary worker; Opus is the expensive specialist called sparingly).**
Escalate by filling the `⚠ NEEDS OPUS` block in `docs/EXECUTION_HANDOFF_LIVE.md`
(exact symptom + the 3 hypotheses already tried with their evidence + the
specific architecture question), committing + pushing, and telling the human to
bring it to an Opus session. Escalate ONLY if:
- you hit the 3-failed-fixes-on-one-symptom architecture threshold, OR
- a change requires a design decision the plan doesn't cover, OR
- you need a change you are <80% sure is safe.
Do NOT escalate for ordinary debugging, parameter tuning within a grid, or
anything the plan already specifies — handle those yourself and keep going.

**STOP and wait for the human ONLY if:** the Lightning VM/account dies; you
escalated to Opus (above); or you reached a stage's Definition of Done (report
the win with the proof bundle). Otherwise keep working task after task.

Begin from the `NEXT TASK` in `docs/EXECUTION_HANDOFF_LIVE.md` (currently T0).
Announce your task, make the change, validate, commit, update the handoff doc,
and continue to the next task without waiting.

---
