# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Task 3 FSM skills: waypoint navigation logic and the Isaac base adapter.

NavigateTo is pure logic over Pose2D (CPU-tested in tests/test_skills.py).
TmrBaseAdapter is the thin Isaac-side shim that turns the skill's body-frame
twists into TMR steering/wheel joint targets via
scripts/common/tmr_base_control.py -- it is exercised on GPU by
scripts/task3/verify_navigate.py, never by CPU tests.
"""

from __future__ import annotations

import math

from task3_autonomy.navigation import (
    Pose2D,
    base_twist_toward,
    pose_reached,
    route_via_door,
)

# Intermediate waypoints only shape the route around the wall partition, so
# they can be passed loosely; only the final stop uses the strict tolerance.
WAYPOINT_PASS_TOLERANCE_M = 0.15

# Arm transit pose for navigation: the default ready pose spans 1.88 m
# across the outboard-mounted arms while both partition crossings measure
# ~1.2 m (probe_arm_tuck.py, sim-dev-g4b 2026-07-17). This is the probe's
# measured winner "lean_pnn": settled body-frame width +-0.37 m at link
# origins (vs +-0.75 default), max joint-target error 0.024 rad.
TRANSIT_ARM_POSE: dict[str, float] = {
    "left_fr3v2_joint1": 1.57,
    "left_fr3v2_joint2": -0.87,
    "left_fr3v2_joint3": -1.57,
    "left_fr3v2_joint4": -2.9,
    "left_fr3v2_joint5": 0.0,
    "left_fr3v2_joint6": 2.9,
    "left_fr3v2_joint7": 0.785,
    "right_fr3v2_joint1": -1.57,
    "right_fr3v2_joint2": -0.87,
    "right_fr3v2_joint3": 1.57,
    "right_fr3v2_joint4": -2.9,
    "right_fr3v2_joint5": 0.0,
    "right_fr3v2_joint6": 2.9,
    "right_fr3v2_joint7": 0.785,
}


def ramp_arm_pose(
    robot,
    pose: dict[str, float],
    *,
    step,
    ramp_steps: int = 300,
    settle_steps: int = 200,
) -> None:
    """Ramp arm joint position targets to `pose`, calling `step()` per tick.

    GPU-only helper (lazy torch import). `step` must advance the sim one
    tick (write targets, step physics, update scene); targets persist in
    the articulation's buffer afterward, so the arms hold the pose while
    later code drives the base.
    """
    if not pose:
        return
    import torch

    names = sorted(pose)
    joint_ids = [robot.joint_names.index(n) for n in names]
    device = robot.data.joint_pos.device
    start = robot.data.joint_pos[0, joint_ids].clone()
    target = torch.tensor(
        [pose[n] for n in names], device=device, dtype=start.dtype
    )
    for tick in range(ramp_steps):
        alpha = (tick + 1) / ramp_steps
        robot.set_joint_position_target(
            ((1.0 - alpha) * start + alpha * target).unsqueeze(0),
            joint_ids=joint_ids,
        )
        step()
    for _ in range(settle_steps):
        robot.set_joint_position_target(
            target.unsqueeze(0), joint_ids=joint_ids
        )
        step()


class NavigateTo:
    """Drive an omnidirectional base through door-aware waypoints to a target.

    Call compute(pose) every control step; it returns (vx, vy, done) in the
    body frame. Yaw is not commanded here -- the caller holds heading with
    tmr_base_control.compensate_yaw_rate().
    """

    def __init__(
        self,
        target_xy: tuple[float, float],
        target_yaw: float | None = None,
        *,
        max_linear_mps: float = 0.5,
        position_kp: float = 1.5,
        position_tolerance_m: float = 0.03,
        yaw_tolerance_rad: float = math.radians(3.0),
    ) -> None:
        self.target_xy = target_xy
        self.target_yaw = target_yaw
        self.max_linear_mps = max_linear_mps
        self.position_kp = position_kp
        self.position_tolerance_m = position_tolerance_m
        self.yaw_tolerance_rad = yaw_tolerance_rad
        self._waypoints: list[tuple[float, float]] | None = None
        self._waypoint_index = 0
        self._done = False

    def compute(self, pose: Pose2D) -> tuple[float, float, bool]:
        if self._done:
            return 0.0, 0.0, True
        if self._waypoints is None:
            self._waypoints = route_via_door(
                (pose.x, pose.y), self.target_xy
            )
            self._waypoint_index = 1 if len(self._waypoints) > 1 else 0

        while self._waypoint_index < len(self._waypoints) - 1:
            waypoint = self._waypoints[self._waypoint_index]
            if pose_reached(
                pose,
                waypoint,
                position_tolerance_m=WAYPOINT_PASS_TOLERANCE_M,
            ):
                self._waypoint_index += 1
            else:
                break

        final_leg = self._waypoint_index >= len(self._waypoints) - 1
        if final_leg and pose_reached(
            pose,
            self.target_xy,
            self.target_yaw,
            position_tolerance_m=self.position_tolerance_m,
            yaw_tolerance_rad=self.yaw_tolerance_rad,
        ):
            self._done = True
            return 0.0, 0.0, True

        goal = (
            self.target_xy
            if final_leg
            else self._waypoints[self._waypoint_index]
        )
        vx, vy = base_twist_toward(
            pose,
            goal,
            max_linear_mps=self.max_linear_mps,
            position_kp=self.position_kp,
        )
        return vx, vy, False


class TmrBaseAdapter:
    """Isaac-side shim: body twist -> TMR steering/wheel joint targets.

    GPU-only (imports torch-backed helpers lazily); verified by
    scripts/task3/verify_navigate.py, not by CPU tests.
    """

    # Wheel velocity-drive damping the wheels actually need: 5.0 left them
    # at ~7% of target; 500 tracks within 2 s (probe_base_drive.py,
    # sim-dev-g4b 2026-07-17). Written directly to PhysX here because the
    # same value in robot_actuator_cfg_specs did NOT reach the sim (the two
    # live runs crawled identically before and after that config change) --
    # the runtime tensor write is the delivery mechanism proven by the
    # probe. The readback print below records what the sim had, as
    # evidence for root-causing the config path later.
    DRIVE_DAMPING = 500.0

    def __init__(self, robot, *, num_envs: int, device: str) -> None:
        import torch

        import tmr_base_control as base

        self._base = base
        self.robot = robot
        self.num_envs = num_envs
        self.device = device
        self.steering_ids, self.drive_ids = base.find_drive_joint_ids(
            robot.joint_names
        )
        self._hold_yaw = base.get_root_yaw(robot)

        sim_damping = getattr(robot.data, "joint_damping", None)
        if sim_damping is not None:
            print(
                "TmrBaseAdapter: sim wheel damping before override: "
                f"{[round(float(sim_damping[0, i]), 3) for i in self.drive_ids]}",
                flush=True,
            )
        robot.write_joint_damping_to_sim(
            torch.full(
                (num_envs, len(self.drive_ids)),
                self.DRIVE_DAMPING,
                device=device,
            ),
            joint_ids=self.drive_ids,
        )
        print(
            f"TmrBaseAdapter: wheel drive damping set to {self.DRIVE_DAMPING}",
            flush=True,
        )

    def pose(self) -> Pose2D:
        position = self.robot.data.root_pos_w[0]
        return Pose2D(
            float(position[0]),
            float(position[1]),
            self._base.get_root_yaw(self.robot),
        )

    def apply_twist(self, vx: float, vy: float) -> None:
        wz, self._hold_yaw = self._base.compensate_yaw_rate(
            self.robot, vx, vy, 0.0, self._hold_yaw, manual_rotation=False
        )
        steering_targets, drive_targets = self._base.compute_drive_targets(
            self.robot,
            self.steering_ids,
            vx,
            vy,
            wz,
            num_envs=self.num_envs,
            device=self.device,
        )
        self.robot.set_joint_position_target(
            steering_targets, joint_ids=self.steering_ids
        )
        self.robot.set_joint_velocity_target(
            drive_targets, joint_ids=self.drive_ids
        )
