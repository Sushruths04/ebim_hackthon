# Task 3 Evaluation Results Log

One line per completed, proven task (docs/task3_master_plan.md section 7.2
Definition of Done). Links point at the proof bundle in `proofs/`.

| Date | Task | Commit | Result | Proof |
|---|---|---|---|---|
| 2026-07-16 | phase2-navigation-math | 9d6ac47 (parent) | 14/14 tests passed | `proofs/phase2-navigation-math/` |
| 2026-07-17 | phase1-harness | b4be9d5 | idle episode: 160 frames + EPISODE_RESULT JSON; seed-42 twice -> SPAWN_MATCH True (300 beans + 5 props bit-identical) | `proofs/phase1-harness/` |
| 2026-07-17 | phase2-navigate-live | fdf9476 | live NavigateTo PASSED: arms tucked (probe-measured pose), doorway crossed, stop 2.9 cm from island-side target in 14.7 s sim | `proofs/phase2-navigate-live/` |
| 2026-07-18 | phase2-grasp-reliability | pending Day 1 commit | 10/10 PASS; 0.088 m lift and 3.0 s hold per trial; deterministic repeatability gate | `proofs/phase2-grasp-reliability/` |
| 2026-07-18 | phase3-stage1-kinematic | pending Day 2 commit | 10/10 PASS at 5/5 across head placements a/b/c; FSM reaches complete; kinematic scene adapter, not physical tray-contact proof | `proofs/phase3-stage1-kinematic/` |
