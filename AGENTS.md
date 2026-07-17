# Agent Protocol — EBiM Task 3 Sprint

Three agents rotate on this repo (each has ~5-hour usage windows):
**Claude** (branch `main`, worktree `EBiM-benchmark`), **Codex**
(`agent/codex-packaging`, worktree `EBiM-benchmark-codex`), **OpenCode**
(`agent/opencode-data`, worktree `EBiM-benchmark-opencode`). Git is the
shared memory; the fork `github.com/Sushruths04/ebim_hackthon` is the sync
bus.

## Session-start ritual (ALWAYS)
1. `git pull` (in your own worktree; also fetch `main`).
2. Read `docs/task3_sprint_plan_2026-07-17.md` (the plan) and
   `docs/AGENT_STATE.md` (live progress). The master architecture doc is
   `docs/task3_master_plan.md`.
3. Claim your task by editing the IN PROGRESS section of
   `docs/AGENT_STATE.md` (name + branch + timestamp), commit, push.

## Session-end ritual (ALWAYS — assume you may not get another turn)
1. Update `docs/AGENT_STATE.md`: move finished items to DONE with proof
   links; list NEXT UP; note BLOCKERS.
2. Update GPU STATUS in `docs/AGENT_STATE.md` — which VMs are
   RUNNING/STOPPED. If you started a VM and are pausing, STOP it
   (`gcloud compute instances stop <name> --zone=<zone>`).
3. Append one entry to `docs/PROJECT_JOURNAL.md` (goal, what, why,
   evidence, lesson) — supervisor-facing, plain language.
4. Log GPU hours/spend in `docs/gpu_budget_log.md`.
5. Commit + push. Unpushed work does not exist.

## Hard rules
- **One GPU VM at a time** (`GPUS_ALL_REGIONS=1`). The sim/FSM track owns
  it. Codex/OpenCode tracks are CPU-only by design — never start a GPU VM
  from those tracks.
- **Never delete `sim-dev` or `sim-dev-g4`** — stop, don't delete.
  Snapshots exist; deletion needs the owner's explicit request.
- Only Claude merges to `main`. Codex/OpenCode commit to their own branch
  and note "ready to merge" in AGENT_STATE.md.
- **Definition of Done** (master plan §7.2): video + result.json +
  repro.txt in `proofs/<slug>/` + a line in `docs/eval_results.md`, ticked
  in the same commit, then frozen. No proof bundle = not done. Send the
  video to the owner.
- Smallest GPU/config that works; escalate only on measured, logged
  evidence. Modal: `modal app list` must be empty when you stop.
- The GCP lab account (`ebim26ham-236`) dies ≈ Jul 19–20. Push everything
  at every exit criterion; export videos to GitHub/local before expiry.
