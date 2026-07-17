# AGENT STATE — live handoff file

> Every agent session reads this first and updates it last. Keep entries
> short; link proofs. Protocol: `AGENTS.md`. Plan:
> `docs/task3_sprint_plan_2026-07-17.md`.

Last update: 2026-07-17 (Claude, main; ~16:00 UTC)

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

## IN PROGRESS — Phase 1 determinism verification (Claude, main; 2026-07-17 ~16:00 UTC)

Determinism pair (two seed-42 idle runs, outputs/task3_det_runA and _runB, logs /tmp/task3_runA.log,/tmp/task3_runB.log in the container) launched at commit ef7af06; runA completed capture (160 frames + gif); runB verdict pending — spawn_positions of both result.json must match to close Phase 1 and tag v0.1-harness with a proof bundle.

## NEXT UP (in order — claim in this file before starting)
1. [GPU/Claude] Phase 1: first real run of `scripts/task3/run_episode.py`
   (`--policy idle --record-video`), repair/disable the legacy steering
   OmniGraph then verify the harness,
   deterministic-reset check, measure episode wall-time → proof bundle →
   tag `v0.1-harness`.
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
