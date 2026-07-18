# Project Journal

## 2026-07-17 — GPU platform findings (smallest-GPU first, then evidence-driven escalation)

Goal: determine which cloud GPU platforms can run the Task 3 headless episode
runner with physics simulation and render output.

Work completed: investigated three GPU paths: Modal serverless (GPU="L4"), GCP
fractional g4 vGPU shapes (g4-standard-24, half of RTX PRO 6000), and GCP full
GPU (g4-standard-48). Modal failed with known limitation (CUDA compute available
but NVIDIA Vulkan graphics stack not exposed in container). Fractional g4 vGPU
shapes (MIG-backed partitions) appeared to pass driver checks but Kit's Isaac Sim
renderer rejected the GPU with "Skipping NVIDIA GPU due CUDA being in bad state"—
a fundamental incompatibility because CUDA↔Vulkan interop is unsupported on
MIG vGPU. Full g4-standard-48 (entire RTX PRO 6000 96 GB, Blackwell, spot instance
in us-central1-b) worked: Task 3 scene render completed in 9.4 s app wall-time
(warm), vs. ~60 s on L4 fallback VM. Snapshot taken: `sim-dev-g4b-verified-20260717`.

Evidence: render output `outputs/task3_g4_render/rgb_0000.png` verified on primary
box `sim-dev-g4b`. AGENT_STATE.md GPU status confirmed; `gpu_budget_log.md`
session entry documented driver findings (MIG vGPU driver selection failed;
standard open kernel modules work on passthrough).

Lesson: smallest-GPU-first discipline finds real blockers early (3 failed paths
cost ~1.5 EUR total), and evidence of *functional incapability* (not just
performance preference) justifies escalation to larger GPU.

## 2026-07-17 — Headless episode runner: OmniGraph composition-time debugging

Goal: run `scripts/task3/run_episode.py --policy idle --record-video` to
completion and produce EPISODE_RESULT JSON with video frames.

Work completed: reproduced the episode runner on real GPU hardware (`sim-dev-g4b`);
corrected gripper actuator joint-name patterns (commit 8431332); diagnosed and
repaired a `RigidPrim` CUDA crash (commit de684a0) by disabling nested enabled
rigid bodies in imported props. Then encountered a second blocker: the robot USD's
built-in ROS2/keyboard controller OmniGraphs (`Steer_joint_Controller` and
`ROS_JointStates`) crash headless after `sim.reset()` with "Attempted to access
an invalid object" while reading `Desired_Linear_Velocity_X` input. Attempted
four repairs (commits 900520f, 221dffa, f71d32e, 69f5913): post-load graph
deactivation, zeroing ScriptNode inputs, and re-initializing named inputs—all
failed because Kit registers OmniGraphs during stage composition, making any
post-load patching ineffective. Final solution: author a thin wrapper USD layer
(`make_headless_robot_usd()` in run_episode.py, commit a328224) that sublayers
the asset and sets `Graph.active=false` *before* composition. The wrapper works
because its deactivation override lives in a stronger layer of the referenced
layer stack, so Kit never composes — and never registers — the controller nodes.

Evidence: 197/197 CPU regression tests pass after a328224, including 6 new
pure-USD tests that mirror Isaac Lab's reference-spawn path; on-GPU episode
verification in progress at time of writing (result to be linked here).

Lesson: composition-time fixes (stage prim overrides before reference) are the
only reliable repair point for USD schema issues in headless environments; post-load
patching of graphs or prims cannot undo Kit's initialization decisions.

## 2026-07-17 — Video capture runaway and the pull-based fix

Goal: produce a complete recorded idle episode (160 frames + EPISODE_RESULT
JSON) on the verified RTX PRO 6000, revealing any remaining blockers before
determinism verification begins.

