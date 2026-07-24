# Task 3 — Full Plan & Handoff (2026-07-24, Claude session → OpenCode)

**Read this whole document before touching any code.** It supersedes
`docs/HANDOFF_2026-07-24_Stage2_grasp_v3.md` (that doc's "7 GPU runs" table
was unverified — see `docs/AGENT_STATE.md` top section for the correction)
and consolidates everything found in this session with a concrete,
sub-tasked plan for every remaining stage.

**Goal, never lose sight of this:** a working, autonomous, scripted FSM that
completes as many of the 4 Task 3 stages as possible, each with a real
physical proof bundle, submitted by **Aug 1** (hard deadline Aug 3). Today
is **2026-07-24 — about 7-8 days left.**

---

## 0. Answer to "should we use a VLM / teleoperation / RL instead?"

**No to all three. Here's why, concretely:**

- **RL/PPO:** not required. The competition's autonomy rule is "Full
  Autonomy required, scripted FSM is legal" — a scripted FSM with
  closed-loop sensing (what we already have) satisfies it. Training a
  policy from scratch now, with 0/4 stages proven and ~7 days left, would
  almost certainly cost the submission. Decided 2026-07-16, re-confirmed
  2026-07-24.
- **VLM for perception:** would be strictly worse than what we have. This
  is a privileged-state simulation — object poses are read directly from
  PhysX (`spoon_view.get_world_poses()`, etc.), which is exact. A VLM
  reading pixels to re-derive a pose we already have exactly would only
  add latency and noise, not fix anything. The actual bugs found this
  session are pure **kinematics/control** problems (arm reach, base
  translation, yaw drift) — a VLM does not touch that layer at all.
- **VLM for grasp verification as the pass/fail signal:** not worth it. We
  already have a much cheaper, deterministic way to check this using data
  we already compute — see §2.2 below. A vision model is slower,
  non-deterministic, and solves a problem a 5-line telemetry check already
  solves.
- **VLM as an automated frame-diagnosis narrator — genuinely useful,
  do this (§0.1).** Different from the point above: not for deciding
  pass/fail, but for turning the rendered frames (already produced by
  every `--record-video` run) into a plain-text description any
  text-only agent can read, without a human manually pulling PNGs over
  `scp` and eyeballing them (which is what happened, by hand, this whole
  session — I am a multimodal model, so I *was* doing this manually;
  automating it removes me/a human from that specific loop).

### 0.1 VLM-as-narrator — concrete sub-task (tooling improvement, do independent of the physics fixes above)

