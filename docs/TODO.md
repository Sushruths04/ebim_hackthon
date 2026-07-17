# Task 3 Sprint TODO — shared across Claude / Codex / OpenCode

Rules: any agent continues from the FIRST unchecked box (respect the [GPU]/
[CPU] tag and your branch from `AGENTS.md`). Tick a box ONLY in the same
commit that adds its proof (video/JSON/log per master plan §7.2 — for pure
code tasks, a passing-test transcript). After every session, append one
line to the Session Log at the bottom (this is the shared memory), update
`docs/AGENT_STATE.md`, commit, push. Full context:
`docs/task3_sprint_plan_2026-07-17.md`.

## Day 1 — Infrastructure + Harness (Jul 17)

- [x] RTX PRO 6000 bring-up: `sim-dev-g4b` (full 96 GB, spot,
      us-central1-b) renders Task 3 room in 9.4 s; snapshot
      `sim-dev-g4b-verified-20260717`; proof image sent to owner.
      Fractional vGPU shapes proven unusable (see AGENT_STATE.md).
- [x] Multi-agent coordination: sprint plan + AGENTS.md + AGENT_STATE.md +
      this TODO, all pushed; worktrees aligned.
- [ ] [GPU] **Phase 1a: `run_episode.py --policy idle` completes** —
      4 bugs fixed so far (commits `34896ce f9c51f4 2d23b63 8431332`);
      continue the crash→fix→rerun loop (crash_traceback.txt in the
      episode dir tells you the next bug; rerun command in AGENT_STATE.md).
- [ ] [GPU] Phase 1b: video frames + `EPISODE_RESULT` JSON line produced.
- [ ] [GPU] Phase 1c: determinism — same seed twice → identical spawn
      poses (diff the logged object poses).
- [ ] [GPU] Phase 1d: proof bundle `proofs/phase1-harness/` + line in
      `docs/eval_results.md` + tag `v0.1-harness` + push.

## Day 1–2 — Skills (Phase 2)

- [ ] [GPU] `navigate_to()` wired to live sim (pure math already proven in
      `task3_autonomy/navigation.py`; use PhysX/tensor pose reads only,
      never USD xforms while playing).
- [ ] [GPU] `verify_navigate.py`: kitchen↔dining ±3 cm/3°, video, proof.
- [ ] [CPU] quat→rpy inverse in `task3_autonomy/` + unit tests
      (round-trip `_quaternion_from_rpy` from
      `scripts/common/teleop_targets.py` — design note in master plan §10
      Phase 2 "reach()" item).
- [ ] [GPU] `reach(arm, world_pose)` via TeleopCommand one-step delta.
- [ ] [GPU] `grasp()`/`release()` with hold predicate; `lift()`, `place()`.
- [ ] [GPU] **`verify_grasp_lift.py` ≥ 8/10 seeded runs + video (CRITICAL
      GATE)** — if unstable after ~6 h: grasp the TRAY, not utensils;
      kinematic attach only with owner's legality OK. Tag `v0.1-skills`.

## Day 2 — Points (Phases 3–4)

- [ ] [GPU] Stage 1 FSM (navigate→grasp tray→transport→place per
      `grading.py`→release→retreat); retries+timeouts on every state.
- [ ] [GPU] Stage 1 exit: ≥4/5 pts on ≥7/10 runs, ≥3 head placements,
      videos. Tag `v0.1-stage1`. SEND VIDEO TO OWNER.
- [ ] [GPU] Stage 4 FSM (utensils→sink; reuses Stage 1 skills). ≥3/4 pts
      on ≥6/10 runs. Tag.
- [ ] [GPU] Stage 2 FSM (scoop, 3 s hold ~20 cm before head, capped
      approach speed, return beans). ≥3/4 on ≥6/10. Tag.
- [ ] [GPU] Stage 3 FSM (bowl→recovery region, slow low pour). ≥3/4 on
      ≥6/10. Tag.

## Day 3 — Chain + Package + EXPORT (Phases 5–6)

- [ ] [GPU] Chained 1→2→3→4 single episode; fix inter-stage carryover.
- [ ] [GPU] Reduced matrix: 3 head placements × 5 seeds = 15 runs →
      results table in `docs/eval_results.md`.
- [ ] [CPU] Dockerfile (Isaac Lab base, one-command entrypoint) — Codex
      can draft ANY TIME from Day 1 on `agent/codex-packaging`.
- [ ] [CPU] Fork README rewrite: run command, expected output, hardware,
      video links.
- [ ] [GPU] Docker dry-run on sim-dev-g4b from a clean clone.
- [ ] [GPU] **EXPORT RITUAL before lab account dies (≈ Jul 19-20):** push
      all; scp videos to local Windows; final snapshot; STOP all
      instances; log spend.
- [ ] [Manual/owner] Submission form by Aug 1.

## Parallel CPU tracks (never block the GPU track)

- [ ] [CPU/OpenCode] `scripts/task3/make_proof_bundle.py` (collect
      video+JSON+repro into `proofs/<slug>/`, append eval_results line).
- [ ] [CPU/OpenCode] 15-run batch script for the Day 3 matrix.
- [ ] [CPU/Codex] `docs/simdev_setup.md` (VM/driver/docker recipe — the
      GPU STATUS section of AGENT_STATE.md has all facts).

## Session Log (shared memory — append one line per session)

- 2026-07-17 (Claude): GCP RTX PRO bring-up end-to-end (quota probe →
  spot create → GRID/open driver saga → verified 9.4 s render → snapshot);
  Phase 1 debug loop started, 4 harness bugs fixed (see AGENT_STATE.md);
  all coordination docs created and pushed.
