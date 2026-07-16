# Stage 1 Kinematic L40S PPO Checkpoint

`model_final.pt` is the longer L40S curriculum run for the Stage 1 kinematic
transport environment.

## Run Record

- GPU: NVIDIA L40S
- Environments: 2,048
- PPO iterations: 500
- Transitions: 24,576,000
- Wall-clock training time: 81 seconds
- Final throughput: about 309,000 steps/second
- Final mean episode length: 33.95 steps, compared with a 120-step limit
- Final reported failure rate: 0.0

The training metric `/metrics/success_rate` is a per-step terminal-event rate,
not an episode success fraction. Its final value of `0.0293` is consistent with
roughly one success event per 34-step episode. Use a dedicated evaluator before
comparing it to the benchmark score.

## Scope

This is a kinematic kitchen-to-dining transport curriculum policy. It is a
real RSL-RL checkpoint and is useful for validating the training pipeline, but
it is not yet a physical Task 3 policy. The next environment must include the
FR3 Duo base and arms, tray grasping, room collisions, and the physical Task 3
objects before this model can be considered a benchmark result.

Recreate the run inside the Isaac Lab container:

```bash
python -m task3_rl.train_kinematic_stage1 \
  --num-envs 2048 --iterations 500 \
  --log-dir outputs/task3_rl/kinematic_stage1_l40s_500
```
