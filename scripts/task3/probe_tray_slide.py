#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Physical-only Step 1 probe: slide the flat tray to an edge and pinch it.

The tray remains the organizer asset. This script uses only robot joint
targets, contact, and PhysX pose reads. It intentionally contains no
kinematic object motion, added geometry, mass override, or fixed joint.
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
for path in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from integration_test import resolve_prim_path  # noqa: E402
from run_episode import (  # noqa: E402
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    _fix_single_articulation_root,
    make_headless_robot_usd,
    prepare_rigid_body_view_path,
)
from verify_grasp_lift import (  # noqa: E402
    CORRIDOR_STOP,
    FACE_WEST_YAW_RAD,
    ROTATE_SPOT,
    STANCE,
)

TRAY_NAME = "simple_tray"
NORTH_COUNTER_EDGE_Y = -1.22
DINING_TARGET = (-2.85, 1.90)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--head-placement", choices=("a", "b", "c"), default="a"
    )
    parser.add_argument("--push-distance", type=float, default=0.28)
    parser.add_argument("--push-y-offset", type=float, default=0.18)
    parser.add_argument("--push-z-offset", type=float, default=0.055)
    parser.add_argument("--push-seconds", type=float, default=3.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_stage1_tray_slide",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from isaaclab.app import AppLauncher

    simulation_app = AppLauncher(
        {"headless": True, "enable_cameras": False}
    ).app
    started = time.time()
    result: dict[str, Any]
    try:
        result = _run(args, simulation_app)
        result["wall_time_seconds"] = round(time.time() - started, 3)
        output = args.output_dir / "result.json"
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(
            "TRAY_SLIDE_RESULT " + json.dumps(result, sort_keys=True),
            flush=True,
        )
        # Isaac Kit shutdown is known to hang after result persistence. The
        # result is durable, so exit without starting another process.
        os._exit(0 if result["passed"] else 1)
    except BaseException:
        output = args.output_dir / "crash_traceback.txt"
        import traceback

        output.write_text(traceback.format_exc())
        raise
    finally:
        simulation_app.close()


def _run(args: argparse.Namespace, simulation_app: Any) -> dict[str, Any]:
    from scene_robot_room_keyboard import (
        configure_keyboard_control_stage,
        configure_robot_room_stage,
        disable_robot_external_wrenches,
        make_control_scene_cfg,
        reset_robot_to_default_state,
        yaw_to_quat,
    )
    from teleop_targets import _quaternion_from_rpy

    from isaacsim.core.prims import RigidPrim
    from pxr import Usd, UsdGeom

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

    from task3_autonomy.arms import (
        GRIPPER_CLOSED_RAD,
        GRIPPER_OPEN_RAD,
        DualArmController,
    )
    from task3_autonomy.navigation import base_twist_toward
    from task3_autonomy.skills import (
        TRANSIT_ARM_POSE,
        NavigateTo,
        RotateTo,
        TmrBaseAdapter,
        ramp_arm_pose,
    )

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
        head_placement=args.head_placement,
        robot_position=ROBOT_SPAWN_POSITION,
        robot_yaw=ROBOT_SPAWN_YAW,
        dynamic_beans=False,
    )
    tray_root_path = resolve_prim_path(sim.stage, TRAY_NAME)
    tray_view_path = prepare_rigid_body_view_path(sim.stage, tray_root_path)
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
    tray_view = RigidPrim(
        prim_paths_expr=tray_view_path, name="task3_tray_slide"
    )
    initialize = getattr(tray_view, "initialize", None)
    if callable(initialize):
        initialize()

    def tray_pose() -> tuple[float, float, float]:
        positions, _ = tray_view.get_world_poses()
        return tuple(float(value) for value in positions.tolist()[0])

    def tray_bounds() -> tuple[list[float], list[float]]:
        cache = UsdGeom.BBoxCache(
            Usd.TimeCode.Default(),
            [
                UsdGeom.Tokens.default_,
                UsdGeom.Tokens.render,
                UsdGeom.Tokens.proxy,
            ],
        )
        box = cache.ComputeWorldBound(
            sim.stage.GetPrimAtPath(tray_root_path)
        ).ComputeAlignedBox()
        return list(box.GetMin()), list(box.GetMax())

    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")
    arms = DualArmController(robot, simulation_app)
    phases: list[dict[str, Any]] = []
    tick = 0
    hold_anchor: tuple[float, float] | None = None

    def sim_tick() -> None:
        nonlocal tick
        disable_robot_external_wrenches(robot)
        if hold_anchor is not None:
            vx, vy = base_twist_toward(
                adapter.pose(),
                hold_anchor,
                max_linear_mps=0.12,
                position_kp=2.0,
            )
            adapter.apply_twist(vx, vy, hold_heading=True)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        tick += 1

    def log(name: str, **detail: Any) -> None:
        base = adapter.pose()
        phase = {
            "phase": name,
            "tick": tick,
            "tray": [round(v, 6) for v in tray_pose()],
            "base": [round(base.x, 6), round(base.y, 6), round(base.yaw, 6)],
            **detail,
        }
        phases.append(phase)
        print(
            "TRAY_SLIDE_DBG " + json.dumps(phase, sort_keys=True), flush=True
        )

    def drive(
        target: tuple[float, float],
        speed: float,
        budget: float,
        accept_tolerance: float = 0.03,
    ) -> bool:
        skill = NavigateTo(target, max_linear_mps=speed)
        for _ in range(math.ceil(budget / sim.cfg.dt)):
            vx, vy, done = skill.compute(adapter.pose())
            if done:
                adapter.apply_twist(0.0, 0.0)
                sim_tick()
                return True
            adapter.apply_twist(vx, vy)
            sim_tick()
        adapter.apply_twist(0.0, 0.0)
        sim_tick()
        pose = adapter.pose()
        residual = math.hypot(pose.x - target[0], pose.y - target[1])
        return residual <= accept_tolerance

    def rotate(target: float, budget: float) -> bool:
        skill = RotateTo(target)
        for _ in range(math.ceil(budget / sim.cfg.dt)):
            wz, done = skill.compute(adapter.pose())
            if done:
                adapter.apply_twist(0.0, 0.0, 0.0)
                sim_tick()
                return True
            adapter.apply_twist(0.0, 0.0, wz)
            sim_tick()
        adapter.apply_twist(0.0, 0.0, 0.0)
        sim_tick()
        return False

    def reach(
        side: str,
        position: tuple[float, float, float],
        quat: tuple[float, ...],
        budget: float,
    ) -> bool:
        return arms.reach(
            side,
            position,
            quat,
            step=sim_tick,
            dt=sim.cfg.dt,
            timeout_s=budget,
            position_tolerance_m=0.025,
        )

    # Stabilize and tuck exactly as the proven cup pipeline does.
    spine_ok = arms.move_spine(
        0.45,
        step=sim_tick,
        dt=sim.cfg.dt,
        timeout_s=6.0,
        tolerance_m=0.03,
    )
    measured_spine = arms.measured_spine_position()
    if not spine_ok:
        log("raise_spine", ok=False, measured_spine=round(measured_spine, 6))
        return _result(
            False, "raise_spine", phases, tray_pose(), tray_pose(), args
        )
    log("raise_spine", ok=True, measured_spine=round(measured_spine, 6))
    ramp_arm_pose(robot, TRANSIT_ARM_POSE, step=sim_tick)
    arms.sync_targets_from_measured()
    corridor_ok = drive(CORRIDOR_STOP, 0.5, 45.0)
    log("navigate_corridor_stop", ok=corridor_ok)
    if not corridor_ok:
        return _result(
            False,
            "navigate_corridor_stop",
            phases,
            tray_pose(),
            tray_pose(),
            args,
        )
    spot_ok = drive(ROTATE_SPOT, 0.4, 35.0, accept_tolerance=0.15)
    log("navigate_rotate_spot", ok=spot_ok)
    if not spot_ok:
        return _result(
            False, "rotate_spot", phases, tray_pose(), tray_pose(), args
        )
    rotate_ok = rotate(FACE_WEST_YAW_RAD, 15.0)
    log("rotate_west", ok=rotate_ok)
    if not rotate_ok:
        return _result(
            False, "rotate_west", phases, tray_pose(), tray_pose(), args
        )
    if not drive(STANCE, 0.25, 20.0):
        log("navigate_stance", ok=False)
        return _result(
            False, "navigate_stance", phases, tray_pose(), tray_pose(), args
        )
    pose = adapter.pose()
    hold_anchor = (pose.x, pose.y)
    log(
        "at_stance",
        base=[round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
    )

    start = tray_pose()
    top_down = _quaternion_from_rpy(math.pi, 0.0, 0.0)
    # Push from the south edge toward the north edge. The closed gripper is a
    # contact pusher; it is never attached to the tray.
    push_start = (
        start[0],
        start[1] + args.push_y_offset,
        start[2] + args.push_z_offset,
    )
    push_end = (
        push_start[0],
        push_start[1] + args.push_distance,
        push_start[2],
    )
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    if not reach("right", push_start, top_down, 10.0):
        log("push_precontact", ok=False, target=push_start)
        return _result(
            False, "push_precontact", phases, start, tray_pose(), args
        )
    arms.set_gripper("right", GRIPPER_CLOSED_RAD)
    for _ in range(math.ceil(1.0 / sim.cfg.dt)):
        arms.command()
        sim_tick()
    closed = arms.gripper_position("right")
    log("push_close", ok=True, gripper_rad=round(closed, 6), target=push_start)
    for _ in range(math.ceil(args.push_seconds / sim.cfg.dt)):
        arms.set_arm_target("right", push_end, top_down)
        arms.command()
        sim_tick()
    after_push = tray_pose()
    bounds_after_push = tray_bounds()
    moved_y = after_push[1] - start[1]
    overhang_north = bounds_after_push[1][1] - NORTH_COUNTER_EDGE_Y
    log(
        "push_result",
        ok=moved_y > 0.02,
        moved_y_m=round(moved_y, 6),
        north_overhang_m=round(overhang_north, 6),
        bounds_min=[round(v, 6) for v in bounds_after_push[0]],
        bounds_max=[round(v, 6) for v in bounds_after_push[1]],
    )

    # Move to the north side of the island, then try a true thin-edge pinch.
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    arms.command()
    sim_tick()
    if not drive((STANCE[0], -0.75), 0.25, 20.0):
        log("navigate_north_side", ok=False)
        return _result(
            False, "navigate_north_side", phases, start, tray_pose(), args
        )
    tray_now = tray_pose()
    edge_y = _quaternion_from_rpy(math.pi, math.pi / 2.0, 0.0)
    edge_target = (tray_now[0], tray_now[1] + 0.02, tray_now[2] + 0.014)
    edge_ok = reach("right", edge_target, edge_y, 10.0)
    log("edge_precontact", ok=edge_ok, target=edge_target)
    holding = False
    lift_ok = False
    if edge_ok:
        holding = arms.grasp(
            "right", step=sim_tick, dt=sim.cfg.dt, settle_seconds=1.5
        )
        log(
            "edge_close",
            ok=holding,
            gripper_rad=round(arms.gripper_position("right"), 6),
        )
        if holding:
            lift_ok = arms.lift(
                "right",
                0.10,
                step=sim_tick,
                dt=sim.cfg.dt,
                timeout_s=5.0,
                position_tolerance_m=0.04,
                spine_assist_m=0.08,
            )
            log(
                "edge_lift",
                ok=lift_ok,
                lift_m=round(tray_pose()[2] - after_push[2], 6),
            )
    final = tray_pose()
    passed = bool(holding and lift_ok)
    return _result(
        passed,
        "complete" if passed else "edge_pinch",
        phases,
        start,
        final,
        args,
    )


def _result(
    passed: bool,
    failed_phase: str,
    phases: list[dict[str, Any]],
    start: tuple[float, float, float],
    final: tuple[float, float, float],
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "passed": bool(passed),
        "failed_phase": failed_phase,
        "mode": "physics_contact_only",
        "object_name": TRAY_NAME,
        "head_placement": args.head_placement,
        "start_pose": [round(v, 6) for v in start],
        "final_pose": [round(v, 6) for v in final],
        "net_translation_m": [round(final[i] - start[i], 6) for i in range(3)],
        "push_distance_commanded_m": args.push_distance,
        "north_edge_world_y": NORTH_COUNTER_EDGE_Y,
        "phases": phases,
    }


if __name__ == "__main__":
    main()
