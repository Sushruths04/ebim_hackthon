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
- **Last commit:** _(fill in after first commit — this file + plan docs)_
- **Overall:** 0/4 stages have a real-rules proof bundle. Plan written, execution
  not yet started.
- **Environment:** Lightning AI L4 only (GCP BANNED). SSH + container per
  `docs/HANDOFF_2026-07-24_FULL_PLAN_Claude_to_OpenCode.md` §7 (verify SSH live
  with `nvidia-smi` — the string changes across Studio restarts).
- **Known blocking unknown:** the 6 seat positions + per-episode assignment are
  NOT in code yet — Task 1.0 must find them in `robot_room.usd`.

## NEXT TASK  (the ONE thing to do next)

**→ T0 (plan §2, §6):** (a) `git mv` the tray-drag work to
`old/task3_tray_drag_ABANDONED_2026-07-24/` (archive, don't delete); (b) commit
the untracked `task3_pipeline/` into git; (c) retarget `stages.py` + `config.py`
off the tray/dining-rectangle objective to the real rules; (d) make
`outcomes.classify` honest (SUCCESS only with measured proof).
**GATE:** CPU tests + ruff green; no tray/rectangle logic in the active path.

_After T0, continue down master plan §7 build order: T1 = seats.py, T2 = world_isaac.py + reach fix, then stages._

## PROGRESS LOG  (append one line per step, newest at bottom)

- 2026-07-24 — Opus — plan + prompt + this handoff written to `docs/`. Execution not started. NEXT: T0.

## ⚠ NEEDS OPUS  (fill ONLY when escalating; clear when resolved)

- _(empty)_
- When filling: state the exact symptom, the 3 hypotheses already tried with their
  evidence (result.json/log lines), and the specific architecture question. The
  human will bring this block to an Opus session.

## DONE / FROZEN  (stages with a real-rules proof bundle — never rework)

- _(none yet)_
