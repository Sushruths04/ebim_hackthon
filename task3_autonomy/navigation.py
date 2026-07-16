# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Pure navigation math for the Task 3 FSM's navigate_to() skill.

No Isaac Sim imports here -- unit-testable on CPU (docs/task3_master_plan.md
hard rule 5: write and unit-test FSM/skill code locally before touching a
GPU). The Isaac-dependent orchestration (reading live robot pose, calling
tmr_base_control.compute_drive_targets()/compensate_yaw_rate(), stepping the
sim) lives in task3_autonomy/skills.py and reuses the functions below.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float  # radians


def wrap_to_pi(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def waypoints_y_then_x(
    start_xy: tuple[float, float], target_xy: tuple[float, float]
) -> list[tuple[float, float]]:
    """Route the y move before the x move.

    Mirrors the routing idea in
    scripts/evaluation/task3/integration_test.py's y_then_x_path(), which
    exists to avoid the kitchen/dining wall partition -- that helper drives
    a kinematic prim path for grading tests; this one produces the waypoint
    list a real closed-loop base controller drives through.
    """
    midpoint = (start_xy[0], target_xy[1])
    waypoints = [start_xy]
    if midpoint != waypoints[-1]:
        waypoints.append(midpoint)
    if target_xy != waypoints[-1]:
        waypoints.append(target_xy)
    return waypoints


def base_twist_toward(
    pose: Pose2D,
    target_xy: tuple[float, float],
    *,
    max_linear_mps: float,
    position_kp: float = 1.5,
) -> tuple[float, float]:
    """Body-frame (vx, vy) command driving `pose` toward `target_xy`.

    Yaw is not controlled here. The TMR base is omnidirectional (every
    wheel module steers independently), so it does not need to face its
    direction of travel -- combine this with
    tmr_base_control.compensate_yaw_rate() for heading hold instead of
    reimplementing yaw control here.
    """
    dx_world = target_xy[0] - pose.x
    dy_world = target_xy[1] - pose.y
    distance = math.hypot(dx_world, dy_world)
    if distance < 1e-9:
        return 0.0, 0.0

    cos_yaw = math.cos(pose.yaw)
    sin_yaw = math.sin(pose.yaw)
    # Rotate the world-frame error vector by -yaw into the body frame.
    vx_body_unit = cos_yaw * dx_world + sin_yaw * dy_world
    vy_body_unit = -sin_yaw * dx_world + cos_yaw * dy_world

    linear_speed = min(max_linear_mps, position_kp * distance)
    scale = linear_speed / distance
    return vx_body_unit * scale, vy_body_unit * scale


def pose_reached(
    pose: Pose2D,
    target_xy: tuple[float, float],
    target_yaw: float | None = None,
    *,
    position_tolerance_m: float = 0.03,
    yaw_tolerance_rad: float = math.radians(3.0),
) -> bool:
    """Stop-condition check: ~3 cm / 3 deg tolerance per the master plan."""
    distance = math.hypot(target_xy[0] - pose.x, target_xy[1] - pose.y)
    if distance > position_tolerance_m:
        return False
    if target_yaw is None:
        return True
    return abs(wrap_to_pi(target_yaw - pose.yaw)) <= yaw_tolerance_rad
