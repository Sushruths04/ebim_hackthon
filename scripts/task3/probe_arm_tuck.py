#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Evidence probe: measure the robot's settled footprint per arm pose.

2026-07-17: the door-routed NavigateTo run still stalled at the partition.
Room USD measurement showed both wall crossings are ~1.2 m wide while the
robot's authored bbox spans 1.88 m across the arms -- the base fits, the
arms do not. This probe ramps the arms through candidate tuck poses in one
app session and prints the settled body-frame extents (from link origins;
true geometry adds ~0.12 m at the hands), so the transit pose for
NavigateTo is chosen on measurement, not guesswork.
"""

from __future__ import annotations

import json
import math
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

ARM_JOINT_NAMES = [
    f"{side}_fr3v2_joint{i}" for side in ("left", "right") for i in range(1, 8)
]

# Candidate poses as (left j1..j7, right j1..j7). "default" is the scene
# config's ready pose (measured 1.88 m wide authored); the others try to
# swing the outboard-mounted arms inward and/or fold them vertically.
DEFAULT_ARM = [0.0, -1.5, 0.0, -2.2, 0.0, 1.5, 0.785]


def _mirror(left: list[float]) -> list[float]:
    """Right-arm mirror of a left-arm pose (negate j1/j3/j5; mounts are
    mirrored, verified by swing_in_a narrowing both sides symmetrically)."""
    return [-left[0], left[1], -left[2], left[3], -left[4], left[5], left[6]]


def _pair(left: list[float]) -> list[float]:
    return left + _mirror(left)


# v4 forward-extent sweep: v3's winner lean_pnn fixed the width
# (+-0.37 m) and the doorway crossing succeeded live (nav9), but its fold
# sticks 0.885 m FORWARD at island height — the robot scraped the kitchen
# island for ~35 s in the 1.32 m wall-island corridor (robot length 1.27 m).
# Sweep wrist/fold tweaks on lean_pnn to shorten the nose.
_PNN = [1.57, -0.87, -1.57, -2.9, 0.0, 2.9, 0.785]


def _variant(**overrides: float) -> list[float]:
    pose = list(_PNN)
    for key, value in overrides.items():
        pose[int(key[1]) - 1] = value
    return _pair(pose)


CANDIDATES: dict[str, list[float]] = {
    "pnn_base": _pair(_PNN),
    "pnn_j6_15": _variant(j6=1.5),
    "pnn_j6_22": _variant(j6=2.2),
    "pnn_j6_40": _variant(j6=4.0),
    "pnn_j4_30": _variant(j4=-3.0),
    "pnn_j6_15_j4_30": _variant(j6=1.5, j4=-3.0),
    "pnn_j5_15": _variant(j5=1.57),
}

RAMP_STEPS = 300  # 1.5 s target interpolation
SETTLE_STEPS = 400  # 2.0 s hold before measuring


def main() -> None:
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({"headless": True, "enable_cameras": False})
    simulation_app = app_launcher.app
    try:
        _probe(simulation_app)
    finally:
        sys.stdout.flush()
        simulation_app.close()


def _probe(simulation_app) -> None:
    for path in (SCENES_DIR, COMMON_DIR, str(REPO_ROOT)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    import torch
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

    # Adapter only for its damping fix + yaw helper; the base is not driven.
    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")

    arm_ids = [robot.joint_names.index(n) for n in ARM_JOINT_NAMES]

    def step_once() -> None:
        disable_robot_external_wrenches(robot)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)

    def measure(label: str, target) -> None:
        # Max joint-target error flags poses the arms could not reach
        # (self-collision or a limit) -- discard those results.
        arm_err = float(
            (robot.data.joint_pos[0, arm_ids] - target).abs().max()
        )
        root = robot.data.root_pos_w[0]
        yaw = adapter._base.get_root_yaw(robot)
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        extents: list[tuple[float, float, str]] = []
        body_pos = robot.data.body_pos_w[0]
        for i, name in enumerate(robot.body_names):
            rel_x = float(body_pos[i, 0] - root[0])
            rel_y = float(body_pos[i, 1] - root[1])
            bx = cos_y * rel_x + sin_y * rel_y
            by = -sin_y * rel_x + cos_y * rel_y
            extents.append((bx, by, name))
        bxs = [e[0] for e in extents]
        bys = [e[1] for e in extents]
        widest = max(extents, key=lambda e: abs(e[1]))
        longest = max(extents, key=lambda e: abs(e[0]))
        # Links that would matter at the 1.2 m doorway: report their height
        # too, because the wall WEST of the door is only 1.18 m tall — wide
        # links above ~1.2 m can overhang it if the crossing is biased west.
        wide_links = sorted(
            (
                (name, round(by, 3), round(float(body_pos[i, 2]), 3))
                for i, (bx, by, name) in enumerate(extents)
                if abs(by) > 0.45
            ),
            key=lambda e: -abs(e[1]),
        )[:8]
        # Forward overhang matters at island height (z 0.35-1.15): report
        # every link past the base_link nose with its height.
        long_links = sorted(
            (
                (name, round(bx, 3), round(float(body_pos[i, 2]), 3))
                for i, (bx, by, name) in enumerate(extents)
                if bx > 0.5
            ),
            key=lambda e: -e[1],
        )[:8]
        print(
            "TUCK_RESULT "
            + json.dumps(
                {
                    "pose": label,
                    "body_x_extent": [round(min(bxs), 3), round(max(bxs), 3)],
                    "body_y_extent": [round(min(bys), 3), round(max(bys), 3)],
                    "widest_link": [widest[2], round(widest[1], 3)],
                    "longest_link": [longest[2], round(longest[0], 3)],
                    "wide_links_by_z": wide_links,
                    "long_links_by_z": long_links,
                    "arm_err": round(arm_err, 3),
                    "root_xy": [
                        round(float(root[0]), 3),
                        round(float(root[1]), 3),
                    ],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    for label, pose in CANDIDATES.items():
        start = robot.data.joint_pos[0, arm_ids].clone()
        target = torch.tensor(pose, device="cuda:0")
        for step in range(RAMP_STEPS):
            alpha = (step + 1) / RAMP_STEPS
            interp = (1 - alpha) * start + alpha * target
            robot.set_joint_position_target(
                interp.unsqueeze(0), joint_ids=arm_ids
            )
            step_once()
        for _ in range(SETTLE_STEPS):
            robot.set_joint_position_target(
                target.unsqueeze(0), joint_ids=arm_ids
            )
            step_once()
        measure(label, target)

    print("PROBE done", flush=True)


if __name__ == "__main__":
    main()
