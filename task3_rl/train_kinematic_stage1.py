# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Train a PPO checkpoint for the Stage 1 kinematic transport curriculum."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from rsl_rl.runners import OnPolicyRunner

from task3_rl.kinematic_stage1 import KinematicStage1Cfg, KinematicStage1Env


def runner_cfg() -> dict:
    """Return the compact PPO configuration used for curriculum bring-up."""
    return {
        "num_steps_per_env": 24,
        "save_interval": 25,
        "obs_groups": {"policy": ["policy"], "critic": ["policy"]},
        "policy": {
            "class_name": "ActorCritic",
            "init_noise_std": 0.8,
            "actor_hidden_dims": [128, 128],
            "critic_hidden_dims": [128, 128],
            "activation": "elu",
            "actor_obs_normalization": True,
            "critic_obs_normalization": True,
        },
        "algorithm": {
            "class_name": "PPO",
            "value_loss_coef": 1.0,
            "use_clipped_value_loss": True,
            "clip_param": 0.2,
            "entropy_coef": 0.01,
            "num_learning_epochs": 5,
            "num_mini_batches": 4,
            "learning_rate": 3.0e-4,
            "schedule": "adaptive",
            "gamma": 0.99,
            "lam": 0.95,
            "desired_kl": 0.01,
            "max_grad_norm": 1.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-envs", type=int, default=2048)
    parser.add_argument("--iterations", type=int, default=150)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("outputs/task3_rl/kinematic_stage1"),
    )
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    env = KinematicStage1Env(
        KinematicStage1Cfg(num_envs=args.num_envs), device=args.device
    )
    args.log_dir.mkdir(parents=True, exist_ok=True)
    runner = OnPolicyRunner(
        env, runner_cfg(), log_dir=str(args.log_dir), device=args.device
    )
    runner.learn(
        num_learning_iterations=args.iterations, init_at_random_ep_len=True
    )
    checkpoint = args.log_dir / "model_final.pt"
    runner.save(str(checkpoint))
    print(f"KINEMATIC_STAGE1_CHECKPOINT {checkpoint.resolve()}", flush=True)


if __name__ == "__main__":
    main()
