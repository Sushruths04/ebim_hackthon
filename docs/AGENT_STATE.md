# AGENT STATE — live handoff file

> Every agent session reads this first and updates it last. Keep entries
> short; link proofs. Protocol: `AGENTS.md`. Plan:
> `docs/task3_sprint_plan_2026-07-17.md`.

Last update: 2026-07-17 (Codex, main)

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

## IN PROGRESS — Phase 1 debug loop (Codex, main; 2026-07-17 ~14:10 UTC)

`scripts/task3/run_episode.py` has now been run repeatedly on the verified
RTX PRO 6000. The original `RigidPrim` CUDA crash has been narrowed and
partially repaired, but the idle episode is still blocked by the robot USD's
legacy steering-controller OmniGraph.

- Fixed and pushed: `8431332` corrects the gripper joint patterns;
  `aaf7905`, `3075b5f`, `de684a0`, and `f02dea2` improve `run_episode.py`
  initialization. Focused CPU regression suite: **106/106 passed** after
  each final change.
- Evidence: the old `RigidPrim` failure was `CUDA illegal memory access`
  after PhysX reported `Unresolved rigid dynamic index`. Commit `de684a0`
  normalizes nested enabled rigid bodies below the grading props; the latest
  run no longer logs that PhysX/CUDA error.
- **Current blocker / NEXT ACTION:** after `sim.reset()`, the robot's
  `/World/envs/env_0/Robot/Graph/Steer_joint_Controller/script_node` raises
  `OmniGraphError: Attempted to access an invalid object` while reading
  `Desired_Linear_Velocity_X`. Every failed run then leaves Kit alive for
  >1 min despite `--max-seconds 8`; stop its exact Kit PID before retrying.
  Repair or disable that legacy controller graph for the headless harness
  (the harness uses Isaac Lab actuator commands, not the USD keyboard graph),
  then rerun the command below.
- No `run_episode.py` process is currently active. Dedicated logs from the
  last attempts are `/tmp/task3_phase1_{aaf7905,3075b5f,de684a0,f02dea2}.log`
  inside the Isaac container.
- Rerun command (VM `sim-dev-g4b`, us-central1-b):
  `cd ~/EBiM-benchmark && git pull && sudo docker exec isaac-lab-2-3-2-workshop \
   bash -lc 'cd /workspace/EBiM_Challenge && python scripts/task3/run_episode.py \
   --seed 42 --head-placement a --policy idle --record-video \
   --out-dir /workspace/EBiM_Challenge/outputs/task3_episodes'`
  On crash, read `outputs/task3_episodes/seed42_a/crash_traceback.txt`.
- Phase 1 exit criterion (then tag `v0.1-harness` + proof bundle §7.2):
  idle episode → video frames + EPISODE_RESULT JSON, and same seed twice
  → identical spawn poses.

## NEXT UP (in order — claim in this file before starting)
1. [GPU/Claude] Phase 1: first real run of `scripts/task3/run_episode.py`
   (`--policy idle --record-video`), repair/disable the legacy steering
   OmniGraph then verify the harness,
   deterministic-reset check, measure episode wall-time → proof bundle →
   tag `v0.1-harness`.
2. [GPU/Claude] Phase 2 skills: live `navigate_to()` → `verify_navigate.py`;
   quat→rpy inverse (unit-test round-trip) → `reach()` → `grasp()`/`lift()`
   → **`verify_grasp_lift.py` ≥8/10 gate**.
3. [CPU/Codex] Dockerfile skeleton + README submission section drafts;
   `docs/simdev_setup.md`; PROJECT_JOURNAL scaffold.
4. [CPU/OpenCode] `scripts/task3/make_proof_bundle.py` helper; 15-run batch
   script; `--record-lerobot` design (code + unit tests only).
5. [GPU/Claude] Phase 3: Stage 1 FSM → `v0.1-stage1`; then Stage 4 → 2 → 3.

## BLOCKERS
- Lab account expiry ≈ Jul 19–20: export ritual (plan §5 Day 3) is mandatory.
- Personal-project L4 quota (fallback after expiry) still pending — check
  daily: `gcloud compute regions describe us-central1
  --account=mitvho09@gmail.com --project=gen-lang-client-0186028838`.
