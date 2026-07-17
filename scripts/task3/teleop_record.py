#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Teleoperation with recording: keyboard control + LeRobot dataset capture.

Runs the Task 3 scene with keyboard teleop (same as
scene_robot_room_keyboard.py) but additionally records every command and
robot state into a LeRobot v2 dataset for Phase 7 policy training.

Usage on the GPU VM (with WebRTC livestream for viewing):

  # Record while you teleoperate:
  python scripts/task3/teleop_record.py \\
      --episode-name grasp_cup_01 \\
      --record-video \\
      --livestream --public-ip 34.61.210.0 \\
      --out-dir /workspace/EBiM_Challenge/teleop_demos

  # Press ESC to stop recording and save the dataset.

The recorded dataset is saved to:
  <out-dir>/lerobot_dataset_<episode-name>/
  ├── metadata.json
  ├── data.jsonl (or data.hdf5 if h5py is available)
  └── videos/  (if --record-video)

Keyboard controls (same as scene_robot_room_keyboard.py):
  LEFT ARM:  [W/S] X+/- [A/D] Y+/- [Q/E] Z-/+  [Z/X] Roll+/- [T/G] Pitch+/- [C/V] Yaw+/- [F] Grip
  RIGHT ARM: [O/L] X+/- [K/;] Y+/- [I/P] Z-/+  [N/M] Roll+/- [U/J] Pitch+/- [,/.] Yaw+/- ['] Grip
  Hold [SHIFT] for mobile base: [H/N] Fwd/Bwd [B/M] L/R [G/J] Rot
  [R] Reset arm targets
  ESC stop recording and save
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"

for import_dir in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, REPO_ROOT):
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

ROBOT_SPAWN_POSITION = (-4.6, 2.7, 0.0)
ROBOT_SPAWN_YAW = -90.0
VIDEO_FPS = 20


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Teleoperate the Task 3 robot and record a LeRobot dataset.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--episode-name", required=True,
                   help="Name for this recording episode (e.g. grasp_cup_01).")
    p.add_argument("--record-video", action="store_true",
                   help="Also record camera frames alongside the LeRobot data.")
    p.add_argument("--livestream", action="store_true",
                   help="Enable WebRTC livestream for remote viewing.")
    p.add_argument("--public-ip", default=os.environ.get("PUBLIC_IP"),
                   help="Public IP for WebRTC (required with --livestream).")
    p.add_argument("--out-dir", type=Path,
                   default=REPO_ROOT / "teleop_demos",
                   help="Output directory for recorded datasets.")
    p.add_argument("--head-placement", default="a",
                   help="Head placement preset for the scene.")
    p.add_argument("--fps", type=int, default=20,
                   help="Recording frame rate (matches sim step rate).")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.livestream:
        if not args.public_ip:
            raise ValueError("--livestream requires --public-ip or PUBLIC_IP")
        os.environ["PUBLIC_IP"] = str(args.public_ip)

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({
        "headless": True,
        "enable_cameras": bool(args.record_video or args.livestream),
        "livestream": 1 if args.livestream else -1,
    })
    simulation_app = app_launcher.app

    try:
        _run_teleop_record(args, simulation_app)
    except BaseException:
        import traceback
        traceback.print_exc()
        simulation_app.close()
        raise
    else:
        simulation_app.close()


