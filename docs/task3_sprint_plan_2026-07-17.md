# EBiM Task 3 — 72-Hour Completion Sprint Plan (2026-07-17)

**Audience: ALL agents (Claude / Codex / OpenCode).** Read this top to
bottom at session start, then read `docs/AGENT_STATE.md` for live progress,
then claim work. The master plan (`docs/task3_master_plan.md`) remains the
architectural source of truth; this document compresses its Phases 1–6 into
the sprint constraint below.

---

## 1. Context & binding constraint

Task 3 (Assisted Living & Feeding): mobile FR3 Duo completes a 4-stage
service cycle in Isaac Sim. 4 pts/stage, 16 max; ranking = highest stage →
score → time; Full Autonomy required (scripted FSM is legal). Portal
deadline Aug 3 (submit by Aug 1).

**The GCP lab account (`devstar2361@gcplab.me`, project `ebim26ham-236`)
expires in <3 days (≈ Jul 19–20).** All GPU work must finish and every
artifact must be exported off-cloud (GitHub fork + local downloads) before
expiry. The user works 24/7, rotating Claude / Codex / OpenCode (each has
~5-hour usage windows) — hence the git-based shared memory below.

**Priority: COMPLETE the task first; accuracy and speed tuning come after.**

## 2. Compute state (updated 2026-07-17)

