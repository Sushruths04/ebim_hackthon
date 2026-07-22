# EBiM Task 3 — FINAL STATE & PROVEN FIXES (2026-07-22)

> This is the **single authoritative reference** for what is done, proven, and
> current. If any older note or folder disagrees with this file, THIS file wins.
> Deep operational detail lives in `docs/task3_stage4_RUNBOOK.md`.

## 0. The one and only codebase

- **Single path:** the `ebim/` repo (this repo). Standalone, independent.
- **Working branch:** `agent/codex-task3-grasp` (HEAD `3d429db0`).
- **Remote:** `origin` = https://github.com/Sushruths04/ebim_hackthon.git
  (NOT yet pushed since 2026-07-22 — push when ready; the 5.8 GB `outputs/` is
  kept out of the working tree but preserved in `.git`).
- All other local folders (`EBiM-benchmark`, `EBiM-benchmark-codex`,
  `ebim_hackthon`, `ebim_hackthon_ci`) are **redundant** — every branch and both
  sibling tips are mirrored here (see tags `preserved/*`). Safe to delete.
- **No Google Cloud** going forward (billing paused). Next runs = Lightning AI.

## 1. PROVEN / DONE (verified with evidence)

| # | Fix | Where it lives | Status |
|---|---|---|---|
| 1 | **Navigation gate** — base wheel damping **500** written at runtime (`TmrBaseAdapter`), `route_via_door` (doorway x=-4.14, kitchen lane y=-0.37), arms ramp to `TRANSIT_ARM_POSE` before driving | `task3_autonomy/skills.py`, `task3_autonomy/navigation.py` | ✅ PASSED (2.9 cm terminal error) |
| 2 | **10/10 cup grasp-lift** (skip-nav, base square to cup) — gripper cages ~0.076 rad, lifts 0.088 m, holds 3 s | `scripts/task3/verify_grasp_lift.py` | ✅ PASSED (deterministic scene). **This is the source of truth for all cup-grasp constants.** |
| 3 | **Stage-4 grasp constants restored** — `CUP_GRASP_Y_OFFSET=0.06`, `CUP_GRASP_HEIGHT_ABOVE_ORIGIN_M=0.068`, `FINAL_APPROACH_CONTACT_TOLERANCE_M=0.10` (had regressed to 0.0 / 0.100 / 0.15) + `NORTH_STANCE` unreachable-warning comment | `scripts/task3/run_stage4_cleanup.py` (commits `e891b107`, `3d429db0`) | ✅ COMMITTED, CI-green, 15 tests pass. Improves the run but does **not** yet pass Stage 4 (see §2). |
| 4 | **Stage-4 RUNBOOK** — scorer truth, reach law, GPU/Lightning run steps, anti-pattern checklist | `docs/task3_stage4_RUNBOOK.md` | ✅ |

## 2. NOT DONE / OPEN (do not claim these are finished)

- **Stage 4 does NOT pass yet.** Latest GPU run (`r-poc1`, 2026-07-22, proof in
  `outputs/task3_stage4_grasp_POC/`): approach + descend are clean, but the
  gripper closes to only **0.58 rad** (catches the cup body 5 cm too high, not
  the rim cage), then a **right-arm IK failure during the lift flings the cup**
  (`passed=false`, `failed_phase=hold`). The `object_lift_m=0.1615` is a fling
  artifact, not a real grasp.
- **Next levers (one per run, GIF-first):** (a) soften base-hold
  `MANIP_BASE_HOLD_POSITION_KP 12→4`, `MAX_LINEAR 0.30→0.25` so the arm can
  descend the last 5 cm to the rim; (b) replace Stage 4's spine-to-0.57 lift
  with `verify_grasp_lift.py`'s proven lift (no IK failure); (c) remember the
  **scorer needs no hold** — object XY inside sink `x[-4.245,-3.805]
  y[-2.413,-2.043]` at `z≥0.74699`; the cup only needs ~0.29 m south, so a
  stable partial grip + base-carry, or a controlled slide with a hard stop, may
  score without a perfect cage.
- **Stages 2 & 3, chained FSM, VLA track** — not started.

## 3. Scorer ground truth (never optimize this away)

`scripts/evaluation/task3/grading.py::score_stage4_cleanup`: an object passes if
its XY footprint overlaps the sink rectangle **and** `z ≥ 0.74699`. No grasp /
lift / carry is required by the scorer. Cup starts `(-4.185,-1.753,0.747)` —
already X-aligned and z-passing; only needs ~0.29 m south.

## 4. Next step (Lightning AI)

1. `git clone` this repo on Lightning (after pushing code — small, no `outputs/`).
2. Build the Isaac Lab container; run per RUNBOOK §6.
3. Apply lever (a), then (b); GIF-first diagnosis each run.
4. Freeze on first `passed=true`, export proof bundle (video + JSON).
