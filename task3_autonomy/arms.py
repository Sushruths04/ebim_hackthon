# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Dual-arm manipulation skills for the Task 3 autonomous FSM.

The pure helpers in this module build the same incremental
``TeleopCommand`` consumed by keyboard teleoperation. ``DualArmController``
then feeds the resulting ``CartesianTargetTracker`` targets through the
proven Lula IK and joint-target composition stack. Isaac imports remain lazy
so command math and hold predicates stay CPU-testable.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from task3_autonomy.rotations import rpy_from_quaternion

# ChangingTek AG2F primary revolute-joint positions. This linkage follows the
# same convention as the original FR3 finger controller: zero is closed and
# increasing the position opens the fingers (USD limit 0..1 rad).
GRIPPER_CLOSED_RAD = 0.0
GRIPPER_OPEN_RAD = 0.9

DEFAULT_POSITION_TOLERANCE_M = 0.02
DEFAULT_ORIENTATION_TOLERANCE_RAD = math.radians(5.0)
DEFAULT_HOLD_MIN_POSITION_RAD = 0.05
DEFAULT_HOLD_MAX_POSITION_RAD = 1.05


def grasp_lift_gate_passed(
    *,
    holding: bool,
    held_ticks: int,
    needed_ticks: int,
    lifted_m: float,
    min_lift_m: float,
) -> bool:
    """Require measured object retention, height, and continuous hold.

    End-effector convergence is diagnostic only: a valid physical lift can
    meet the object-space goal even when the wrist stops short of a more
    ambitious Cartesian target.
    """
    return holding and held_ticks >= needed_ticks and lifted_m >= min_lift_m


def linear_ramp_target(
    start: float, end: float, completed_steps: int, total_steps: int
) -> float:
    """Return a clamped linear ramp target for deterministic soft closure."""
    if not all(math.isfinite(value) for value in (start, end)):
        raise ValueError("ramp endpoints must be finite")
    if total_steps <= 0 or completed_steps < 0:
        raise ValueError("ramp steps must be positive")
    alpha = min(1.0, completed_steps / total_steps)
    return start + (end - start) * alpha


def synchronized_drag_targets(
    arm_start_y: float,
    anchor_start_y: float,
    distance: float,
    completed_steps: int,
    total_steps: int,
) -> tuple[float, float]:
    """Advance an arm push target and a base hold anchor by one shared offset.

    Both must move north together so the arm's commanded reach relative to
    the base never grows past the proven envelope: the Step 1 trial 1 root
    cause was a single unsynchronized reach ~1.0 m from stance, well past the
    proven ~0.83 m dead-ahead ceiling. Sharing one ramp offset guarantees the
    arm/base separation stays exactly constant for every step.
    """
    offset = linear_ramp_target(0.0, distance, completed_steps, total_steps)
    return arm_start_y + offset, anchor_start_y + offset


def ordered_joint_targets(
    targets: Mapping[str, float], joint_names: Sequence[str]
) -> list[float] | None:
    """Convert Lula's immutable name mapping into composer joint order."""
    if not targets:
        return None
    try:
        values = [float(targets[name]) for name in joint_names]
    except KeyError as error:
        raise ValueError(
            f"IK result is missing joint {error.args[0]}"
        ) from None
    if not all(math.isfinite(value) for value in values):
        raise ValueError("IK joint targets must be finite")
    return values


