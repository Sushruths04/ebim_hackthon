# GPU / Compute Budget Log

Tracks actual spend against the ≈1,170 EUR budget (§4 of
`docs/task3_master_plan.md`). One row per session. Log immediately after
each session, not retroactively.

| Date | Platform | Machine / GPU | Hours | EUR (est.) | Outcome | Evidence forcing any escalation |
|---|---|---|---|---|---|---|
| 2026-07-16 | Local (Windows) | none — CPU only, git/admin | 0 | 0 | Force-synced fork (`origin/main`) to local `main`'s current state as a clean single-commit snapshot (old fork history had unrecoverable Git LFS objects from a dead upstream `amp_for_hardware` path — full-history push was impossible; backup of prior fork state saved at `backup/pre-sync-2026-07-16`). Verified Modal workspace `mitvho09` has zero running apps (clean). Verified GCP project `gen-lang-client-0186028838`: billing enabled, but `NVIDIA_L4_GPUS` and `NVIDIA_A100_GPUS` quota = 0 in `us-central1` — quota request from Phase 0 has NOT been submitted yet. Lightning SSH (`lightning-p4`) currently returns `Permission denied (publickey)` — studio appears stopped. | n/a |

## Running totals

- GCP: 0 EUR spent (no instances created — quota not yet approved).
- Modal: 0 EUR spent (0 running apps, verified 2026-07-16).
- Lightning: 0 EUR this session (no GPU time used; SSH access currently down).

## Session log (continued)

- 2026-07-16 (same day, continued): authored `scripts/task3/run_episode.py`
  (headless episode runner: seed, head placement, policy=idle, off-screen
  video via the proven `record_robot_demo.py` GIF-encoding pattern, grading
  hookup to `scripts/evaluation/task3/grading.py`'s pure scoring functions
  via `isaacsim.core.prims.RigidPrim` for Fabric-safe live pose reads).
  0 GPU hours — still blocked on Lightning/GCP access, so this is
  **unverified, untested code**. No proof bundle exists; Phase 1 checklist
  boxes remain unticked per the visual-proof Definition of Done (§7.2).

## Session log (continued 2)

