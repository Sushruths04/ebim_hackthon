# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU coverage for probe_tray_slide.py's pure-math helpers.

The script's own module-level sys.path insertions make it importable
without Isaac Sim (all Isaac-dependent code lives inside main()/_run()).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "task3"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from probe_tray_slide import (  # noqa: E402
    EDGE_PINCH_ROLL_RAD,
    KITCHEN_PARTITION_SOUTH_FACE_Y,
    NORTH_COUNTER_EDGE_Y,
    TRAY_HALF_EXTENT_Y_M,
    _measure_fingertip_midpoint,
    north_overhang_m,
    north_pinch_stance,
    north_pinch_target,
    stance_in_safe_lane,
    stroke_needs_realign,
)
from teleop_targets import _quaternion_from_rpy, _rotate_vector  # noqa: E402


def test_north_overhang_zero_at_counter_edge():
    tray_y = NORTH_COUNTER_EDGE_Y - TRAY_HALF_EXTENT_Y_M
    assert north_overhang_m(tray_y) == pytest.approx(0.0, abs=1e-9)


def test_north_overhang_positive_past_the_edge():
    tray_y = NORTH_COUNTER_EDGE_Y - TRAY_HALF_EXTENT_Y_M + 0.06
    assert north_overhang_m(tray_y) == pytest.approx(0.06)


def test_north_overhang_negative_before_the_edge():
    # Matches the round-1 measured case: tray center well short of the
    # counter edge, so the tray's own north edge has not reached it yet.
    tray_y = -1.5
    expected = (tray_y + TRAY_HALF_EXTENT_Y_M) - NORTH_COUNTER_EDGE_Y
    assert north_overhang_m(tray_y) == pytest.approx(expected)
    assert north_overhang_m(tray_y) < 0.0


def test_north_pinch_target_is_trays_own_north_edge():
    target = north_pinch_target(-4.25, -1.35, x_offset=0.0)
    assert target == pytest.approx((-4.25, -1.35 + TRAY_HALF_EXTENT_Y_M))


def test_north_pinch_target_applies_x_offset():
    target = north_pinch_target(-4.25, -1.35, x_offset=0.05)
    assert target[0] == pytest.approx(-4.20)


def test_north_pinch_stance_is_north_of_target_and_dead_ahead():
    target = (-4.25, -1.2)
    stance = north_pinch_stance(target, standoff_m=0.8)
    assert stance[0] == pytest.approx(target[0])  # same x -> dead ahead
    assert stance[1] == pytest.approx(target[1] + 0.8)
    assert stance[1] > target[1]  # north of the pinch point


@pytest.mark.parametrize(
    "stance_y,expected",
    [
        (-0.5, True),  # squarely inside the lane
        (-1.22, False),  # exactly at the island's north face
        (-1.20, False),  # inside the margin
        (0.10, False),  # exactly at the partition's south face
        (0.05, False),  # inside the margin
        (-2.0, False),  # south of the island entirely
        (0.5, False),  # north of the partition entirely
    ],
)
def test_stance_in_safe_lane(stance_y, expected):
    assert stance_in_safe_lane(stance_y) is expected


def test_stance_in_safe_lane_uses_documented_room_geometry_defaults():
    # Sanity-check the defaults match the constants cited in the room
    # geometry comment (task3_autonomy/navigation.py): island north face
    # -1.22, partition south face 0.10.
    assert NORTH_COUNTER_EDGE_Y == -1.22
    assert KITCHEN_PARTITION_SOUTH_FACE_Y == 0.10


@pytest.mark.parametrize(
    "contact_y,base_y,expected",
    [
        (-1.4, -1.4, False),
        (-1.4, -1.45, False),  # 0.05 m drift, under threshold
        (-1.4, -1.49, True),  # 0.09 m drift, over threshold
        (-1.4, -1.31, True),  # 0.09 m drift the other way
    ],
)
def test_stroke_needs_realign(contact_y, base_y, expected):
    assert stroke_needs_realign(contact_y, base_y) is expected


