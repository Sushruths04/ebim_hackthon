# AGENT STATE — live handoff file

> Every agent session reads this first and updates it last. Keep entries
> short; link proofs. Protocol: `AGENTS.md`. Plan:
> `docs/task3_sprint_plan_2026-07-17.md`.

Last update: 2026-07-19 12:05 UTC (Codex,
`agent/codex-task3-grasp`).
GPU STATUS: `sim-dev-g4b` is STOPPED after Round 11. Day 1 remains complete;
the Day 2 FSM proof is adapter-only. Day 3 Step 0 is complete. Step 1's
slide-to-overhang SUB-gate passes reliably, but the full single-edge
pinch+lift gate remains open. The tray remains a required owner deliverable;
no Step 2 work has started.

## Day 3 Step 1 Round 11 result — 2026-07-19 11:55 UTC

Round 11 increased the contact drag duration to 8 s, but coupling was weaker:
four strokes ended at `-0.013220 m` overhang. The actual-overhang gate stopped
the run before pinch or carry. Raw evidence:
`outputs/task3_stage1_tray_slide_r11_20260719/result.json`.

The next bounded contact trial uses a slightly deeper commanded press,
`--descend-ee-z 0.810`, with the proven 5 s drag. This stays above the prior
0.80 m IK failure boundary and changes only contact depth.

## Day 3 Step 1 Round 10 result — 2026-07-19 10:40 UTC

Round 10 used the carry-target fix and four physical strokes with
`--push-distance 0.26`, but the slide was weak: moved `+0.203907 m` and
reached only `+0.024374 m` overhang. The new actual-overhang gate stopped the
run before pinch, lift, or carry. Raw evidence:
`outputs/task3_stage1_tray_slide_r10_20260719/result.json`.

The carry-target fix remains untested on a fresh gate-passing episode because
Round 10 did not reach pinch. The next trial increases only the contact drag
time to improve physical coupling; no scene or physics parameters are edited.

## Day 3 Step 1 Round 9 result — 2026-07-19 09:35 UTC

Round 9 reached `+0.098956 m` measured north overhang after three strokes,
then produced a physical tray lift of `+0.036547 m`. The tray was held while
the base successfully traversed the first three door-route waypoints, but the
final westward target `[-2.85, 1.12]` stalled at base `[-3.661546, 1.102825]`.
The tray remained in the kitchen and the carry gate failed. Raw evidence:
`outputs/task3_stage1_tray_slide_r9_20260719/result.json`.

Diagnosis: the edge pinch/lift and doorway route are physically active; the
carry loop was leaving the arm target in a fixed world pose while the base
moved. The next code change reissues the hand target from its measured
robot-relative offset during carry. No object transform, attachment, mass,
scene asset, or physics parameter is changed.

## Day 3 Step 1 Round 8 result — 2026-07-19 08:15 UTC

Round 8 used the 12 s recovery reach budget and repeated `--push-distance
0.26`. All three push strokes completed, the tray moved `+0.214900 m`, and
the actual north overhang reached `+0.035366 m`. The physical edge approach
and closure then succeeded (`0.217117 rad`), but the measured lift was
`-0.000555 m` because the tray still rested on the counter. Carry-to-dining
was not attempted. Raw evidence:
`outputs/task3_stage1_tray_slide_r8_20260719/result.json`.

The next committed probe change allows a fourth ordinary press-drag stroke
and makes the actual `>=0.05 m` overhang—not net translation alone—the
carry-ready gate. This preserves physics and avoids spending pinch time on a
tray that cannot yet clear the counter.

## Day 3 Step 1 Round 7 result — 2026-07-19 07:10 UTC

Round 7 repeated the proven `--push-distance 0.26` setting. The first
physical stroke moved the tray `+0.098265 m`, but the second-stroke
pregrasp-above reach timed out with measured position error `0.056190 m` and
orientation error `0.122625 rad`. The run stopped before pinch and carry.
Raw evidence: `outputs/task3_stage1_tray_slide_r7_20260719/result.json`.

Result: **full Step 1 still not passed**. This is a recovery-reach timeout,
not a new tray-contact or physics-geometry failure. The next code change is a
larger bounded pregrasp reach budget only; scene geometry, masses, contacts,
and object poses remain untouched.

## Day 3 Step 1 Round 6 result — 2026-07-19 06:20 UTC

Round 6 used the committed physical carry chain with `NORTH_PINCH_STANDOFF_M=
0.7` and `--push-distance 0.30`. North-side navigation, edge approach,
contact, and closure all succeeded. The gripper closed to `0.198886 rad`,
which is the same physical pinch signature as the successful Round 4
partial lift. However, this run's three drag strokes moved the tray only
`+0.193888 m` and reached `+0.014355 m` north overhang, below the required
overhang gate. The tray therefore remained supported by the counter and
measured lift was `0.000 m`; carry-to-dining was not attempted. Raw evidence:
`outputs/task3_stage1_tray_slide_r6_20260719/result.json`.

Result: **full Step 1 still not passed**. The immediate next trial is a
slide-gate repeat using the previously proven `--push-distance 0.26`
configuration, then the already-implemented carry-and-release route to the
dining table. No physics or scene changes are authorized.

## Day 3 Step 1 Round 3 resume claim — 2026-07-19 04:45 UTC

CPU validation completed before GPU use: `pytest scripts/tests` passed
`198/198`; the focused tray tests passed `25/25`; Ruff and compilation are
clean. The full repository-wide pytest command is not a valid gate on this
Windows checkout because unrelated ROS test collection imports missing
`rclpy`.

