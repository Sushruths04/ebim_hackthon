# Task 3 Stage 4 (utensils → sink) — Diagnosis & Corrective Plan for Codex

> Author: Claude (Opus 4.8), 2026-07-20, at owner's request.
> Purpose: stop the stuck open-loop-push tuning loop, diagnose the root
> cause, and hand Codex a bounded, ordered plan with a better strategy.
> Read `AGENTS.md`, `docs/AGENT_STATE.md`, and this file before acting.

---

## 1. What Codex is currently doing (and why it's stuck)

Codex is trying to get `spoon2` (and other utensils) into the sink by
**pushing/sliding them with arm contact strokes**, then tuning ONE scalar per
GPU run (hold strength, stroke depth, stroke length, contact energy…). The
symptom loop, in Codex's own words:

- strong hold → spoon moves ~5.1 cm south (correct direction) →
- a later contact stroke over-pushes → spoon leaves the counter, **Z falls to
  0.013 m** (floor) → not a sink success →
- "next lever: shallower / lower-energy contact" → repeat →
- eventually: *"blocked … current robot/contact geometry cannot produce a
  robust transport path without a new manipulation strategy or additional
  direction."*

**That last sentence is correct. This is not a tuning problem — it is a
strategy (architecture) problem.** Per systematic-debugging: when 3+ fixes each
reveal the same failure in a new place, you STOP tuning and question the
approach. Codex has done 15+ single-scalar trials (tray r14–r18, r24–r33, plus
the spoon runs) — well past that threshold.

### Root cause (why push can never be robust here)
Open-loop pushing imparts **momentum** to a small rigid object, then lets it
**coast**. Under PhysX, the coast distance + rotation is stochastic (friction,
contact point, spoon geometry). The acceptable landing zone is a small box with
a **cliff (counter edge) immediately beyond it** in the push direction. You are
trying to meter an impulse precisely enough to stop a coasting object inside a
narrow strip next to a drop-off. That is fundamentally uncontrollable by
scalar tuning. No "shallower stroke" value fixes a controllability problem.

### Two hard constraints that box Codex in
1. **No kinematic cheating.** The `r17` audit correctly flagged that a Stage-4
   runner which disabled rigid bodies and repositioned objects is **INVALID**.
   Cleanup must be physical contact only. (Keep this constraint.)
2. **Flat-object acquisition is genuinely hard.** Codex went to *push* because a
   thin spoon lying flat is hard to top-pinch (fingers hit the counter before
   closing on ~5 mm of handle). This is the real sub-problem to solve — not the
   push tuning.

---

## 2. What the grader ACTUALLY requires (this makes it much easier)

From `scripts/evaluation/task3/grading.py::score_stage4_cleanup` and
`run_episode.py` (lines ~516–539):

- Stage 4 uses a **point** approximation of each object:
  `Bounds2D.from_point(final_positions[name])`. Only the object's **center
  point** is tested, not its full footprint.
- Success per object = center point inside the **sink XY box** AND
  `z >= tabletop_z`:
  - Sink box: `x ∈ [-4.245322, -3.805322]`, `y ∈ [-2.412793, -2.042793]`
    → **center `(-4.0253, -2.2278)`, size `0.440 m × 0.370 m`.**
  - `tabletop_z = 0.74699`. So `z >= 0.747` — i.e. **the object must NOT have
    fallen off the counter.** Resting on the sink surface passes.

**Implication:** the entire task reduces to *"place the spoon's center inside a
0.44 × 0.37 m box without it leaving the counter."* An object set down with
~zero velocity trivially satisfies this. A coasting pushed object does not.
This is why **place beats push.**

---

## 3. Can we proceed? YES — reuse the proven pipeline

Day 1 is **complete**: `verify_grasp_lift.py` achieved a **10/10 grasp + ≥0.08 m
sustained lift** on the cup (commit `cf37203`), with the spine-high transit,
`one_step_reach_command` (TeleopCommand + CartesianTargetTracker boundary), and
the 1.0 s slow-close + 0.5 s force-settle closure that stops contact ejection.

`probe_tray_slide.py` **already proved physical flat-object acquisition**:
slide-to-edge-overhang → edge-pinch → lift produced a real pinch (0.217 rad) and
`+0.099 m` overhang / `+0.037 m` lift on the flat tray. The tray work only
stalled on the *long carry to the dining table* — a harder placement than the
sink.

We are NOT starting from zero. We have (a) controllable acquisition of a flat
object and (b) controllable lift/hold. We just need to **compose them into
grasp → carry → RELEASE-over-sink** instead of pushing.

---

## 4. The plan (ordered, bounded, gated)

### Step 0 — Confirm the GPU is available (do this first, cheaply)
The lab GCP account (`ebim26ham-236`) was expiring ~Jul 19–20 and `sim-dev-g4b`
is STOPPED. Before planning GPU trials, confirm one GPU can start:
```
gcloud compute instances list --account=<lab-account>
# and/or personal L4 fallback quota:
gcloud compute regions describe us-central1 \
  --account=mitvho09@gmail.com --project=gen-lang-client-0186028838
```
- If **no GPU**: do NOT burn the session guessing. Do the CPU-only prep in
  Step 1 + Step 2a design + unit tests, and flag to the owner that GPU access
  is the blocker.
