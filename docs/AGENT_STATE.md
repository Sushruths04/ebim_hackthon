# AGENT STATE — live handoff file

> Every agent session reads this first and updates it last. Keep entries
> short; link proofs. Protocol: `AGENTS.md`. Plan:
> `docs/task3_sprint_plan_2026-07-17.md`.

Last update: 2026-07-17 (Claude, main; ~18:20 UTC)

## GPU STATUS (final verdict 2026-07-17 ~13:10 UTC)
- **`sim-dev-g4b` (g4-standard-48 = FULL RTX PRO 6000 Blackwell 96 GB,
  SPOT, us-central1-b): RUNNING — THE PRIMARY BOX.** Isaac render VERIFIED
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
  WebRTC livestream ready — firewall rule ebim-webrtc-owner (owner IP 134.61.98.3/32 only) targets tag webrtc-stream on sim-dev-g4b (35.202.157.74); container is host-networked; run_episode.py has --livestream (commit ccd6c66); Isaac Sim 5.1.0 → view with NVIDIA "Isaac Sim WebRTC Streaming Client".
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
- Grading + integration tests for all 4 stages (upstream state, see master plan §3).
- `task3_autonomy/navigation.py` pure math, 14/14 tests —
  `proofs/phase2-navigation-math/`.
- sim-dev L4 Isaac bring-up + verified render + snapshot (2026-07-17).
- RTX PRO 6000 bring-up: **COMPLETE (2026-07-17)** — full-GPU spot
  `sim-dev-g4b` verified rendering the Task 3 room in 9.4 s; snapshot
  taken; proof image sent to owner. Fractional/vGPU shapes proven
  unusable for Isaac (see GPU STATUS).
- Phase 1 blocker RESOLVED (2026-07-17): robot USD's ROS2/keyboard controller OmniGraphs now deactivated BEFORE composition via generated wrapper layer (make_headless_robot_usd, commit a328224; CPU tests 198/198). Video capture rebuilt pull-based via rgb annotator after Replicator BasicWriter runaways of 139k/93 GB and 12k frames — even set_capture_on_play(False) cannot stop an attached writer while the timeline plays (commits 9caecb1, ef7af06). First clean idle episode: exactly 160 frames + episode.gif on sim-dev-g4b.

## IN PROGRESS — Phase 2 NavigateTo live verification (Claude, main; 2026-07-17 ~18:20 UTC)

Base-drive chain is PROVEN GOOD: with runtime wheel damping 500 (TmrBaseAdapter
writes it to PhysX directly; actuator-cfg path does NOT deliver), wheels track
10 rad/s targets and the base does a true 0.5 m/s (NAVDBG, /tmp/task3_verify_nav7.log,
camera-free). enable_cameras is NOT a culprit (camera-free run behaved identically).

The remaining Phase 2 blocker is GEOMETRY: the "crawl"/stall is the robot
contact-stalling against the dining/kitchen partition (wall y in [0.10,0.34]).
route_via_door (commit ebe88ba, CPU 207/207) crosses at doorway center x=-4.14,
and live run nav8 confirmed the door turn executes — but the robot STILL stalls
in the gap: both wall crossings measure ~1.2 m wide (second gap x in (3.79,4.99);
east detour walled by Rectangle009) while the robot spans 1.88 m across its
outboard-mounted FR3 arms (base_link is only 0.8x0.58 m — the base fits, the
arms don't). Fix in flight: probe_arm_tuck.py (commit f7d1a6e) measures settled
body-frame extents for candidate tuck poses in one session; wire the winner into
NavigateTo as a transit pose, rerun verify.

Phase 1 is CLOSED: proof bundle `proofs/phase1-harness/` (c1681b2) with
SPAWN_MATCH True, tag `v0.1-harness` pushed. Re-confirmed 2026-07-17 ~18:30:
runA/runB result.json agree on every physics field (spawn/final positions,
stages, total_steps); only timestamps/paths differ.

## NEXT UP (in order — claim in this file before starting)
1. [GPU/Claude] Arm transit pose: run `probe_arm_tuck.py`, pick the pose
   with body-y half-extent ≤ ~0.45 m, ramp arms to it in verify_navigate
   before driving, rerun the door-routed verify → Phase 2 navigate proof.
2. [GPU/Claude] Fix nonfatal PhysX error spam: disable_robot_external_wrenches() calls addTorque/setLinearVelocity which are illegal with eENABLE_DIRECT_GPU_API — guard or replace with Isaac Lab tensor API.
3. [GPU/Claude] Phase 2 skills: live `navigate_to()` → `verify_navigate.py`;
   quat→rpy inverse (unit-test round-trip) → `reach()` → `grasp()`/`lift()`
   → **`verify_grasp_lift.py` ≥8/10 gate**.
4. [CPU/Codex] Dockerfile skeleton + README submission section drafts;
   `docs/simdev_setup.md`; PROJECT_JOURNAL scaffold.
5. [CPU/OpenCode] `scripts/task3/make_proof_bundle.py` helper; 15-run batch
   script; `--record-lerobot` design (code + unit tests only).
6. [GPU/Claude] Phase 3: Stage 1 FSM → `v0.1-stage1`; then Stage 4 → 2 → 3.

## BLOCKERS
- Lab account expiry ≈ Jul 19–20: export ritual (plan §5 Day 3) is mandatory.
- Personal-project L4 quota (fallback after expiry) still pending — check
  daily: `gcloud compute regions describe us-central1
  --account=mitvho09@gmail.com --project=gen-lang-client-0186028838`.
