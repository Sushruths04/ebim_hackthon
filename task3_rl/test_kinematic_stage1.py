# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for the vectorized Stage 1 transport curriculum."""

import unittest

import torch

from task3_rl.kinematic_stage1 import KinematicStage1Cfg, KinematicStage1Env


class KinematicStage1Tests(unittest.TestCase):
    def test_step_has_task3_observation_shape(self) -> None:
        env = KinematicStage1Env(KinematicStage1Cfg(num_envs=8), device="cpu")
        observations = env.get_observations()
        self.assertEqual(tuple(observations["policy"].shape), (8, 13))
        next_observations, rewards, dones, extras = env.step(
            torch.zeros((8, 3))
        )
        self.assertEqual(tuple(next_observations["policy"].shape), (8, 13))
        self.assertEqual(tuple(rewards.shape), (8,))
        self.assertEqual(tuple(dones.shape), (8,))
        self.assertIn("time_outs", extras)


if __name__ == "__main__":
    unittest.main()
