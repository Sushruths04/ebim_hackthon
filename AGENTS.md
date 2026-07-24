# Agent Protocol — EBiM Task 3 Sprint

> ## ⭐ AUTHORITATIVE, PERMANENT — READ THIS FIRST (2026-07-24 onward)
> **The single source of truth for continuing Task 3 is `plans/handoff.md`.**
> EVERY session, EVERY agent (Claude, Codex, OpenCode) MUST:
> 1. **START:** read `plans/handoff.md` in full, then
>    `docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`. `git pull` on
>    `task3-current-clean`. Begin the first unchecked step in `plans/handoff.md` §5.
> 2. **WORK:** one hypothesis → one change → one run. **Never claim a run result
>    you did not just observe — paste the real evidence.** `"ok":true` ≠ a real hold.
> 3. **END (you may be cut off mid-task by a usage limit at any time):** update
>    `plans/handoff.md` (§2 current state, §4 new failures + why, §5 next steps),
>    then `git commit && git push origin task3-current-clean`. Unpushed = lost.
> 4. **STUCK (3 fails on one symptom / a decision this doesn't cover):** write it
>    into `plans/handoff.md` §6 NEEDS OPUS, commit+push, stop. Don't guess.
>
> This process is mandatory and permanent — maintain `plans/handoff.md` as the
> living record so any fresh session continues without redoing or deviating.
> **Note:** GCP is BANNED (no budget) — Lightning AI is the only GPU venue;
> ignore any `gcloud` instructions in the older ritual text below.

The following (older) ritual text predates the pivot and is kept for reference;
`plans/handoff.md` supersedes it wherever they conflict.

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
