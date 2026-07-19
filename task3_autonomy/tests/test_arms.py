# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU coverage for the autonomous reach command and grasp predicate."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "common"))

from teleop_targets import (  # noqa: E402
    CartesianTargetTracker,
    Pose,
    TargetLimits,
    TeleopTargets,
    _quaternion_from_rpy,
    pose_world_to_base,
)

from task3_autonomy.arms import (  # noqa: E402
    GRIPPER_CLOSED_RAD,
    GRIPPER_OPEN_RAD,
    DualArmController,
    grasp_lift_gate_passed,
    gripper_holds_object,
    linear_ramp_target,
    one_step_reach_command,
    ordered_joint_targets,
    synchronized_drag_targets,
)


def test_changingtek_gripper_uses_zero_closed_convention():
    assert GRIPPER_CLOSED_RAD == 0.0
    assert GRIPPER_OPEN_RAD == 0.9


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({}, True),
        ({"holding": False}, False),
        ({"held_ticks": 599}, False),
        ({"lifted_m": 0.0799}, False),
    ],
)
def test_grasp_lift_gate_uses_measured_object_outcome(overrides, expected):
    values = {
        "holding": True,
        "held_ticks": 600,
        "needed_ticks": 600,
        "lifted_m": 0.088,
        "min_lift_m": 0.08,
        **overrides,
    }
    assert grasp_lift_gate_passed(**values) is expected


def test_linear_ramp_target_clamps_at_end():
    assert linear_ramp_target(0.9, 0.0, 0, 4) == pytest.approx(0.9)
    assert linear_ramp_target(0.9, 0.0, 2, 4) == pytest.approx(0.45)
    assert linear_ramp_target(0.9, 0.0, 4, 4) == pytest.approx(0.0)
    assert linear_ramp_target(0.9, 0.0, 8, 4) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "args",
    [
        (math.nan, 0.0, 1, 2),
        (0.9, math.inf, 1, 2),
        (0.9, 0.0, -1, 2),
        (0.9, 0.0, 1, 0),
    ],
)
def test_linear_ramp_target_rejects_invalid_inputs(args):
    with pytest.raises(ValueError, match="ramp"):
        linear_ramp_target(*args)


@pytest.mark.parametrize("completed_steps", [0, 1, 3, 5, 8])
def test_synchronized_drag_targets_preserve_relative_offset(completed_steps):
    arm_start_y = -1.62
    anchor_start_y = -1.72
    starting_gap = arm_start_y - anchor_start_y
    arm_y, anchor_y = synchronized_drag_targets(
        arm_start_y, anchor_start_y, 0.26, completed_steps, 5
    )
    assert arm_y - anchor_y == pytest.approx(starting_gap)


def test_synchronized_drag_targets_ramp_endpoints():
    arm_y, anchor_y = synchronized_drag_targets(-1.62, -1.72, 0.26, 0, 5)
    assert arm_y == pytest.approx(-1.62)
    assert anchor_y == pytest.approx(-1.72)
    arm_y, anchor_y = synchronized_drag_targets(-1.62, -1.72, 0.26, 5, 5)
    assert arm_y == pytest.approx(-1.62 + 0.26)
    assert anchor_y == pytest.approx(-1.72 + 0.26)


def test_lift_ramps_vertical_target_before_accepting_convergence():
    controller = object.__new__(DualArmController)
    targets = []
    start = (1.0, 2.0, 0.8)
    quaternion = (1.0, 0.0, 0.0, 0.0)
    controller.ee_world_poses = lambda: (
        (start, quaternion),
        (start, quaternion),
    )
    controller.set_arm_target = lambda side, position, quat: targets.append(
        (side, position, quat)
    )
    controller.command = lambda: SimpleNamespace(
        left_succeeded=True, right_succeeded=True
    )
    controller.pose_error = lambda side, position, quat: (0.0, 0.0)
    controller._tracker = CartesianTargetTracker(
        TeleopTargets(
            left=Pose(start, quaternion),
            right=Pose(start, quaternion),
            left_gripper=0.0,
            right_gripper=0.0,
            spine=0.44,
        ),
        limits=TargetLimits(
            position_min=(-2.0, -2.0, -1.0),
            position_max=(2.0, 2.0, 3.0),
            spine_min=0.0,
            spine_max=0.85,
        ),
    )

    assert controller.lift(
        "right",
        0.3,
        step=lambda: None,
        dt=0.5,
        timeout_s=3.0,
        ramp_seconds=2.0,
        spine_assist_m=0.12,
    )
    assert all(target[1][:2] == (1.0, 2.0) for target in targets)
    assert [target[1][2] for target in targets] == pytest.approx(
        [0.875, 0.95, 1.025, 1.1]
    )
    assert controller.spine == pytest.approx(0.56)


