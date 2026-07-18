# Day 3 plan — physical Stage 1 without fighting the flat tray (2026-07-18)

Author: Claude (orchestrator review of the Codex 04:25 UTC handoff).
Read after `docs/AGENT_STATE.md`. This SUPERSEDES the "purpose-modeled
two-contact tray handle" next-step in the 2026-07-18 entries.

## 1. The reframe (read this before touching the GPU)

**The official grading never requires lifting the tray.**
`scripts/evaluation/task3/grading.py::score_stage1_table_setup` scores each
of the 5 objects (`simple_tray`, `bowl2`, `spoon2`, `plate2`, `cup`)
independently by ONE predicate: final **XY inside the dining area**
(`classify_table_area == "dining"`). No z check, no grasp check, no
"carried together" check. The `>=0.08 m` tray-lift gate was inherited from
the cup verifier — it is a self-imposed proxy, not the task.

Consequences:

- Objects may be transported **one at a time**. The proven 10/10 cup
  grasp/lift pipeline is directly reusable for per-object transport.
- The tray only has to END in the dining area by robot action. Any
  physics-legal manipulation (pinch, bimanual, slide-to-edge-then-pinch)
  counts; sustained 0.08 m lift is NOT required — only enough clearance to
  carry it across the room without dropping it outside "dining".
- Stage 1 FSM pass bar is `score >= 4/5`, so even losing one hard object
  (e.g. `plate2`) still passes the sprint exit criterion.

## 2. Why the Day 2 physical attempts measured 0.0 m (root-cause notes)

1. **Geometry, not tuning.** The tray is a 0.337×0.436×0.013 m flat mesh
   flush on the counter. A parallel pinch needs opposing surfaces; a flat
   plate on a support gives the fingers no underside, so every top-contact
   friction attempt necessarily reads 0.0 m. More force/friction/mass
   tuning cannot fix this class of failure.
2. **The rim fixture was un-graspable.** `add_tray_grasp_rim` creates an
   **0.18 m cube** (`AddScaleOp 0.18`). If the gripper's max aperture at
   0.9 rad is smaller than 18 cm (very likely — it was sized for a cup
   rim), the fingers can press on the cube but never span it: no force
   closure, tray never follows the arm. The measured "best closure
   0.57 rad with 0.0 m lift" is consistent with jamming on the cube faces.
3. **Scene-modification legality.** `simple_tray` is an organizer asset.
   Adding handles / changing its mass edits the benchmark scene; a graded
   submission with a modified tray risks disqualification exactly like a
   kinematic attach. Sprint plan §7 already requires owner sign-off for
   kinematic attach — the same bar applies to geometry edits. Default:
   **do not ship any scene modification.** Keep the fixture code only as a
   diagnostic flag, never in the submission path.

## 3. Day 3 order of work (account dies ≈ Jul 19–20 — export is mandatory)

Time-box everything; the sprint rule is COMPLETE > perfect.

### Step 0 — cheap probes (≤30 min GPU)

- Measure the real gripper aperture: open to 0.9 rad, read finger-tip
  world separation. Record it in AGENT_STATE (this decides what is
  pinchable forever after).
- Query the tray's actual PhysX mass in the UNMODIFIED scene
  (unauthored mass ⇒ density default ⇒ possibly ~1.9 kg, not 0.35 kg).
  Also measure `bowl2`, `spoon2`, `plate2`, `cup` poses + bounding boxes
  and distance from the counter's east/north edges.

### Step 1 — tray via slide-to-overhang pinch (time-box: 3 focused hours)

The standard flat-object strategy, zero scene modification:

1. With the proven reach() pipeline, PUSH the tray horizontally (closed
   gripper as a pusher — pushing is contact-rich and easy) until one edge
   overhangs the counter edge by 6–8 cm.
2. Pinch the overhanging 13 mm edge (far under the aperture that fully
   closes to 0.0 rad). Use the frozen 1 s soft-close + force settle.
3. Lift a few cm, tuck to the proven TRANSIT_ARM_POSE variant, NavigateTo
   the dining table with the proven heading-hold, place, release.
   If the pinch torques out with a heavy cantilevered tray, escalate ONCE:
   slide the tray to a counter CORNER so two edges overhang and do a
   two-arm two-edge pinch (each arm gets a thin edge — this is the real
   "two-contact" version, no new geometry needed).
4. Gate: tray final XY in dining on ≥7/10 seeded runs. Lift height is a
   diagnostic, not a gate.

### Step 2 — per-object transport fills the score to ≥4/5

- `cup`: already 10/10 proven. Wire it into the Stage 1 FSM as-is.
- `bowl2`: rim pinch, same as cup (bowl walls are cup-like).
- `spoon2`: handle pinch at the raised handle end; if it sits flat, use
  the same overhang trick.
- `plate2`: same overhang trick as the tray, or skip — 4/5 still passes.
- FSM: replace the kinematic `drive_group_translation` adapter calls with
  the real skill chain per object; keep retries/timeouts. The FSM ordering
  and grading path are already proven — only the actuation layer changes.

### Step 3 — tag and prove Stage 1

- 10-run matrix across head placements a/b/c, `score >= 4` on ≥7/10.
- Proof bundle `proofs/phase3-stage1-physical/`, tag `v0.1-stage1`,
  video to owner. Retire the word "kinematic" from the headline claim.

### Step 4 — Stage 4 is cheap points; take it before Stages 2–3

`score_stage4_cleanup` needs bounds-overlap with the SINK region and
z ≥ 0.747. The sink is IN the kitchen (~0.6 m from the utensil spawns):
no navigation, and **sliding objects along the countertop into the sink
region can score** as long as they stay at tabletop height. Do this right
after Stage 1 — it is the highest points-per-GPU-hour left.

### Step 5 — EXPORT RITUAL (non-negotiable, start ≥6 h before expiry)

Push all code/proofs/JSONs, scp videos to Windows, final snapshot, STOP
`sim-dev-g4b`, log spend. A half-finished Stage 2 is recoverable from a
pushed repo; nothing is recoverable from a dead account.

## 4. Anti-goals (do not spend Day 3 on these)

- No purpose-modeled tray handles or any organizer-asset edits in the
  submission path (legality risk, and Step 1 makes them unnecessary).
- No kinematic attach without explicit owner/organizer sign-off.
- No MCP/LangChain/VLA work until Stage 1 physical + export are done.
- No further tuning of top-surface friction grasps on flat objects —
  the 0.0 m result is geometric, not a parameter problem.
