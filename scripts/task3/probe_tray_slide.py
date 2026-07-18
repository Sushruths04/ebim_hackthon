#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Physical-only Step 1 probe: slide the flat tray to an edge and pinch it.

The tray remains the organizer asset. This script uses only robot joint
targets, contact, and PhysX pose reads. It intentionally contains no
kinematic object motion, added geometry, mass override, or fixed joint.

Fix (2026-07-18): the first trial failed at ``push_precontact`` because a
single direct reach targeted a pose ~1.0 m from the stance -- past the
proven ~0.83 m dead-ahead envelope from the cup pipeline -- and swept the
outstretched arm through the tray airspace. This revision mirrors the proven
cup pipeline instead: a local ``TRAY_STANCE`` puts the contact point dead
ahead (~0.86 m), a pregrasp-above reach is followed by a closed-fist ramped
vertical descend onto the tray top (not a single ``reach()``, which would
never converge into contact), then a synchronized north drag that ramps the
arm's push target and the base hold anchor by the same offset every tick so
the commanded arm/base separation never grows.
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

# Pure-math helpers: no Isaac dependency, safe to import at module scope.
from task3_autonomy.arms import (  # noqa: E402
    linear_ramp_target,
    synchronized_drag_targets,
)

TRAY_NAME = "simple_tray"
NORTH_COUNTER_EDGE_Y = -1.22
DINING_TARGET = (-2.85, 1.90)

# Same depth as the proven cup grasp (CUP_GRASP_XY = tray/cup center + 0.10 m
# in x from the proven west-facing stance); dead ahead from TRAY_STANCE.
CONTACT_X_OFFSET_M = 0.10
PREGRASP_EE_Z = 1.05
# ~1.5-2 cm below the expected fingertip-contact height so the position PD
# presses down onto the tray top rather than stopping just above it.
DESCEND_EE_Z = 0.80
CONTACT_STALL_EPS_M = 0.01
CONTACT_STALL_SECONDS = 0.3
SLIDE_MOVED_Y_GATE_M = 0.20
SLIDE_OVERHANG_GATE_M = 0.05


def _reach_failure_detail(
    arms: Any,
    side: str,
    position: tuple[float, float, float],
    quat: tuple[float, ...],
) -> dict[str, Any]:
    """Measured EE pose, position/orientation error, and IK flag.

    Diagnostic-only IK solve: ``arms.command()`` here does not call
    ``step()``, so it does not advance physics or actuate anything -- it
    only reports whether Lula could converge on the failed target from the
    current configuration.
    """
    ik_result = arms.command()
    ik_succeeded = (
        ik_result.left_succeeded
        if side == "left"
        else ik_result.right_succeeded
    )
    ee_position, ee_quat = arms.ee_world_poses()[0 if side == "left" else 1]
    position_error, orientation_error = arms.pose_error(side, position, quat)
    return {
        "target": [round(v, 4) for v in position],
        "measured_ee_position": [round(v, 6) for v in ee_position],
        "measured_ee_quat": [round(v, 6) for v in ee_quat],
        "position_error_m": round(position_error, 6),
        "orientation_error_rad": round(orientation_error, 6),
        "ik_succeeded": bool(ik_succeeded),
    }