def one_step_reach_command(
    current_base_target: Any,
    world_target: Any,
    base_position: Sequence[float],
    base_orientation_wxyz: Sequence[float],
    *,
    side: str,
    timestamp: float = 0.0,
) -> Any:
    """Build the single incremental command that lands on ``world_target``.

    ``CartesianTargetTracker`` stores a base-frame target and left-multiplies
    its orientation by the command delta. Therefore the exact delta is
    ``target * inverse(current)``. Frame conversion and quaternion operations
    deliberately reuse ``teleop_targets`` rather than introducing a second
    implementation.
    """
    from teleop_commands import PoseDelta, TeleopCommand
    from teleop_targets import (
        _normalize_quaternion,
        _quaternion_conjugate,
        _quaternion_multiply,
        pose_world_to_base,
    )

    if side not in ("left", "right"):
        raise ValueError("side must be 'left' or 'right'")

    target_base = pose_world_to_base(
        world_target, base_position, base_orientation_wxyz
    )
    current_orientation = _normalize_quaternion(
        current_base_target.orientation_wxyz
    )
    delta_quaternion = _quaternion_multiply(
        target_base.orientation_wxyz,
        _quaternion_conjugate(current_orientation),
    )
    delta = PoseDelta(
        translation=tuple(
            target - current
            for target, current in zip(
                target_base.position, current_base_target.position
            )
        ),
        rotation_rpy=rpy_from_quaternion(delta_quaternion),
    )
    kwargs = {"left_pose": delta} if side == "left" else {"right_pose": delta}
    return TeleopCommand(
        timestamp=timestamp,
        source="task3_autonomy.reach",
        active=True,
        **kwargs,
    )


def gripper_holds_object(
    position_rad: float,
    *,
    min_position_rad: float = DEFAULT_HOLD_MIN_POSITION_RAD,
    max_position_rad: float = DEFAULT_HOLD_MAX_POSITION_RAD,
) -> bool:
    """Return whether an object stopped closure before the 0 rad limit."""
    values = (position_rad, min_position_rad, max_position_rad)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("gripper positions must be finite")
    if min_position_rad < 0.0 or max_position_rad <= min_position_rad:
        raise ValueError("gripper hold bounds must be positive and ordered")
    return min_position_rad < position_rad < max_position_rad


def _quaternion_angle_error(
    measured: Sequence[float], target: Sequence[float]
) -> float:
    from teleop_targets import _normalize_quaternion

    measured_q = _normalize_quaternion(tuple(measured))
    target_q = _normalize_quaternion(tuple(target))
    dot = abs(sum(a * b for a, b in zip(measured_q, target_q)))
    return 2.0 * math.acos(max(-1.0, min(1.0, dot)))


