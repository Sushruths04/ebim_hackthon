# Task 3 Lightning Workflow

This repository is designed to survive Lightning account changes. Source code,
configuration, and small checkpoints live in GitHub. Isaac container caches are
local to a Lightning account and must be rebuilt when that account changes.

## One command after NGC login

On a new GPU Lightning Studio:

```bash
git clone --recurse-submodules https://github.com/Sushruths04/ebim_hackthon.git
cd ebim_hackthon
docker login nvcr.io
bash scripts/task3/lightning_workflow.sh bootstrap
```

`bootstrap` updates Git LFS assets, checks the NVIDIA Docker runtime, creates
persistent cache directories, and starts the Isaac Lab container. The first run
on an account downloads the NVIDIA image; later starts on the same account use
the cache.

## Normal commands

```bash
# Verify all current Task 3 grading and PPO unit tests.
bash scripts/task3/lightning_workflow.sh verify

# Inspect the active GPU, container, two required Task 3 assets, and checkpoints.
bash scripts/task3/lightning_workflow.sh status

# Run the fast Stage 1 kinematic PPO curriculum on an L40S.
bash scripts/task3/lightning_workflow.sh train-kinematic-stage1

# Stop the container before ending the Studio session.
bash scripts/task3/lightning_workflow.sh stop
```

## Asset map

| Purpose | Repository path |
| --- | --- |
| Task 3 room | `assets/robot_room.usd` |
| Mobile dual-arm robot | `assets/mobile_fr3_duo_v0_2.usd` |
| Interactive Task 3 scene | `scripts/scenes/scene_robot_room_keyboard.py` |
| Task 3 grading | `scripts/evaluation/task3/` |
| PPO training workspace | `task3_rl/` |

## Persistence rules

Keep code and small model checkpoints in GitHub. Do not commit recordings,
rendered videos, TensorBoard logs, or large replay datasets to Git. Put those
in durable dataset storage before changing accounts. Each recorded episode must
include its seed, asset revision, control stream, robot state, task state, and
terminal result so it can be replayed on a new account.