**Model:** a small open-source VLM, self-hosted **on the lightning.ai VM**
(no local GPU available) — `Moondream2` (~1.8B, ~4-5GB VRAM, Apache-2.0) or
`Qwen2-VL-2B-Instruct` (similarly small, slightly stronger). Do not reach
for a 7B+ model — this is simple VQA ("is the gripper closed around
anything," "did the object move between these two frames"), not
open-ended reasoning; a bigger model only costs more VRAM/time for no
benefit here.

**Integration point:** run it as a **post-processing step after Isaac Sim
exits**, not concurrently (let the sim's ~5-6GB VRAM free first, then load
the VLM, batch over the run's key frames — e.g. the 5-10 frames spanning
each phase transition near the failure point — then unload). Write output
to a plain-text `outputs/<run_dir>/vlm_summary.txt` alongside
`result.json`, one line per analyzed frame, e.g.:
```
frame_0056 (tick~5544, phase=descend_spoon): gripper fingers visible,
appear open/empty; small object visible on table ~3cm to the left of
the fingertips, not between them.
```

**What this buys:** a text-only agent (if OpenCode's harness can't view
images) gets the same diagnostic signal a human/multimodal reviewer would
get, automatically, every run — closing exactly the gap that made this
session's frame-pulling manual and slow.

**What this does NOT do:** decide pass/fail (that's §2.2's telemetry
check, which is exact and instant) or fix any of the actual kinematics
bugs in §2.1. Treat it as a debugging aid, not a control-loop component.
- **Teleoperation:** explicitly out of scope for the graded submission
  (Full Autonomy required; teleop was only ever considered for collecting
  demonstration data for a *stretch-goal* learned policy, and that track is
  parked — see `[[ebim-task3-strategy]]` memory / `docs/AGENT_STATE.md`).
  Do not add a teleop path to solve the current blocker.

**Bottom line:** stay on the scripted-FSM path. The remaining work is
debugging real kinematics/physics bugs, not an architecture change.

---

## 1. What's actually done vs. claimed (per the project's own proof ledger)

Per `docs/eval_results.md` (the Definition-of-Done ledger — the only source
that counts, not verbal claims): **0 of 4 scored stages have a real,
physically-autonomous proof bundle yet.** What IS proven:

| Proven | Evidence |
|---|---|
| Navigation primitive (corridor drive, door transit, arm-tuck to avoid collision) | `proofs/phase2-navigate-live/`, reused across all stages |
| Isolated grasp-and-lift physics (pre-positioned, not through navigation) | `proofs/phase2-grasp-reliability/`, 10/10 |
| Stage 1 FSM + grading logic | `proofs/phase3-stage1-kinematic/` — **kinematic only, explicitly logged as NOT an autonomous run** |

Everything else (Stage 1 physical pinch+lift, Stage 2 feeding, Stage 3
transport, Stage 4 cleanup) has **no** frozen proof bundle. Some have prior
"success" claims in chat/handoffs that turned out to be overclaimed when
checked against real artifacts (see `[[ebim-r-poc25-overclaim-2026-07-23]]`
memory and the Stage 2 v3-handoff correction this session) — **do not
trust a "passed" claim anywhere in this project's history without reading
the actual `result.json`/log/frames yourself.**

---

## 2. Stage 2 (Feeding) — current blocker, most detail, most progress

### 2.0 What's proven this session (GPU-verified, not claimed)

- Navigation to the island (`ISLAND_STANCE`) works.
- `pregrasp_spoon` works (arm reaches 19cm above the spoon reliably).
- Two real bugs found and fixed in the base-driving code (commits
  `86590df6`, `8aef9f66`) — both real, both GPU-confirmed, neither
  sufficient on their own.
- **The actual root blocker found (commit `60580fd1`):** `descend_spoon`
  converges only to ~0.10-0.12m of the true target (a spoon handle is
  ~1-2cm wide), the code's own fallback accepts this as "close enough,"
  `close_spoon` then closes the gripper on **empty air**
  (`gripper_position_rad: 1.0119`, more open than the ~0.9 resting-open
  angle), and **every phase after that (`spoon_grasped`, `lift_spoon`,
  `tuck_for_dining`, `navigate_dining_waypoint`) reports `"ok": true` while
  the spoon is in unbounded freefall** (z observed at -160, -330, -608,
  -1238, -2139 across ticks — falling forever, never held). None of the
  downstream phase checks verify an actual hold.

### 2.1 Sub-task A — fix the base-approach geometry (recommended: redesign, not patch)

**Do not keep patching the two-phase `pregrasp → drive 8cm closer →
re-pregrasp` sequence.** Three attempts this session (anchor-release fix,
arm-lift-before-drive fix, offset-magnitude diagnostics) all showed the
same signature: the base barely translates and yaws 0.15-0.3 rad
regardless of the fix, most likely because the base's own physical
footprint contacts the island cabinet at any stance closer than the
originally-proven `ISLAND_STANCE = (-3.47, -1.61)` — this is unconfirmed
but is the leading hypothesis (see `docs/AGENT_STATE.md` top section for
full reasoning).

**Recommended approach — redesign, not patch:**
1. Delete the `approach_spoon` / `lift_before_approach` /
   `repregrasp_after_approach` phases entirely (they were added this
   session, commits `f6558f82`, `8aef9f66`, `86590df6` — revert or just
   remove the phase code, the anchor-fix logic can go with it).
2. Instead, find a single **static** stance, closer to the spoon than the
   current `ISLAND_STANCE`, that the base can navigate to **directly**
   (one `drive_to` call, no secondary approach maneuver) and hold there
   collision-free. Use `--skip-navigation` (validated this session — same
   failure signature in half the wall-clock time, ~5 min vs ~9 min) to
   iterate fast:
   ```
   python scripts/task3/run_stage2_feeding.py --out-dir outputs/task3_stageX --skip-navigation --record-video --fast-exit
   ```
3. **Before trying a new stance value**, actually measure the base's
   collision footprint and the island's true boundary near this specific
   stance (don't reuse `ISLAND_EAST_FACE_X=-3.77`/`BASE_HALF_WIDTH=0.40`
   from `task3_autonomy/navigation.py` blindly — those were computed for a
   different maneuver/direction). A cheap way: bisect — try stances at
   -3.50, -3.52, -3.54 (i.e. 3, 5, 7cm closer than -3.47) with
   `--skip-navigation`, and find the closest one where the base actually
   reaches the target within 2cm and yaw stays within ~2° of nominal. That
   tells you the real limit empirically instead of guessing.
4. Once a working closer stance is found: re-test the *full* navigation
   path to it (not just `--skip-navigation`) to confirm it's still reachable
   through the corridor/door route, since the original `ISLAND_STANCE` was
   chosen partly for that reason.
5. **One variable at a time.** Don't change the stance AND the descend
   logic AND the grasp offsets in the same commit.

### 2.2 Sub-task B — add a real grasp-verification check (do this regardless of 2.1's outcome)

This is independent of the approach-geometry problem and protects every
future run from the false-positive pattern found this session (and
previously in Stage 4, see `[[ebim-r-poc25-overclaim-2026-07-23]]`).

**Implementation (cheap, deterministic, no VLM needed):** after
`close_spoon`, before proceeding to `lift_spoon`, run a short verification
window (e.g. 10-20 ticks) where you:
1. Record the gripper's end-effector position and the spoon's tracked
   world position.
2. Command a small arm motion (or just let `lift_spoon` start).
3. Check that the spoon's position stays rigidly consistent with the
   end-effector (sub-cm relative distance, moving together) — this exact
   technique was already validated in this project for Stage 4
   (`r-poc27`, object-to-EE distance consistency across phases). If the
   distance grows or the spoon's z drops unexpectedly, **fail the phase
   immediately** with an honest `"failed_phase": "close_spoon"` /
   `"grasp_not_verified"` rather than reporting false success.
4. Also just sanity-check `gripper_position_rad` directly: if it's within
   ~0.05 rad of the fully-open resting angle after a close command, that
   alone means nothing was grasped — fail fast on this cheap check before
   even doing the relative-distance check.

This turns "silently reports success on an empty gripper" into "fails
loudly and immediately," which is strictly better for debugging even
before 2.1 is fixed.

### 2.3 Once grasp works: remaining Stage 2 sub-tasks (untested territory)

Nobody has gotten this far yet. Each of these needs its own GIF-first
diagnosis, not a guess-and-bundle fix:
- `scoop` phase (bean pickup) — prior handoff claims "0 beans every run,"
  never GPU-verified this session. `--scoop-pitch-deg` (default 30.0) is
  the first lever to sweep, per the original master plan risk table.
- `feed` / `head_found` / insertion positioning near the head — safety-
  capped approach speed required near the head (master plan risk table).
- `hold` gate (3s continuous hold at the head).
- Once all pass: produce the real Definition-of-Done proof bundle (video +
  result.json + repro.txt + `docs/eval_results.md` line) and freeze it —
  do not rework a frozen stage without the owner's explicit request.

---

## 3. Stage 1 (Table Setup / tray slide) — next after Stage 2

**Status:** kinematic FSM + grading logic proven
(`proofs/phase3-stage1-kinematic/`, 10/10 at 5/5 across head placements) —
explicitly logged as NOT a physical/autonomous proof. Physical sub-gate
"slide-to-overhang" is reliable per earlier session notes; the full
"single-edge pinch+lift" physical gate has never passed.

**Sub-tasks:**
1. Read `docs/AGENT_STATE.md`'s "Day 3 Step 1" history (the long round-by-
   round log lower in that file) before touching this — many prior
   attempts are already documented, don't repeat them blind.
