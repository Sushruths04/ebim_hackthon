#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Record a short real-physics Task 3 mobile-robot demonstration as a GIF."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record real Isaac Lab motion of the Task 3 robot."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_robot_demo",
    )
    parser.add_argument("--frames", type=int, default=80)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    return parser.parse_args()


def motion_command(step: int) -> tuple[float, float, float]:
    """Return a short, collision-conscious base motion in robot coordinates."""
    if step < 120:
        return 0.0, 0.0, 0.0
    if step < 520:
        return 0.32, 0.0, 0.0
    if step < 720:
        return 0.0, 0.22, 0.0
    return 0.0, 0.0, 0.0


def encode_gif(frames_dir: Path, output_path: Path) -> None:
    from PIL import Image

    images = [
        Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE)
        for path in sorted(frames_dir.glob("rgb_*.png"))
    ]
    if not images:
        raise RuntimeError(f"Isaac Sim did not write frames to {frames_dir}")
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=50,
        loop=0,
        optimize=False,
    )


def main() -> None:
    args = parse_args()
    if args.frames < 1:
        raise ValueError("--frames must be positive")
    args.output_dir = args.output_dir.resolve()
    frames_dir = args.output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # SimulationApp must start before importing Isaac Lab/Omniverse modules.
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({"headless": True})
    simulation_app = app_launcher.app
    try:
        for path in (SCENES_DIR, COMMON_DIR):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))

        from scene_robot_room_keyboard import (
            configure_keyboard_control_stage,
            configure_robot_room_stage,
            disable_robot_external_wrenches,
            make_control_scene_cfg,
            measured_position_targets,
            reset_robot_to_default_state,
            robot_root_world_pose,
            yaw_to_quat,
        )
        from teleop_targets import (
            discover_joint_groups,
            position_target_subset,
        )
        from tmr_base_control import (
            compute_drive_targets,
            find_drive_joint_ids,
        )

        import omni.replicator.core as rep

        import isaaclab.sim as sim_utils
        from isaaclab.scene import InteractiveScene
        from isaaclab.sim import SimulationContext

        robot_position = (-4.6, 2.7, 0.0)
        sim = SimulationContext(
            sim_utils.SimulationCfg(
                dt=0.005,
                device="cuda:0",
                gravity=(0.0, 0.0, -9.81),
            )
        )
        configure_keyboard_control_stage(
            configure_robot_room_stage,
            simulation_app,
            sim.stage,
            room_path=REPO_ROOT / "assets" / "robot_room.usd",
            task="task3",
            head_placement="A",
            robot_position=robot_position,
            robot_yaw=-90.0,
            dynamic_beans=False,
        )
        scene = InteractiveScene(
            make_control_scene_cfg(
                num_envs=1,
                robot_path=REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd",
                robot_position=robot_position,
                robot_rotation=yaw_to_quat(-90.0),
            )
        )
        sim.reset()
        scene.reset()
        robot = scene["robot"]
        reset_robot_to_default_state(robot, scene.env_origins)
        scene.write_data_to_sim()

        steering_ids, drive_ids = find_drive_joint_ids(robot.joint_names)
        groups = discover_joint_groups(robot.joint_names)
        arm_targets = measured_position_targets(robot)
        camera = rep.create.camera(
            position=(-8.1, -3.3, 2.8),
            look_at=(-4.1, 1.65, 0.85),
        )
        render_product = rep.create.render_product(
            camera, (args.width, args.height)
        )
        writer = rep.writers.get("BasicWriter")
        writer.initialize(output_dir=str(frames_dir), rgb=True)
        writer.attach([render_product])

        total_steps = max(820, args.frames * 10)
        capture_every = max(1, total_steps // args.frames)
        captured = 0
        for step in range(total_steps):
            vx, vy, wz = motion_command(step)
            steering_targets, drive_targets = compute_drive_targets(
                robot,
                steering_ids,
                vx,
                vy,
                wz,
                num_envs=1,
                device=sim.device,
            )
            phase = step * sim.cfg.dt
            arm_targets[:, groups.left_arm[3]] = -2.2 + 0.28 * math.sin(
                2.0 * phase
            )
            arm_targets[:, groups.right_arm[3]] = -2.2 - 0.28 * math.sin(
                2.0 * phase
            )
            arm_values, arm_ids = position_target_subset(arm_targets, groups)
            robot.set_joint_position_target(arm_values, joint_ids=arm_ids)
            robot.set_joint_position_target(
                steering_targets, joint_ids=steering_ids
            )
            robot.set_joint_velocity_target(drive_targets, joint_ids=drive_ids)
            disable_robot_external_wrenches(robot)
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.cfg.dt)
            if step % capture_every == 0 and captured < args.frames:
                rep.orchestrator.step(rt_subframes=1)
                captured += 1

        rep.orchestrator.wait_until_complete()
        writer.detach()
        render_product.destroy()
        position, orientation = robot_root_world_pose(robot)
        gif_path = args.output_dir / "task3_robot_motion.gif"
        encode_gif(frames_dir, gif_path)
        print(f"ROBOT_DEMO_GIF {gif_path}", flush=True)
        print(
            f"ROBOT_FINAL_POSE position={position} orientation={orientation}"
        )
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