- 2026-07-16 (same day, continued): user asked to try Modal serverless GPUs
  as a substitute for the (still-down) Lightning studio. Investigated and
  tested directly (all `modal run` batch jobs, auto-exit, confirmed
  `modal app list` shows 0 running afterward):
  - `nvcr.io/nvidia/isaac-lab:2.3.2` etc. (this repo's documented images)
    need NGC registry auth -- no NGC API key available locally or as a
    Modal secret. BUT: `isaacsim` (4.5.0.0) and `isaaclab` (2.1.0) are
    plain public pip packages on `pypi.nvidia.com` (and even pypi.org),
    no NGC auth needed at all -- confirmed by a cheap CPU-only probe.
  - Built a Modal image (Ubuntu 22.04 + CUDA 12.4 base, apt Kit runtime
    deps, pip-installed isaacsim[all,extscache]==4.5.0.0) and ran a
    minimal headless-boot + off-screen-render smoke test on `gpu="L4"`.
  - **Result: FAILED, twice, reproducibly.** `nvidia-smi` inside the
    container correctly shows a real NVIDIA L4 (23GB, driver 580.95.05)
    -- CUDA compute access works. But `vulkaninfo` only enumerates a
    software renderer (`llvmpipe`/Mesa), never the NVIDIA Vulkan ICD, and
    Isaac Sim's Kit renderer fails with
    `[gpu.foundation.plugin] No device could be created` / "Driver
    Version: 0, Graphics API: Vulkan", then hard-crashes with
    `Fatal Python error: Segmentation fault`. Tried the standard fix
    (`NVIDIA_DRIVER_CAPABILITIES=all`, `NVIDIA_VISIBLE_DEVICES=all`) --
    no change, identical failure both times.
  - **Conclusion: Modal's GPU container runtime exposes CUDA compute but
    not the NVIDIA Vulkan/OpenGL graphics stack Isaac Sim's RTX renderer
    needs.** This is a platform-level limitation, not a missing package --
    confirms (with actual evidence, not assumption) the master plan's
    original allocation table judgment: Modal is fine for Phase 7's
    pure-PyTorch VLA fine-tuning, but cannot run Isaac Sim/Isaac Lab.
  - GPU time spent: 3 short `gpu="L4"` invocations, each failing within
    ~15-30s of Kit startup (well under a minute of L4 time total,
    negligible cost). Image-build steps (apt/pip installs) ran CPU-only.

## Session log (continued 3)

- 2026-07-16 17:33 UTC: submitted the GCP GPU quota request via
  `gcloud alpha quotas preferences create` (project
  `gen-lang-client-0186028838`): `NVIDIA-L4-GPUS-per-project-region`=2 and
  `NVIDIA-A100-GPUS-per-project-region`=1 in `us-central1`, plus
  `GPUS-ALL-REGIONS-per-project`=3. All three currently show
  `grantedValue: 0` (pending review, normal for this API) -- check status
  with `gcloud alpha quotas preferences list
  --service=compute.googleapis.com --project=gen-lang-client-0186028838`.
  Standard 24-48h approval latency applies. Billing alerts (250/500/750
  EUR) were NOT set up automatically -- left as a manual step since it
  needs a currency/notification-channel judgment call.

## Session log (continued 4)

- 2026-07-16 (same day, continued): while all three GPU paths are stalled,
  did local CPU-only Phase 2 work that's actually verifiable now:
  `task3_autonomy/navigation.py` (waypoint routing, body-frame control
  law, stop-tolerance check for `navigate_to()`) with 14/14 passing unit
  tests, no Isaac Sim needed. First real proof bundle of this project:
  `proofs/phase2-navigation-math/`, logged in the new `docs/eval_results.md`.
  0 GPU hours.

## Session log (continued 5) — 2026-07-17: RTX PRO 6000 bring-up

- Compute moved to the **hackathon lab account** `devstar2361@gcplab.me`,
  project `ebim26ham-236` — **expires ≈ Jul 19–20**; `GPUS_ALL_REGIONS=1`
  (one GPU VM at a time). Prior session (Sonnet) built `sim-dev`
  (g2-standard-16, L4, us-central1-c) there: Isaac Lab 2.3.2 verified
  render, snapshot `sim-dev-verified-20260717-1310`.
- Owner requested RTX PRO 6000 (explicitly overriding smallest-first; wants
  ½ GPU or less VRAM). Evidence gathered:
  - Legacy region quotas show NO RTX PRO metric; Cloud Quotas API shows
    **spot RTX PRO 6000 = 1, VWS = 1, plain on-demand = 0**.
  - On-demand create: quota-blocked. us-central1-b & us-east1-d: stockout.
    **us-east5-a spot g4-standard-12: SUCCESS** → resized to
    **g4-standard-24 (½ GPU, 48 GB VRAM, 24 vCPU)** on owner instruction.
- **Driver findings (important, cost ~1.5 h of debugging):** fractional g4
  shapes are **vGPU partitions**:
  1. Proprietary 580.159 rejects the GPU (`10de:2bb5 not supported`).
  2. `nvidia-driver-580-open` rejects vGPU ("not supported by open nvidia.ko").
  3. GRID vGPU 20.1 guest (595.71.05) → **Xid 78 guest/host incompatible**
     (GCP host runs the 19.x branch).
  4. **GRID vGPU 19.5 guest (`NVIDIA-Linux-x86_64-580.159.03-grid.run`
     from `gs://nvidia-drivers-us-public/GRID/vGPU19.5/`) WORKS**:
     nvidia-smi shows RTX Pro 6000 Blackwell 48 GB; vulkaninfo enumerates
     `RTX Pro 6000 Blackwell DC-2-48Q` as a discrete Vulkan 1.4 device
     (Q-profile = graphics-capable despite MIG-mode flag).
  - Caveat: apt purge of old drivers also removed `libvulkan1` —
    reinstalled (`libvulkan1 vulkan-tools`). Isaac render smoke test on the
    g4 in progress at time of writing.
- `sim-dev` (L4) left STOPPED as proven fallback. Spot g4 ≈ $1.5–2/hr est.;
  session GPU time so far ≈ 1.5 h ≈ 3 EUR.
- **OUTCOME (continued, ~13:10 UTC): fractional vGPU = DEAD END for Isaac;
  FULL GPU works.** On the ½-GPU vGPU shape, driver-level Vulkan+ray-tracing
  verified fine, but Kit's renderer refuses the device ("Skipping NVIDIA
  GPU due CUDA being in bad state") — CUDA↔Vulkan interop is unsupported
  on MIG-backed vGPU partitions; also `/dev/nvidia-uvm` had to be created
  manually (`.run` installs don't autoload it). Escalation evidence for
  going to the full GPU: not a size upgrade by preference — the fractional
  shapes are *functionally incapable* of running Isaac Sim.
  `g4-standard-48` (FULL RTX PRO 6000 96 GB) spot: us-east5-a stockout;
  **us-central1-b create SUCCEEDED** (`sim-dev-g4b`, from the L4 snapshot).
  Standard `nvidia-driver-580-open` via apt works on passthrough.
  **Task 3 room render VERIFIED: 9.4 s app wall-time warm (vs ~60 s+ on
  L4)** → `sim-dev-g4b` is now the primary box; snapshot
  `sim-dev-g4b-verified-20260717` taken. Gotcha for future runs:
  `capture_static_view.py` needs an ABSOLUTE `--output-dir`. Extra GPU time
  for this leg ≈ 0.5 h ≈ 1 EUR. `sim-dev-g4` (us-east5-a) left STOPPED —
  owner may delete its disk (~$10/mo equiv.) since the snapshot supersedes it.

## Session log (continued 6) — 2026-07-17 afternoon (Claude): OmniGraph fix + video capture rebuild + determinism pair

- sim-dev-g4b (spot g4-standard-48) afternoon session: OmniGraph pre-composition fix (commit a328224, make_headless_robot_usd wrapper layer deactivates controller graph BEFORE composition); Replicator video-capture runaway incident #2 (12k frames, ~1 GB on already-full disk) repaired with pull-based RGB annotator (commits 9caecb1, ef7af06). First clean idle episode completed: exactly 160 frames + episode.gif captured. Determinism pair launched at commit ef7af06 (two seed-42 runs, runA verdict pending, runB in flight). CPU tests 198/198 passing. WebRTC livestream configured (IP-locked to owner); livestream ready in --livestream mode.
- Estimated GPU hours: ~2 h (three aborted runs debugging video capture, then first clean episode + determinism pair launch).
- Estimated cost: 3–4 EUR (spot g4-standard-48 ≈ $1.5–2/h).
- Disk maintenance: deleted 93 GB Replicator runaway frames + ~16 GB older debug frame dirs (task3_episodes_aaf7905/de684a0/f02dea2); disk now 17% used.

## Outstanding blockers (as of 2026-07-16)

1. **GCP GPU quota not requested** — `NVIDIA_L4_GPUS` / `NVIDIA_A100_GPUS` = 0
   in `us-central1` for project `gen-lang-client-0186028838`. This is a
   manual step (§7.1 item 1) — submit ASAP, 24-48h approval latency blocks
   all GCP-based phases.
2. **Lightning studio (`lightning-p4`) unreachable** — SSH key rejected,
   consistent with the studio being stopped. Needs to be started from the
   Lightning AI web console before any GPU-side Phase 0-2 work can resume.
3. **Modal cannot run Isaac Sim** — confirmed by direct testing (see
   session log above), not usable as a Lightning/GCP substitute for any
   Isaac Sim/Isaac Lab work. Still fine for Phase 7 (pure PyTorch
   training), unchanged from the original plan.