- If **GPU available**: start ONE VM, keep it warm across the bounded trials
  below, and **stop it at the session boundary** (GPU cost discipline).

### Step 1 — Get a MAP before touching contact params (evidence, not inference)
Codex has been inferring geometry from z-values. Stop. Capture the facts once:
- Use `scripts/task3/capture_static_view.py` (ABSOLUTE `--output-dir`) for a
  **top-down** view of the kitchen counter + sink.
- From live PhysX poses, record and annotate on a GIF/frame:
  1. spoon spawn XY,
  2. sink box `(-4.0253, -2.2278)` ± (0.22, 0.185),
  3. **the counter's south edge Y** (the cliff the spoon keeps falling off),
  4. all four counter edges reachable from the stance.
- **Decision output of Step 1:** is the sink adjacent to the south edge (a
  cliff just past `y=-2.413`), or is there counter surface beyond it? This
  determines whether any overshoot is fatal and which edge is usable for
  edge-pinch.

### Step 2 — PRIMARY strategy: grasp-and-place (reuse proven code)
**2a. Acquire the spoon (physical, no scene edits).**
- First try a direct top-pinch at the spoon's measured pose using the proven
  `one_step_reach_command` + slow-close. Budget: **1 GPU trial.**
- If the flat spoon can't be pinched (fingers bottom out on the counter), reuse
  the **proven overhang + edge-pinch** mechanic from `probe_tray_slide.py`:
  slide the spoon to the nearest usable counter edge (from Step 1), then
  edge-pinch + lift. Budget: **2 GPU trials** to reproduce a pinch+lift on the
  spoon.

**2b. Carry with the proven transit posture.**
- Spine HIGH (`TRAVEL_SPINE_M = 0.45`, 0.02 m tolerance — the fix that
  re-converged transport, see AGENT_STATE "ROOT CAUSE of the transport nav
  stall"). Base anchored with active XY feedback (the r14 fix), not zero-wheel.
- Carry to a stance dead-ahead of the sink (short move — the sink is near the
  acquisition area, unlike the dining-table carry that stalled).

**2c. Place by RELEASE (the whole point).**
- Move the EE so the grasped spoon's center is over the **sink center
  `(-4.0253, -2.2278)`**, descend to `z ≈ 0.76` (just above `0.747`), then
  **open the gripper**. Release velocity ≈ 0 → the spoon drops < 2 cm and stops
  inside the box. No coast, no cliff overshoot.
- Budget: **2 GPU trials** to land one clean place.

### Step 3 — FALLBACK (only if 2a proves grasp truly infeasible)
Do NOT return to open-loop push. Instead use a **position-servoed controlled
slide with a stop**, which is categorically different from an impulse:
- Keep a closed fist / finger **in continuous contact** with the spoon for the
  whole motion (the tray probe's "synchronized drag: arm push target and base
  hold anchor ramp by the same offset every tick" already does this).
- Command the contact target to **decelerate to zero AT the sink center**, not
  past it. The object stops because the pusher stops on it, not because you
  guessed the right impulse.
- This is only safe if Step 1 shows counter surface (not a cliff) at/just past
  the sink. If the sink is at the cliff, controlled slide is still viable but
  must undershoot the far edge — target the sink's NEAR edge, not center.
- Budget: **2 GPU trials.**

### Step 4 — Gate + proof
- Run the seeded Stage-4 matrix; target the sprint gate (**≥6/10 seeded runs**,
  per `docs/task3_sprint_plan_2026-07-17.md` Step 4).
- Per the visual-proof workflow: **every run produces an annotated `run.gif` +
  `result.json`**, and a failure is diagnosed from the GIF *before* changing
  anything.
- Export code + proofs + JSON + video immediately after the gate (account
  expiry risk).

---

## 5. Guardrails — how to not get stuck again

1. **No more blind scalar sweeps.** Each GPU trial must test a *named
   hypothesis*, not "the next offset." If a hypothesis fails twice, change the
   *strategy*, not the fourth decimal.
2. **Hard budget:** the whole plan above is ~9 GPU trials. If Step 2 hasn't
   produced one clean place in that budget, STOP and report to the owner with
   the GIFs — do not open-endedly iterate.
3. **Evidence before tuning:** Step 1's map is mandatory. Guessing geometry
   from z-values is what caused the loop.
4. **Constraints that stay:** no rigid-body disable, no object teleport, no
   mass override, no added geometry, no fixed joints (the `r17` INVALID line).
5. **Cost:** one GPU VM max; keep it warm across the bounded trials; **stop it
   at the session boundary.**
6. **Update `docs/AGENT_STATE.md`** one line per run, and this file's status if
   the strategy changes.

---

## 6. TL;DR for Codex
Stop pushing the spoon. Pushing = uncontrollable coast toward a cliff. The
grader only needs the spoon's **center in a 0.44×0.37 m box at z ≥ 0.747** — a
**gentle release** satisfies that trivially. Reuse the proven cup grasp/lift +
the proven tray overhang/edge-pinch to **grasp → carry (spine high) → release
over the sink center `(-4.0253, -2.2278)`**. Map the geometry first (Step 1),
budget ~9 trials, GIF every run, no scene edits, stop the VM at the end.
