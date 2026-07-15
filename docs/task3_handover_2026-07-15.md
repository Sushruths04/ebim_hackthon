# Task 3 Handover - 2026-07-15

## Current Goal

Build, train, evaluate, and export a policy for EBiM Task 3 (Assisted Living
and Feeding) using Isaac Lab on Lightning AI.

## Persistent Workspace

Use this directory on Lightning AI for all project work:

```bash
/teamspace/studios/this_studio/EBiM-benchmark
```

Do not work from `/home/zeus/EBiM-benchmark`; Lightning AI warns that files
there are not persisted to Drive.

## Environment That Was Set Up

- Lightning AI GPU: NVIDIA L40S.
- Docker profiles available: `isaac-sim-5.1.0`, `isaac-sim-6.0.0`, and
  `isaac-lab-2.3.2`.
- Running container names used by this project:
  - `isaac-sim-5-1-0-workshop`
  - `isaac-lab-2-3-2-workshop`
- Isaac Lab and RSL-RL import successfully. Verified with:

```bash
python -c "from rsl_rl.runners import OnPolicyRunner; print('RSL-RL ready')"
```

## Task 3 Assets and Scene

- Room USD: `assets/robot_room.usd`
- Task 3 scene launcher: `scripts/scenes/scene_robot_room_keyboard.py`
- Robot asset: mobile Franka FR3 Duo with hands.
- Passive Isaac Sim scene robot root: `/World/Robot`
- Isaac Lab keyboard-control scene robot root:
  `/World/envs/env_0/Robot`
- Task 3 start pose: `(-4.6, 2.7, 0.0)`, yaw `-90` degrees.
- Task 3 includes 300 coffee beans and a head placement. The current session
  used head placement `A`.

The unresolved USD `visuals` warnings and NGX/ROS warnings seen during startup
did not prevent the room, robot, or keyboard controller from starting. They
should be cleaned up later, but they are not the current training blocker.

## GUI and Teleoperation

The first streamed GUI was a passive Isaac Sim viewer. It cannot control the
robot. The interactive session was launched directly from the Isaac Lab
container on the Lightning remote desktop using:

```bash
DISPLAY=:1 /workspace/isaaclab/isaaclab.sh -p \
  scripts/scenes/scene_robot_room_keyboard.py \
  --task task3 --head-placement A --keyboard-control
```

The launch log confirmed:

```text
Keyboard teleop backend ready.
Keyboard robot control enabled (direct dual-arm + Shift base map)
Keyboard teleop listener started.
```

Controls for the active interactive GUI:

| Control | Action |
| --- | --- |
| `Shift` + `H` / `N` | Move base forward / backward |
| `Shift` + `B` / `M` | Move base left / right |
| `Shift` + `G` / `J` | Rotate base counter-clockwise / clockwise |
| `W/S`, `A/D`, `Q/E` | Left end-effector translation |
| `O/L`, `K/;`, `I/P` | Right end-effector translation |
| `F` / `'` | Left / right gripper |
| `R` | Reset arm targets |
| `Esc` | Stop the teleoperation session |

The interactive launch output is saved at:

```text
outputs/task3_keyboard_gui.log
```

## Verification Completed

1. Task 3 grading unit tests completed successfully:

```text
7 task3 all grading tests passed.
```

2. Task 3 Stage 1 live Isaac Sim integration test completed successfully:

```text
score: 5/5
objects passed: simple_tray, bowl2, spoon2, plate2, cup
beans in dining: 300/300
```

3. RSL-RL is available in the Isaac Lab container:

```text
RSL-RL ready
```

4. A small, testable Stage 1 RL foundation was added under `task3_rl/`:

- `task3_rl/stage1.py`: privileged-state observation, progress reward,
  success/failure termination.
- `task3_rl/test_stage1.py`: focused unit tests for that contract.
- `task3_rl/live_stage1_smoke.py`: reads the live Task 3 scene to validate
  training signals.

This is not yet an Isaac Lab RL environment and is not a trained model.

## What Is Not Yet Available

There is no released Task 3 pretrained model, official Task 3 RL environment,
or full benchmark baseline in this checkout. `STATUS.md` also records Task 3
as under active development. Therefore, a complete usable model must be built
and trained in this project.

## Remaining Work to Produce a Usable Model

### 1. Build the actual Isaac Lab environment

- Create `DirectRLEnv` or `ManagerBasedRLEnv` configuration for Stage 1.
- Implement vectorized scene cloning and reset for many environments.
- Spawn/reset the mobile base, tray, utensils, bowl, beans, and head.
- Connect robot joint/base commands to the action space.
- Add collision/contact, tray grasp, drop, and termination signals.
- Use the existing `task3_rl.stage1` reward semantics as the initial contract.

### 2. Train Stage 1 first

- Start with state observations, not vision.
- Train mobile-base transport and stable tray handling with PPO/RSL-RL.
- Save checkpoints, TensorBoard metrics, configs, and evaluation rollouts.
- Validate success across randomized start poses, head placements, and object
  perturbations.

### 3. Add the remaining curriculum stages

- Stage 2: spoon feeding with the required smooth path and hold time.
- Stage 3: bean recovery into the target sphere.
- Stage 4: return utensils to the sink/table placement areas.
- Train each stage separately first, then test chained execution.

### 4. Make the policy robust

- Add domain randomization for object poses, friction, mass, lights, and
  camera/observation noise.
- Add safety constraints: collisions, drops, spoon/head distance, velocity,
  and joint limits.
- Add scripted or teleoperated demonstrations if PPO exploration is not
  sufficient for grasping and feeding.

### 5. Evaluate and export

- Run the project grading and live integration tests after every major change.
- Run held-out randomized evaluation episodes and record per-stage scores.
- Export the selected checkpoint, inference configuration, normalization
  statistics, dependency versions, and a deterministic evaluation command.

## Recommended Next Session Order

1. Restart Docker and the interactive GUI.
2. Confirm base and both arms move with keyboard teleoperation.
3. Run the Stage 1 live smoke test from `task3_rl/`.
4. Create the vectorized Stage 1 Isaac Lab environment.
5. Run a tiny 1-4 environment smoke training run.
6. Scale to the L40S, inspect rollouts, then train a Stage 1 checkpoint.

## Restart Commands

From the persistent project directory:

```bash
cd /teamspace/studios/this_studio/EBiM-benchmark/docker
export P=isaac-lab-2.3.2
docker compose --env-file .env.base --profile "$P" up -d
```

Open a shell in the Isaac Lab container:

```bash
docker exec -it isaac-lab-2-3-2-workshop bash
```

Start interactive Task 3 control on the Lightning desktop:

```bash
cd /workspace/EBiM_Challenge
DISPLAY=:1 /workspace/isaaclab/isaaclab.sh -p \
  scripts/scenes/scene_robot_room_keyboard.py \
  --task task3 --head-placement A --keyboard-control
```

Run the fast grading tests:

```bash
cd /workspace/EBiM_Challenge
python -B scripts/evaluation/task3/tests/test_grading.py
```

## Shutdown Performed

At the end of this session the active Isaac Sim/Isaac Lab GUI processes and
both Docker containers were stopped. Docker images, caches, project files,
test results, and this handover note remain intact for the next session.
