# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from task3_autonomy.navigation import (  # noqa: E402
    TASK3_DOOR_X,
    TASK3_DOOR_Y,
    Pose2D,
    base_twist_toward,
    pose_reached,
    route_via_door,
    waypoints_x_then_y,
    waypoints_y_then_x,
    wrap_to_pi,
)

pytest_approx = pytest.approx


def test_wrap_to_pi_keeps_values_already_in_range():
    assert wrap_to_pi(0.5) == pytest_approx(0.5)


def test_wrap_to_pi_wraps_values_outside_range():
    # +-pi is the wrap boundary itself (both signs are the same angle), so
    # avoid asserting a sign exactly at the boundary -- use interior points.
    assert wrap_to_pi(2.5 * math.pi) == pytest_approx(0.5 * math.pi)
    assert wrap_to_pi(-2.5 * math.pi) == pytest_approx(-0.5 * math.pi)
    assert abs(wrap_to_pi(3.0 * math.pi)) == pytest_approx(math.pi)
    assert abs(wrap_to_pi(-3.0 * math.pi)) == pytest_approx(math.pi)


def test_waypoints_y_then_x_routes_through_y_first_when_both_change():
    waypoints = waypoints_y_then_x((0.0, 0.0), (3.0, 4.0))
    assert waypoints == [(0.0, 0.0), (0.0, 4.0), (3.0, 4.0)]


def test_waypoints_y_then_x_collapses_when_x_already_aligned():
    waypoints = waypoints_y_then_x((0.0, 0.0), (0.0, 4.0))
    assert waypoints == [(0.0, 0.0), (0.0, 4.0)]


def test_waypoints_y_then_x_collapses_when_y_already_aligned():
    waypoints = waypoints_y_then_x((0.0, 0.0), (3.0, 0.0))
    assert waypoints == [(0.0, 0.0), (3.0, 0.0)]


def test_waypoints_y_then_x_is_single_point_when_already_at_target():
    waypoints = waypoints_y_then_x((1.0, 1.0), (1.0, 1.0))
    assert waypoints == [(1.0, 1.0)]


def test_waypoints_x_then_y_routes_through_x_first_when_both_change():
    waypoints = waypoints_x_then_y((0.0, 0.0), (3.0, 4.0))
    assert waypoints == [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]


def test_waypoints_x_then_y_is_single_point_when_already_at_target():
    waypoints = waypoints_x_then_y((1.0, 1.0), (1.0, 1.0))
    assert waypoints == [(1.0, 1.0)]


def test_route_via_door_same_side_falls_back_to_y_then_x():
    start, target = (-4.6, 2.7), (-1.0, 1.5)  # both north of the partition
    assert route_via_door(start, target) == waypoints_y_then_x(start, target)


def test_route_via_door_crossing_passes_through_doorway_center():
    route = route_via_door((-4.6, 2.7), (-2.0, -1.5))
    assert (TASK3_DOOR_X, TASK3_DOOR_Y + 0.9) in route
    assert (TASK3_DOOR_X, TASK3_DOOR_Y - 0.9) in route
    # The two door waypoints must be consecutive: the crossing leg is a
    # straight line at the doorway's x, never a diagonal near the wall.
    approach_i = route.index((TASK3_DOOR_X, TASK3_DOOR_Y + 0.9))
    assert route[approach_i + 1] == (TASK3_DOOR_X, TASK3_DOOR_Y - 0.9)
    assert route[0] == (-4.6, 2.7)
    assert route[-1] == (-2.0, -1.5)


def test_route_via_door_crossing_south_to_north_is_mirrored():
    route = route_via_door((-2.0, -1.5), (-4.6, 2.7))
    approach_i = route.index((TASK3_DOOR_X, TASK3_DOOR_Y - 0.9))
    assert route[approach_i + 1] == (TASK3_DOOR_X, TASK3_DOOR_Y + 0.9)
    assert route[-1] == (-4.6, 2.7)


def test_base_twist_toward_drives_straight_forward_in_body_frame():
    pose = Pose2D(x=0.0, y=0.0, yaw=0.0)
    vx, vy = base_twist_toward(
        pose, (1.0, 0.0), max_linear_mps=0.5, position_kp=1.5
    )
    assert vx == pytest_approx(0.5)
    assert vy == pytest_approx(0.0, abs=1e-9)


def test_base_twist_toward_drives_sideways_in_body_frame():
    pose = Pose2D(x=0.0, y=0.0, yaw=0.0)
    vx, vy = base_twist_toward(
        pose, (0.0, 1.0), max_linear_mps=0.5, position_kp=1.5
    )
    assert vx == pytest_approx(0.0, abs=1e-9)
    assert vy == pytest_approx(0.5)


def test_base_twist_toward_rotates_world_error_into_body_frame():
    # Facing +90 deg (world +y): a target ahead in world +x is to the
    # robot's right, i.e. negative body-frame y.
    pose = Pose2D(x=0.0, y=0.0, yaw=math.pi / 2.0)
    vx, vy = base_twist_toward(
        pose, (1.0, 0.0), max_linear_mps=0.5, position_kp=1.5
    )
    assert vx == pytest_approx(0.0, abs=1e-9)
    assert vy == pytest_approx(-0.5)


def test_base_twist_toward_is_proportional_when_close():
    pose = Pose2D(x=0.0, y=0.0, yaw=0.0)
    vx, vy = base_twist_toward(
        pose, (0.1, 0.0), max_linear_mps=0.5, position_kp=1.5
    )
    assert vx == pytest_approx(0.15)  # kp * distance, below the cap
    assert vy == pytest_approx(0.0, abs=1e-9)


def test_base_twist_toward_returns_zero_at_target():
    pose = Pose2D(x=2.0, y=-1.0, yaw=1.2)
    vx, vy = base_twist_toward(
        pose, (2.0, -1.0), max_linear_mps=0.5, position_kp=1.5
    )
    assert vx == pytest_approx(0.0, abs=1e-9)
    assert vy == pytest_approx(0.0, abs=1e-9)


def test_pose_reached_true_within_position_tolerance():
    pose = Pose2D(x=0.02, y=0.0, yaw=0.0)
    assert pose_reached(pose, (0.0, 0.0), position_tolerance_m=0.03)


def test_pose_reached_false_outside_position_tolerance():
    pose = Pose2D(x=0.05, y=0.0, yaw=0.0)
    assert not pose_reached(pose, (0.0, 0.0), position_tolerance_m=0.03)


def test_pose_reached_checks_yaw_when_target_yaw_given():
    close_yaw = Pose2D(x=0.0, y=0.0, yaw=math.radians(1.0))
    far_yaw = Pose2D(x=0.0, y=0.0, yaw=math.radians(10.0))
    assert pose_reached(
        close_yaw,
        (0.0, 0.0),
        target_yaw=0.0,
        yaw_tolerance_rad=math.radians(3.0),
    )
    assert not pose_reached(
        far_yaw,
        (0.0, 0.0),
        target_yaw=0.0,
        yaw_tolerance_rad=math.radians(3.0),
    )