# --- Round 3: closing-axis orientation verification -----------------------
#
# Regression test for the round-3 diagnosis: rounds 1-2's edge_y quaternion
# (rpy(pi, pi/2, 0)) left the gripper's closing axis on world Y (horizontal)
# -- identical to top_down's closing axis -- because pitching about an axis
# that IS already the closing axis does not rotate it. That is why edge_close
# always closed to ~0 rad across three different z-targets: the fingers were
# never oriented to straddle a horizontal lip in the first place. A pure roll
# of +pi/2 (no pitch, no yaw) instead rotates the closing axis to world Z.
#
# The local closing-axis vector is (0, 1, 0): _rotate_vector at the KNOWN
# top_down orientation (rpy(pi, 0, 0)) must reproduce the empirically
# observed "closes along world Y" behavior from prior cup-grasp runs, which
# anchors what "the closing axis" means in this gripper's own frame before
# asserting anything about candidate orientations.
_CLOSING_AXIS_LOCAL = (0.0, 1.0, 0.0)
_APPROACH_AXIS_LOCAL = (0.0, 0.0, 1.0)


def _closing_axis_world(roll: float, pitch: float, yaw: float) -> tuple:
    quat = _quaternion_from_rpy(roll, pitch, yaw)
    return _rotate_vector(quat, _CLOSING_AXIS_LOCAL)


def _approach_axis_world(roll: float, pitch: float, yaw: float) -> tuple:
    quat = _quaternion_from_rpy(roll, pitch, yaw)
    return _rotate_vector(quat, _APPROACH_AXIS_LOCAL)


def test_top_down_closing_axis_is_horizontal_world_y():
    # Anchors the convention: top_down = rpy(pi, 0, 0) is the proven
    # top-down grasp orientation (cup pipeline, tray push), and prior runs
    # observed the fingers close along world Y ("south finger pushed cup
    # +0.07 m in Y"). This must hold, or the local axis assignment below
    # is wrong.
    axis = _closing_axis_world(math.pi, 0.0, 0.0)
    assert abs(axis[0]) < 1e-9
    assert abs(axis[2]) < 1e-9
    assert abs(abs(axis[1]) - 1.0) < 1e-9


def test_round1_2_edge_quat_closing_axis_is_still_horizontal():
    # The bug: rpy(pi, pi/2, 0) pitches about Y, which is already the
    # closing axis, so it stays horizontal -- confirmed by direct
    # computation, not armchair rotation algebra.
    axis = _closing_axis_world(math.pi, math.pi / 2.0, 0.0)
    assert abs(axis[0]) < 1e-9
    assert abs(axis[2]) < 1e-9
    assert abs(abs(axis[1]) - 1.0) < 1e-9


def test_edge_pinch_roll_rad_gives_vertical_closing_axis():
    # The round-3 fix: EDGE_PINCH_ROLL_RAD (pure roll, no pitch/yaw) must
    # rotate the closing axis to world Z (vertical), correct for
    # straddling a horizontal lip.
    axis = _closing_axis_world(EDGE_PINCH_ROLL_RAD, 0.0, 0.0)
    assert abs(axis[0]) < 1e-9
    assert abs(axis[1]) < 1e-9
    assert abs(abs(axis[2]) - 1.0) < 1e-9


def test_edge_pinch_roll_rad_gives_south_facing_approach_axis():
    # The wrist must point INTO the tray (south, world -Y) from the
    # north stance, not away from it.
    axis = _approach_axis_world(EDGE_PINCH_ROLL_RAD, 0.0, 0.0)
    assert abs(axis[0]) < 1e-9
    assert abs(axis[2]) < 1e-9
    assert axis[1] == pytest.approx(-1.0, abs=1e-9)


# --- Round 3: fingertip midpoint measurement -------------------------------


def _fake_robot(body_names, body_positions):
    return SimpleNamespace(
        body_names=body_names,
        data=SimpleNamespace(body_pos_w=[body_positions]),
    )


def test_measure_fingertip_midpoint_right_arm():
    names = [
        "spine_link",
        "right_left_2_link",
        "right_iight_2_link",
        "left_left_2_link",
    ]
    positions = [
        (0.0, 0.0, 0.0),
        (-4.2, -1.16, 0.78),
        (-4.2, -1.16, 0.75),
        (0.0, 0.0, 0.0),
    ]
    robot = _fake_robot(names, positions)
    midpoint = _measure_fingertip_midpoint(robot, "right")
    assert midpoint == pytest.approx((-4.2, -1.16, 0.765))


def test_measure_fingertip_midpoint_missing_bodies_returns_none():
    robot = _fake_robot(["spine_link"], [(0.0, 0.0, 0.0)])
    assert _measure_fingertip_midpoint(robot, "right") is None


def test_measure_fingertip_midpoint_rejects_bad_side():
    robot = _fake_robot(["spine_link"], [(0.0, 0.0, 0.0)])
    with pytest.raises(ValueError, match="side"):
        _measure_fingertip_midpoint(robot, "up")
