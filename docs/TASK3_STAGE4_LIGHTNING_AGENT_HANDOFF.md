# Task 3 Agent Handoff - Current Source Of Truth

Last updated: 2026-07-22 by OpenCode

## Correct Local Repo

Use:

```bash
cd "D:\Mini Thesis\EBIM HAckthon\ebim"
git checkout task3-current-clean
```

Correct branch:

```text
task3-current-clean
```

Latest pushed commit at handoff time:

```text
8a3fdefb fix(stage4): use proven arm lift with spine assist
```

Do not use `EBiM-benchmark-codex` as the main clean repo. It has messy branch/output history.

Do not push `agent/codex-task3-grasp`; it has huge output/proof pollution in other clones.

## GitHub Branch To Use

```bash
git clone --recurse-submodules https://github.com/Sushruths04/ebim_hackthon.git
cd ebim_hackthon
git checkout task3-current-clean
```

## Lightning Paths

Lightning UI shows:

```text
/teamspace/studios/this_studio
```

Actual clean repo is:

```text
/home/zeus/ebim_hackthon_current
```

Visible links created:

```text
/teamspace/studios/this_studio/ebim_hackthon_current -> /home/zeus/ebim_hackthon_current
/teamspace/studios/this_studio/LATEST_TASK3_STAGE4_R_POC2_FAILED_HOLD -> /home/zeus/ebim_hackthon/proofs/task3_stage4_r_poc2_failed_hold
```

Dirty old Claude clone:

```text
/home/zeus/ebim_hackthon
```

Do not overwrite/delete the dirty old clone unless the user explicitly approves.

## Container Rules

Active container used:

```text
isaac-current
```

Start pattern that works:

```bash
docker run -d --name isaac-current --entrypoint /bin/bash --gpus all --network host \
  -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
  -v /home/zeus/ebim_hackthon_current:/workspace/EBiM_Challenge \
  -w /workspace/EBiM_Challenge \
  nvcr.io/nvidia/isaac-lab:2.3.2 -lc 'sleep infinity'
```

Important: use `--entrypoint /bin/bash`. Without it, the Isaac image entrypoint starts extra `runheadless.sh sleep infinity`, wasting GPU/CPU.

Use repo-local logs under `outputs/.../run.log`, not `/tmp`, so the user can see files in Lightning UI.

## Latest Run Result: r-poc3_liftfix

Output:

```text
/home/zeus/ebim_hackthon_current/outputs/task3_stage4_grasp_r_poc3_liftfix
```

Log:

```text
/home/zeus/ebim_hackthon_current/outputs/task3_stage4_grasp_r_poc3_liftfix/run.log
```

Result:

```text
/home/zeus/ebim_hackthon_current/outputs/task3_stage4_grasp_r_poc3_liftfix/result.json
```

Status: finished, failed.

Key result:

```json
{
  "passed": false,
  "failed_phase": "hold",
  "object_lift_m": 0.0408,
  "hold_seconds": 1.0,
  "min_lift_m": 0.02
}
```

Important phase data:

```text
descend: ok true
close: ok true
lift: cup_rise 0.063, but arm_lift_ok=false
hold: failed, object_to_ee_m=0.1961, max_held_s=0.0
```

Interpretation: the cup is being moved/lifted, but not staying within the hold distance gate.

## What Was Changed

Branch `task3-current-clean` includes lever #1:

```python
MANIP_BASE_HOLD_POSITION_KP = 4.0
MANIP_BASE_HOLD_MAX_LINEAR_MPS = 0.25
```

This fixed earlier descend/close issues enough to progress.

Branch `task3-current-clean` also includes lever #2:

```python
arms.lift(
    active_side,
    max(0.0, lift_z - lift_pose[0][2]),
    step=sim_tick,
    dt=sim.cfg.dt,
    timeout_s=6.0,
    position_tolerance_m=0.03,
    spine_assist_m=0.12,
)
```

This increased cup lift but still failed hold because object drifted away from the end effector.

## Proof Preserved

Failed r-poc2 proof preserved:

```text
/home/zeus/ebim_hackthon/proofs/task3_stage4_r_poc2_failed_hold
```

Contains:

```text
result.json
stage4.gif
repro.txt
```

Need to preserve r-poc3 similarly next.

Suggested command:

```bash
cd /home/zeus/ebim_hackthon_current
mkdir -p proofs/task3_stage4_r_poc3_liftfix_failed_hold
cp outputs/task3_stage4_grasp_r_poc3_liftfix/result.json proofs/task3_stage4_r_poc3_liftfix_failed_hold/result.json
cp outputs/task3_stage4_grasp_r_poc3_liftfix/stage4.gif proofs/task3_stage4_r_poc3_liftfix_failed_hold/stage4.gif 2>/dev/null || true
cp outputs/task3_stage4_grasp_r_poc3_liftfix/run.log proofs/task3_stage4_r_poc3_liftfix_failed_hold/run.log
printf '%s\n' '/isaac-sim/python.sh scripts/task3/run_stage4_cleanup.py --skip-navigation --approach-stance east --object-name=cup --pickup-only --record-video --fast-exit --out-dir outputs/task3_stage4_grasp_r_poc3_liftfix' > proofs/task3_stage4_r_poc3_liftfix_failed_hold/repro.txt
```

## Next Best Diagnosis

Do not go back to navigation or base setup first. Current failure is after close/lift.

Likely issue: hold gate and gripper/object relation.

r-poc3 lifted object by `0.0408m`, but object-to-EE distance became `0.1961m`, above hold gate `0.15m`.

Next agent should inspect:

- `object_follows_end_effector(...)`
- `max_distance_m=0.15` in Stage4 hold
- verifier default for max hold distance in `verify_grasp_lift.py`
- whether Stage4 uses different active EE/hold pose after `arms.lift`
- whether `lift_z = CUP_LIFT_Z = 1.10` is too aggressive compared to actual verifier target and pulls the cup sideways
- whether the lift command should require `lift_command_ok`; currently `lift_ok = lift_command_ok and cup_rise >= MIN_LIFT_M`

Suggested next experiment:

1. Preserve r-poc3 proof.
2. Compare `verify_grasp_lift.py` successful run args/defaults for `--max-held-object-distance-m`.
3. If verifier allows larger hold distance, align Stage4 with verifier.
4. If verifier also uses `0.15`, inspect GIF: cup is likely slipping sideways during arm lift, so reduce commanded lift height or use smaller arm lift delta.

## Commands To Check Current Lightning

```bash
ssh s_01ky4p7c2j9mgbn029kw8m7y31@ssh.lightning.ai "docker ps; ls -la /teamspace/studios/this_studio; ls -lh /home/zeus/ebim_hackthon_current/outputs/task3_stage4_grasp_r_poc3_liftfix"
```

```bash
ssh s_01ky4p7c2j9mgbn029kw8m7y31@ssh.lightning.ai "cat /home/zeus/ebim_hackthon_current/outputs/task3_stage4_grasp_r_poc3_liftfix/result.json"
```

## Rules For Next Agent

- Use only `task3-current-clean`.
- Commit and push every code/doc change.
- Do not push output folders to GitHub unless a tiny proof bundle is explicitly required.
- Preserve proof bundles under `proofs/<slug>/`.
- Keep Lightning visible paths linked under `/teamspace/studios/this_studio`.
- Do not use GCP. User said budget exhausted; Lightning only.
- Do not delete dirty old clone or user files.
- Run from clean clone `/home/zeus/ebim_hackthon_current`.
- Use repo-local logs under `outputs/.../run.log`, not `/tmp`.
