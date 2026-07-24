# TASK 3 — MASTER EXECUTION PLAN (Organizer-Aligned, End-to-End, Autonomous)

**Author:** Opus supervisory session, 2026-07-24.
**Status:** AUTHORITATIVE execution plan. Supersedes the Stage-1/objective
sections of every prior handoff. Read this top-to-bottom before touching code.
**This document is the single reference an executing agent (Sonnet / OpenCode /
Codex) must cite and follow.** When in doubt, this file + the organizer rules
win over any older doc in `docs/`.

---

## 0. THE ONE REFRAME THAT CHANGES EVERYTHING (read first)

1. **`scripts/evaluation/task3/grading.py` is the organizers' DEV-TIME helper,
   NOT the official scorer.** Their own README says verbatim: *"It is not the
   official competition scorer."* It scores a lenient dining **rectangle** and
   wrongly includes `simple_tray`. **Do not treat it as the definition of
   done.** Use it only as a cheap CPU smoke-test.
2. **The authoritative spec is the prose competition rules**
   (`https://ebim-benchmark.github.io/competition.html`). Build to these.
3. **The tray-drag strategy is DEAD.** It optimized the rectangle proxy and a
   physical-pinch fidelity that neither the rules nor the organizers' own
   Stage-1 integration test (`disable_utensil_rigid_bodies=True`) require.
   Archive it (§2), do not extend it.
4. **Deadlines (verified live):** Phase I simulation = **Aug 10, 2026 (AoE)**
   (~17 days from today). Phase II real hardware = **Sep 10, 2026** — 7 onboard
   cameras, **NO privileged state**. This is why perception is built now (§3),
   not deferred.
5. **Autonomy:** Full autonomy required; a scripted/hybrid FSM is legal. **No
   fixed/hardcoded per-episode values** — every target is read from perceived
   or privileged world state each episode (seats are randomized; §5.1).

### 0.1 The real Task 3 rules, exactly

| Stage | Real requirement (prose rules) | Points |
|---|---|---|
| **1 Table Setup** | Carry **plate, cup, bowl-with-beans, spoon** (4 objects, **NO tray**) from the kitchen to **3 of 6 seats, randomly assigned per episode**. Objects start **stacked on a plate** in the kitchen. | 4 |
| **2 Feeding** | **Bimanual**: one arm holds the spoon, one steadies the bowl; scoop beans, hold at the head **≥ 3 s**, return the beans. | 4 |
| **3 Bean Recovery** | Empty the beans into the **scaled recycling bin** (scored by recovered-bean ratio: ≥0.8→2, ≥0.9→3, =1.0→4). | 4 |
| **4 Cleanup** | Return **all four utensils** to the **marked sink region**. | 4 |

- **Total 16 pts. Ranking: highest completed stage → total score → time.**
  → Reaching a higher stage beats perfecting a lower one. **Never hang;
  take partial credit and advance.**
- **Safety = HARD FAIL:** peak head/face force (ISO/TS 15066) + watchdog
  interventions. Stage 2 approach speed/standoff is the safety lever.
- **Process metrics (reported, not ranked):** SPARC smoothness, re-grasps,
  handovers. → minimize re-grasps, never trip a safety gate; don't over-tune
  smoothness.

---

## 1. TARGET ARCHITECTURE — one scripted brain, perceived state, modular skills

```
 ┌──────────────── PERCEPTION LAYER (pretrained, no training) ─────────────────┐
 │ eval_camera RGB-D (/World/Scene/eval_camera) → open-vocab detect + 6D pose  │
 │ Phase I: CROSS-VALIDATE against privileged PhysX poses (auto-label + trust). │
 │ Also: log (RGB-D, proprio, action, outcome) every skill → self-gen dataset. │
 └───────────────────────────────────────┬─────────────────────────────────────┘
                                          │ WorldState (poses, assigned seats)
                              ┌───────────▼────────────┐
                              │  ORCHESTRATOR           │  task3_pipeline/orchestrator.py
                              │  (Task3Pipeline +       │  + task3_autonomy/chained_fsm.py
                              │   Task3ChainFSM)        │  reads state → picks skill+target
                              └───────────┬────────────┘  → consults param memory
      each skill = SelfCorrectingSkill(execute → verify → retry-w/-adjust → record)
 ┌──────────┬───────────┬───────────┬───────────┬───────────┬───────────┬────────┐
 ▼          ▼           ▼           ▼           ▼           ▼           ▼        ▼
Navigate  Reach       Grasp        Place       Scoop       FeedHold    Pour   Carry
[S]       [S]        [S]→[L]      [S]         [S]→[L]      [S]         [S]     [S]
 └────────────────────── each returns metrics → AUTO-VERIFIER ───────────────────┘
                                          │  SUCCESS / WEAK / SLIP / IK_FAIL / MISS…
                              ┌───────────▼────────────┐
                              │  VERIFIER + POLICY      │  retry w/ new params (grid)
                              │  + JSON MEMORY          │  → escalate to [L] model
                              └─────────────────────────┘  → or accept partial, advance
```

