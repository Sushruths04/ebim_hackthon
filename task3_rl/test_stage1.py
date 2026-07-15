"""Fast tests for the Stage 1 training contract."""

import unittest

import torch

from task3_rl.stage1 import Stage1TaskCfg, build_observation, evaluate_transition


class Stage1TaskTests(unittest.TestCase):
    def test_observation_has_expected_features(self) -> None:
        result = build_observation(
            torch.tensor([[0.0, 0.0, 0.0]]),
            torch.tensor([[1.0, 2.0, 0.8]]),
            torch.tensor([[0.1, 0.0, 0.0]]),
            torch.tensor([[2.0, 2.0]]),
        )
        self.assertEqual(result.shape, (1, 13))
        self.assertTrue(torch.allclose(result[0, 9:11], torch.tensor([1.0, 0.0])))

    def test_progress_is_rewarded(self) -> None:
        reward, failed, success = evaluate_transition(
            torch.tensor([[0.0, 0.0]]),
            torch.tensor([[0.5, 0.0, 0.8]]),
            torch.tensor([[1.0, 0.0]]),
            torch.tensor([False]),
        )
        self.assertGreater(float(reward[0]), 0.0)
        self.assertFalse(bool(failed[0]))
        self.assertFalse(bool(success[0]))

    def test_success_and_drop_terminate(self) -> None:
        cfg = Stage1TaskCfg(goal_xy=(1.0, 0.0))
        reward, failed, success = evaluate_transition(
            torch.tensor([[1.5, 0.0], [1.5, 0.0]]),
            torch.tensor([[1.0, 0.0, 0.8], [1.0, 0.0, 0.2]]),
            torch.tensor([[1.0, 0.0], [1.0, 0.0]]),
            torch.tensor([False, False]),
            cfg,
        )
        self.assertTrue(bool(success[0]))
        self.assertFalse(bool(failed[0]))
        self.assertTrue(bool(success[1]))
        self.assertTrue(bool(failed[1]))
        self.assertGreater(float(reward[0]), float(reward[1]))


if __name__ == "__main__":
    unittest.main()