The authorized trial will use the unmodified organizer scene and the
physics-contact probe only. Round 3 changes the pinch closing axis to vertical
using verified quaternion kinematics, approaches the lip horizontally from
the north, measures the live fingertip midpoint, and re-anchors the base
after each reach. No kinematic attachment, object transform write, asset edit,
mass edit, or scene repair is allowed.

## Day 3 Step 1 Round 3 result — 2026-07-19 04:49–05:00 UTC

The clean trial ran in the dependency-complete remote worktree after the
container's main mount was found to lack `verify_grasp_lift.py`. No benchmark
asset was changed. Raw result:
`outputs/task3_stage1_tray_slide_r3_20260719/result.json`.

- Physical slide passed: tray moved `+0.238593 m` north and reached
  `+0.059059 m` measured north overhang after three strokes.
- Corrected horizontal edge approach reached contact, but the live fingertip
  midpoint before close was `z=0.819059 m` versus the tray lip target
  `z=0.759661 m` — about `5.94 cm` too high.
- The gripper closed empty at `0.000569 rad`; result `passed=false`,
  `failed_phase=edge_pinch`. No carry to the dining table occurred.
- Diagnosis: the closing-axis orientation is corrected, but the wrist/hand
  still cannot place the fingertips vertically around the lip at this
  approach. The next physical action is a targeted hand/wrist approach
  correction or the authorized two-arm corner pinch; do not retune the old
  z-offset path.

## Organizer update check — 2026-07-19

Fetched organizer `upstream/main` at `cb51845`, a participant-runtime
refactor authored July 17. It relocates Task 3 into `task3_isaacsim/` and
removes older development-only paths; it was not merged because that would
delete this branch's proofs and active physical probe. The current competition
page still lists simulation end as Aug 3, 2026, notes that the submission
schedule will be revised, and requires a public repository with Dockerfile
and README. Owner instruction remains the sprint priority: finish and preserve
the tray-to-dining-table physics result.

## Day 3 Step 1 round 2 — 2026-07-18/19 (owner-approved 3-fix plan)

Round 1 (commits 57f2ca7, b9d92d6, cc9ae02; see the entry below) fixed the
reach-envelope and navigation bugs but left three diagnosed blockers open.
Round 2 (commits ee443d5, 6778728, d050901) fixed all three, per an
explicit owner-approved plan, then ran the same bounded 4-trial protocol:

