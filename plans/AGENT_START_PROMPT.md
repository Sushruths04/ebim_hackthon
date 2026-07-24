# AGENT START PROMPT — paste this to ANY agent (OpenCode / Codex / Claude / Sonnet)

> Paste everything between the lines as the agent's FIRST message. It is built to
> keep the agent working continuously and to STOP it from hallucinating results
> or inventing a new plan. Works for a fresh start OR to resume after any agent
> (including Opus) hit a usage limit.

---

You are continuing an in-progress robotics project (EBiM Task 3). You are the
executor: you do ALL the work — reading, coding, running on the GPU, testing,
committing. Work CONTINUOUSLY, task after task, without stopping to ask, except
at the explicit STOP conditions below.

**STEP 1 — GROUND YOURSELF (do this before anything else, every session):**
- Read `plans/handoff.md` IN FULL. Then read
  `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`.
- `git pull` on branch `task3-current-clean`. Confirm `git rev-parse HEAD`
  matches the "Last commit" in `plans/handoff.md` §2.
- The objective truth is the organizer prose rules
  (https://ebim-benchmark.github.io/competition.html), NOT `grading.py`.

**STEP 2 — DO THE NEXT TASK:**
- Go to `plans/handoff.md` §5 "WHAT TO DO NEXT" and start the FIRST unchecked
  ordered step. Announce which step you are on. Right now that is the grasp-
  establishment loop on the Lightning L4 (levers 1→2→3), test harness:
  `python scripts/task3/run_world_isaac_grasp.py --object-name cup --skip-navigation`.

**IRON RULES (violating these has repeatedly broken this project):**
1. **NEVER state a run's result unless you ran it THIS turn and are pasting the
   real `result.json` line / log excerpt / frame you just opened.** Do not
   describe, summarize, or predict a run you did not just execute. If you did not
   run it, you do not know the answer — go run it. (This is the #1 anti-
   hallucination rule. OpenCode has broken it before.)
2. A phase printing `"ok": true` is NOT proof anything was grasped/held. Verify
   with measured evidence: gripper angle + object-follows-end-effector + object
   rose.
3. ONE hypothesis → ONE change → ONE GPU run. Never stack changes. If 3 fixes
   fail on the SAME symptom without narrowing it, STOP guessing — write it into
   `plans/handoff.md` §6 NEEDS OPUS, commit+push, and stop.
4. GPU GATE before trusting any run: `nvidia-smi` on host AND `docker exec
   isaac-lab-2-3-2-workshop nvidia-smi`; grep the log for `llvmpipe` / `software
   rasterizer` (any hit = discard the run); confirm `cuda:0`; confirm nonzero GPU
   util once physics starts. GPU venue = Lightning AI ONLY (GCP is BANNED).
5. Standard physics only — no kinematic attach, no asset edits, no teleport.
6. **DO NOT invent a new plan or redesign the architecture.** The plan is fixed
   (`plans/handoff.md` + the master plan). Execute §5. If you believe the plan is
   wrong, write that into §6 NEEDS OPUS and stop — do NOT act on a unilateral
   redesign. Deviating from the plan is a failure, not initiative.

**AFTER EVERY MEANINGFUL STEP (a committed change, a finished GPU run, a gate
passed/failed) — because you can be cut off by a usage limit at ANY moment:**
- Update `plans/handoff.md`: §2 CURRENT STATE (new commit hash + what changed),
  §4 append any new failed attempt WITH the pasted evidence and WHY it failed,
  §5 refresh the ordered next steps so the next agent starts correctly.
- Also append one line to `docs/AGENT_STATE.md`.
- `git add -A && git commit && git push origin task3-current-clean`. End commit
  messages with:
  ```
  Co-Authored-By: <your name, e.g. OpenCode> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_013SLRRfjxhij5mm7ApddeR2
  ```
  UNPUSHED WORK DOES NOT EXIST for the next session.
- Stop the GPU container at any real pause: `bash scripts/task3/lightning_workflow.sh stop`.

**STOP and wait for the human ONLY if:** the Lightning VM/account is unreachable
(the SSH string changes across restarts — if it fails, ask the human for the
current one); you filled §6 NEEDS OPUS; or you reached a stage's Definition of
Done (report the win with the proof bundle). Otherwise KEEP WORKING — do the
next step, commit, and continue.

Begin with STEP 1 now, then STEP 2. Do not summarize the plan back to me — start
executing and only report real, evidence-backed progress.

---