Work completed: launched the first clean idle episode after the OmniGraph
pre-composition fix (commit a328224); encountered a second critical incident:
attached Replicator BasicWriter writes a frame to disk on every app-state
update while the timeline plays, not just when requested. Two runaway incidents
occurred: first writing 139,471 frames over 93 GB in one 20-minute attempt,
then a second runaway writing 12,000 frames (≈1 GB) despite setting
set_capture_on_play(False) — the attached writer still fires on all state
changes. Replaced the push-based BasicWriter with a pull-based RGB annotator
that yields a single frame only when the episode loop explicitly requests it
(commits 9caecb1, ef7af06); the first complete run produced exactly 160 frames
plus an animated gif, with no disk overflow. Disk freed: 93 GB + ~16 GB of
older debug frame directories.

Evidence: 160/161 expected frames in the first clean idle run;
VM disk 17% after cleanup; determinism pair (seed-42, two runs) launched at
commit ef7af06 to verify reproducibility (runA completed, runB in flight).

Lesson: prefer pull-based data acquisition in autonomous pipelines — push-based
recorders fail open (fill the disk and hang the app), pull-based fail closed
(data exists only when requested, boundaries are explicit).

## 2026-07-17 — Phase 1 harness diagnosis (prior work, frozen)

Goal: make the first recorded idle Task 3 episode complete on the verified
RTX PRO 6000 VM.

Work completed: reproduced the episode runner on real GPU hardware; corrected
the mobile FR3 gripper actuator patterns; added a regression assertion; and
diagnosed the `RigidPrim` CUDA crash as malformed nested rigid-body hierarchies
in imported room props. The nested-body normalization removes that CUDA/PhysX
failure. Focused CPU tests passed 106/106.

Current evidence: the remaining block is the robot USD's legacy steering
OmniGraph (`Steer_joint_Controller`), which reads an invalid
`Desired_Linear_Velocity_X` input during reset and leaves the Kit process
stalled. The next session should repair or disable that unused keyboard graph,
then rerun the recorded idle episode.

## 2026-07-17 (evening) — Navigation root cause: the room, not the robot

Goal: make the live NavigateTo skill actually reach a kitchen-side target
(Phase 2 gate), and let the owner watch runs live.

Work completed: an instrumented, camera-free verify run proved the base
drive chain is healthy — wheels track their commanded 10 rad/s and the base
moves at the full 0.5 m/s — and that every "slow crawl" seen so far was the
robot pressing against the dining/kitchen partition wall (wheels
contact-stalled at zero speed while targets stayed high). Routing was fixed
to cross only through the doorway (route_via_door, 207/207 CPU tests), and
a livestream-enabled rerun both gave the owner a live WebRTC view and
produced video of the next blocker: the doorway is ~1.2 m wide but the
robot spans 1.88 m across its outboard-mounted arms. USD measurements show
the arm mounts themselves are narrow (±0.12 m), so a folded "transit pose"
can fit; two probe sessions measured candidate poses in-sim and a
systematic 8-way sweep of the fold geometry is running to pick the
narrowest reachable pose.

Evidence: NAVDBG logs nav7/nav8 (sim-dev-g4b), TUCK_RESULT lines in
/tmp/task3_tuck*.log, stall video sent to owner, room/robot bbox
measurements recorded in task3_autonomy/navigation.py comments.

Lesson: when a controlled system underperforms, verify the actuators
against their targets before tuning them — a wheel commanded to 10 rad/s
that reads back ~0 is an obstruction, not a gain problem. And measure the
environment before planning through it: both partition crossings were
narrower than the robot's default pose from day one.

## 2026-07-17 (late evening) — Phase 2 navigate gate PASSED

Goal: get the live NavigateTo run to actually reach its kitchen-side
target after the arm-width discovery.

Work completed: two more measurement probes picked the arm "transit
pose" entirely from in-sim evidence — an 8-way sweep of fold geometries
found a pose that cancels the arms' outward mount lean (width 1.88 m to
0.74 m), and a follow-up sweep shortened its forward overhang (0.885 m to
0.78 m) after the first tucked run scraped the kitchen island. The route
gained a shallow "kitchen lane" (y=-0.37) that threads the 1.32 m gap
between partition and island, and the verify target moved to a stop the
room actually allows (the old default sat behind an unmapped wall).
Run nav10 then passed cleanly: doorway crossed, 2.9 cm final error,
14.7 s of sim time, heading held within ~1 degree. Proof bundle
proofs/phase2-navigate-live/ (video + result.json + repro chain);
video sent to the owner. VM stopped at session close.