**[S]** scripted (have it) · **[P]** pretrained perception (no training) ·
**[L]** learned fallback (ONLY if [S] < 70% after retry) · **[V]** verifier.

**Ruthless rule:** train a model for **at most two** skills (grasp, scoop), and
only if the scripted version stays <70% after the auto-retry loop. Everything
else stays scripted. If scripted grasp clears 70%, ship with **zero** training.

---

## 2. CODE DECISION — keep / archive / retarget / build

### 2.1 KEEP AS THE SPINE (adopt OpenCode's brain; commit it — currently untracked)
- `task3_pipeline/orchestrator.py`, `skills.py`, `policy.py`, `memory.py`,
  `outcomes.py` — the self-correcting orchestration brain. Good as-is.
- `task3_autonomy/chained_fsm.py` — fail-closed stage sequencer. Good as-is.
- `scripts/task3/verify_grasp_lift.py` — the **proven 10/10 grasp** and its
  constants (`STANCE=(-3.32,-1.72)`, `PREGRASP_Z`, `GRASP_Z=0.815`,
  `LIFT_Z=1.10`, `TRAVEL_SPINE_M=0.45`) and the `object_follows_end_effector()`
  hold-verification primitive. This is the crown jewel — the skill library
  wraps THIS, does not reinvent it.
- `task3_autonomy/navigation.py`, `skills.py`, `arms.py`, `rotations.py`,
  `recording.py` — proven navigation/arm/recording primitives.

### 2.2 ARCHIVE (move to `old/`, do NOT delete — keep the weeks of work)
Create `old/task3_tray_drag_ABANDONED_2026-07-24/` and `git mv` into it:
- `scripts/task3/probe_tray_slide.py` (tray-drag, dead objective)
- `scripts/task3/run_stage1_fsm.py` + `task3_autonomy/stage1_fsm.py` **IF** they
  encode the tray/5-object dining-rectangle logic (verify first, then move).
- Leave a one-line `old/task3_tray_drag_ABANDONED_2026-07-24/README.md`:
  "Archived 2026-07-24 — optimized the dev-helper rectangle proxy + tray-carry,
  which the organizer rules do not score. Kept for reference. See
  docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md §0."
- Do the same for any Stage-4 "scorer-exploit" code if it is a separate file.