def _ramp_vertical_ee(
    arms: Any,
    step: Any,
    tray_pose_fn: Any,
    side: str,
    xy: tuple[float, float],
    quat: tuple[float, ...],
    start_z: float,
    end_z: float,
    seconds: float,
    dt: float,
    *,
    detect_contact: bool = False,
    stall_eps_m: float = CONTACT_STALL_EPS_M,
    stall_seconds: float = CONTACT_STALL_SECONDS,
) -> dict[str, Any]:
    """Time-bounded linear EE-z ramp, reissuing targets every tick.

    This intentionally does not use ``reach()``: descending into contact
    must never converge (the position PD is meant to keep pressing), and
    ``reach()`` would report a spurious timeout failure. When
    ``detect_contact`` is set, log the first tick where the measured EE z
    stalls above the (still-descending) commanded z for more than
    ``stall_seconds`` -- evidence the fingers are on the tray top.
    """
    ramp_ticks = max(1, math.ceil(seconds / dt))
    stall_start_tick: int | None = None
    contact_tick: int | None = None
    contact_measured_z: float | None = None
    contact_tray_pose: tuple[float, float, float] | None = None
    for tick_index in range(ramp_ticks):
        commanded_z = linear_ramp_target(
            start_z, end_z, tick_index + 1, ramp_ticks
        )
        arms.set_arm_target(side, (xy[0], xy[1], commanded_z), quat)
        arms.command()
        step()
        if not detect_contact:
            continue
        measured_z = arms.ee_world_poses()[0 if side == "left" else 1][0][2]
        if measured_z - commanded_z <= stall_eps_m:
            stall_start_tick = None
            continue
        if stall_start_tick is None:
            stall_start_tick = tick_index
        elif (
            contact_tick is None
            and (tick_index - stall_start_tick) * dt >= stall_seconds
        ):
            contact_tick = tick_index
            contact_measured_z = measured_z
            contact_tray_pose = tray_pose_fn()
    final_measured_z = arms.ee_world_poses()[0 if side == "left" else 1][0][2]
    return {
        "final_commanded_ee_z": round(end_z, 6),
        "final_measured_ee_z": round(final_measured_z, 6),
        "contact_detected": contact_tick is not None,
        "contact_tick": contact_tick,
        "contact_measured_ee_z": (
            round(contact_measured_z, 6)
            if contact_measured_z is not None
            else None
        ),
        "contact_tray_pose": (
            [round(v, 6) for v in contact_tray_pose]
            if contact_tray_pose is not None
            else None
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--head-placement", choices=("a", "b", "c"), default="a"
    )
    parser.add_argument("--push-distance", type=float, default=0.26)
    parser.add_argument("--descend-seconds", type=float, default=2.0)
    parser.add_argument("--drag-seconds", type=float, default=5.0)
    parser.add_argument("--raise-seconds", type=float, default=2.0)
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

    # Local tray stance: put the contact point dead ahead so the reach stays
    # inside the proven ~0.83 m envelope (CUP_GRASP_XY dead-ahead distance
    # from STANCE), instead of the ~1.0 m diagonal reach that failed trial 1.
    initial_tray_pose = tray_pose()
    contact_x = initial_tray_pose[0] + CONTACT_X_OFFSET_M
    contact_y = initial_tray_pose[1]
    tray_stance = (STANCE[0], contact_y)

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

    def log_reach_failure(
        name: str,
        side: str,
        position: tuple[float, float, float],
        quat: tuple[float, ...],
        **detail: Any,
    ) -> None:
        log(
            name,
            ok=False,
            **_reach_failure_detail(arms, side, position, quat),
            **detail,
        )

    def ramp_vertical(
        side: str,
        xy: tuple[float, float],
        quat: tuple[float, ...],
        start_z: float,
        end_z: float,
        seconds: float,
        *,
        detect_contact: bool = False,
    ) -> dict[str, Any]:
        return _ramp_vertical_ee(
            arms,
            sim_tick,
            tray_pose,
            side,
            xy,
            quat,
            start_z,
            end_z,
            seconds,
            sim.cfg.dt,
            detect_contact=detect_contact,
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
    if not drive(tray_stance, 0.25, 20.0):
        log("navigate_stance", ok=False, target=list(tray_stance))
        return _result(
            False, "navigate_stance", phases, tray_pose(), tray_pose(), args
        )
    pose = adapter.pose()
    hold_anchor = (pose.x, pose.y)
    log(
        "at_stance",
        base=[round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
        tray_stance=list(tray_stance),
    )

    start = tray_pose()
    top_down = _quaternion_from_rpy(math.pi, 0.0, 0.0)
    # Press-and-drag from the top of the tray: pregrasp above the contact
    # point, close the fist (a rigid pusher, never attached to the tray),
    # ramp down onto the tray top, then drag the contact point (and the base
    # under it) north together. This mirrors the proven cup pipeline's
    # pregrasp-above + ramped-descend structure instead of one direct reach.
    pregrasp_above = (contact_x, contact_y, PREGRASP_EE_Z)
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    if not reach("right", pregrasp_above, top_down, 8.0):
        log_reach_failure(
            "push_pregrasp_above", "right", pregrasp_above, top_down
        )
        return _result(
            False, "push_pregrasp_above", phases, start, tray_pose(), args
        )
    log("push_pregrasp_above", ok=True, target=list(pregrasp_above))

    arms.set_gripper("right", GRIPPER_CLOSED_RAD)
    for _ in range(math.ceil(1.0 / sim.cfg.dt)):
        arms.command()
        sim_tick()
    closed = arms.gripper_position("right")
    log("push_close", ok=True, gripper_rad=round(closed, 6))

    descend_info = ramp_vertical(
        "right",
        (contact_x, contact_y),
        top_down,
        PREGRASP_EE_Z,
        DESCEND_EE_Z,
        args.descend_seconds,
        detect_contact=True,
    )
    log("push_descend", ok=True, **descend_info)

    drag_start_anchor = hold_anchor
    drag_ramp_ticks = max(1, math.ceil(args.drag_seconds / sim.cfg.dt))
    for tick_index in range(drag_ramp_ticks):
        arm_y, anchor_y = synchronized_drag_targets(
            contact_y,
            drag_start_anchor[1],
            args.push_distance,
            tick_index + 1,
            drag_ramp_ticks,
        )
        arms.set_arm_target(
            "right", (contact_x, arm_y, DESCEND_EE_Z), top_down
        )
        arms.command()
        hold_anchor = (drag_start_anchor[0], anchor_y)
        sim_tick()
    log(
        "push_drag",
        ok=True,
        target_arm_y=round(contact_y + args.push_distance, 6),
        target_anchor=[
            round(drag_start_anchor[0], 6),
            round(drag_start_anchor[1] + args.push_distance, 6),
        ],
    )

    raise_info = ramp_vertical(
        "right",
        (contact_x, contact_y + args.push_distance),
        top_down,
        DESCEND_EE_Z,
        PREGRASP_EE_Z,
        args.raise_seconds,
    )
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    arms.command()
    sim_tick()
    pose = adapter.pose()
    hold_anchor = (pose.x, pose.y)
    log("push_raise", ok=True, **raise_info)

    after_push = tray_pose()
    bounds_after_push = tray_bounds()
    moved_y = after_push[1] - start[1]
    overhang_north = bounds_after_push[1][1] - NORTH_COUNTER_EDGE_Y
    slide_ok = (
        moved_y >= SLIDE_MOVED_Y_GATE_M
        or overhang_north >= SLIDE_OVERHANG_GATE_M
    )
    log(
        "push_result",
        ok=slide_ok,
        moved_y_m=round(moved_y, 6),
        north_overhang_m=round(overhang_north, 6),
        bounds_min=[round(v, 6) for v in bounds_after_push[0]],
        bounds_max=[round(v, 6) for v in bounds_after_push[1]],
    )

    # Move to the north side of the island, then try a true thin-edge pinch.
    if not drive((STANCE[0], -0.75), 0.25, 20.0):
        log("navigate_north_side", ok=False)
        return _result(
            False, "navigate_north_side", phases, start, tray_pose(), args
        )
    tray_now = tray_pose()
    edge_y = _quaternion_from_rpy(math.pi, math.pi / 2.0, 0.0)
    edge_target = (tray_now[0], tray_now[1] + 0.02, tray_now[2] + 0.014)
    edge_ok = reach("right", edge_target, edge_y, 10.0)
    if not edge_ok:
        log_reach_failure("edge_precontact", "right", edge_target, edge_y)
        return _result(
            False, "edge_precontact", phases, start, tray_pose(), args
        )
    log("edge_precontact", ok=True, target=list(edge_target))
    lift_ok = False
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