Lesson: in cluttered scenes, navigation failures are usually geometry
budget failures — measure the robot's true swept extents per pose and
the room's true corridor widths, then plan with explicit margins, instead
of tuning controllers against symptoms.

## 2026-07-17 (night) — Codex takeover: reach boundary, real gripper, and live grasp calibration

Goal: resume the interrupted Phase 2 work without losing provenance, obtain
one real grasp/lift, then run the >=8/10 reliability gate.

Work completed so far: moved Claude's uncommitted changes onto
`agent/codex-task3-grasp`; replaced the draft direct-Lula world-pose path with
the required one-step `TeleopCommand`/`CartesianTargetTracker` boundary; added
measured pose errors, explicit timeouts, absolute-world target reissue, and CPU
tests. Inspection of the robot USD proved that the actuated ChangingTek joints
are `left_gripper_joint`/`right_gripper_joint` (0..1 rad), while the FR3 finger
joints are passive linkage/mimic joints. The spine is a 0..0.85 m prismatic
joint whose authored drive is 50k stiffness / 5k damping / 500k max force; the
prior 200 N actuator override could not lift both arms. Runtime mappings and
actuator configuration were corrected. Current focused regression gate is
436/436 passing with Ruff and compile clean.

Live evidence: Run 7 reached the stance but failed pregrasp because the wheel
target remained nonzero and the arm goal was stored base-relative. Run 8 fixed
pregrasp by stopping navigation targets and reissuing the world goal each tick,
then stopped at first cup contact. Run 9 allowed a bounded physical-contact
residual and reached gripper closure, but the motor measured 0.9667 rad (fully
closed, no cup trapped); the cup moved +0.07 m in Y and rose only 0.0318 m.
Its compact 50-frame GIF is 8.9 MB under
`outputs/task3_verify_grasp_skip9_live/`. Run 10 changes only the final Y
offset by +0.06 m and is active at time of this entry.

WebRTC diagnosis was kept separate from manipulation: Isaac reported the
server started and bound TCP 49100, but the old VPN `/32` prevented ingress.
After the owner disconnected VPN, the exact allowlist was replaced with
`92.209.223.203/32`; a client-network TCP probe to `34.61.210.0:49100` then
passed. No wider CIDR was opened.

Lesson: do not tune against names or assumed conventions. Read the USD's real
joint schemas and drive limits, and require measured state at every gate. Keep
calibration runs single-variable so their outcome remains attributable.

## 2026-07-18 — Physical grasp achieved; reliability configuration frozen

Goal: turn the calibrated cup contact into a repeatable >=0.08 m lift held for
three continuous seconds, with measured object physics as the final contract.

Work completed: Runs 11–17 isolated the gripper direction, contact predicate,
base drift, lift margin, and closure impulse. Public Run 18 produced the first
complete visual proof: cup start z=0.7470, peak z=0.9420, final z=0.8557
(+0.1087 m), held 3.0 s; its 11 MB GIF and JSON are preserved under
`outputs/task3_verify_grasp_skip18_margin_public/`. WebRTC public mode 1 was
proven end-to-end and the owner confirmed the stream works.

Six subsequent tuning trials exposed a brittle instantaneous arm lift and a
base yaw controller that re-anchored whenever XY velocity reached zero. The
final configuration uses a 3 s vertical ramp, preserves manipulation heading
while stopped, and raises the strong prismatic spine 0.12 m along the same
Cartesian path. Tuning trial 05 physically held the cup +0.0880 m for 3.0 s;
the verifier incorrectly rejected it because the wrist missed an aspirational
1.10 m target. The gate was aligned with its documented object-space contract:
valid pinch, measured cup lift, and continuous duration; wrist convergence
remains diagnostic. Tuning trial 06 then passed with the identical +0.0880 m,
3.0 s result. CPU gate: 451/451; changed files Ruff/compile clean. The frozen
10-run official batch is running sequentially at
`outputs/task3_grasp_reliability_official_20260718/`.

