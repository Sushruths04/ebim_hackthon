# AGENT STATE — live handoff file

> Every agent session reads this first and updates it last. Keep entries
> short; link proofs. Protocol: `AGENTS.md`. Plan:
> `docs/task3_sprint_plan_2026-07-17.md`.

Last update: 2026-07-17 (Claude, main)

## GPU STATUS
- `sim-dev` (L4, us-central1-c): **STOPPED** — proven Isaac box, fallback. Never delete.
- `sim-dev-g4` (RTX PRO 6000, SPOT, us-east5-a): **RUNNING** — created
  2026-07-17 from snapshot `sim-dev-verified-20260717-1310`.
  `nvidia-driver-580-open` installed (Blackwell needs open kernel modules;
  proprietary 580 rejected GPU `10de:2bb5`); rebooting; nvidia-smi /
  vulkaninfo / Isaac render verification IN PROGRESS.
- Quota: `GPUS_ALL_REGIONS=1` — one GPU VM at a time, total.

## DONE (frozen — do not rework)
- Grading + integration tests for all 4 stages (upstream state, see master plan §3).
- `task3_autonomy/navigation.py` pure math, 14/14 tests —
  `proofs/phase2-navigation-math/`.
- sim-dev L4 Isaac bring-up + verified render + snapshot (2026-07-17).
- RTX PRO 6000 feasibility: RESOLVED — spot quota=1 works; sim-dev-g4 created (2026-07-17).

## IN PROGRESS
- (Claude, main) sim-dev-g4 driver bring-up → Isaac render smoke test →
  snapshot g4 disk.

## NEXT UP (in order — claim in this file before starting)
1. [GPU/Claude] Phase 1: first real run of `scripts/task3/run_episode.py`
   (`--policy idle --record-video`), fix RigidPrim init if needed,
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
