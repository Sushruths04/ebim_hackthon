"""Stage 1 tray-transport task logic shared by the future Isaac Lab adapter.

The benchmark has no released Task 3 RL environment.  Keeping the reward and
termination logic independent of Kit makes it testable before wiring it to the
robot, articulated tray grasp, and scene reset implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class Stage1TaskCfg:
    """Task constants in metres and simulator steps."""

    goal_xy: tuple[float, float] = (-2.85, 1.8)
    success_radius: float = 0.20
    drop_height: float = 0.45
    progress_scale: float = 4.0
    success_bonus: float = 10.0
    collision_penalty: float = 2.0
    drop_penalty: float = 5.0


def build_observation(
    base_pose: torch.Tensor,
    tray_pose: torch.Tensor,
    tray_velocity: torch.Tensor,
    goal_xy: torch.Tensor,
) -> torch.Tensor:
    """Return the privileged-state observation for the initial Stage 1 policy.

    Inputs are batched tensors.  The observation deliberately uses poses first;
    cameras can replace this interface later without changing reward semantics.
    """

    if base_pose.shape[-1] != 3 or tray_pose.shape[-1] != 3:
        raise ValueError("base_pose and tray_pose must contain x, y, yaw/z values")
    if tray_velocity.shape[-1] != 3 or goal_xy.shape[-1] != 2:
        raise ValueError("tray_velocity must be xyz and goal_xy must be xy")
    relative_goal = goal_xy - tray_pose[..., :2]
    relative_tray = tray_pose[..., :2] - base_pose[..., :2]
    return torch.cat((base_pose, tray_pose, tray_velocity, relative_goal, relative_tray), dim=-1)


def evaluate_transition(
    previous_tray_xy: torch.Tensor,
    tray_pose: torch.Tensor,
    goal_xy: torch.Tensor,
    collision: torch.Tensor,
    cfg: Stage1TaskCfg = Stage1TaskCfg(),
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Compute reward, failure termination, and success termination per env."""

    previous_distance = torch.linalg.vector_norm(previous_tray_xy - goal_xy, dim=-1)
    current_distance = torch.linalg.vector_norm(tray_pose[..., :2] - goal_xy, dim=-1)
    success = current_distance <= cfg.success_radius
    dropped = tray_pose[..., 2] < cfg.drop_height
    failure = collision.to(dtype=torch.bool) | dropped
    reward = cfg.progress_scale * (previous_distance - current_distance)
    reward = reward + success.to(reward.dtype) * cfg.success_bonus
    reward = reward - collision.to(reward.dtype) * cfg.collision_penalty
    reward = reward - dropped.to(reward.dtype) * cfg.drop_penalty
    return reward, failure, success
