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
- **Last commit:** `fc7d1f0e` (T1: seats.py derived from real
  TASK3_HEAD_PLACEMENTS coords; local dining-scorer validation; CPU-only).
- **Overall:** 0/4 stages have a real-rules GPU proof bundle. T0 (CPU-only
  logic retarget) done; T1 (CPU-only seat targets) done; no GPU work has
  happened yet.
- **Environment:** Lightning AI L4 only (GCP BANNED). SSH + container per
  `docs/HANDOFF_2026-07-24_FULL_PLAN_Claude_to_OpenCode.md` §7 (verify SSH live
  with `nvidia-smi` — the string changes across Studio restarts).
- **Resolved:** the seat-discovery unknown from T0 is closed — see
  `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md` §5.1 "DISCOVERY TASK 1.0 —
  RESOLVED" and `task3_pipeline/seats.py`. Summary: no separate seat geometry
  exists in `robot_room.usd`; the shipped scorer grades the dining rectangle,
  not seats; `seats.py` now derives real targets from
  `TASK3_HEAD_PLACEMENTS` (scene_robot_room_keyboard.py).

## STAGE 1 STATUS

Stage 1 CPU side COMPLETE (plan + targets + honest verifier + local scorer
validation all green). Remaining: GPU wiring in `world_isaac.py` (T2) + a
real GPU run.

## NEXT TASK  (the ONE thing to do next)

**→ T2 (plan §4 + §5.1 Task 1.2/1.3):** implement
`task3_pipeline/world_isaac.py` against the proven primitives
(`verify_grasp_lift.py` geometry) with the <0.80m stance-first reach
guarantee — this is the first task requiring the Lightning GPU/VM.

_After T2, continue down master plan §7 build order: perception, then Stage 1+4 end-to-end._

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

## ⚠ NEEDS OPUS  (fill ONLY when escalating; clear when resolved)

- _(empty)_
- When filling: state the exact symptom, the 3 hypotheses already tried with their
  evidence (result.json/log lines), and the specific architecture question. The
  human will bring this block to an Opus session.

## DONE / FROZEN  (stages with a real-rules proof bundle — never rework)

- _(none yet)_
