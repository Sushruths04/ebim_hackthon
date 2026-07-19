#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Evidence probe: command a constant body twist, log commanded vs actual.

2026-07-17: first live NavigateTo run moved in the correct direction with
perfect heading hold but at ~0.04 m/s instead of the commanded 0.5 m/s.
This probe prints, every half second, the steering positions/targets and
wheel velocities/targets plus the base velocity, to show WHERE the 12x
authority deficit lives (skill -> targets -> PhysX response).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"

from run_episode import (  # noqa: E402
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    _fix_single_articulation_root,
    make_headless_robot_usd,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--drive-damping",
        type=float,
        default=None,
        help="Override the wheel drive damping written to PhysX (isolates "
        "the drive-authority variable without touching shared config).",
    )
    args = parser.parse_args()

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({"headless": True, "enable_cameras": False})
    simulation_app = app_launcher.app
    try:
        _probe(simulation_app, args)
    finally:
        sys.stdout.flush()
        simulation_app.close()


def _probe(simulation_app, args) -> None:
    for path in (SCENES_DIR, COMMON_DIR, str(REPO_ROOT)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from scene_robot_room_keyboard import (  # noqa: E402
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

    from task3_autonomy.skills import TmrBaseAdapter

    sim = SimulationContext(
        sim_utils.SimulationCfg(
            dt=0.005, device="cuda:0", gravity=(0.0, 0.0, -9.81)
        )
    )
    configure_keyboard_control_stage(
        configure_robot_room_stage,
        simulation_app,
        sim.stage,
        room_path=REPO_ROOT / "assets" / "robot_room.usd",
        task="task3",
        head_placement="a",
        robot_position=ROBOT_SPAWN_POSITION,
        robot_yaw=ROBOT_SPAWN_YAW,
        dynamic_beans=False,
    )
    scene = InteractiveScene(
        make_control_scene_cfg(
            num_envs=1,
            robot_path=make_headless_robot_usd(
                REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd"
            ),
            robot_position=ROBOT_SPAWN_POSITION,
            robot_rotation=yaw_to_quat(ROBOT_SPAWN_YAW),
        )
    )
    _fix_single_articulation_root(sim.stage, "/World/envs/env_0/Robot")
    sim.reset()
    scene.reset()
    robot = scene["robot"]
    reset_robot_to_default_state(robot, scene.env_origins)
    scene.write_data_to_sim()

    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")
    steer_names = [robot.joint_names[i] for i in adapter.steering_ids]
    drive_names = [robot.joint_names[i] for i in adapter.drive_ids]
    print(f"PROBE steering joints: {steer_names}", flush=True)
    print(f"PROBE drive joints:    {drive_names}", flush=True)

    if args.drive_damping is not None:
        import torch

        damping = torch.full(
            (1, len(adapter.drive_ids)), args.drive_damping, device="cuda:0"
        )
        robot.write_joint_damping_to_sim(damping, joint_ids=adapter.drive_ids)
        print(
            f"PROBE drive damping override: {args.drive_damping}", flush=True
        )

    def fmt(tensor, ids) -> list[float]:
        return [round(float(tensor[0, i]), 3) for i in ids]

    for step in range(600):  # 3 s at dt=0.005
        adapter.apply_twist(0.5, 0.0)
        disable_robot_external_wrenches(robot)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        if step % 100 == 0:
            data = robot.data
            print(
                f"PROBE step={step}"
                f" base_vel_xy={[round(float(v), 3) for v in data.root_lin_vel_w[0][:2]]}"
                f" steer_pos={fmt(data.joint_pos, adapter.steering_ids)}"
                f" steer_tgt={fmt(data.joint_pos_target, adapter.steering_ids)}"
                f" wheel_vel={fmt(data.joint_vel, adapter.drive_ids)}"
                f" wheel_tgt={fmt(data.joint_vel_target, adapter.drive_ids)}",
                flush=True,
            )

    print("PROBE done", flush=True)


if __name__ == "__main__":
    main()
