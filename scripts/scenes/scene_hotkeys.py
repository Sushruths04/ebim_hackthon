#!/usr/bin/env python3
"""Hotkey teleoperation for Task 3 tray transport.

Adds one-key shortcuts to the standard keyboard teleop:
  F1 = Move right arm above tray, open gripper
  F2 = Close gripper (grab tray)
  F3 = Lift tray 15cm
  F4 = Open gripper (release tray)
  F5 = Right arm to READY pose (tuck)
  F6 = Raise spine to 0.45m

All other keyboard controls (WASD arm, SHIFT+base) still work.
Drive to the tray with SHIFT+H/N/B/M, then press F1 to position the arm.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
for import_path in (SCENES_DIR, COMMON_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="task3")
    parser.add_argument("--head-placement", default="a")
    parser.add_argument("--keyboard-control", action="store_true", default=True)
    parser.add_argument("--livestream", action="store_true")
    parser.add_argument("--public-ip", default=os.environ.get("PUBLIC_IP"))
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    if args.livestream and args.public_ip:
        os.environ["PUBLIC_IP"] = args.public_ip

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({
        "headless": args.headless,
        "enable_cameras": bool(args.livestream),
        "livestream": 1 if args.livestream else -1,
    })
    simulation_app = app_launcher.app

    try:
        _run_hotkey_teleop(args, simulation_app)
    except BaseException:
        import traceback
        traceback.print_exc()
        raise
    finally:
        simulation_app.close()


def _run_hotkey_teleop(args: argparse.Namespace, simulation_app: Any) -> None:
    from scene_robot_room_keyboard import (
        TASK_ROBOT_POSES,
        build_stage,
        configure_keyboard_control_stage,
    )

    import omni.kit.app

    robot_pose = TASK_ROBOT_POSES[args.task]
    room_path = Path(__file__).resolve().parents[2] / "assets" / "robot_room.usd"
    robot_usd_path = (
        Path("/workspace/EBiM_Challenge/third_party/franka_description/urdfs")
        / "configuration/mobile_fr3_duo_v0_2_franka_hand.usd"
    )

    stage = omni.kit.app.get_app().get_stage()
    configure_keyboard_control_stage(
        build_stage,
        omni.kit.app.get_app(),
        stage,
        room_usd=room_path,
        robot_usd=robot_usd_path,
        task=args.task,
        head_placement=args.head_placement,
        robot_position=robot_pose["position"],
        robot_rotation=_yaw_to_quat(robot_pose["yaw"]),
        robot_yaw=robot_pose["yaw"],
    )

    _run_control_loop(simulation_app, args)


def _yaw_to_quat(yaw_deg: float) -> tuple[float, float, float, float]:
    yaw_rad = math.radians(yaw_deg)
    return (math.cos(yaw_rad / 2), 0.0, 0.0, math.sin(yaw_rad / 2))


def _run_control_loop(simulation_app: Any, args: argparse.Namespace) -> None:
    from dual_arm_lula import LEFT_ARM_JOINTS, RIGHT_ARM_JOINTS, create_raw_dual_arm_lula
    from keyboard_arm_teleop import (
        KeyboardTeleopMapper,
        control_help,
    )
    from scene_robot_room_keyboard import (
        DirectJointTargetLatch,
        create_keyboard_teleop,
        disable_robot_external_wrenches,
        drive_joint_ids,
        enable_motion_generation_extension,
        get_root_yaw,
        measured_position_targets,
        print_keyboard_control_help,
        robot_root_world_pose,
        safe_command,
        steering_joint_ids,
    )
    from teleop_commands import PoseDelta, TeleopCommand
    from teleop_targets import (
        CartesianTargetTracker,
        Pose,
        TargetLimits,
        compose_position_targets,
        discover_joint_groups,
        normalize_quaternion,
        pose_base_to_world,
        pose_world_to_base,
        position_target_subset,
    )
    from tmr_base_control import compensate_yaw_rate, compute_drive_targets

    import omni.kit.app
    from pxr import UsdGeom

    sim = simulation_app

    scene_prim = UsdGeom.Xform.Define(
        omni.kit.app.get_app().get_stage(), "/World/envs"
    )

    robot = None
    scene = None
    with suppress(Exception):
        from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
        from isaaclab.assets import Articulation
        robot_cfg = None
        for _try in range(10):
            sim.update()
        robot_path = "/World/envs/env_0/Robot"
        robot = Articulation(robot_path)

    if robot is None:
        print("ERROR: Could not find robot articulation", flush=True)
        return

    robot.initialize()
    sim.update()

    joint_names = list(robot.joint_names)
    joint_groups = discover_joint_groups(joint_names)
    position_targets = measured_position_targets(robot)

    enable_motion_generation_extension(
        omni.kit.app.get_app().get_extension_manager()
    )

    steering_indices = steering_joint_ids(joint_names)
    drive_indices = drive_joint_ids(joint_names)

    dual_arm_ik = create_raw_dual_arm_lula(
        joint_names,
        lambda: robot.data.joint_pos[0].detach().cpu().numpy(),
    )

    root_position, root_orientation = robot_root_world_pose(robot)
    spine_idx = joint_groups.spine[0]
    initial_spine = float(robot.data.joint_pos[0, spine_idx].item())

    left_world_values, right_world_values = dual_arm_ik.current_end_effector_poses(
        root_position, root_orientation, initial_spine,
    )
    from teleop_targets import pose_world_to_base
    left_relative = pose_world_to_base(
        Pose(tuple(left_world_values[0]), tuple(left_world_values[1])),
        root_position, root_orientation,
    )
    right_relative = pose_world_to_base(
        Pose(tuple(right_world_values[0]), tuple(right_world_values[1])),
        root_position, root_orientation,
    )

    initial_left_gripper = float(position_targets[0, joint_groups.left_gripper[0]].item())
    initial_right_gripper = float(position_targets[0, joint_groups.right_gripper[0]].item())

    tracker = CartesianTargetTracker(
        targets=__import__("teleop_targets").TeleopTargets(
            left=left_relative,
            right=right_relative,
            left_gripper=initial_left_gripper,
            right_gripper=initial_right_gripper,
            spine=initial_spine,
        ),
        limits=TargetLimits(
            position_min=(-1.5, -1.5, -0.5),
            position_max=(1.5, 1.5, 2.5),
            gripper_min=0.0,
            gripper_max=1.0,
            spine_min=0.0,
            spine_max=0.85,
        ),
    )

    mapper = KeyboardTeleopMapper()
    direct_joint_latch = DirectJointTargetLatch()
    heading_hold_yaw = get_root_yaw(robot)
    teleop = create_keyboard_teleop()

    PREGRASP_RIGHT_POSITION = (0.50, -0.20, 0.90)
    PREGRASP_RIGHT_QUAT = (1.0, 0.0, 0.0, 0.0)
    LIFT_DZ = 0.15
    SPINE_UP = 0.45
    GRIPPER_OPEN = 0.9
    GRIPPER_CLOSED = 0.0

    hotkey_actions: dict[str, str] = {}
    pending_action: str | None = None
    action_ticks_remaining: int = 0
    action_start_targets: Any = None

    print("=" * 60)
    print("HOTKEY TELEOP READY")
    print("=" * 60)
    print("F1 = Arm to tray + open gripper")
    print("F2 = Close gripper (grab tray)")
    print("F3 = Lift tray 15cm")
    print("F4 = Open gripper (release tray)")
    print("F5 = Arm to ready pose")
    print("F6 = Raise spine")
    print("SHIFT + H/N/B/M = Drive")
    print("WASD = Fine arm control")
    print("ESC = Exit")
    print("=" * 60)

    teleop.start()
    count = 0
    try:
        while simulation_app.is_running() and not teleop.stop_requested:
            now = time.monotonic()

            pressed = set(teleop.pressed)

            fkey = None
            for fk in ("f1", "f2", "f3", "f4", "f5", "f6"):
                if fk in pressed:
                    fkey = fk
                    break

            if fkey and fkey not in hotkey_actions:
                hotkey_actions[fkey] = True
                pending_action = fkey
            elif not fkey:
                hotkey_actions.clear()

            if pending_action and action_ticks_remaining <= 0:
                _execute_hotkey(
                    pending_action,
                    tracker,
                    robot,
                    joint_groups,
                    root_position,
                    root_orientation,
                    PREGRASP_RIGHT_POSITION,
                    PREGRASP_RIGHT_QUAT,
                    LIFT_DZ,
                    SPINE_UP,
                    GRIPPER_OPEN,
                    GRIPPER_CLOSED,
                )
                pending_action = None

            if action_ticks_remaining > 0:
                action_ticks_remaining -= 1
                command = TeleopCommand(
                    timestamp=now, source="hotkey", active=True,
                )
            else:
                command = mapper.map_keys(pressed, timestamp=now, dt=sim.cfg.dt)

            command = safe_command(command, now=now, timeout=0.25)
            command = clamp_direct_joint_command(command, robot, joint_groups)

            vx, vy, wz_cmd = command.base_twist
            wz, heading_hold_yaw = compensate_yaw_rate(
                robot, vx, vy, wz_cmd, heading_hold_yaw,
                manual_rotation=abs(wz_cmd) > 1.0e-4,
            )

            targets = tracker.apply(command)
            root_position, root_orientation = robot_root_world_pose(robot)
            left_world = pose_base_to_world(targets.left, root_position, root_orientation)
            right_world = pose_base_to_world(targets.right, root_position, root_orientation)

            ik_result = dual_arm_ik.solve(
                left_world.position, right_world.position,
                left_world.orientation_wxyz, right_world.orientation_wxyz,
                spine_position=targets.spine,
                base_position=root_position,
                base_orientation_wxyz=root_orientation,
            )

            left_arm_targets, right_arm_targets = direct_joint_latch.select(
                command, ik_result, LEFT_ARM_JOINTS, RIGHT_ARM_JOINTS,
            )

            position_targets = compose_position_targets(
                position_targets, joint_groups,
                left_arm=left_arm_targets,
                right_arm=right_arm_targets,
                left_gripper=targets.left_gripper,
                right_gripper=targets.right_gripper,
                spine=targets.spine,
            )

            arm_position_targets, arm_position_joint_ids = position_target_subset(
                position_targets, joint_groups,
            )
            robot.set_joint_position_target(arm_position_targets, joint_ids=arm_position_joint_ids)

            steering_pos_targets, drive_vel_targets = compute_drive_targets(
                robot, steering_indices, vx, vy, wz,
                num_envs=1, device=sim.device,
            )
            robot.set_joint_position_target(steering_pos_targets, joint_ids=steering_indices)
            robot.set_joint_velocity_target(drive_vel_targets, joint_ids=drive_indices)

            disable_robot_external_wrenches(robot)
            scene.write_data_to_sim() if hasattr(scene, 'write_data_to_sim') else None
            sim.step()
            if hasattr(scene, 'update'):
                scene.update(sim.cfg.dt)

            count += 1
            if count % 200 == 0:
                rp = robot_root_world_pose(robot)
                rpos = rp[0]
                print(f"step={count} base=({rpos[0]:.2f},{rpos[1]:.2f}) "
                      f"keys={sorted(pressed)[:5]}", flush=True)
    finally:
        teleop.stop()


def _execute_hotkey(
    key: str,
    tracker: Any,
    robot: Any,
    joint_groups: Any,
    root_position: Any,
    root_orientation: Any,
    pregrasp_pos: tuple,
    pregrasp_quat: tuple,
    lift_dz: float,
    spine_up: float,
    gripper_open: float,
    gripper_closed: float,
) -> None:
    from teleop_commands import PoseDelta, TeleopCommand
    from teleop_targets import Pose, pose_world_to_base

    targets = tracker.targets
    current_right = targets.right
    current_spine = targets.spine

    if key == "f1":
        world_target = Pose(pregrasp_pos, pregrasp_quat)
        base_target = pose_world_to_base(world_target, root_position, root_orientation)
        delta_pos = tuple(b - c for b, c in zip(base_target.position, current_right.position))
        delta_quat = (1.0, 0.0, 0.0, 0.0)
        tracker.apply(TeleopCommand(
            timestamp=0.0, source="hotkey_f1", active=True,
            right_pose=PoseDelta(translation=delta_pos, rotation_rpy=(0.0, 0.0, 0.0)),
            right_gripper_delta=gripper_open - targets.right_gripper,
        ))
        print("F1: Arm to pre-grasp, gripper open", flush=True)

    elif key == "f2":
        tracker.apply(TeleopCommand(
            timestamp=0.0, source="hotkey_f2", active=True,
            right_gripper_delta=gripper_closed - targets.right_gripper,
        ))
        print("F2: Gripper closing", flush=True)

    elif key == "f3":
        delta = (0.0, 0.0, lift_dz)
        tracker.apply(TeleopCommand(
            timestamp=0.0, source="hotkey_f3", active=True,
            right_pose=PoseDelta(translation=delta, rotation_rpy=(0.0, 0.0, 0.0)),
        ))
        spine_delta = spine_up - current_spine
        if spine_delta > 0.01:
            tracker.apply(TeleopCommand(
                timestamp=0.0, source="hotkey_f3_spine", active=True,
                spine_delta=spine_delta,
            ))
        print(f"F3: Lift +{lift_dz:.2f}m, spine to {spine_up:.2f}m", flush=True)

    elif key == "f4":
        tracker.apply(TeleopCommand(
            timestamp=0.0, source="hotkey_f4", active=True,
            right_gripper_delta=gripper_open - targets.right_gripper,
        ))
        print("F4: Gripper open (release)", flush=True)

    elif key == "f5":
        world_target = Pose((0.3, -0.3, 0.8), (1.0, 0.0, 0.0, 0.0))
        base_target = pose_world_to_base(world_target, root_position, root_orientation)
        delta_pos = tuple(b - c for b, c in zip(base_target.position, current_right.position))
        tracker.apply(TeleopCommand(
            timestamp=0.0, source="hotkey_f5", active=True,
            right_pose=PoseDelta(translation=delta_pos, rotation_rpy=(0.0, 0.0, 0.0)),
            right_gripper_delta=gripper_open - targets.right_gripper,
        ))
        print("F5: Arm to ready pose", flush=True)

    elif key == "f6":
        spine_delta = spine_up - current_spine
        tracker.apply(TeleopCommand(
            timestamp=0.0, source="hotkey_f6", active=True,
            spine_delta=spine_delta,
        ))
        print(f"F6: Spine to {spine_up:.2f}m", flush=True)


def clamp_direct_joint_command(command: Any, robot: Any, joint_groups: Any) -> Any:
    return command


if __name__ == "__main__":
    main()
