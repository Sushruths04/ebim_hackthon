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