### 2.3 RETARGET (rewrite to organizer rules)
- `task3_pipeline/stages.py` — rewrite `plan_stage1` (4 objects → 3 assigned
  seats, per-object pick-carry-place; NO tray) and `plan_stage4` (real 4-utensil
  place; drop the "SCORER EXPLOIT" framing — a controlled place is legal, just
  don't call the dev-helper the source of truth).
- `task3_pipeline/config.py` — replace the "grading.py is the single source of
  truth" targets with **rules-derived** targets: the 4 official objects, the
  seat-target resolver (§5.1), and keep sink/bean geometry (those match).

### 2.4 BUILD NEW (the real work)
- `task3_pipeline/world_isaac.py` — **implement every stubbed method for real**
  (§4, §5). This is the main GPU job.
- `task3_pipeline/perception.py` (NEW) — the perception layer (§3).
- `task3_pipeline/seats.py` (NEW) — locate the 6 seats + resolve the 3 assigned
  per episode (§5.1). BLOCKING discovery task — see §5.1.
- `task3_pipeline/scoring_real.py` (NEW) — real-rules Stage-1 seat scorer +
  Stage-4 sink scorer wrappers (grading.py stays as smoke-test only).

---

## 3. PERCEPTION LAYER (your VLM + camera get a real job here)

**Goal:** produce a `WorldState` each episode = {object 6D poses, which 3 seats
are assigned, head pose, bin/sink pose} from the camera — and in Phase I,
cross-check it against privileged PhysX state so you get a free trust metric AND
a labeled dataset for Phase II.

### 3.1 Components (all pretrained — NO training data needed)
- **Camera:** `/World/Scene/eval_camera` already exists in
  `scripts/scenes/scene_robot_room_keyboard.py` (RGB + Depth + Semantic ROS2
  publishers). Task: read RGB-D frames from it into `perception.py` (via the
  render product / annotator, not necessarily ROS — simplest is Isaac's
  `rep.create.render_product` + `Annotator`).
- **Open-vocab detection + pose:** Grounding-DINO-style detector OR a
  pointing-capable VLM (Molmo / Qwen-2.5-VL class — you already run Qwen2-VL)
  to localize "plate/cup/bowl/spoon/seat/recycling bin/sink". Back-project the
  detection centroid with the depth channel → 3D pose. For known USD assets you
  may also register the mesh for exact 6D.
- **Grasp fallback [L]:** Contact-GraspNet / AnyGrasp / GraspGen on the object
  point cloud → ranked 6-DoF grasps. Only invoked when scripted grasp <70%.
- **Run async, off the control loop:** perceive at a few Hz into a cached
  `WorldState`; the control loop reads the cache. Perception never blocks the
  1 kHz control tick.

### 3.2 The Phase-I trick (do this — it's free double-duty)
In `perception.py`, every frame compute `perceived_pose` and compare to the
privileged `world.object_xy/z(name)`. Log the delta. This gives (a) a live trust
metric ("is perception good enough to rely on?") and (b) an auto-labeled
`(RGB-D → true 6D pose)` dataset written to `outputs/perception_dataset/` for
Phase II fine-tuning. **Perception work is never wasted.**

### 3.3 VLM roles (both of the user's stated intents, made concrete)
- **Feedback for the current task (verifier assist):** after each skill, the VLM
  narrates the key frames (`vlm_narrate.py` already exists on the VM) → a
  plain-text failure description the orchestrator/agent can read. Coarse signal,
  NOT the pass/fail authority (that's the deterministic verifier, §6).
- **Data collection for future training:** every skill execution logs
  `(RGB-D, proprioception, action params, verifier outcome)` to
  `outputs/skill_dataset/<skill>/`. The moment a scripted skill works even
  sometimes, it mints its own labeled training data — this is the data engine
  that feeds any future [L] model with ZERO teleoperation.

---

## 4. THE REACH-WALL FIX (root cause shared by Stage 1/2/4 — do this FIRST)

**Root cause (verified this project, multiple stages):** the FR3 arm's max reach
is **855 mm**. Stances sit at ~0.86–0.87 m (`TRAY_STANCE`, old `ISLAND_STANCE`)
— at/past the limit, zero margin → IK fails → arm freezes (`dual_arm_lula.py`
`_solve_arm` returns previous targets) → contact-loaded lever-arm spin / 10-12cm
descend miss. **Scalar tuning (`PREGRASP_Z`, `--drag-seconds`) cannot fix a
geometric limit. STOP all scalar sweeps.**

**Fix = APPROACH GEOMETRY (Phase A), then pretrained grasp (Phase B):**

### Phase A — every manipulation happens at < 0.80 m reach
Implement a **stance-first reach guarantee** in `world_isaac.reach()`:
1. Given a live object pose, compute the base stance that puts the object at a
   **target reach of 0.70–0.78 m** directly in front of the manipulating arm's
   shoulder (square to the object) — do NOT reuse a fixed island stance.
2. The reach budget is a hard precondition: if the required reach at the chosen
   stance exceeds 0.80 m, re-stance (drive closer / re-orient) BEFORE reaching,
   or, if blocked by collision, step the base in mid-skill. Never command a
   reach the arm cannot make.
3. Reuse the proven grasp geometry from `verify_grasp_lift.py` (it worked 10/10
   precisely because skip-navigation spawned the base square to the cup at a
   reachable distance) — the job is to **reproduce that square, <0.80 m pose
   through real navigation**, not to invent a new grasp.
4. Validate with the `approach_stance` grid already in `config.py`
   (`GRASP_GRID`: stance first). The policy already flips stance on `IK_FAIL`.

**Verifier gate for Phase A:** reach `position_error_m ≤ 0.05` AND no `IK_FAIL`
in the log AND object not displaced before contact.

### Phase B — pretrained grasp fallback (only if scripted grasp <70%)
Wire `world_isaac.grasp()` to optionally call Contact-GraspNet/AnyGrasp on the
object point cloud and execute the top-ranked reachable grasp via the existing
`DualArmController`. This is the `[L]` escalation the policy triggers.

---

## 5. PER-STAGE PLANS (goal → tasks → subtasks; each subtask is a checkable gate)

Legend: **[S]** scripted · **[P]** perception · **[L]** learned fallback · **[V]** verifier gate.

### 5.1 STAGE 1 — Table Setup (4 objects → 3 assigned seats)  ⟵ BIGGEST REWRITE

**GOAL:** plate, cup, bowl+beans, spoon each end at a distinct assigned seat.

**DISCOVERY TASK 1.0 — RESOLVED (T1, 2026-07-24):**
`robot_room.usd` has **no separate seat/chair geometry** at all (checked
directly — no seat prim paths exist to find), and **no seat scorer ships
anywhere**: neither the organizers' shipped smoke-test
(`scripts/evaluation/task3/grading.py::score_stage1_table_setup` /
`classify_table_area`) nor their `integration_test.py::run_stage1` grade by
seat — both score purely by "object lands in the `TASK3_DINING_AREA`
rectangle" (center (-2.85, 1.9), scale 5.9x3.4). The official (non-dev)
scorer is unpublished, so there is nothing further to "find" in the USD.

What the code DOES have are the real seating positions:
`TASK3_HEAD_PLACEMENTS` in `scripts/scenes/scene_robot_room_keyboard.py` — 9
named tabletop placements (A–I) at z=0.74659, all inside the dining
rectangle. **Decision:** `task3_pipeline/seats.py` now derives
`TABLE_SEAT_POSITIONS` from these 9 real coordinates (copied, not
re-imported, to avoid pulling Isaac deps into CPU code) and
`assigned_seats()` deterministically selects a distinct subset (default A,
C, G; seeded sample otherwise) as the seat targets. This is real, grounded
data (not an invented mock) and satisfies the only scorer that exists.
`SeatTarget` / `object_to_seat()` kept their shape, so `stages.py` needed no
change. Validated locally: `task3_pipeline/tests/test_pipeline.py` asserts
every assigned seat and every object→seat mapping classifies as `"dining"`
via `grading.py::classify_table_area` (the local Stage-1 validation gate —
no GPU needed). **Open item:** prose says "6 seats" but the scene ships 9
head placements and no seat scorer — revisit if organizers publish real seat
data.

**Task 1.1 — Perceive & plan [P][S].**
  - 1.1a Perceive the 4 objects' poses in the kitchen (stacked on a plate) and
    the assigned seat targets (from 1.0). Build `WorldState`.
  - 1.1b Orchestrator computes a per-object pick order + per-object seat target
    (parametric, NOT hardcoded).

**Task 1.2 — Pick each object [S]→[L][V].** For each of the 4 objects:
  - 1.2a `navigate_to` a reach-safe kitchen stance for that object (§4 Phase A).
  - 1.2b `reach` + `grasp` using proven `verify_grasp_lift.py` geometry;
    **[V]** cage (`gripper_rad ≤ 0.20`) + `object_follows_end_effector` hold
    check + object rose. The **spoon is the hard one** (thin) → `[L]` grasp
    model fallback if scripted <70%.
  - 1.2c *Simplification to try after the 4-pick path works:* if the objects
    start stacked on the plate, carrying the **plate as the carrier** with the
    others riding is one carry instead of four picks (fewer re-grasps = better
    Process metrics). Try it as an optimization, not the first implementation.

**Task 1.3 — Carry & place at the assigned seat [S][V].** For each object:
  - 1.3a `navigate_to` the dining area near the target seat (door-aware route;
    freeze arm targets during base motion — the proven transit tuck).
  - 1.3b `place` the object at the seat target pose (from 1.0), release.
  - 1.3c **[V]** confirm the object's live pose is at the assigned seat (real
    scorer). Retry a miss (bounded); then advance. **Never hang** (ranking
    rewards reaching Stage 2).

**Task 1.4 — Score & freeze.** Run the real-rules Stage-1 scorer; capture proof
bundle (video + result.json + repro). Log to `docs/eval_results.md`.

### 5.2 STAGE 2 — Feeding (bimanual, SAFETY-CRITICAL)

**GOAL:** hold spoon + steady bowl (bimanual), scoop beans, hold at head ≥3 s, return.

- **Task 2.1 [S]** Left arm steadies the bowl (bimanual hold) — REQUIRED by rules.
- **Task 2.2 Scoop [S]→[L][V]** (2nd hard skill): right arm enters bean pile at
  30–45° pitch (`SCOOP_GRID.entry_pitch_deg`), drags ~5 cm, levels, lifts.
  **[V]** count beans retained on the spoon. `[L]` learned scoop only if
  retained < threshold across retries.
- **Task 2.3 [P]** Locate the head pose (`TASK3_HEAD_PLACEMENTS` a–i exist in
  `scene_robot_room_keyboard.py`; in sim read privileged, in real perceive it).
- **Task 2.4 Present + hold [S][V] — SAFETY GATE:** move spoon to the feed zone
  in front of the head **slowly** and **stop short** of the ISO/TS 15066
  head-force limit. Approach speed + standoff are the levers. **[V]** hold ≥3 s
  with beans in the feed zone (`update_feed_hold` / `feed_score` in grading.py
  give the exact gate logic). **A single head-force trip = hard fail — cap
  approach velocity conservatively.**
- **Task 2.5 [S]** Return the beans toward the bowl. Score + freeze.

### 5.3 STAGE 3 — Bean Recovery (ratio game)

**GOAL:** empty beans into the scaled recycling bin; maximize recovered ratio.
- **Task 3.1 [S]** Carry the bowl (bimanual hold, don't spill) to the recycling
  bin region (`TASK3_BEAN_RECOVERY_REGION`, sphere r=0.2 at the bowl spawn).
- **Task 3.2 [S]** Pour **low and slow** (`POUR_GRID`: `pour_height_m` small,
  `tilt_rate` slow) to minimize scatter.
- **Task 3.3 [V]** `count_points_in_sphere` / `bean_recovery_score`: ≥0.8→2,
  ≥0.9→3, =1.0→4. Maximize, don't chase perfection. Score + freeze.

### 5.4 STAGE 4 — Cleanup (4 utensils → marked sink region)

**GOAL:** all four utensils end inside the sink region (`TASK3_SINK_REGION`,
bounds + `tabletop_z=0.747`).
- For each utensil: **Task 4.x** `navigate` (reach-safe stance §4) → `grasp`
  (proven geometry; `[L]` fallback) → `navigate` to sink → `place` inside the
  sink region → **[V]** confirm XY-overlap-sink AND z ≥ tabletop.
- A controlled carry/place is legal and sufficient (the scorer checks the object
  ends in-region at height; a perfect cage isn't required — but do it with a
  real grasp+place, not a physics exploit). Score + freeze.

---

## 6. AUTO-VERIFIER + SELF-GENERATED DATA ENGINE (kills the manual grind)

- The `SelfCorrectingSkill` loop (`skills.py`) already does execute→verify→
  retry→record. Your job: make `outcomes.classify(skill, metrics)` and the
  `VerifierThresholds` (`config.py`) **honest** — a phase is SUCCESS only if the
  measured evidence proves it (e.g. grasp: `gripper_rad ≤ 0.20` AND
  `object_follows_end_effector` AND object rose ≥ `min_lift_m`). This closes the
  project's recurring "ok:true on an empty gripper" gap (confirmed Stage 1/2/4).
- Every attempt logs to `param_memory.json` (best params per skill/context) AND
  to `outputs/skill_dataset/` (RGB-D + proprio + params + outcome) for future
  [L] training. **No human in the loop.**
- **Overnight matrix:** `run_matrix.py` over seeds × head placements × domain
  randomization → thousands of auto-labeled episodes → freeze the best config
  per skill; anything <70% is a candidate for an [L] model.

---

## 7. 17-DAY BUILD ORDER (to Aug 10) — with hard gates

| Days | Milestone | GATE (don't advance until true) |
|---|---|---|
| 1 | Commit `task3_pipeline` to git; archive tray-drag to `old/` (§2.2); retarget `stages.py`/`config.py` to real rules (§2.3); make `outcomes.classify` honest (§6). | CPU tests green; no tray/rectangle logic in the active path. |
| 1–2 | **Task 1.0** — locate seats + assignment; write `seats.py`. | Teleport-test: object at seat target → real scorer accepts. |
| 2–3 | Implement `world_isaac.py` navigate/reach/grasp/lift against proven primitives + **§4 Phase A reach fix**. | GPU: grasp `position_error ≤0.05`, no IK_FAIL, object held (verified). |
| 3–4 | `perception.py` (camera read + open-vocab pose + privileged cross-validation). Wire perceived targets into orchestrator. | Perceived vs privileged pose delta logged < a few cm on all objects. |
| 4–6 | **Stage 1 + Stage 4 end-to-end** (pick-carry-place). Tag first submittable build. | ≥1 full autonomous run scoring Stage 1 (≥1 object at a real seat) + Stage 4, proof bundle committed. |
| 6–9 | Stage 2 (bimanual feeding, SAFETY gate respected) + Stage 3 pour. Chain 1→4 via orchestrator. | No head-force trip; hold ≥3 s; pour ratio ≥0.8. |
| 7–10 | Data engine mints self-labeled grasp/scoop data overnight; fine-tune an [L] model ONLY if the matrix shows that skill <70%. | Skill success ≥70% (scripted or [L]). |
| 10–13 | Unattended matrix (placements × seeds); freeze best config; fix regressions. | Stable ≥70% across the matrix. |
| 13–15 | Dockerfile + README + submission dry-run + buffer. | Fresh-clone Docker run reproduces a scored episode. |

**Cost discipline:** develop/verify logic on CPU (MockWorld); GPU (Lightning L4
only, GCP banned) only to make `world_isaac.py` methods return real
measurements. Stop the container at pauses.

---

## 8. NON-NEGOTIABLE RULES (carry over — these are why this project is credible)

1. **Every GPU-run claim backed by a pasted `result.json`/log/frame you opened
   this session.** No stating results from memory.
2. **One hypothesis, one change, one run.** If 3 fixes fail on the same symptom
   without narrowing it, STOP and raise an architecture question — don't guess a
   4th time.
3. **GPU gate before trusting any run:** host `nvidia-smi`, `docker exec …
   nvidia-smi`, grep log for `llvmpipe`/`software rasterizer` (any hit = discard
   the run), confirm `cuda:0` + nonzero util once physics starts.
4. **`"ok": true` is NOT proof of a hold.** Verify with measured evidence
   (gripper angle + object-follows-EE + object rose). This is the project's
   recurring failure — the verifier (§6) exists to end it.
5. **Commit + push after every meaningful result.** Check for another agent's
   uncommitted work before committing; reconcile, don't overwrite.
6. **Standard physics only** — no kinematic attach, no scene/asset edits, no
   teleport in the graded path. (Teleport allowed only in a `seats.py` unit test
   to validate the scorer.)
7. **No hardcoded per-episode values in the graded path** — seats are
   randomized; read targets from state every episode.
8. **Archive, don't delete** superseded work (`old/`).

---

## 9. REFERENCE INDEX (what to read for each piece)
- Organizer rules: `https://ebim-benchmark.github.io/competition.html`
- Proven grasp + constants + hold-verify primitive:
  `scripts/task3/verify_grasp_lift.py`
- Orchestration brain: `task3_pipeline/{orchestrator,skills,policy,memory,
  outcomes}.py`, `task3_autonomy/chained_fsm.py`
- Isaac wiring map (implement these): `task3_pipeline/world_isaac.py` docstrings
- Scene / camera / head placements / objects:
  `scripts/scenes/scene_robot_room_keyboard.py`
- Dev-helper scorer (smoke-test ONLY): `scripts/evaluation/task3/grading.py`
- Nav/arm primitives: `task3_autonomy/{navigation,skills,arms,rotations}.py`
- Reach-wall mechanism: `scripts/common/dual_arm_lula.py` `_solve_arm`
- Env/VM/GPU setup: `docs/HANDOFF_2026-07-24_FULL_PLAN_Claude_to_OpenCode.md` §7
- Prior evidence/history (context, not objective): `docs/AGENT_STATE.md`

---

## 10. DEFINITION OF DONE (per stage)
One **fully autonomous, standard-physics** run where the **real-rules scorer**
accepts the stage, with **video + result.json + repro.txt** committed to
`docs/eval_results.md`. Frozen stages are never reworked without explicit owner
request. Priority: **reach the highest stage** first, then improve score.