class DualArmController:
    """Absolute-world manipulation interface over the teleop/Lula runtime."""

    def __init__(self, robot: Any, simulation_app: Any) -> None:
        from dual_arm_lula import (
            LEFT_ARM_JOINTS,
            RIGHT_ARM_JOINTS,
            create_raw_dual_arm_lula,
        )
        from scene_robot_room_keyboard import (
            enable_motion_generation_extension,
            measured_position_targets,
            robot_root_world_pose,
        )
        from teleop_targets import (
            CartesianTargetTracker,
            TargetLimits,
            compose_position_targets,
            discover_joint_groups,
            pose_base_to_world,
            position_target_subset,
        )

        import omni.kit.app

        self._CartesianTargetTracker = CartesianTargetTracker
        self._TargetLimits = TargetLimits
        self._compose = compose_position_targets
        self._pose_base_to_world = pose_base_to_world
        self._subset = position_target_subset
        self._measured_position_targets = measured_position_targets
        self._root_pose = robot_root_world_pose
        self._left_arm_joint_names = LEFT_ARM_JOINTS
        self._right_arm_joint_names = RIGHT_ARM_JOINTS

        self.robot = robot
        enable_motion_generation_extension(
            omni.kit.app.get_app().get_extension_manager()
        )
        self.joint_groups = discover_joint_groups(robot.joint_names)
        self._default_gripper_effort_limits = {
            side: self._gripper_effort_limit(side)
            for side in ("left", "right")
        }
        self._position_targets = measured_position_targets(robot)
        self._ik = create_raw_dual_arm_lula(
            robot.joint_names,
            lambda: robot.data.joint_pos[0].detach().cpu().numpy(),
        )
        self._tracker = None
        self.sync_targets_from_measured()

    def _measured_spine(self) -> float:
        return float(
            self.robot.data.joint_pos[0, self.joint_groups.spine[0]].item()
        )

    def measured_spine_position(self) -> float:
        """Return the live prismatic spine position in metres."""
        return self._measured_spine()

    def sync_targets_from_measured(self) -> None:
        """Re-anchor tracker targets after direct-joint transit motions."""
        from teleop_targets import Pose, TeleopTargets, pose_world_to_base

        root_position, root_orientation = self._root_pose(self.robot)
        spine = self._measured_spine()
        left_world, right_world = self._ik.current_end_effector_poses(
            root_position, root_orientation, spine
        )
        left_relative = pose_world_to_base(
            Pose(tuple(left_world[0]), tuple(left_world[1])),
            root_position,
            root_orientation,
        )
        right_relative = pose_world_to_base(
            Pose(tuple(right_world[0]), tuple(right_world[1])),
            root_position,
            root_orientation,
        )
        positions = self.robot.data.joint_pos[0]
        left_gripper = float(
            positions[self.joint_groups.left_gripper[0]].item()
        )
        right_gripper = float(
            positions[self.joint_groups.right_gripper[0]].item()
        )
        self._tracker = self._CartesianTargetTracker(
            TeleopTargets(
                left=left_relative,
                right=right_relative,
                left_gripper=left_gripper,
                right_gripper=right_gripper,
                spine=spine,
            ),
            limits=self._TargetLimits(
                position_min=(-1.5, -1.5, -0.5),
                position_max=(1.5, 1.5, 2.5),
                gripper_min=0.0,
                gripper_max=1.0,
                spine_min=0.0,
                spine_max=0.85,
            ),
        )
        self._position_targets = self._measured_position_targets(self.robot)

    @property
    def spine(self) -> float:
        return float(self._tracker.targets.spine)

    @spine.setter
    def spine(self, position_m: float) -> None:
        from teleop_commands import TeleopCommand

        delta = float(position_m) - self.spine
        self._tracker.apply(
            TeleopCommand(
                timestamp=0.0,
                source="task3_autonomy.spine",
                active=True,
                spine_delta=delta,
            )
        )

    def ee_world_poses(self):
        """Measured ``(position, quat_wxyz)`` world pose for each arm."""
        root_position, root_orientation = self._root_pose(self.robot)
        left, right = self._ik.current_end_effector_poses(
            root_position, root_orientation, self._measured_spine()
        )
        return (
            (tuple(left[0]), tuple(left[1])),
            (tuple(right[0]), tuple(right[1])),
        )

    def arm_pose_relative(self, side: str):
        """Return a measured end-effector pose in the robot-base frame."""
        from teleop_targets import Pose, pose_world_to_base

        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        pose = self.ee_world_poses()[0 if side == "left" else 1]
        root_position, root_orientation = self._root_pose(self.robot)
        return pose_world_to_base(
            Pose(tuple(pose[0]), tuple(pose[1])),
            root_position,
            root_orientation,
        )

    def set_arm_target(self, side: str, position, quat_wxyz) -> None:
        """Apply one ``TeleopCommand`` that sets an absolute world target."""
        from teleop_targets import Pose, pose_world_to_base

        world_target = Pose(tuple(position), tuple(quat_wxyz))
        root_position, root_orientation = self._root_pose(self.robot)
        current = getattr(self._tracker.targets, side, None)
        if current is None:
            raise ValueError("side must be 'left' or 'right'")
        command = one_step_reach_command(
            current,
            world_target,
            root_position,
            root_orientation,
            side=side,
        )
        updated = self._tracker.apply(command)
        actual = getattr(updated, side)
        requested = pose_world_to_base(
            world_target, root_position, root_orientation
        )
        position_error = math.sqrt(
            sum(
                (a - b) ** 2
                for a, b in zip(actual.position, requested.position)
            )
        )
        orientation_error = _quaternion_angle_error(
            actual.orientation_wxyz, requested.orientation_wxyz
        )
        if position_error > 1.0e-8 or orientation_error > 1.0e-7:
            raise ValueError(
                "world target lies outside CartesianTargetTracker limits"
            )

    def set_arm_target_relative(self, side: str, position, quat_wxyz) -> None:
        """Set an arm target expressed in the current robot-base frame.

        This is the carry counterpart to :meth:`set_arm_target`: a held
        object should move with the robot base rather than leave its gripper
        target fixed in the world while the robot drives through the room.
        """
        from teleop_targets import Pose

        root_position, root_orientation = self._root_pose(self.robot)
        world_target = self._pose_base_to_world(
            Pose(tuple(position), tuple(quat_wxyz)),
            root_position,
            root_orientation,
        )
        self.set_arm_target(
            side, world_target.position, world_target.orientation_wxyz
        )

    def set_gripper(self, side: str, position_rad: float) -> None:
        from teleop_commands import TeleopCommand

        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        field = f"{side}_gripper"
        current = float(getattr(self._tracker.targets, field))
        kwargs = {f"{field}_delta": float(position_rad) - current}
        self._tracker.apply(
            TeleopCommand(
                timestamp=0.0,
                source="task3_autonomy.gripper",
                active=True,
                **kwargs,
            )
        )

    def gripper_position(self, side: str) -> float:
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        ids = getattr(self.joint_groups, f"{side}_gripper")
        return float(self.robot.data.joint_pos[0, ids[0]].item())

    def _gripper_effort_limit(self, side: str) -> float:
        """Return the authored effort limit for a primary gripper joint."""
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        limits = getattr(self.robot.data, "joint_effort_limits", None)
        if limits is None:
            raise RuntimeError("robot does not expose joint effort limits")
        joint_id = getattr(self.joint_groups, f"{side}_gripper")[0]
        limit = float(limits[0, joint_id].item())
        if not math.isfinite(limit) or limit <= 0.0:
            raise RuntimeError(
                "gripper authored effort limit must be positive"
            )
        return limit

    def set_gripper_effort_scale(self, side: str, scale: float) -> None:
        """Scale the gripper's authored maximum effort for physical closure."""
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        if not math.isfinite(scale) or not 0.0 < scale <= 1.0:
            raise ValueError("effort scale must be finite and in (0, 1]")
        joint_ids = getattr(self.joint_groups, f"{side}_gripper")
        self.robot.write_joint_effort_limit_to_sim(
            self._default_gripper_effort_limits[side] * scale,
            joint_ids=joint_ids,
        )

    def restore_gripper_effort_limit(self, side: str) -> None:
        """Restore the gripper's authored maximum effort limit."""
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        joint_ids = getattr(self.joint_groups, f"{side}_gripper")
        self.robot.write_joint_effort_limit_to_sim(
            self._default_gripper_effort_limits[side],
            joint_ids=joint_ids,
        )

    def command(self):
        """Solve the current tracker targets and write articulation targets."""
        targets = self._tracker.targets
        root_position, root_orientation = self._root_pose(self.robot)
        left_world = self._pose_base_to_world(
            targets.left, root_position, root_orientation
        )
        right_world = self._pose_base_to_world(
            targets.right, root_position, root_orientation
        )
        ik_result = self._ik.solve(
            left_world.position,
            right_world.position,
            left_world.orientation_wxyz,
            right_world.orientation_wxyz,
            spine_position=targets.spine,
            base_position=root_position,
            base_orientation_wxyz=root_orientation,
        )
        left_arm = ordered_joint_targets(
            ik_result.left, self._left_arm_joint_names
        )
        right_arm = ordered_joint_targets(
            ik_result.right, self._right_arm_joint_names
        )
        self._position_targets = self._compose(
            self._position_targets,
            self.joint_groups,
            left_arm=left_arm,
            right_arm=right_arm,
            left_gripper=targets.left_gripper,
            right_gripper=targets.right_gripper,
            spine=targets.spine,
        )
        position_targets, joint_ids = self._subset(
            self._position_targets, self.joint_groups
        )
        self.robot.set_joint_position_target(
            position_targets, joint_ids=joint_ids
        )
        return ik_result

    def pose_error(
        self, side: str, position, quat_wxyz
    ) -> tuple[float, float]:
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        measured = self.ee_world_poses()[0 if side == "left" else 1]
        position_error = math.sqrt(
            sum((m - t) ** 2 for m, t in zip(measured[0], position))
        )
        return position_error, _quaternion_angle_error(measured[1], quat_wxyz)

    def position_error(self, side: str, target_position) -> float:
        if side not in ("left", "right"):
            raise ValueError("side must be 'left' or 'right'")
        measured = self.ee_world_poses()[0 if side == "left" else 1][0]
        return math.sqrt(
            sum((m - t) ** 2 for m, t in zip(measured, target_position))
        )

    def reach(
        self,
        side: str,
        position,
        quat_wxyz,
        *,
        step: Callable[[], None],
        dt: float,
        timeout_s: float,
        position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
        orientation_tolerance_rad: float = DEFAULT_ORIENTATION_TOLERANCE_RAD,
    ) -> bool:
        """Reach a world pose, returning False on explicit timeout."""
        if dt <= 0.0 or timeout_s < 0.0:
            raise ValueError("dt must be positive and timeout_s non-negative")
        for _ in range(math.ceil(timeout_s / dt)):
            # Tracker poses are base-relative. Reissue the absolute target
            # every tick so base reaction/drift cannot carry the goal away.
            self.set_arm_target(side, position, quat_wxyz)
            ik_result = self.command()
            step()
            position_error, orientation_error = self.pose_error(
                side, position, quat_wxyz
            )
            succeeded = (
                ik_result.left_succeeded
                if side == "left"
                else ik_result.right_succeeded
            )
            if (
                succeeded
                and position_error <= position_tolerance_m
                and orientation_error <= orientation_tolerance_rad
            ):
                return True
        position_error, orientation_error = self.pose_error(
            side, position, quat_wxyz
        )
        return (
            position_error <= position_tolerance_m
            and orientation_error <= orientation_tolerance_rad
        )

    def grasp(
        self,
        side: str,
        *,
        step: Callable[[], None],
        dt: float,
        settle_seconds: float = 1.5,
        ramp_seconds: float = 1.0,
        close_effort_scale: float | None = None,
    ) -> bool:
        """Soft-close, settle, then confirm an object blocks full closure."""
        if (
            dt <= 0.0
            or settle_seconds < 0.0
            or ramp_seconds < 0.0
            or ramp_seconds > settle_seconds
        ):
            raise ValueError(
                "dt must be positive and 0 <= ramp_seconds <= settle_seconds"
            )
        start_position = self.gripper_position(side)
        if close_effort_scale is not None:
            self.set_gripper_effort_scale(side, close_effort_scale)
        ramp_ticks = max(1, math.ceil(ramp_seconds / dt))
        for tick in range(math.ceil(settle_seconds / dt)):
            target = linear_ramp_target(
                start_position,
                GRIPPER_CLOSED_RAD,
                tick + 1,
                ramp_ticks,
            )
            self.set_gripper(side, target)
            self.command()
            step()
        return gripper_holds_object(self.gripper_position(side))

    def release(
        self,
        side: str,
        *,
        step: Callable[[], None],
        dt: float,
        timeout_s: float = 1.5,
        tolerance_rad: float = 0.02,
    ) -> bool:
        """Open the gripper and return False if it misses the timeout."""
        if dt <= 0.0 or timeout_s < 0.0:
            raise ValueError("dt must be positive and timeout_s non-negative")
        self.restore_gripper_effort_limit(side)
        self.set_gripper(side, GRIPPER_OPEN_RAD)
        for _ in range(math.ceil(timeout_s / dt)):
            self.command()
            step()
            if (
                abs(self.gripper_position(side) - GRIPPER_OPEN_RAD)
                <= tolerance_rad
            ):
                return True
        return (
            abs(self.gripper_position(side) - GRIPPER_OPEN_RAD)
            <= tolerance_rad
        )

    def move_spine(
        self,
        position_m: float,
        *,
        step: Callable[[], None],
        dt: float,
        timeout_s: float = 4.0,
        tolerance_m: float = 0.01,
    ) -> bool:
        """Move the spine with measured convergence and an explicit timeout."""
        if dt <= 0.0 or timeout_s < 0.0:
            raise ValueError("dt must be positive and timeout_s non-negative")
        self.spine = position_m
        for _ in range(math.ceil(timeout_s / dt)):
            self.command()
            step()
            if abs(self._measured_spine() - position_m) <= tolerance_m:
                return True
        return abs(self._measured_spine() - position_m) <= tolerance_m

    def lift(
        self,
        side: str,
        dz: float,
        *,
        step: Callable[[], None],
        dt: float,
        timeout_s: float,
        position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
        ramp_seconds: float = 3.0,
        spine_assist_m: float = 0.0,
    ) -> bool:
        """Raise vertically with a bounded ramp while holding attitude.

        A full-height position step can accelerate a pinched object sideways
        before the fingers have developed a stable contact.  The ramp keeps
        every intermediate IK request close to the measured configuration and
        leaves the remainder of ``timeout_s`` for convergence at full height.
        """
        if (
            dt <= 0.0
            or timeout_s < 0.0
            or ramp_seconds < 0.0
            or ramp_seconds > timeout_s
            or spine_assist_m < 0.0
        ):
            raise ValueError(
                "dt must be positive, 0 <= ramp_seconds <= timeout_s, "
                "and spine_assist_m non-negative"
            )
        measured = self.ee_world_poses()[0 if side == "left" else 1]
        start_spine = self.spine
        start_position = measured[0]
        final_position = (
            start_position[0],
            start_position[1],
            start_position[2] + float(dz),
        )
        ramp_ticks = max(1, math.ceil(ramp_seconds / dt))
        timeout_ticks = math.ceil(timeout_s / dt)
        for tick in range(timeout_ticks):
            completed_steps = tick + 1
            target = (
                start_position[0],
                start_position[1],
                linear_ramp_target(
                    start_position[2],
                    final_position[2],
                    completed_steps,
                    ramp_ticks,
                ),
            )
            if spine_assist_m > 0.0:
                self.spine = linear_ramp_target(
                    start_spine,
                    start_spine + spine_assist_m,
                    completed_steps,
                    ramp_ticks,
                )
            self.set_arm_target(side, target, measured[1])
            ik_result = self.command()
            step()
            if tick + 1 < ramp_ticks:
                continue
            position_error, orientation_error = self.pose_error(
                side, final_position, measured[1]
            )
            succeeded = (
                ik_result.left_succeeded
                if side == "left"
                else ik_result.right_succeeded
            )
            if (
                succeeded
                and position_error <= position_tolerance_m
                and orientation_error <= DEFAULT_ORIENTATION_TOLERANCE_RAD
            ):
                return True
        position_error, orientation_error = self.pose_error(
            side, final_position, measured[1]
        )
        return (
            position_error <= position_tolerance_m
            and orientation_error <= DEFAULT_ORIENTATION_TOLERANCE_RAD
        )

    def place(self, side: str, position, quat_wxyz, **kwargs) -> bool:
        """Place is the pose-convergent motion portion of reach→release."""
        return self.reach(side, position, quat_wxyz, **kwargs)