Lesson: object-space task success should be judged in object space. Internal
IK convergence is useful diagnostic evidence, but it must not veto a measured
successful grasp/lift when the commanded wrist goal intentionally contains
extra margin. Also, a heading controller that resets at zero translation is a
navigation convenience, not a valid stationary manipulation hold.

## 2026-07-18 01:15 UTC - Codex: official grasp reliability gate closed

Goal: finish the Day 1 reliability gate without restarting the detached GPU
batch. The existing parent completed all ten fresh sequential trials: 10/10
passed, each measured 0.088 m cup lift and 3.0 s continuous hold, against the
required 8/10. The batch summary and all per-trial result files were copied
from the VM into `outputs/task3_grasp_reliability_official_20260718/`; Run 18's
GIF remains preserved as the visual proof.

Why it matters: the frozen grasp/lift pipeline now has a reproducible proof
bundle at `proofs/phase2-grasp-reliability/`. Because the scene and controller
are deterministic, this is repeatability evidence rather than a claim of
robustness to physical variation. The VM batch parent exited cleanly; the VM
exited cleanly. The VM was stopped after the Day 2 GPU work completed.

Lesson: package the machine-readable gate, per-trial evidence, visual proof,
and exact reproduction command together before moving to the next phase.

## 2026-07-18 01:34 UTC - Codex: Stage 1 FSM adapter gate

Goal: put the Day 2 Stage 1 controller and scoring path on the board while
keeping its physical-evidence boundary explicit. Added a simulator-independent
FSM with ordered navigate, grasp, transport, place, release, and retreat states;
each state has a timeout and retry budget, and collision/drop observations abort
the attempt. The live adapter ran 10/10 trials at 5/5 across head placements
`a`, `b`, and `c`, and reached `complete` on every run. A 22 MB GIF and matrix
JSON are in `proofs/phase3-stage1-kinematic/`.

This is not yet a full physical Stage 1 claim: the current scene adapter moves
the scored object group kinematically. The next upgrade is to bind
`GRASP_TRAY` and `TRANSPORT` to the proven `DualArmController` and base skills
with PhysX tray-contact measurements. Keeping this distinction in the result
prevents the deterministic adapter gate from being mistaken for robustness or
rigid-contact evidence.

Lesson: make the FSM and grading contract executable first, then replace the
adapter behind the same state milestones without changing the acceptance path.

## 2026-07-18 03:40-04:25 UTC - Codex: physical tray-contact investigation

Goal: replace the Day 2 kinematic tray adapter with measured PhysX tray
contact so the robot itself carries the tray.

The imported tray was inspected in-simulator: a single flat collision mesh,
approximately `0.337 x 0.436 x 0.013 m`, with no grasp affordance. Diagnostics
tested live pose targeting, a fixed-joint rim, an embedded collision child,
cube and cylinder handles, explicit friction, and an explicit `0.35 kg` mass.
The original tray bottom was `z=0.7466 m`; it intersected the countertop, so
the physical repair path adds `0.02 m` clearance and measured `z=0.7666 m`.

Result: every physical tray attempt failed the actual object-space gate with
`0.0 m` tray lift. The best single-arm closure was approximately `0.57 rad`,
but the tray stayed at its starting height. A two-arm test also failed IK and
contact sequencing at the current targets. These results are evidence of a
missing/unsuitable grasp affordance and unstable dual-arm targeting, not proof
of autonomous tray carrying. The Day 2 kinematic adapter proof remains valid
only for FSM ordering and grading-path validation.

Next: model a proper two-contact tray handle/edge in the scene asset, validate
both arms against measured handle poses, then add the physical carry state
machine and rerun a multi-trial proof. Do not tag physical Stage 1 until the
tray clears `0.08 m` and holds continuously under PhysX.