def _run_teleop_record(
    args: argparse.Namespace,
    simulation_app: Any,
) -> None:
    from run_episode import (
        _fix_single_articulation_root,
        _save_rgb_frame,
        make_headless_robot_usd,
    )
    from scene_robot_room_keyboard import (
        configure_keyboard_control_stage,
        configure_robot_room_stage,
        disable_robot_external_wrenches,
        make_control_scene_cfg,
        reset_robot_to_default_state,
        yaw_to_quat,
    )

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

    sim = SimulationContext(sim_utils.SimulationCfg(
        dt=0.005, device="cuda:0", gravity=(0.0, 0.0, -9.81),
    ))

    configure_keyboard_control_stage(
        configure_robot_room_stage,
        simulation_app,
        sim.stage,
        room_path=REPO_ROOT / "assets" / "robot_room.usd",
        task="task3",
        head_placement=args.head_placement,
        robot_position=ROBOT_SPAWN_POSITION,
        robot_yaw=ROBOT_SPAWN_YAW,
        dynamic_beans=False,
    )

    scene = InteractiveScene(make_control_scene_cfg(
        num_envs=1,
        robot_path=make_headless_robot_usd(
            REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd"
        ),
        robot_position=ROBOT_SPAWN_POSITION,
        robot_rotation=yaw_to_quat(ROBOT_SPAWN_YAW),
    ))

    _fix_single_articulation_root(sim.stage, "/World/envs/env_0/Robot")
    sim.reset()
    scene.reset()
    robot = scene["robot"]
    reset_robot_to_default_state(robot, scene.env_origins)
    scene.write_data_to_sim()

    # --- Keyboard teleop setup ---
    from keyboard_arm_teleop import KeyboardTeleopMapper, control_help
    from teleop_commands import safe_command
    from teleop_targets import (
        CartesianTargetTracker,
        DirectJointTargetLatch,
        Pose,
        TargetLimits,
        TeleopTargets,
        compose_position_targets,
        discover_joint_groups,
        pose_base_to_world,
        position_target_subset,
    )
    from dual_arm_lula import (
        LEFT_ARM_JOINTS,
        RIGHT_ARM_JOINTS,
        create_raw_dual_arm_lula,
    )
    from tmr_base_control import (
        compensate_yaw_rate,
        compute_drive_targets,
        find_drive_joint_ids,
        get_root_yaw,
    )
    from scene_robot_room_keyboard import (
        clamp_direct_joint_command,
        robot_root_world_pose,
        enable_motion_generation_extension,
        measured_position_targets,
    )

    import omni.kit.app
    enable_motion_generation_extension(omni.kit.app.get_app().get_extension_manager())

    joint_groups = discover_joint_groups(robot.joint_names)
    position_targets = measured_position_targets(robot)
    tracker = CartesianTargetTracker(
        TeleopTargets(
            left=Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)),
            right=Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)),
            left_gripper=0.0,
            right_gripper=0.0,
            spine=0.0,
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
    dual_arm_ik = create_raw_dual_arm_lula(
        robot.joint_names,
        lambda: robot.data.joint_pos[0].detach().cpu().numpy(),
    )
    direct_joint_latch = DirectJointTargetLatch()
    mapper = KeyboardTeleopMapper()
    steering_indices, drive_indices = find_drive_joint_ids(robot.joint_names)
    heading_hold_yaw = get_root_yaw(robot)

    # --- Recording setup ---
    from task3_autonomy.lerobot_recorder import (
        ARM_JOINTS,
        LeRobotRecorder,
        LeRobotFrame,
        collect_frame_cpu,
    )

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    if args.record_video:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for stale in frames_dir.glob("rgb_*.png"):
            stale.unlink()

    recorder = LeRobotRecorder(fps=args.fps, out_dir=str(out_dir))
    episode_slug = args.episode_name

    # --- Video annotator (optional) ---
    import omni.replicator.core as rep

    rgb_annotator = None
    render_product = None
    frames_written = 0
    capture_every = max(1, round(1.0 / (sim.cfg.dt * args.fps)))
    if args.record_video:
        camera = rep.create.camera(
            position=(-8.1, -3.3, 2.8), look_at=(-4.1, 1.65, 0.85)
        )
        render_product = rep.create.render_product(camera, (640, 360))
        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_annotator.attach([render_product])

    # --- Keyboard listener ---
    from scene_robot_room_keyboard import create_keyboard_teleop

    teleop = create_keyboard_teleop()
    print("=" * 70)
    print(f"RECORDING episode: {episode_slug}")
    print("Teleoperate the robot. Press ESC to stop and save.")
    print("=" * 70)
    print(control_help())

    tick = 0
    listener_started = False
    try:
        teleop.start()
        listener_started = True
        print("Keyboard listener active. Recording started.", flush=True)

        while simulation_app.is_running() and not teleop.stop_requested:
            now = time.monotonic()

            # --- Read keyboard ---
            command = mapper.map_keys(
                set(teleop.pressed), timestamp=now, dt=sim.cfg.dt
            )
            command = safe_command(command, now=now, timeout=0.25)
            command = clamp_direct_joint_command(command, robot, joint_groups)

            # --- Record frame BEFORE applying command ---
            joint_pos = robot.data.joint_pos[0].tolist()
            joint_vel = robot.data.joint_vel[0].tolist()
            joint_names_list = robot.joint_names

            base_pos = robot.data.root_pos_w[0].tolist()
            base_yaw = get_root_yaw(robot)
            base_vel_w = robot.data.root_lin_vel_w[0].tolist()
            base_ang_vel_w = robot.data.root_ang_vel_w[0].tolist()

            # Extract arm joints, grippers, base velocity
            name_to_idx = {name: i for i, name in enumerate(joint_names_list)}
            arm_pos = [0.0] * 14
            arm_vel = [0.0] * 14
            for i, name in enumerate(ARM_JOINTS):
                if name in name_to_idx:
                    idx = name_to_idx[name]
                    arm_pos[i] = joint_pos[idx]
                    arm_vel[i] = joint_vel[idx]

            left_gripper = 0.0
            right_gripper = 0.0
            for name in ("left_gripper_joint",):
                if name in name_to_idx:
                    left_gripper = joint_pos[name_to_idx[name]]
            for name in ("right_gripper_joint",):
                if name in name_to_idx:
                    right_gripper = joint_pos[name_to_idx[name]]

            # Action: teleop command as a flat vector
            action = _command_to_action(command)

            frame = LeRobotFrame(
                joint_pos=arm_pos,
                joint_vel=arm_vel,
                gripper_pos=[left_gripper, right_gripper],
                base_pose=[base_pos[0], base_pos[1], base_yaw],
                base_velocity=[base_vel_w[0], base_vel_w[1], base_ang_vel_w[2]],
                action=action,
            )
            recorder.add_frame(frame)

            # --- Apply command to robot ---
            vx, vy, wz_cmd = command.base_twist
            wz, heading_hold_yaw = compensate_yaw_rate(
                robot, vx, vy, wz_cmd, heading_hold_yaw,
                manual_rotation=abs(wz_cmd) > 1.0e-4,
            )

            targets = tracker.apply(command)
            root_position, root_orientation = robot_root_world_pose(robot)
            left_world = pose_base_to_world(
                targets.left, root_position, root_orientation
            )
            right_world = pose_base_to_world(
                targets.right, root_position, root_orientation
            )
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
                left_arm=left_arm_targets, right_arm=right_arm_targets,
                left_gripper=targets.left_gripper,
                right_gripper=targets.right_gripper,
                spine=targets.spine,
            )
            arm_position_targets, arm_position_joint_ids = (
                position_target_subset(position_targets, joint_groups)
            )
            robot.set_joint_position_target(
                arm_position_targets, joint_ids=arm_position_joint_ids,
            )

            steering_pos_targets, drive_vel_targets = compute_drive_targets(
                robot, steering_indices, vx, vy, wz,
                num_envs=1, device=sim.device,
            )
            robot.set_joint_position_target(
                steering_pos_targets, joint_ids=steering_indices,
            )
            robot.set_joint_velocity_target(
                drive_vel_targets, joint_ids=drive_indices,
            )

            disable_robot_external_wrenches(robot)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.cfg.dt)

            # --- Capture video frame ---
            if args.record_video and tick % capture_every == 0:
                if _save_rgb_frame(rgb_annotator, frames_dir, frames_written):
                    frames_written += 1

            tick += 1
            if tick % 500 == 0:
                print(f"  tick={tick} frames={len(recorder)} "
                      f"keys={sorted(teleop.pressed)}", flush=True)

    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")
    finally:
        if listener_started:
            teleop.stop()

    # --- Save dataset ---
    print(f"\nRecording complete: {len(recorder)} frames in {tick} ticks")

    if args.record_video and rgb_annotator is not None:
        rgb_annotator.detach()
        render_product.destroy()
        if frames_written:
            from PIL import Image
            images = [
                Image.open(p).convert("P", palette=Image.Palette.ADAPTIVE)
                for p in sorted(frames_dir.glob("rgb_*.png"))
            ]
            gif_path = out_dir / f"{episode_slug}.gif"
            images[0].save(
                gif_path, save_all=True, append_images=images[1:],
                duration=round(1000 / VIDEO_FPS), loop=0, optimize=True,
            )
            print(f"Saved video: {gif_path}")

    metadata = {
        "episode_name": episode_slug,
        "task": "task3_grasp_lift",
        "head_placement": args.head_placement,
        "robot_spawn": list(ROBOT_SPAWN_POSITION),
        "robot_yaw": ROBOT_SPAWN_YAW,
        "sim_dt": sim.cfg.dt,
        "total_ticks": tick,
        "git_commit": _git_commit_hash(),
    }
    dataset_path = recorder.save(metadata=metadata)
    print(f"Dataset saved: {dataset_path}")
    print(f"Frames recorded: {len(recorder)}")
    print(f"Episode: {episode_slug}")


def _command_to_action(command: Any) -> list[float]:
    """Flatten a TeleopCommand into a fixed-size action vector.

    Layout (17 floats):
      [0:3]   left_pose.translation (x, y, z)
      [3:6]   left_pose.rotation_rpy (r, p, y)
      [6:9]   right_pose.translation (x, y, z)
      [9:12]  right_pose.rotation_rpy (r, p, y)
      [12]    left_gripper_delta
      [13]    right_gripper_delta
      [14:17] base_twist (vx, vy, wz)
    """
    lp = command.left_pose
    rp = command.right_pose
    return [
        *lp.translation,
        *lp.rotation_rpy,
        *rp.translation,
        *rp.rotation_rpy,
        command.left_gripper_delta,
        command.right_gripper_delta,
        *command.base_twist,
    ]


def _git_commit_hash() -> str:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT
        ).decode().strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
