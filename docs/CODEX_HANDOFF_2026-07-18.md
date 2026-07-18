# Codex Task 3 compact handoff — 2026-07-18

## User priority

1. Finish the grasp/lift reliability phase (fresh 10 runs, at least 8 pass).
2. Package proof and durable logs.
3. Start Stage 1 FSM end-to-end.
4. Validate one teleoperation recording before collecting a learned-grasp
   dataset. Do not let the data track delay Stage 1.

## Repository state

- Work only in `D:\Mini Thesis\EBIM HAckthon\EBiM-benchmark-codex`.
- Branch: `agent/codex-task3-grasp` (base `f6c6582`).
- The original `EBiM-benchmark` worktree is on `agent/opencode-data` and has
  separate dirty work. It was deliberately left untouched.
- Read `AGENTS.md`, then this file and `docs/AGENT_STATE.md`.
- Current focused gate: 451/451 tests pass; changed files Ruff/compile clean.

## GCP state

- Project `ebim26ham-236`; VM `sim-dev-g4b`; zone `us-central1-b`.
- Container `isaac-lab-2-3-2-workshop`.
- VM IP `34.61.210.0`; owner-confirmed WebRTC works. Correct client input is
  exactly `34.61.210.0` (no port, protocol, or spaces).
- Firewall is safely restricted to `92.209.223.203/32`.
- Container mount `/workspace/EBiM_Challenge` maps to host
  `/home/sushr/EBiM-benchmark`.
- User authorized maximum GCP use; still obey the one-GPU quota rule.

## Completed evidence

- Required world-frame reach path uses one-step `TeleopCommand` plus
  `CartesianTargetTracker`, with absolute-world target reissue every tick.
- Real gripper joints are `left_gripper_joint`/`right_gripper_joint`, with
  0 rad closed and 0.9 rad open. Passive FR3 linkage joints are not actuated.
- Spine drive restored to authored 50k/5k/500k strength.
- Public Run 18 passed and was recorded: cup final lift 0.1087 m, 3.0 s hold,
  peak +0.195 m. Local proof files:
  `outputs/task3_verify_grasp_skip18_margin_public/result.json` and
  `grasp_lift.gif` (11 MB).
- Final frozen controller: 1 s soft close, 3 s vertical lift ramp, stationary
  base heading hold, 0.12 m spine-assisted lift, and unchanged physical gate
  of >=0.08 m cup lift for 3 continuous seconds.
- Tuning confirmation trial 06 passed: +0.0880 m for 3.0 s, pinch 0.4086 rad.
- `--fast-exit` safely avoids Kit shutdown hangs after result persistence.
- `scripts/task3/run_grasp_reliability_batch.py` launches fresh trials
  sequentially and creates `batch_summary.json`.

## Live official batch — do not restart

At this handoff, official trials 01–03 passed; trial 04/10 is active. The
batch runs independently in the container and survives a new chat.

Monitor:

```powershell
gcloud compute ssh sim-dev-g4b --zone=us-central1-b --project=ebim26ham-236 --command="sudo docker exec isaac-lab-2-3-2-workshop cat /tmp/task3_grasp_reliability_official_20260718.log"
```

Exact process check:

```powershell
gcloud compute ssh sim-dev-g4b --zone=us-central1-b --project=ebim26ham-236 --command="sudo docker exec isaac-lab-2-3-2-workshop ps -eo pid,ppid,state,lstart,args"
```

Final summary (exists after trial 10):

```text
/workspace/EBiM_Challenge/outputs/task3_grasp_reliability_official_20260718/batch_summary.json
```

Batch log:

```text
/tmp/task3_grasp_reliability_official_20260718.log
```

Do not launch another Isaac process while the batch parent is alive. Do not
use broad `pkill`; if recovery is required, inspect and kill only exact PIDs.

## Next actions after batch

1. Confirm `batch_summary.json` says `gate_passed: true` and `pass_count >= 8`.
2. Download the batch summary and per-trial `result.json` files into the Codex
   worktree; preserve Run 18 GIF as visual proof.
3. Create the grasp/lift proof bundle and reproduction commands.
4. Update `docs/AGENT_STATE.md`, `docs/PROJECT_JOURNAL.md`, and
   `docs/gpu_budget_log.md` with the final 10-run result and actual VM time.
5. Run the full focused CPU gate, Ruff, compile, and `git diff --check`.
6. Commit and push `agent/codex-task3-grasp`; do not merge unrelated work.
7. Start Stage 1 FSM end-to-end using the proven navigate + reach/grasp/lift
   skills. Day 1 is not complete until the reliability proof is packaged.

## Teleoperation/SmolVLA warning

Do not collect 50–100 episodes with the current recorder yet. Inspection of
`agent/opencode-data` found:

- `LeRobotRecorder.save()` always writes `<out-dir>/lerobot_dataset`, ignoring
  `--episode-name`, so later episodes can overwrite earlier data.
- The serializer produces a custom HDF5/JSONL layout, not a proven native
  SmolVLA-loadable LeRobot v2 dataset.
- GCP download must use the host path
  `/home/sushr/EBiM-benchmark/teleop_demos`, not container-only
  `/workspace/EBiM_Challenge/teleop_demos`.

First fix unique episode directories, validate one saved episode, and load it
with the actual training dataloader before large-scale collection.