1. **Overhang measurement**: dropped `tray_bounds()`/`UsdGeom.BBoxCache`
   (it returned an IDENTICAL spawn-pose bounding box in all 4 round-1
   trials, never reflecting the tray's live PhysX pose). New
   `north_overhang_m()` computes overhang directly from the live
   `RigidPrim` tray-center y plus the Step 0 measured static half-extent
   (`0.436315/2 = 0.218158 m`). Verified correct in every round-2 trial
   (overhang values now track the tray's actual measured slide distance).
2. **Multi-stroke drag**: up to `MAX_PUSH_STROKES=3` press-drag strokes,
   each re-reading the live tray pose, re-aligning the base via
   `stroke_needs_realign()` if the contact point drifted `>0.08 m`, and
   stopping early once `north_overhang_m>=0.05` or `moved_y>=0.22`. The
   per-stroke body lives in module-level `_run_push_stroke()` (kept out of
   `_run()` for the mccabe complexity budget) and shares `hold_anchor`
   state with `sim_tick()` via a one-entry mutable box -- a plain
   parameter would have silently reintroduced the round-1 hold_anchor
   clobbering bug across the function boundary.
3. **Tray-relative north pinch stance**: `north_pinch_target()` (the
   tray's own live north edge) + `north_pinch_stance()` (dead ahead,
   `0.8 m` standoff, inside the proven `~0.83 m` envelope) replace the
   inherited, never-validated `(STANCE[0], -0.75)`. `stance_in_safe_lane()`
   checks the computed stance against the room geometry documented in
   `task3_autonomy/navigation.py` (island north face `y=-1.22`, partition
   south face `y=0.10`) before committing; the geometry check never
   triggered in any trial (plenty of margin across the observed slide
   range). The base routes around the island (transit at the proven-safe
   `STANCE[0]` x, then west along the now-clear lane) rather than through
   it, then rotates to face south (`FACE_SOUTH_YAW_RAD = -pi/2`).

New unit tests: `scripts/tests/test_probe_tray_slide.py` (18 tests) cover
`north_overhang_m`, `north_pinch_target`, `north_pinch_stance`,
`stance_in_safe_lane`, `stroke_needs_realign`. CPU gate 512/512 throughout
round 2, Ruff/py_compile clean at every commit.

**4 round-2 trials** (`outputs/task3_stage1_tray_slide_r2t{1,2,3,4}_*`):

| trial | change from previous | slide gate (moved_y / overhang) | strokes | edge_precontact | edge_close | IK failures |
|---|---|---|---|---|---|---|
| r2t1 | (baseline: overhang fix + multi-stroke + north stance) | **PASSED**: +0.2367 m / +0.0571 m | 3 | direct reach FAILED (0.49 m error, 5x IK-fail) | not reached | 5 (all at edge_precontact) |
| r2t2 | split edge_precontact into edge_pregrasp_above + edge_descend (mirrors the round-1 push fix) | not met: +0.196 m / +0.017 m (weaker stroke coupling this run) | 3 | PASSED | FAILED: gripper closed to ~0.00036 rad (missed) | 0 |
| r2t3 | edge pinch z-offset: `tray_z+0.014` -> `tray_z+0.0` (tray center, not above it) | not met: +0.196 m / +0.016 m | 3 | PASSED | FAILED: ~0.00035 rad; descend stall barely moved (0.813->0.820 m) despite a lower target | 0 |
| r2t4 | edge pinch z-offset: `tray_z-0.03` (deliberately far below, to test whether more force clears the stall) | not met: +0.094 m / -0.086 m (worst coupling: one stroke went net-south) | 3 | PASSED | FAILED: ~0.00072 rad; stall still ~0.826 m, same as r2t2/r2t3 despite a 4.4 cm range of commanded targets | 6 (during strokes, not edge phases) |

4-trial ceiling reached (round 2). Stopped for owner review per protocol;
did not launch a 5th trial or the two-arm escalation.

**Diagnosis of the remaining blocker (evidence-based):** the slide,
overhang measurement, multi-stroke drag, north-stance navigation, and
edge-pregrasp/descend reach are now all solid (0 IK failures at every one
of those phases across all 4 trials; r2t1 passed the slide gate outright).
The sole remaining failure is `edge_close`: across three very different
commanded descend targets spanning a 4.4 cm range (`tray_z+0.014`,
`tray_z+0.0`, `tray_z-0.03`), the wrist consistently stalls at almost the
SAME measured height (`ee_z` 0.813, 0.820, 0.826 m) and the gripper always
closes to ~0.0003-0.0008 rad (i.e., catches nothing). A real stall height
that does not move with a 4.4 cm change in commanded depth means this is
not a targeting-formula problem -- it is a genuine, fairly repeatable
physical/kinematic contact (most likely the wrist or palm, not the
fingertips, contacting the tray top from this approach before the fingers
can drop low enough to straddle the 13 mm edge) or a lateral (x/y)
misalignment putting the true edge outside the closed aperture. Continuing
to tune the z-offset is very unlikely to fix it; a structural change to the
approach (verify the `edge_y` wrist orientation actually points the
finger-closing axis vertically for a north-facing approach, or add a
horizontal reach-in sub-phase after descend) is the next reasonable step,
and/or the two-arm corner-pinch escalation the owner has reserved judgment
on.

## Day 3 Step 1 fix + 4-trial evidence run — 2026-07-18/19

Root cause of the earlier Step 1 failure (commit dab4613) was that the
pre-contact pose was ~1.0 m from stance -- past the proven ~0.83 m
dead-ahead envelope -- so `arms.reach()` timed out by construction. Fix
(commits 57f2ca7, b9d92d6, cc9ae02) rewrote
`scripts/task3/probe_tray_slide.py` to mirror the proven cup pipeline: a
local `TRAY_STANCE` puts the contact point (`tray_x+0.10`, `tray_y`) dead
ahead (~0.86 m); pregrasp-above reach + closed-fist ramped vertical
descend (never `reach()`, which cannot converge into contact) with
contact-stall detection; a synchronized north drag ramps the arm push
target and the base `hold_anchor` by the same offset every tick so the
commanded arm/base separation never grows (new pure-math helper
`synchronized_drag_targets` in `task3_autonomy/arms.py`, unit-tested).
CPU gate 494/494, Ruff/py_compile clean throughout.

4 bounded GPU trials (`outputs/task3_stage1_tray_slide_fix{1,2,3,4}_*`):

| trial | descend_ee_z | failed_phase | moved_y_m | IK failures | change made after |
|---|---|---|---|---|---|
| fix1 | 0.80 | navigate_north_side | -0.045 (wrong direction) | 3x "no solution" | raise descend_ee_z: 0.80 m assumed the OPEN-gripper cup fingertip offset, but the probe closes the fist before descending; measured closed-fist contact stalls at ee_z~=0.852-0.854 m, so 0.80 demanded an infeasible ~5 cm press-through |
| fix2 | 0.83 | navigate_north_side | +0.072 (right direction, weak coupling) | 0 | bisect deeper (0.815) for more press force while stayin IK-safe |
| fix3 | 0.815 | navigate_north_side | +0.123 | 0 | diagnosed separate bug: `hold_anchor` was never cleared after manipulation, so `sim_tick()`'s anchor-hold twist silently overrode every `NavigateTo` command in the north-side drive() -- base moved ~0.01-0.02 m in a 20 s budget in all 3 trials. Fixed by clearing `hold_anchor` before free navigation and re-anchoring after arrival. |
| fix4 | 0.815 (unchanged) | edge_precontact | +0.099 | 0 | navigation bug fix confirmed working (base actually reached the north-side stance this time); edge-pinch reach failed with 0.81 m position error, ik_succeeded=false -- diagnosis below |

4-trial ceiling reached; per protocol, stopping here for owner review rather
than continuing to iterate or escalating to two-arm corner-pinch.

**Diagnosis of the remaining blocker (evidence-based, not yet fixed):**
1. **Slide magnitude is short of the gate.** Best measured `moved_y_m` is
   +0.123 m (fix3) against the `>=0.20 m` gate (or `>=0.05 m` overhang,
   see caveat below); coupling between the commanded 0.26 m arm drag and
   actual tray displacement is only ~28-47%, i.e. the closed fist is
   slipping on the tray top rather than dragging it fully. Deeper contact
   (smaller `descend_ee_z`) increases coupling but at 0.80 m breaks IK
   feasibility during the lateral drag (fix1). The safe range measured so
   far is `[0.815, 0.83]`; 0.815 is the best point found.
2. **The `north_overhang_m` reading is unreliable.** `tray_bounds()` (via
   `UsdGeom.BBoxCache.ComputeWorldBound`) returned the IDENTICAL
   `bounds_min`/`bounds_max` in all 4 trials (`[-4.447627,-1.835848,...]` /
   `[-4.110983,-1.399533,...]`) despite the tray's live PhysX pose (read
   correctly via the `RigidPrim` view, `tray_pose()`) differing by up to
   0.17 m in y across trials. That bbox exactly matches the tray's ORIGINAL
   spawn-pose bounds from the Step 0 measurement -- the USD-stage bounding
   box is not reflecting the live PhysX/Fabric transform. `moved_y_m` (from
   the live `RigidPrim` pose) is the only trustworthy slide metric right
   now; `north_overhang_m` should not be trusted until this is fixed.
3. **The north-side edge-pinch approach point is unproven and likely
   over-reaches.** With the tray only at y~=-1.499 (fix4), the edge target
   is ~1.18 m diagonally from the north-side stance `(STANCE[0], -0.75)` =
   `(-3.32, -0.75)` -- far past the proven ~0.83 m envelope, and IK
   correctly failed to converge (`ik_succeeded=false`,
   `position_error_m=0.81`). Even a FULLY successful slide (tray landing
   around y~=-1.36 to -1.38) would still put the edge target ~1.09 m from
   that same stance -- still over budget. This stance constant appears to
   have never been exercised/tuned before (all prior trials failed earlier
   in the pipeline); it likely needs its own local, tray-relative stance
   (the same fix pattern already applied to the south-side push) rather
   than the fixed `(STANCE[0], -0.75)`.

Recommended next steps for whoever picks this up: (a) fix `tray_bounds()`
to read live geometry (e.g. combine `tray_pose()` with a bbox computed
once at the identity/spawn orientation, or query PhysX collision extents
directly) so the overhang gate is trustworthy; (b) give the north-side
edge-pinch approach its own local tray-relative stance, mirroring
`TRAY_STANCE`; (c) re-examine whether 0.26 m push distance at ~50%
coupling is enough once IK/navigation are no longer the limiting factor,
or whether the two-arm corner-pinch escalation is warranted instead.

## Physical tray investigation — 2026-07-18

The Day 3 plan supersedes the earlier purpose-modeled-handle proposal. The
submission path must use the unmodified organizer scene and physics-legal
manipulation; no kinematic attach, added tray geometry, or authored mass edit.
The official Stage 1 predicate is final XY in dining for each object, so the
tray does not have a separate lift gate.

- The imported `simple_tray` is a flat mesh: world bounds about
  `0.337 x 0.436 x 0.013 m`, with no raised grasp affordance.
- The tray is dynamic (`kinematic_enabled=false`) and was explicitly set to
  `0.35 kg` for the diagnostic. Its original bottom was `z=0.7466 m`, below
  the countertop contact plane; the repair path now raises it by `0.02 m`,
  producing `z=0.7666 m` clearance.
- Physical fixture attempts were measured, not inferred: separate fixed-joint
  rim, embedded collision child, cube/cylinder handles, explicit friction,
  and lightweight mass all produced `0.0 m` tray lift. The best single-arm
  closure was approximately `0.57 rad`, but the tray did not follow the arm.
- The synchronized two-arm path reached only a marginal pregrasp and then
  failed IK/contact sequencing. No physical Stage 1 carry proof exists yet.
- Do not describe the fixture path or the Day 2 adapter as full autonomy. The
  next physical task is Step 0 measurement, then slide-to-overhang edge pinch;
  escalate once to a two-arm corner pinch only if the single-edge method
  fails.

## Day 3 Step 0 measurements — 2026-07-18

Completed in the unmodified organizer scene at head placement `a` using
PhysX/Fabric runtime reads. The only stage normalization was disabling nested
rigid-body schemas so the existing `RigidPrim` views could bind; no tray
geometry, mass, joint, or kinematic attachment was authored. Full raw result:
`outputs/task3_stage0_probe_20260718/result.json`.

- Gripper open command `0.9 rad`; measured joint positions were left
  `0.899995 rad`, right `0.899944 rad`. Fingertip bodies were
  `left_left_2_link`/`left_right_2_link` and
  `right_left_2_link`/`right_iight_2_link` (the latter preserves the USD typo).
  World fingertip separations: **left `0.034000 m`, right `0.034000 m`**.
- Unmodified tray runtime mass: **`0.300000 kg`** via
  `RigidPrim.get_masses()`; its authored USD mass is also `0.300000 kg`.
  This replaces the earlier diagnostic-only `0.35 kg` fixture measurement.
- Counter edge references: east `x=-3.77`, north `y=-1.22`; each gap below
  is edge coordinate minus object world-bbox maximum coordinate.

| object | PhysX pose `(x,y,z)` | world bbox size (m) | runtime mass (kg) | east gap (m) | north gap (m) |
|---|---|---:|---:|---:|---:|
| `simple_tray` | `(-4.279305,-1.617691,0.759661)` | `0.336644 × 0.436315 × 0.013141` | `0.300000` | `0.340983` | `0.179533` |
| `bowl2` | `(-4.298296,-1.499874,0.746420)` | `0.118367 × 0.117874 × 0.055793` | `0.220000` | `0.469334` | `0.221006` |
| `spoon2` | `(-4.341526,-1.678126,0.760765)` | `0.125166 × 0.047448 × 0.029423` | `0.050000` | `0.547419` | `0.427435` |
| `plate2` | `(-4.308727,-1.660848,0.747168)` | `0.215316 × 0.215320 × 0.023251` | `0.220000` | `0.431065` | `0.333191` |
| `cup` | `(-4.184931,-1.752757,0.747003)` | `0.080053 × 0.081109 × 0.087307` | `0.093608` | `0.374844` | `0.491608` |

## Day 3 Step 1 physical tray trial — 2026-07-18 20:28–20:35 UTC

Ran one explicit north-side slide-to-edge attempt in the unmodified scene at
head placement `a`. The probe used real navigation, arm joint targets,
gripper contact, and PhysX `RigidPrim` pose reads. It did not write an object
transform, add geometry, alter mass, attach a kinematic body, or use the Day 2
adapter. Raw result: `outputs/task3_stage1_tray_slide_north_20260718/result.json`.

- Navigation reached the physical stance at `(-3.2937,-1.7322)` while the
  tray remained at `(-4.279305,-1.617691,0.759661)`.
- The contact attempt moved the tray physically north by `0.038228 m` with
  only `0.000001 m` vertical change; this is contact evidence, not a
  grasp/carry pass.
- The arm timed out at `push_precontact`, so no overhang measurement, edge
  pinch, lift, or dining placement occurred. Result `passed=false`.
- Current blocker: the commanded north-side pre-contact pose was not reached;
  the tray needs a better physics-legal approach/contact sequence. One
  two-arm corner-pinch escalation remains available, but no scene repair is
  authorized.

## GPU STATUS (final verdict 2026-07-17 ~13:10 UTC)
- **`sim-dev-g4b` (g4-standard-48 = FULL RTX PRO 6000 Blackwell 96 GB,
  SPOT, us-central1-b): STOPPED after the physical tray diagnostics.** Isaac render VERIFIED
  (`outputs/task3_g4_render/rgb_0000.png`, app wall-time 9.4 s warm).
  Driver: `nvidia-driver-580-open` (apt) — Blackwell passthrough needs the
  OPEN kernel modules. `/dev/nvidia-uvm` must exist (persisted via
  `/etc/modules-load.d/nvidia-uvm.conf`). After ANY driver change:
  `docker restart isaac-lab-2-3-2-workshop` to re-inject GPU libs.
  Snapshot: `sim-dev-g4b-verified-20260717`. Spot → preemption expected;
  restore = boot from snapshot, drivers included.
  **capture_static_view.py gotcha: pass an ABSOLUTE --output-dir** (a
  relative path makes Replicator write the PNG somewhere else and
  fastShutdown swallows the error).
  WebRTC server starts and TCP `0.0.0.0:49100` is verified listening.
  Firewall `ebim-webrtc-owner` targets tag `webrtc-stream` and currently
  allows only the owner's post-VPN IPv4 `92.209.223.203/32`; VM tag and NAT
  IP `34.61.210.0` verified. After the exact-IP update at 22:42 UTC, a live
  TCP probe from the client network to `34.61.210.0:49100` passed. Separate
  agent diagnosis: all earlier verifiers incorrectly used private/NVCF mode
  `livestream=2`; public mode is `1` with `PUBLIC_IP`. Clean Run 12 verified
  mode 1, one Kit process, one listener, and no lock conflict. The NVIDIA
  client's newest saved server value is nevertheless
  **` 34.61.210.0` (leading space)** and it opened zero sockets, so visual
  confirmation awaits a Ctrl+A/retype retry. Full evidence:
  `docs/webrtc_diagnosis_2026-07-17.md`. Do not silently broaden ingress.
  VM disk cleaned 2026-07-17 (~16 GB runaway frames deleted; 17% used).
- `sim-dev-g4` (g4-standard-24/48-resized, us-east5-a): **STOPPED — DEAD
  END for Isaac.** Fractional g4 shapes are MIG-backed vGPU partitions:
  driver-level Vulkan+RT works (GRID vGPU 19.5 guest only), but Kit
  refuses the GPU ("Skipping NVIDIA GPU due CUDA being in bad state" —
  CUDA↔Vulkan interop unsupported on MIG vGPU). Do not retry without new
  evidence. Owner may delete this VM's disk to save cost.
- `sim-dev` (L4, us-central1-c): **STOPPED** — proven fallback. Never delete.
- Quota: `GPUS_ALL_REGIONS=1` — one GPU VM running at a time, total.
- Quota: `GPUS_ALL_REGIONS=1` — one GPU VM at a time, total.

## DONE (frozen — do not rework)
- **Phase 2 navigate gate PASSED (2026-07-17, commit fdf9476; proof
  `proofs/phase2-navigate-live/`, eval_results line, video sent to owner).**
  Full chain: TmrBaseAdapter runtime wheel damping 500 (actuator-cfg path
  does NOT reach PhysX) → base does a true 0.5 m/s; NavigateTo plans
  route_via_door (doorway x=-4.14; kitchen-side lane y=-0.37); arms ramp to
  TRANSIT_ARM_POSE "pnn_j6_15_j4_30" (probe-measured: width 1.88→0.74 m,
  nose 0.885→0.78 m) before driving. nav10: stop 2.9 cm from the
  island-east corridor stop (-3.18,-1.6) in 14.7 s sim. Room geometry
  measurements live in task3_autonomy/navigation.py comments; probe tool
  scripts/task3/probe_arm_tuck.py. Old verify target (-2.0,-1.5) is behind
  a full-height wall at x≈-2.5 — never use it.
- Grading + integration tests for all 4 stages (upstream state, see master plan §3).
- `task3_autonomy/navigation.py` pure math, 14/14 tests —
  `proofs/phase2-navigation-math/`.
- sim-dev L4 Isaac bring-up + verified render + snapshot (2026-07-17).
- RTX PRO 6000 bring-up: **COMPLETE (2026-07-17)** — full-GPU spot
  `sim-dev-g4b` verified rendering the Task 3 room in 9.4 s; snapshot
  taken; proof image sent to owner. Fractional/vGPU shapes proven
  unusable for Isaac (see GPU STATUS).
- Phase 1 blocker RESOLVED (2026-07-17): robot USD's ROS2/keyboard controller OmniGraphs now deactivated BEFORE composition via generated wrapper layer (make_headless_robot_usd, commit a328224; CPU tests 198/198). Video capture rebuilt pull-based via rgb annotator after Replicator BasicWriter runaways of 139k/93 GB and 12k frames — even set_capture_on_play(False) cannot stop an attached writer while the timeline plays (commits 9caecb1, ef7af06). First clean idle episode: exactly 160 frames + episode.gif on sim-dev-g4b.

## IN PROGRESS

### Codex one-task-at-a-time checklist (live)

- [x] Preserve inherited work on `agent/codex-task3-grasp` and audit it.
- [x] Implement/test world-frame `reach()` through the teleop boundary.
- [x] Correct the real gripper joint mapping and spine actuator strength.
- [x] Restore exact-IP WebRTC ingress after VPN disconnect; TCP gate passes.
- [x] Obtain one measured grasp + >=0.08 m sustained lift and compact GIF.
  Run 18 passed: final lift 0.1087 m, 3.0 s sustained hold, peak 0.195 m.
  `result.json` and the 11 MB GIF are preserved locally under
  `outputs/task3_verify_grasp_skip18_margin_public/`.
- [x] Official reliability gate: **10/10 PASS** (`0.088 m` lift,
  `3.0 s` hold each; `gate_passed=true`, required `8/10`). Evidence is
  packaged in `proofs/phase2-grasp-reliability/`; per-trial JSONs remain in
  `outputs/task3_grasp_reliability_official_20260718/`. This proves frozen
  pipeline repeatability in the deterministic scene, not robustness to
  randomized object physics.
  Tuning trial 01 failed (0.0072 m final lift): pregrasp/close passed, then
  the instantaneous lift request timed out and pushed the cup 0.137 m in +Y.
  Tuning trial 02 used a 3.0 s vertical Cartesian ramp: lift succeeded and
  cup ended +0.1481 m, but only 0.98 s continuous hold fit inside the 5 s
  observation window. Trial 03 leaves the 3 s continuous gate unchanged and
  extends only post-lift recovery observation from 2 s to 8 s. The official
  10-run count restarts only after configuration freeze. Trial 03 still
  oscillated: final lift +0.1018 m, continuous hold 1.93 s, with measured base
  yaw drift of ~0.43 rad during lift. Root cause: the shared yaw compensator
  deliberately re-anchored whenever XY velocity reached zero, disabling
  heading hold at the manipulation anchor. Trial 04 preserves the anchored
  yaw while stopped; normal navigation semantics remain the default. Trial 04
  produced a strong mid-stroke pinch (0.4086 rad) but arm-only lift timed out;
  cup ended +0.0894 m with 1.52 s continuous hold. Trial 05 adds 0.12 m of
  prismatic-spine assistance along the same 3 s Cartesian lift path, reducing
  the arm's relative vertical travel and base reaction. Trial 05 achieved the
  physical gate: +0.0880 m final cup lift and 3.0 s continuous hold, but the
  verifier reported false because the wrist missed the aspirational 1.10 m
  target by >3 cm. The gate now follows its documented object-space contract
  (valid pinch + measured cup height + continuous hold); wrist convergence is
  retained as a diagnostic. Tuning trial 06 confirmed the frozen configuration
  with an identical pass: +0.0880 m final lift, 3.0 s continuous hold, 0.4086
  rad pinch. The official fresh 10-run batch is next. CPU gate is 451/451;
  changed files are Ruff-clean.

  **Official batch complete:** 10/10 passed at +0.0880 m and 3.0 s hold;
  `gate_passed=true`, required `8/10`. Proof:
  `proofs/phase2-grasp-reliability/`.
- [x] **Step 0 (Codex, 2026-07-18 18:44–19:05 UTC):** started
  `sim-dev-g4b`; measure open-0.9-rad fingertip aperture, unmodified-scene
  runtime tray mass, and pose/bounds/edge distances for
  `simple_tray`, `bowl2`, `spoon2`, `plate2`, and `cup`; record raw output
  in `outputs/task3_stage0_probe_20260718/result.json`; commit and push.
- [ ] **Step 1 (Codex, rounds 1–11, 2026-07-18/19, 17 trials
  total):** slide tray to 6-8 cm overhang, edge pinch, dining XY gate
  `>=7/10`; one escalation to a two-arm corner pinch if needed. Round 1
  fixed the reach-envelope and hold_anchor-clobbering navigation bugs.
  Round 2 (owner-approved 3-fix plan) fixed the stale overhang
  measurement, added multi-stroke dragging, and derived a tray-relative
  north pinch stance -- the slide-to-overhang SUB-gate now passes reliably
  (r2t1: `+0.2367 m` moved, `+0.0571 m` overhang) and navigation +
  pregrasp/descend reach are solid (0 IK failures at those phases in every
  round-2 trial). The remaining, now well-isolated blocker is `edge_close`:
  across a 4.4 cm range of commanded pinch depths (3 trials), the wrist
  stalls at nearly the same height every time and the gripper always
  closes on nothing -- a real physical/kinematic contact or lateral
  misalignment, not a targeting-formula problem. See the 2026-07-18/19
  round 2 evidence table and diagnosis above. Both 4-trial ceilings used
  (8 GPU trials total); stopped for owner review each time.
  Round 3 fixed the closing-axis orientation and re-anchored the base after
  each pinch reach. It passed slide/overhang again (`+0.238593 m` moved,
  `+0.059059 m` overhang) but failed the physical edge pinch because the live
  fingertips remained `5.94 cm` above the lip and closed empty at `0.000569
  rad`. Round 4 then produced a physical pinch and `+0.025787 m` tray lift,
  but its generic lift predicate was false. Round 5 passed the slide gate but
  failed at north-stance navigation. Round 6 passed north-stance navigation
  and physical closure (`0.198886 rad`) but did not pass the slide gate, so
  the tray could not lift. Round 7 repeated the proven push distance but
  stopped at a second-stroke pregrasp reach timeout (`0.056190 m` position
  error, `0.122625 rad` orientation error). The carry-to-table phase remains
  unverified. Round 8 reached a physical pinch (`0.217117 rad`) after three
  strokes but had only `0.035366 m` overhang and `-0.000555 m` lift, so no
  carry was attempted. The active probe now permits a fourth stroke and
  requires the actual overhang gate before edge pinch. Round 9 passed the
  overhang and physical lift (`+0.098956 m`, `+0.036547 m`) and crossed three
  door-route waypoints, but final dining carry stalled with the tray still in
  the kitchen. Round 10 did not pass the overhang gate (`+0.024374 m`), so
  the carry hand-target update remains untested on a fresh gate-passing run.
  Round 11's 8 s drag also failed the slide gate (`-0.013220 m` overhang).
  `scripts/task3/probe_tray_slide.py` remains active. No kinematic or scene
  edits were made in any round.
- [ ] Step 2: physical per-object chain `cup → bowl2 → spoon2 → plate2`,
  Stage 1 gate `>=4/5` on `>=7/10` seeded runs.
- [ ] Step 3: 10-run head-placement matrix, physical proof bundle, tag
  `v0.1-stage1`, and video handoff.
- [ ] Step 4: utensils to sink, gate `>=6/10`; export code/proofs/JSONs and
  videos immediately after this exit criterion.
- [ ] Step 5: Stage 2 then Stage 3, shipping partial credit if time-boxes
  expire; complete the chained episode and packaging only after export.
- [ ] Run evaluation, assemble proof, and create the Day 1 tag.
- [ ] Update journal/budget, commit, push, and leave exact resume commands.

- **Phase 2 reach/grasp/lift gate — Codex,
  `agent/codex-task3-grasp`, claimed 2026-07-17 21:39 UTC.** Inherited
  uncommitted `task3_autonomy/arms.py`, `RotateTo`/yaw support in
  `task3_autonomy/skills.py`, and
  `scripts/task3/verify_grasp_lift.py`. First actions: preserved the dirty
  tree on a dedicated branch, verified `origin/main...HEAD = 0/0`, and
  confirmed the G4b VM is RUNNING. Audit finding: the draft sends world
  poses directly to Lula and bypasses the required one-step
  `TeleopCommand`/`CartesianTargetTracker` boundary, so it is not yet a
  completed `reach()` implementation. That audit is now resolved:
  `one_step_reach_command()` uses the required `TeleopCommand` +
  `CartesianTargetTracker` boundary and reissues absolute world targets on
  every tick. Real ChangingTek gripper joints are
  `left_gripper_joint`/`right_gripper_joint` (0..1 rad), not the fake FR3
  finger names; linkage joints are passive. The prismatic spine needed its
  authored 50k/5k/500k drive strength instead of the prior 200 N effort.
  Current CPU gate: **436/436 targeted tests pass**, Ruff and compile clean.
  Owner confirmed GCP usage has no cost ceiling for this sprint; the single
  permitted GPU should remain productively occupied while work remains.

  Live evidence: Runs 1–4 exposed import, fake-finger, MappingProxy, degrees
  vs radians, and unsafe direct-spawn bugs. Run 5 reached the final stance
  but timed out and produced an impractical 184 MB GIF. Run 6 measured the
  weak-spine failure. Run 7 passed spine+tuck+stance but failed pregrasp
  because wheels were not stopped and a base-relative goal drifted. Run 8
  fixed pregrasp (`EE [-4.153,-1.737,1.038]` vs target
  `[-4.145,-1.750,1.050]`) but final contact stopped 8.6 cm from the
  mathematical wrist goal and slid the cup ~6 cm; it aborted before close.
  Run 9 reasserts zero wheel/heading targets each manipulation tick, derives
  final XY/Z from the measured cup pose, accepts a bounded 10 cm contact
  residual before gripper closure, and records at 2 FPS/640x360. Run 9
  passed through descend but failed close: the fully closed joint measured
  0.9667 rad, cup contact lift was only 0.0318 m, and the 50-frame/8.9 MB
  GIF shows the south finger pushing the cup +0.07 m in Y. Run 10 changes
  only final grasp Y offset to +0.06 m; it failed with the gripper again at
  0.9865 rad and pushed the cup 0.134 m in X, disproving that offset. The
  authoritative older FR3 controller uses 0.04=open and 0.0=closed; visual
  evidence plus the near-1.0 final state show the real linkage direction was
  reversed in the new code. Run 11 restores baseline XY and corrects only the
  ChangingTek convention to 0.9=open, 0.0=closed. It kept the cup nearly
  fixed and the final frame shows both fingers around it, but the measured
  joint stayed 0.9562 rad and the old `<0.85` predicate aborted before lift.
  Run 12 expands only the candidate-contact ceiling to the USD limit tolerance
  (1.05); the actual >=0.08 m lift and 3 s hold remain mandatory.
  Clean public Run 12 exercised the lift: wrist z 0.859 -> 0.971 m, but cup
  rose only 0.0307 m and held_s=0, proving no grasp. Run 13 adds a free-space
  close-to-0/reopen-to-0.9 probe at pregrasp height to distinguish actuation
  failure from alignment before another cup contact. Run 13 proved both
  motions (close=0.0009, reopen=0.8802), but the base then drifted ~0.46 m
  during descent and pushed the cup ~0.40 m. Run 14 replaces zero-wheel
  velocity with active XY feedback to the post-navigation anchor on every
  manipulation tick; yaw still uses the proven adapter compensator. Current
  Run 14 reduced base drift to ~0.10-0.14 m and lifted the cup to z=0.824
  (0.077 m above start, just below gate), but one-finger contact pushed it
  ~0.13 m in +Y and it fell from the table during hold. Run 15 changes only
  final grasp Y by +0.06 m now that the base makes that calibration valid.
  Run 15 produced a genuine mid-stroke pinch (0.4351 rad) and cup peak
  z=0.816 (+0.069 m), but it missed the 0.08 m gate and settled to +0.038 m
  because the post-lift loop stopped reissuing its absolute world target.
  Run 16 raises the wrist target 0.05 m and reissues the attained world hold
  pose every tick. Current gate before Run 16 is **448/448 tests pass**, Ruff
  and compile clean. Run 16 reached cup peak z=0.852 (+0.105 m, above the
  height gate) but the instantaneous close ended at 0.0785 rad and the cup
  slipped before hold. Run 17 changes only closure dynamics: 1.0 s linear
  close ramp plus 0.5 s force settle to avoid contact bounce/ejection. Run 17
  then kept the cup aloft: peak +0.134 m and final +0.098 m, but oscillation
  limited consecutive time above +0.08 m to 0.14 s. Run 18 changed only the
  wrist lift target from z=1.05 to 1.10 m and **passed**: cup start z=0.7470,
  peak z=0.9420 (+0.1950 m), final z=0.8557 (+0.1087 m), with 3.0 s sustained
  hold. Exact JSON/GIF are preserved locally and on the VM. Day 1 is
  **complete and pushed in commit `cf37203`**.

- [x] Day 2 Stage 1 controller and live kinematic-scene matrix: **10/10
  PASS at 5/5**, across head placements `a/b/c`; proof is in
  `proofs/phase3-stage1-kinematic/` with a 22 MB GIF. The runner records the
  mode as `kinematic_scene_adapter`.
- [ ] Physical Stage 1 tray-contact gate remains open: the existing matrix
  validates the FSM ordering and official grading predicates, but does not
  yet validate rigid tray grasp under PhysX. Do not oversell the adapter proof
  as full physical autonomy.

Phase 1 is CLOSED: proof bundle `proofs/phase1-harness/` (c1681b2) with
SPAWN_MATCH True, tag `v0.1-harness` pushed. Re-confirmed 2026-07-17 ~18:30:
runA/runB result.json agree on every physics field (spawn/final positions,
stages, total_steps); only timestamps/paths differ.

## NEXT UP (in order — claim in this file before starting)
1. [GPU/Claude] Fix nonfatal PhysX error spam: disable_robot_external_wrenches() calls addTorque/setLinearVelocity which are illegal with eENABLE_DIRECT_GPU_API — guard or replace with Isaac Lab tensor API.
   Reported done in the interrupted Claude session; Codex must verify the
   committed/diff state and test evidence before moving it to DONE.
3. [x] [GPU/Codex] Finish `reach()` → `grasp()`/`lift()` →
  **`verify_grasp_lift.py` ≥8/10 gate**. Navigation and quat→RPY are
  already committed/proven (`73f6098`, `f6c6582`).
4. [CPU/Codex] Dockerfile skeleton + README submission section drafts;
   `docs/simdev_setup.md`; PROJECT_JOURNAL scaffold.
5. [CPU/OpenCode] `scripts/task3/make_proof_bundle.py` helper; 15-run batch
   script; `--record-lerobot` design (code + unit tests only).
6. [x] [GPU/Codex, 2026-07-18] Stage 1 FSM controller and kinematic proof
   complete; physical tray-contact validation remains next before a final
   `v0.1-stage1` tag.

## BLOCKERS
- Lab account expiry ≈ Jul 19–20: export ritual (plan §5 Day 3) is mandatory.
- Personal-project L4 quota (fallback after expiry) still pending — check
  daily: `gcloud compute regions describe us-central1
  --account=mitvho09@gmail.com --project=gen-lang-client-0186028838`.
