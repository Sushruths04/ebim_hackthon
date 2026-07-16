# Stage 1 Kinematic PPO Smoke Checkpoint

`model_final.pt` is a small, reproducible RSL-RL PPO checkpoint produced on an
NVIDIA L40S. It validates the Task 3 Stage 1 training pipeline end-to-end:

- 1,024 parallel GPU environments
- 30 PPO iterations
- 737,280 transitions
- 13-feature observation from `task3_rl.stage1.build_observation`
- 3 actions: forward, lateral, and yaw velocity

It is a **kinematic transport curriculum checkpoint**, not a deployable Task 3
robot policy. The tray is carried kinematically while the policy learns the
kitchen-to-dining transport objective. It does not grasp objects, drive the
physical FR3 Duo, avoid the full room geometry, feed the head, recover beans,
or complete cleanup.

Recreate it from the repository root inside the Isaac Lab container:

```bash
python -m task3_rl.train_kinematic_stage1 \
  --num-envs 1024 --iterations 30 \
  --log-dir outputs/task3_rl/kinematic_stage1_smoke
```

The next model must replace this curriculum with the physical, vectorized
Isaac Lab Stage 1 environment.
