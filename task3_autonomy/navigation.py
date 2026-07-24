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


# Task 3 room geometry, measured from assets/robot_room.usd (2026-07-17):
# the dining/kitchen partition runs along y in [0.10, 0.34] with a single
# doorway gap x in (-4.74, -3.54); the kitchen island (grading-prop counter)
# occupies x [-4.51, -3.77] x y [-2.47, -1.22]. The first live runs proved
# walls are load-bearing: a y-then-x route descending at x=-4.60 hugged the
# door jamb (jamb edge x=-4.74) and stalled the base at y ~ 0.99 with wheels
# contact-stalled (NAVDBG, /tmp/task3_verify_nav7.log on sim-dev-g4b).

TASK3_DOOR_X = -4.14
TASK3_DOOR_Y = 0.22
TASK3_DOOR_APPROACH_M = 0.9

# East edge of the doorway gap. The partition is solid for x > -3.54;
# the base must be at or west of this x to pass through the gap.
# Measured from assets/robot_room.usd (2026-07-17).
TASK3_GAP_EAST_EDGE = -3.54

# Kitchen-side door point sits in the shallow lane between the partition
# (south face y=0.10) and the kitchen island (north face y=-1.22): rear
# extent ~0.42 clears the wall (rear tip 0.05) and the tucked arms' 0.80 m
# effective forward overhang clears the island (nose tip -1.17) — ~5 cm
# margin each way. Live evidence: nav9 scraped the island for ~35 s with
# the 0.885 m overhang of the v3 fold at lane y=-0.68.
TASK3_KITCHEN_LANE_Y = -0.37


def waypoints_x_then_y(
    start_xy: tuple[float, float], target_xy: tuple[float, float]
) -> list[tuple[float, float]]:
    """Route the x move before the y move (mirror of waypoints_y_then_x).

    Needed on the kitchen side: descending at the door's x runs into the
    kitchen island, so cross the clear row first, then descend.
    """
    midpoint = (target_xy[0], start_xy[1])
    waypoints = [start_xy]
    if midpoint != waypoints[-1]:
        waypoints.append(midpoint)
    if target_xy != waypoints[-1]:
        waypoints.append(target_xy)
    return waypoints


def route_via_door(
    start_xy: tuple[float, float], target_xy: tuple[float, float]
) -> list[tuple[float, float]]:
    """Waypoint route that crosses the partition only through the doorway.

    Same-side start/target fall back to plain y-then-x. Crossing routes:
    y-then-x to the door point on the start side (dining side is open at
    +TASK3_DOOR_APPROACH_M; kitchen side uses the shallow
    TASK3_KITCHEN_LANE_Y lane), straight through the gap, then x-then-y on
    the far side (hugs the wall to clear the island).
    """
    start_north = start_xy[1] > TASK3_DOOR_Y
    target_north = target_xy[1] > TASK3_DOOR_Y
    if start_north == target_north:
        return waypoints_y_then_x(start_xy, target_xy)
    north_point = (TASK3_DOOR_X, TASK3_DOOR_Y + TASK3_DOOR_APPROACH_M)
    south_point = (TASK3_DOOR_X, TASK3_KITCHEN_LANE_Y)
    first, second = (
        (north_point, south_point)
        if start_north
        else (south_point, north_point)
    )
    route = waypoints_y_then_x(start_xy, first)
    print(f"DEBUG route_via_door start={start_xy} target={target_xy} first={first} second={second} route={route}", flush=True)
    route.append(second)
    route.extend(waypoints_x_then_y(second, target_xy)[1:])
    return route


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
