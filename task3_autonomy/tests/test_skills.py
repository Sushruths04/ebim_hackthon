# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU tests for the NavigateTo skill's waypoint/twist logic.

The skill is pure logic over Pose2D: it plans door-aware waypoints
(route_via_door), emits body-frame twists, and reports completion. Here it
drives a kinematic omnidirectional integrator; the Isaac-side adapter that
turns twists into TMR wheel commands is exercised on GPU by
scripts/task3/verify_navigate.py.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from task3_autonomy.navigation import Pose2D  # noqa: E402
from task3_autonomy.skills import NavigateTo, RotateTo  # noqa: E402

DT = 0.05


def drive(
    skill: NavigateTo, pose: Pose2D, max_steps: int
) -> tuple[Pose2D, list[Pose2D], bool]:
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


def test_reaches_target_and_crosses_partition_only_in_doorway():
    # The Task 3 spawn->kitchen route crosses the dining/kitchen partition
    # (y in [0.10, 0.34], doorway gap x in (-4.74, -3.54)). The first live
    # run stalled against the door jamb descending at x=-4.6; the route must
    # cross the partition band only near the doorway center.
    start = Pose2D(-4.6, 2.7, math.radians(-90.0))
    skill = NavigateTo((-3.18, -1.6))
    final, trajectory, done = drive(skill, start, max_steps=3000)

    assert done, "navigation never finished"
    assert math.hypot(final.x - (-3.18), final.y - (-1.6)) <= 0.05
    # Wall band [0.10, 0.34] plus the robot's 0.38 m rear extent: while any
    # part of the robot overlaps the partition, x must stay in the doorway.
    for pose in trajectory:
        if -0.25 <= pose.y <= 0.8:
            assert -4.74 < pose.x < -3.54, (
                f"crossed partition outside doorway at ({pose.x}, {pose.y})"
            )


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


def test_rotate_to_uses_shortest_wrapped_direction_and_rate_limit():
    skill = RotateTo(
        math.radians(-179.0),
        max_yaw_rate=0.5,
        yaw_kp=2.0,
        yaw_tolerance_rad=math.radians(0.5),
    )
    wz, done = skill.compute(Pose2D(0.0, 0.0, math.radians(179.0)))
    assert not done
    assert 0.0 < wz <= 0.5


def test_rotate_to_finishes_within_tolerance_and_stays_stopped():
    skill = RotateTo(1.0, yaw_tolerance_rad=0.03)
    wz, done = skill.compute(Pose2D(0.0, 0.0, 1.02))
    assert done
    assert wz == 0.0
    assert skill.compute(Pose2D(0.0, 0.0, -2.0)) == (0.0, True)
