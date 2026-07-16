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
