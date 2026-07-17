# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU tests for the NavigateTo skill's waypoint/twist logic.

The skill is pure logic over Pose2D: it plans y-then-x waypoints, emits
body-frame twists, and reports completion. Here it drives a kinematic
omnidirectional integrator; the Isaac-side adapter that turns twists into
TMR wheel commands is exercised on GPU by scripts/task3/verify_navigate.py.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from task3_autonomy.navigation import Pose2D  # noqa: E402
from task3_autonomy.skills import NavigateTo  # noqa: E402

DT = 0.05


def drive(skill: NavigateTo, pose: Pose2D, max_steps: int) -> tuple[
    Pose2D, list[Pose2D], bool
]:
    """Integrate the skill's twists kinematically (perfect omni base)."""
    trajectory = [pose]
    for _ in range(max_steps):
        vx, vy, done = skill.compute(pose)
        if done:
            return pose, trajectory, True
        cos_yaw = math.cos(pose.yaw)
        sin_yaw = math.sin(pose.yaw)
        pose = Pose2D(
            pose.x + (cos_yaw * vx - sin_yaw * vy) * DT,
            pose.y + (sin_yaw * vx + cos_yaw * vy) * DT,
            pose.yaw,
        )
        trajectory.append(pose)
    return pose, trajectory, False


def test_reaches_target_with_y_then_x_routing():
    start = Pose2D(-4.6, 2.7, math.radians(-90.0))
    skill = NavigateTo((-2.0, -1.5))
    final, trajectory, done = drive(skill, start, max_steps=2000)

    assert done, "navigation never finished"
    assert math.hypot(final.x - (-2.0), final.y - (-1.5)) <= 0.05
    # y-then-x: while y is still far from the target, x must not drift.
    for pose in trajectory:
        if abs(pose.y - (-1.5)) > 0.5:
            assert abs(pose.x - start.x) < 0.3, "moved in x before y leg done"


def test_zero_length_navigation_is_immediately_done():
    start = Pose2D(1.0, 1.0, 0.0)
    skill = NavigateTo((1.0, 1.0))
    _, _, done = drive(skill, start, max_steps=5)
    assert done


def test_twist_magnitude_respects_speed_limit():
    start = Pose2D(0.0, 0.0, 0.3)
    skill = NavigateTo((3.0, -4.0), max_linear_mps=0.5)
    vx, vy, done = skill.compute(start)
    assert not done
    assert math.hypot(vx, vy) <= 0.5 + 1e-9


def test_done_state_is_sticky_and_stops():
    start = Pose2D(0.0, 0.0, 0.0)
    skill = NavigateTo((0.2, 0.0))
    pose, _, done = drive(skill, start, max_steps=500)
    assert done
    vx, vy, done_again = skill.compute(pose)
    assert done_again
    assert (vx, vy) == (0.0, 0.0)
