"""Vectorized Stage 1 transport curriculum for PPO bring-up.

This is intentionally a kinematic curriculum, not the final Isaac Lab task.
It validates the RSL-RL observation, reward, reset, checkpoint, and evaluation
pipeline before replacing the carried tray with the physical FR3 Duo scene.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from tensordict import TensorDict

from rsl_rl.env import VecEnv

from task3_rl.stage1 import Stage1TaskCfg, build_observation, evaluate_transition


@dataclass(frozen=True)
class KinematicStage1Cfg:
    """Configuration for the transport curriculum."""

    num_envs: int = 1024
    dt: float = 0.10
    episode_length: int = 120
    linear_speed_mps: float = 0.75
    angular_speed_radps: float = 1.20
    start_xy: tuple[float, float] = (-4.282, -1.618)
    start_z: float = 0.767
    start_jitter_m: float = 0.20
    workspace_x: tuple[float, float] = (-5.25, -1.75)
    workspace_y: tuple[float, float] = (-2.50, 2.75)


class KinematicStage1Env(VecEnv):
    """GPU vector environment for the first Task 3 transport policy.

    The tray is held at a fixed offset from the mobile base. This isolates
    base transport and stable carried-object motion; grasping is deliberately
    deferred to the physical Isaac Lab environment.
    """

    def __init__(self, cfg: KinematicStage1Cfg = KinematicStage1Cfg(), device: str = "cuda:0") -> None:
        self.cfg = cfg
        self.device = torch.device(device)
        self.num_envs = cfg.num_envs
        self.num_actions = 3
        self.max_episode_length = cfg.episode_length
        self.episode_length_buf = torch.zeros(self.num_envs, dtype=torch.long, device=self.device)
        self._task_cfg = Stage1TaskCfg()
        self._goal_xy = torch.tensor(self._task_cfg.goal_xy, device=self.device).repeat(self.num_envs, 1)
        self._base_pose = torch.zeros((self.num_envs, 3), device=self.device)
        self._tray_pose = torch.zeros((self.num_envs, 3), device=self.device)
        self._tray_velocity = torch.zeros((self.num_envs, 3), device=self.device)
        self._episode_return = torch.zeros(self.num_envs, device=self.device)
        self._reset(torch.arange(self.num_envs, device=self.device))

    def get_observations(self) -> TensorDict:
        return TensorDict({"policy": self._observation()}, batch_size=[self.num_envs], device=self.device)

    def step(self, actions: torch.Tensor) -> tuple[TensorDict, torch.Tensor, torch.Tensor, dict]:
        actions = actions.to(self.device).clamp(-1.0, 1.0)
        if actions.shape != (self.num_envs, self.num_actions):
            raise ValueError(f"Expected actions {(self.num_envs, self.num_actions)}, got {tuple(actions.shape)}")

        previous_xy = self._tray_pose[:, :2].clone()
        heading = self._base_pose[:, 2]
        forward = actions[:, 0] * self.cfg.linear_speed_mps
        lateral = actions[:, 1] * self.cfg.linear_speed_mps
        yaw_rate = actions[:, 2] * self.cfg.angular_speed_radps
        cos_heading = torch.cos(heading)
        sin_heading = torch.sin(heading)
        velocity_xy = torch.stack(
            (cos_heading * forward - sin_heading * lateral, sin_heading * forward + cos_heading * lateral), dim=-1
        )

        self._base_pose[:, :2] += velocity_xy * self.cfg.dt
        self._base_pose[:, 2] += yaw_rate * self.cfg.dt
        self._tray_pose[:, :2] = self._base_pose[:, :2]
        self._tray_velocity[:, :2] = velocity_xy
        self._tray_velocity[:, 2] = 0.0
        self.episode_length_buf += 1

        out_of_bounds = (
            (self._tray_pose[:, 0] < self.cfg.workspace_x[0])
            | (self._tray_pose[:, 0] > self.cfg.workspace_x[1])
            | (self._tray_pose[:, 1] < self.cfg.workspace_y[0])
            | (self._tray_pose[:, 1] > self.cfg.workspace_y[1])
        )
        reward, failed, success = evaluate_transition(
            previous_xy, self._tray_pose, self._goal_xy, out_of_bounds, self._task_cfg
        )
        reward -= 0.01 * torch.sum(torch.square(actions), dim=-1)
        time_outs = self.episode_length_buf >= self.max_episode_length
        dones = failed | success | time_outs
        self._episode_return += reward

        done_ids = torch.nonzero(dones, as_tuple=False).squeeze(-1)
        extras: dict[str, torch.Tensor | dict[str, torch.Tensor]] = {
            "time_outs": time_outs,
            "log": {
                "/metrics/success_rate": success.float().mean(),
                "/metrics/failure_rate": failed.float().mean(),
                "/metrics/mean_distance": torch.linalg.vector_norm(self._tray_pose[:, :2] - self._goal_xy, dim=-1).mean(),
            },
        }
        if done_ids.numel() > 0:
            extras["log"]["/metrics/episode_return"] = self._episode_return[done_ids].mean()
            self._reset(done_ids)
        return self.get_observations(), reward, dones, extras

    def reset(self) -> tuple[TensorDict, dict]:
        self._reset(torch.arange(self.num_envs, device=self.device))
        return self.get_observations(), {}

    def _observation(self) -> torch.Tensor:
        return build_observation(self._base_pose, self._tray_pose, self._tray_velocity, self._goal_xy)

    def _reset(self, env_ids: torch.Tensor) -> None:
        count = env_ids.numel()
        jitter = (torch.rand((count, 2), device=self.device) * 2.0 - 1.0) * self.cfg.start_jitter_m
        start_xy = torch.tensor(self.cfg.start_xy, device=self.device).expand(count, -1) + jitter
        self._base_pose[env_ids, :2] = start_xy
        self._base_pose[env_ids, 2] = torch.pi / 2
        self._tray_pose[env_ids, :2] = start_xy
        self._tray_pose[env_ids, 2] = self.cfg.start_z
        self._tray_velocity[env_ids] = 0.0
        self.episode_length_buf[env_ids] = 0
        self._episode_return[env_ids] = 0.0