2. GPU-verify the current slide-to-overhang code state fresh (don't trust
   old logs — verify with a new run and the GPU gate).
3. Diagnose the pinch+lift gate specifically with GIF-first analysis
   (`[[gif-first-failure-analysis]]` memory: this project's established
   practice — read the recorded GIF/frames around the pinch/lift
   transition before tuning any parameter).
4. Objects to place: `simple_tray`, `bowl2`, `spoon2`, `plate2`, `cup` (5
   objects, scored independently by XY-in-dining-area only per
   `grading.py::score_stage1_table_setup` — z is discarded, no lifting
   required for scoring, only for physically moving the object there).
5. Freeze with a real proof bundle once physical pinch+lift passes
   reliably (≥6/10 runs per master plan's own bar).

---

## 4. Stage 4 (Cleanup / utensils to sink) — root cause known, plan unexecuted

**Status:** root cause already diagnosed in a prior session
(`[[ebim-stage4-rootcause-2026-07-22]]` memory): base-stance geometry
issue — the proven grasp from `verify_grasp_lift.py`'s skip-navigation
conditions was never ported to the real navigated approach geometry.
Scorer requires no grasp integrity, just XY-in-sink + z≥0.747 — cup needs
to move ~0.29m south. A corrective plan document exists
(`docs/task3_stage4_corrective_plan.md`) but was never executed.

**Sub-tasks:**
1. Read `docs/task3_stage4_corrective_plan.md` in full before starting.
2. Read `[[ebim-r-poc25-overclaim-2026-07-23]]` memory FIRST — a prior
   "Full E2E Success" claim on this exact stage was overclaimed (misleading
   metric, unresolved descend stall, empty-gripper frame ambiguity). Do not
   repeat that mistake — verify everything against real artifacts.
3. Apply the SAME grasp-verification check from §2.2 here too — this
   codebase has the identical "reports success without checking actual
   hold" gap in this script as well.
4. Execute the corrective plan's ordered steps; GPU-verify each; log real
   evidence in `AGENT_STATE.md` after every run per this project's own
   rules.

---

## 5. Stage 3 (Bean Recovery / cup transport) — needs real re-verification

**Status:** grasp+lift proven in isolated/skip-navigation conditions
(10/10), but integrated with real navigation the geometry differs (per
Stage 4 root-cause memory: "the recorded right-arm grasp differs from
skip-nav geometry"). A prior "Full E2E Success" claim for this stage
(`r-poc25`) was found to be overclaimed on re-review — see
`[[ebim-r-poc25-overclaim-2026-07-23]]`. Treat as **unproven** until a
fresh run is independently verified.

**Sub-tasks:**
1. Do not reuse or cite the r-poc25/r-poc27 result as proof — re-run fresh.
2. Apply the §2.2 grasp-verification check here as well before trusting
   any "held" claim.
3. Densely sample frames through the actual close→lift→hold window (not
   sparse sampling — a prior session's sparse-sample "verified" call was
   itself later found wrong on dense re-sampling, see the same memory's
   "CORRECTION" section) before declaring this stage passed.

---

## 6. Non-negotiable rules for whoever works this (OpenCode or otherwise)

These exist because this exact project has already been burned by
violating them, more than once, including this session:

1. **Every claim about a GPU run's outcome must be backed by a pasted
   result.json line, log excerpt, or frame you actually opened this
   session.** If you didn't read it this turn, you don't get to state its
   contents. (Rule already in `docs/HANDOFF_2026-07-24_Stage2_navdining_fix.md`,
   violated once already by a prior session on this exact task.)
2. **One hypothesis, one code change, one GPU run.** Never stack fixes.
   If 3 fixes fail on the same specific symptom without narrowing the
   problem, stop and raise an architecture question rather than trying a
   4th blind fix (`superpowers:systematic-debugging` Iron Law).
3. **GPU-verification gate before trusting any run:** host `nvidia-smi`,
   `docker exec <container> nvidia-smi`, grep the log for
   `llvmpipe`/`No device could be created`/`software rasterizer` (any hit
   = discard the run entirely), confirm `cuda:0` in the boot log, confirm
   GPU utilization goes nonzero once physics starts.
4. **A phase reporting `"ok": true` is not proof an object was grasped/
   held** — this session found that gap is real and current in at least
   two scripts (Stage 2, and previously Stage 4). Check §2.2's kind of
   verification, not just the phase flag.
5. **Update `docs/AGENT_STATE.md` and commit+push after every meaningful
   result, pass or fail.** Unpushed work does not exist for the next
   session. Check for another agent's concurrent uncommitted edits before
   committing (this happened once this session between Claude and
   OpenCode — reconcile, don't silently overwrite).
6. **Standard physics only** — no kinematic attach, no scene/asset edits,
   no teleportation. Hard competition-legality rule, followed throughout
   this project.
7. Stop the GPU/container at natural pause points; this project has no
   budget for idle spend (Lightning AI is the only paid venue left, GCP is
   hard-banned — see `[[gpu-cost-discipline]]` memory).

---

## 7. Environment — verified working state as of this session

- SSH: `s_01ky82mwnw8s1125cnc3gajaaw@ssh.lightning.ai` (changes across
  Studio restarts — verify live with `nvidia-smi` over SSH, don't trust an
  old string).
- Repo on VM: `~/EBiM_Challenge` = `/teamspace/studios/this_studio/EBiM_Challenge`,
  branch `task3-current-clean`. **Ignore** `/home/zeus/ebim_hackthon` on the
  same VM — unrelated, older, unused checkout.
- Container: `isaac-lab-2-3-2-workshop`, image `isaac-lab-2.3.2:ebim2026`,
  built and cached this session. Bring-up: `bash scripts/task3/lightning_workflow.sh bootstrap`
  (fast — layer-cached, not a from-scratch build). Stop when pausing:
  `bash scripts/task3/lightning_workflow.sh stop`.
- Fast iteration: `--skip-navigation` flag drives directly to the island
  stance, validated this session to reproduce the same failures in about
  half the wall-clock time of the full navigation path — use it for any
  Stage 2 grasp-geometry iteration.
- Current HEAD as of this handoff: `60580fd1` on `task3-current-clean`,
  pushed to `github.com/Sushruths04/ebim_hackthon`.

---

## 8. End goal reminder

The deliverable is **one working, end-to-end, fully autonomous scripted
FSM per stage**, each producing its own proof bundle, ranked by highest
stage reached → score → time. It does not need to be one single script
covering all 4 stages simultaneously — each stage is scored and frozen
independently — but it does need to run with **zero human intervention**
during the graded execution, which the current scripted-FSM-with-closed-
loop-sensing architecture already satisfies by design. The work remaining
is making each stage's FSM actually succeed physically, not changing the
architecture.