def _tracker(left: Pose, right: Pose) -> CartesianTargetTracker:
    return CartesianTargetTracker(
        TeleopTargets(
            left=left,
            right=right,
            left_gripper=0.04,
            right_gripper=0.04,
            spine=0.2,
        ),
        limits=TargetLimits(
            position_min=(-2.0, -2.0, -1.0),
            position_max=(2.0, 2.0, 3.0),
        ),
    )


def _assert_same_rotation(actual, expected, *, tolerance=1.0e-9):
    dot = abs(sum(a * b for a, b in zip(actual, expected)))
    assert dot == pytest.approx(1.0, abs=tolerance)


@pytest.mark.parametrize("side", ("left", "right"))
def test_one_step_reach_command_lands_exactly_on_world_target(side):
    initial_left = Pose((-0.3, 0.4, 0.8), _quaternion_from_rpy(0.2, -0.1, 0.3))
    initial_right = Pose(
        (0.5, -0.2, 1.1), _quaternion_from_rpy(-0.4, 0.2, -0.5)
    )
    tracker = _tracker(initial_left, initial_right)
    before_other = (
        tracker.targets.right if side == "left" else tracker.targets.left
    )
    base_position = (-3.32, -1.72, 0.0)
    base_orientation = _quaternion_from_rpy(0.0, 0.0, math.pi)
    world_target = Pose(
        (-4.145, -1.75, 1.05),
        _quaternion_from_rpy(math.pi, 0.0, 0.0),
    )

    command = one_step_reach_command(
        getattr(tracker.targets, side),
        world_target,
        base_position,
        base_orientation,
        side=side,
        timestamp=12.5,
    )
    updated = tracker.apply(command)
    expected = pose_world_to_base(
        world_target, base_position, base_orientation
    )
    actual = getattr(updated, side)

    assert command.active
    assert command.source == "task3_autonomy.reach"
    assert command.timestamp == 12.5
    assert actual.position == pytest.approx(expected.position, abs=1.0e-9)
    _assert_same_rotation(actual.orientation_wxyz, expected.orientation_wxyz)
    assert (updated.right if side == "left" else updated.left) == before_other


def test_one_step_reach_command_rejects_unknown_side():
    pose = Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="side"):
        one_step_reach_command(
            pose,
            pose,
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            side="middle",
        )


@pytest.mark.parametrize(
    "position,expected",
    [
        (0.0, False),
        (0.049, False),
        (0.051, True),
        (0.4, True),
        (0.9, True),
        (1.049, True),
        (1.05, False),
        (1.1, False),
    ],
)
def test_gripper_holds_object(position, expected):
    assert gripper_holds_object(position) is expected


@pytest.mark.parametrize("width", (math.nan, math.inf, -math.inf))
def test_gripper_hold_predicate_rejects_nonfinite_width(width):
    with pytest.raises(ValueError, match="finite"):
        gripper_holds_object(width)


def test_gripper_hold_predicate_rejects_invalid_bounds():
    with pytest.raises(ValueError, match="ordered"):
        gripper_holds_object(0.1, min_position_rad=0.3, max_position_rad=0.2)


def test_ordered_joint_targets_converts_lula_mappingproxy_to_sequence():
    targets = MappingProxyType({"joint_b": 2.0, "joint_a": 1.0})
    assert ordered_joint_targets(targets, ("joint_a", "joint_b")) == [1.0, 2.0]
    assert ordered_joint_targets(MappingProxyType({}), ("joint_a",)) is None


def test_ordered_joint_targets_rejects_missing_joint():
    with pytest.raises(ValueError, match="missing joint joint_b"):
        ordered_joint_targets({"joint_a": 1.0}, ("joint_a", "joint_b"))