| Resource | State |
|---|---|
| `sim-dev` (g2-standard-16, 1×L4, us-central1-c) | STOPPED — proven-working Isaac box, verified render. **NEVER DELETE.** Fallback if g4 fails. |
| `sim-dev-g4` (g4-standard-12, 1×RTX PRO 6000 Blackwell, SPOT, us-east5-a) | CREATED 2026-07-17 from snapshot. Driver fix in progress: snapshot's proprietary 580 driver does NOT support Blackwell (`NVRM: GPU 10de:2bb5 not supported`); fix = `nvidia-driver-580-open`. Isaac render NOT yet verified on it. |
| Snapshot `sim-dev-verified-20260717-1310` | READY (global) — boots either VM family in ~10 min. Dies with the account; GitHub is the real backup. |
| Quota | `GPUS_ALL_REGIONS = 1` → **only ONE GPU VM can run at a time** (that's why sim-dev is stopped). RTX PRO 6000: spot quota 1 (in use by sim-dev-g4), on-demand plain 0, VWS 1. L4 quota 1. |
| Post-expiry fallbacks | (1) personal project `gen-lang-client-0186028838` (auth `mitvho09@gmail.com`; L4×2 quota request pending since Jul 16 — check daily). (2) Lightning L40S (~70 EUR). Modal = pure-PyTorch only (CANNOT run Isaac — proven). |

**GPU rules (hard, from the owner):** smallest config that works; escalate
only on measured evidence; stop instances whenever work pauses; if the g4
spot VM gets preempted repeatedly, fall back to sim-dev (L4) rather than
fighting it; snapshot the g4 disk as soon as Isaac is verified on it. Log
every session in `docs/gpu_budget_log.md`.

## 3. Multi-agent coordination (Workstream A — do first, CPU-only)

The fork (`github.com/Sushruths04/ebim_hackthon`) is the sync bus.
**Session start: `git pull` → read `docs/AGENT_STATE.md`. Session end:
update AGENT_STATE.md → commit → push → record whether any GPU VM was left
running.**

- Branch ownership: `main` = Claude (integration + sim work),
  `agent/codex-packaging` = Codex, `agent/opencode-data` = OpenCode.
  Only Claude merges to main. Worktrees already exist beside the repo.
- **GPU sharing: there is ONE GPU VM.** The sim/FSM track owns it. Codex
  and OpenCode tracks are deliberately CPU-local (packaging, docs, tooling,
  unit tests) so they never contend.
- Files to create in this workstream (if not yet present):
  1. `AGENTS.md` (repo root) — this protocol, condensed; Codex/OpenCode
     read it natively; add a pointer line in `CLAUDE.md`.
  2. `docs/AGENT_STATE.md` — living handoff: DONE (with proof links) /
     IN PROGRESS (who, branch) / NEXT UP / BLOCKERS / GPU STATUS.
  3. `docs/PROJECT_JOURNAL.md` — supervisor-facing narrative: one entry
     per session (goal, what, why, evidence, lesson learned).
  4. `docs/simdev_setup.md` — how sim-dev/sim-dev-g4 were built (image,
     driver 580(-open for Blackwell), Docker, NGC, Isaac Lab 2.3.2,
     snapshot restore command) so setup survives account death.
  5. Update `docs/gpu_budget_log.md` for the new lab project/account.

## 4. Definition of Done (MANDATORY, unchanged from master plan §7.2)

No checklist item is done without a **proof bundle** in
`proofs/<phase>-<slug>/`: (1) video (`proof.mp4`) of the verification run,
(2) `result.json` (score/seed/head-placement/commit/date), (3) `repro.txt`
(exact one-line command), (4) a line in `docs/eval_results.md`. Tick the
checkbox + tag + push in the same commit. Frozen once proven — only the
regression batch may reopen a task. **Send the video to the owner**
(SendUserFile or pushed link) at every completion.

## 5. Sprint schedule (Workstream B — the GPU box)

### Day 1 (Jul 17) — GPU switch + harness + skills
- [ ] **Step 0 — finish sim-dev-g4 bring-up:** `nvidia-driver-580-open`
      installed, reboot, `nvidia-smi` shows RTX PRO 6000, `vulkaninfo`
      shows the NVIDIA ICD (not llvmpipe), then the Isaac render smoke test
      (same one that produced `rgb_0000.png` on the L4). **Snapshot the g4
      disk immediately after verification** (spot VM — preemption is
      expected). If bring-up exceeds ~1 more hour of work, STOP, restart
      sim-dev (L4), record evidence in the budget log, and move on — the
      sprint matters more than the GPU.
- [ ] **Phase 1 — verify `scripts/task3/run_episode.py`** (authored
      2026-07-16, never executed): `--policy idle --record-video`; fix the
      known risk (`isaacsim.core.prims.RigidPrim` init) live; deterministic
      reset check (same seed → identical spawns, 2 runs); measure episode
      wall-time (this is the GPU-sufficiency evidence). Proof bundle → tag
      `v0.1-harness`.
- [ ] Optional (owner wants to SEE the sim): enable Isaac WebRTC livestream
      + firewall rule for the owner's IP; put the URL in AGENT_STATE.md.
      Recorded video remains the proof medium.
- [ ] **Phase 2 — skills** in `task3_autonomy/`:
      - Wire the proven `navigation.py` math into a live `navigate_to()`
        (PhysX/tensor pose reads ONLY — never USD xforms while playing;
        `tmr_base_control` helpers) → `verify_navigate.py`
        kitchen↔dining ±3 cm/3°, video.
      - `reach()` per the documented design finding in the master plan §10
        Phase 2 (reuse `scripts/common/teleop_targets.py`; FIRST write +
        unit-test the missing quat→rpy inverse by round-tripping
        `_quaternion_from_rpy`); then `grasp()`/`release()` (hold
        predicate), `lift()`, `place()`.
      - **Critical gate: `verify_grasp_lift.py` ≥ 8/10 seeded runs, video.**
        If unstable after ~6 focused hours: grasp the TRAY instead of
        utensils; kinematic attach only as last resort (owner must OK
        legality). Tag `v0.1-skills`.

### Day 2 (Jul 18) — points on the board
- [ ] **Phase 3 — Stage 1 FSM** (navigate → grasp tray → transport →
      place per `grading.py` predicates → release → retreat); retry
      budgets + timeouts on every state. Exit: ≥4/5 pts on ≥7/10 runs,
      ≥3 head placements. Tag `v0.1-stage1`, send video.
- [ ] **Phase 4 — remaining stages, ranking-optimal order:**
      - **Stage 4 first** (utensils → sink; easiest; reuses Stage 1 skills).
      - **Stage 2** (scoop beans; 3 s hold ~20 cm before head; capped
        approach speed for the ISO force gate; return beans).
      - **Stage 3** (bowl → recovery region; slow low pour; ratio-scored —
        partial credit fine).
      - Exit per stage: ≥3/4 pts on ≥6/10 seeded runs, video, tag.

### Day 3 (Jul 19) — chain, package, EXPORT
- [ ] **Phase 5 (reduced)** — chained 1→2→3→4 episode; fix inter-stage
      carryover; reduced matrix: 3 head placements × 5 seeds = 15 headless
      runs; results table in `docs/eval_results.md`.
- [ ] **Phase 6 — submission package** (Codex drafts from Day 1; Claude
      integrates): Dockerfile (Isaac Lab base image, one-command
      deterministic entrypoint); fork README rewrite (exact run command,
      expected output, hardware needs, video links); dry-run the Docker
      build on the GPU box.
- [ ] **EXPORT RITUAL (mandatory final GPU session):** push everything
      (code, proofs, JSONs); large videos → GitHub release assets AND
      `gcloud compute scp` to the local Windows machine; final disk
      snapshot; STOP all instances; log final spend.
- [ ] Submission form by Aug 1 from the packaged repo (survives account
      death). Post-expiry fixes → personal-project L4 (if quota granted)
      or Lightning.

## 6. Parallel agent tracks (CPU-only, start immediately)

**Codex (`agent/codex-packaging`):** Dockerfile skeleton + README
submission section (Phase 6 drafts); `docs/simdev_setup.md`;
`docs/PROJECT_JOURNAL.md` scaffold; keep both updated as main advances.

**OpenCode (`agent/opencode-data`):** proof-bundle helper script
(`scripts/task3/make_proof_bundle.py`: collects video+JSON+repro into
`proofs/<slug>/` and appends the eval_results line); the 15-run batch
script for Phase 5; `--record-lerobot` flag design for `run_episode.py`
(Phase 7 prep — code + unit tests only, no GPU, never blocks submission).

## 7. Contingencies

- g4 spot preempted → restart it; if preempted >2×/day, fall back to
  sim-dev (L4). Both boot from snapshots in ~10 min.
- Grasping fails → tray-grasp → kinematic attach (ask owner re: legality).
- Beans/scooping fails → ship stages 1+4 solid; 2–3 partial (ratio credit).
- Lab account dies early → the fork has everything pushed at every exit
  criterion; that push discipline is the insurance policy.

## 8. Verification (how anything gets believed)

- Per task: its `verify_*.py` / `run_episode.py` one-liner → proof bundle →
  eval_results line → tag → push → video sent to owner.
- Fast regression after ANY change:
  `python -B scripts/evaluation/task3/tests/test_grading.py` +
  `task3_autonomy` unit tests (CPU, seconds).
- Session end: AGENT_STATE.md updated + pushed; GPU state recorded;
  `modal app list` clean.
- Final: `docker build && docker run` from a clean clone reproduces a
  graded full episode.
