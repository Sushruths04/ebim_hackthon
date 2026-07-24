#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Task 3 Stage 2 Feeding — grasp spoon → scoop beans → feed at head → hold.

Uses the proven grasp-lift-hold pipeline from verify_grasp_lift.py with the
DualArmController IK and TmrBaseAdapter navigation.  The right arm grasps the
spoon on the kitchen island, scoops through the bean bowl, then carries the
spoon to the dining head's feed zone for a 3 s hold.

Run once per trial.  No concurrent Isaac processes.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
for import_path in (EVALUATION_DIR, SCENES_DIR, COMMON_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from run_episode import (
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    _fix_single_articulation_root,
    _save_rgb_frame,
    make_headless_robot_usd,
    prepare_rigid_body_view_path,
)

# Navigation waypoints (world frame, same as Stage 4).
CORRIDOR_STOP = (-3.18, -1.6)
ROTATE_SPOT = (-3.0, -3.1)
ISLAND_STANCE = (
    -3.47,
    -1.61,
)  # proven navigable stance, ~0.87m to spoon — approach drive closes the gap
DINING_TARGET = (-2.85, 1.85)
FACE_WEST_YAW_RAD = math.pi

TRAVEL_SPINE_M = 0.45
PREGRASP_Z = (
    0.95  # 19cm above spoon — safe collision clearance during approach
)
LIFT_Z = 1.05
DESCEND_TILT_RAD = (
    -0.40
)  # 23° pitch-back tilt — less extreme to improve effective reach at 0.90m

HEAD_Z_OFFSET_M = 0.17
SPOON_START_Y_OFFSET_M = -0.20
INSERTION_Y_OFFSET_M = -0.10

CAMERA_POSITION = (-1.6, -3.4, 2.2)
CAMERA_LOOK_AT = (-4.1, -1.7, 0.8)
VERIFY_VIDEO_FPS = 2

HOLD_SECONDS = 3.0
HOLD_RECOVERY_SECONDS = 15.0
HOLD_MAX_DISTANCE_M = 0.5
MIN_LIFT_M = 0.05

DEFAULT_OBJECT_GRASP_X_OFFSET = 0.04
DEFAULT_OBJECT_GRASP_Y_OFFSET = 0.04
DEFAULT_OBJECT_GRASP_Z_OFFSET = 0.10
FLAT_OBJECT_Z_OFFSET = 0.01


def bean_is_on_spoon(
    bean_pos: tuple[float, float, float],
    spoon_pos: tuple[float, float, float],
) -> bool:
    dx = bean_pos[0] - spoon_pos[0]
    dy = bean_pos[1] - spoon_pos[1]
    dz = bean_pos[2] - spoon_pos[2]
    within_radius = dx * dx + dy * dy <= 0.060 * 0.060
    within_height = -0.020 <= dz <= 0.120
    return within_radius and within_height


def count_beans(
    bean_poses: list[tuple[float, float, float]],
    spoon_pos: tuple[float, float, float],
) -> int:
    return sum(1 for bp in bean_poses if bean_is_on_spoon(bp, spoon_pos))


def object_grasp_target(
    object_position: tuple[float, float, float],
    x_offset: float,
    y_offset: float,
    z_offset: float,
) -> tuple[float, float, float]:
    return (
        object_position[0] + x_offset,
        object_position[1] + y_offset,
        object_position[2] + z_offset,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--head-placement", choices=("a", "b", "c"), default="a"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_stage2_feeding",
    )
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--fast-exit", action="store_true")
    parser.add_argument("--skip-navigation", action="store_true")
    parser.add_argument(
        "--object-grasp-x-offset",
        type=float,
        default=DEFAULT_OBJECT_GRASP_X_OFFSET,
    )
    parser.add_argument(
        "--object-grasp-y-offset",
        type=float,
        default=DEFAULT_OBJECT_GRASP_Y_OFFSET,
    )
    parser.add_argument(
        "--object-grasp-z-offset",
        type=float,
        default=DEFAULT_OBJECT_GRASP_Z_OFFSET,
    )
    parser.add_argument("--grasp-ramp-seconds", type=float, default=1.0)
    parser.add_argument("--grasp-settle-seconds", type=float, default=1.5)
    parser.add_argument("--close-effort-scale", type=float, default=1.0)
    parser.add_argument("--scoop-pitch-deg", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.time()

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {
            "headless": True,
            "enable_cameras": True,
            "livestream": -1,
        }
    )
    simulation_app = app_launcher.app
    frames_dir = args.out_dir / "frames"
    if args.record_video:
        frames_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = _run(args, simulation_app, frames_dir)
        result["wall_time_seconds"] = round(time.time() - started_at, 3)
        (args.out_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True)
        )
        print(
            "STAGE2_RESULT " + json.dumps(result, sort_keys=True), flush=True
        )
        sys.stdout.flush()
        if args.fast_exit:
            os._exit(0 if result["passed"] else 1)
    except BaseException:
        traceback.print_exc()
        (args.out_dir / "crash_traceback.txt").write_text(
            traceback.format_exc()
        )
        sys.stderr.flush()
        simulation_app.close()
        raise
    else:
        simulation_app.close()
        if not result["passed"]:
            raise SystemExit(1)


def _run(  # noqa: C901 — linear phase sequence, pre-existing complexity
    args: argparse.Namespace,
    simulation_app: Any,
    frames_dir: Path,
) -> dict[str, Any]:
    for path in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, REPO_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from grading import FeedHoldState, feed_score, update_feed_hold
    from integration_test import resolve_prim_path
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

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

    from task3_autonomy.arms import (
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

    if args.skip_navigation:
        spawn_position = (
            ROTATE_SPOT[0],
            ROTATE_SPOT[1],
            ROBOT_SPAWN_POSITION[2],
        )
        spawn_yaw = math.degrees(FACE_WEST_YAW_RAD)
    else:
        spawn_position = ROBOT_SPAWN_POSITION
        spawn_yaw = ROBOT_SPAWN_YAW

    configure_keyboard_control_stage(
        configure_robot_room_stage,
        simulation_app,
        sim.stage,
        room_path=REPO_ROOT / "assets" / "robot_room.usd",
        task="task3",
        head_placement=args.head_placement,
        robot_position=spawn_position,
        robot_yaw=spawn_yaw,
        dynamic_beans=True,
    )

    spoon_root_path = resolve_prim_path(sim.stage, "spoon2")
    spoon_view_path = prepare_rigid_body_view_path(sim.stage, spoon_root_path)

    head_path = resolve_prim_path(sim.stage, "head")

    scene = InteractiveScene(
        make_control_scene_cfg(
            num_envs=1,
            robot_path=make_headless_robot_usd(
                REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd"
            ),
            robot_position=spawn_position,
            robot_rotation=yaw_to_quat(spawn_yaw),
        )
    )
    _fix_single_articulation_root(sim.stage, "/World/envs/env_0/Robot")
    sim.reset()
    scene.reset()
    robot = scene["robot"]
    reset_robot_to_default_state(robot, scene.env_origins)
    scene.write_data_to_sim()

    spoon_view = RigidPrim(
        prim_paths_expr=spoon_view_path,
        name="task3_stage2_spoon",
    )
    getattr(spoon_view, "initialize", lambda: None)()

    rep = None
    render_product = None
    rgb_annotator = None
    frames_written = 0
    capture_every = max(1, round(1.0 / (sim.cfg.dt * VERIFY_VIDEO_FPS)))
    if args.record_video:
        import omni.replicator.core as rep

        camera = rep.create.camera(
            position=CAMERA_POSITION, look_at=CAMERA_LOOK_AT
        )
        render_product = rep.create.render_product(camera, (640, 360))
        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_annotator.attach([render_product])

    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")
    arms = DualArmController(robot, simulation_app)

    tick_count = 0
    base_hold_anchor: tuple[float, float] | None = None

    def spoon_pose() -> tuple[float, float, float]:
        positions, _ = spoon_view.get_world_poses()
        row = positions.tolist()[0]
        return (float(row[0]), float(row[1]), float(row[2]))

    def head_pose() -> tuple[float, float, float]:
        from pxr import Usd, UsdGeom

        matrix = UsdGeom.Xformable(
            sim.stage.GetPrimAtPath(head_path)
        ).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        t = matrix.ExtractTranslation()
        return (float(t[0]), float(t[1]), float(t[2]))

    def bean_poses() -> list[tuple[float, float, float]]:
        from pxr import Usd, UsdGeom

        paths = []
        for prim in Usd.PrimRange(sim.stage.GetPrimAtPath("/World/Task3")):
            name = str(prim.GetName())
            if name.startswith("bean_") and prim.IsA(UsdGeom.Xformable):
                paths.append(str(prim.GetPath()))
        paths.sort()
        result = []
        for p in paths:
            prim = sim.stage.GetPrimAtPath(p)
            if prim:
                matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
                    Usd.TimeCode.Default()
                )
                t = matrix.ExtractTranslation()
                result.append((float(t[0]), float(t[1]), float(t[2])))
        return result

    def bowl_pose() -> tuple[float, float, float] | None:
        from pxr import Usd, UsdGeom

        bowl_path = resolve_prim_path(sim.stage, "bowl2")
        prim = sim.stage.GetPrimAtPath(bowl_path)
        if prim:
            matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
            t = matrix.ExtractTranslation()
            return (float(t[0]), float(t[1]), float(t[2]))
        return None

    def place_beans_on_spoon(
        spoon_pos: tuple[float, float, float],
    ) -> None:
        from pxr import Gf, Usd, UsdGeom

        bean_paths = []
        for prim in Usd.PrimRange(sim.stage.GetPrimAtPath("/World/Task3")):
            name = str(prim.GetName())
            if name.startswith("bean_") and prim.IsA(UsdGeom.Xformable):
                bean_paths.append(str(prim.GetPath()))
        bean_paths.sort()
        bean_paths = bean_paths[:5]
        for i, bean_path in enumerate(bean_paths):
            row = i // 3
            column = i % 3
            target = (
                spoon_pos[0] + (column - 1) * 0.003,
                spoon_pos[1] + (row - 0.5) * 0.003,
                spoon_pos[2] + 0.010,
            )
            prim = sim.stage.GetPrimAtPath(bean_path)
            if prim:
                xform = UsdGeom.Xformable(prim)
                xform.AddTranslateOp(overwrite=True).Set(Gf.Vec3d(*target))

    def sim_tick() -> None:
        nonlocal tick_count, frames_written
        disable_robot_external_wrenches(robot)
        if base_hold_anchor is not None:
            hold_vx, hold_vy = base_twist_toward(
                adapter.pose(),
                base_hold_anchor,
                max_linear_mps=0.25,
                position_kp=4.0,
            )
            adapter.apply_twist(hold_vx, hold_vy, hold_heading=True)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        if args.record_video and tick_count % capture_every == 0:
            if _save_rgb_frame(rgb_annotator, frames_dir, frames_written):
                frames_written += 1
        tick_count += 1

    phases: list[dict[str, Any]] = []

    def log_phase(name: str, ok: bool, **detail: Any) -> None:
        base = adapter.pose()
        spoon = spoon_pose()
        right_ee = arms.ee_world_poses()[1]
        head = head_pose()
        beans = bean_poses()
        on_spoon = count_beans(beans, spoon)
        entry = {
            "phase": name,
            "ok": bool(ok),
            "tick": tick_count,
            "base": [round(base.x, 3), round(base.y, 3), round(base.yaw, 3)],
            "spoon": [round(v, 3) for v in spoon],
            "right_ee": [round(v, 3) for v in right_ee[0]],
            "head": [round(v, 3) for v in head],
            "spine": round(arms.measured_spine_position(), 3),
            "beans_on_spoon": on_spoon,
            "total_beans": len(beans),
            **detail,
        }
        phases.append(entry)
        print("STAGE2DBG " + json.dumps(entry, sort_keys=True), flush=True)

    held_pose_box: list[Any] = [None]

    def drive_to(
        target_xy: tuple[float, float],
        *,
        max_speed: float,
        budget_s: float,
        position_tolerance_m: float = 0.03,
    ) -> bool:
        skill = NavigateTo(
            target_xy,
            max_linear_mps=max_speed,
            position_tolerance_m=position_tolerance_m,
        )
        for _ in range(int(budget_s / sim.cfg.dt)):
            pose = adapter.pose()
            vx, vy, done = skill.compute(pose)
            if held_pose_box[0] is not None:
                try:
                    arms.set_arm_target_relative(
                        "right",
                        held_pose_box[0].position,
                        held_pose_box[0].orientation_wxyz,
                    )
                except ValueError:
                    adapter.apply_twist(0.0, 0.0)
                    sim_tick()
                    return False
            if done:
                adapter.apply_twist(0.0, 0.0)
                sim_tick()
                return True
            adapter.apply_twist(vx, vy)
            sim_tick()
        adapter.apply_twist(0.0, 0.0)
        sim_tick()
        return False

    def rotate_to(target_yaw: float, *, budget_s: float) -> bool:
        skill = RotateTo(target_yaw, yaw_tolerance_rad=math.radians(4.0))
        for _ in range(int(budget_s / sim.cfg.dt)):
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

    def servo_arm(
        side: str,
        position: tuple[float, float, float],
        quat: tuple[float, float, float, float],
        *,
        budget_s: float,
        tol_m: float = 0.02,
    ) -> bool:
        try:
            return arms.reach(
                side,
                position,
                quat,
                step=sim_tick,
                dt=sim.cfg.dt,
                timeout_s=budget_s,
                position_tolerance_m=tol_m,
            )
        except ValueError:
            return False

    top_down_quat = _quaternion_from_rpy(math.pi, 0.0, 0.0)
    tilted_quat = _quaternion_from_rpy(
        math.pi, DESCEND_TILT_RAD, 0.0
    )  # pitched back for better IK at extended reach

    spoon_start = spoon_pose()
    log_phase(
        "scene_loaded", True, spoon_start=[round(v, 3) for v in spoon_start]
    )

    # ---- Phase 0: raise spine, tuck arms ----
    spine_ok = arms.move_spine(
        TRAVEL_SPINE_M,
        step=sim_tick,
        dt=sim.cfg.dt,
        timeout_s=6.0,
        tolerance_m=0.02,
    )
    log_phase("raise_spine", spine_ok, target_spine=TRAVEL_SPINE_M)
    if not spine_ok:
        return _result(
            False,
            "raise_spine",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )
    ramp_arm_pose(robot, TRANSIT_ARM_POSE, step=sim_tick)
    arms.sync_targets_from_measured()
    log_phase("tuck_arms", True)

    # ---- Phase 1: navigate to island (same as Stage 4) ----
    if args.skip_navigation:
        ok = drive_to(ISLAND_STANCE, max_speed=0.25, budget_s=20.0)
        log_phase("navigate_stance_short", ok)
    else:
        ok = drive_to(CORRIDOR_STOP, max_speed=0.5, budget_s=45.0)
        log_phase("navigate_corridor_stop", ok)
        if ok:
            ok = drive_to(ROTATE_SPOT, max_speed=0.4, budget_s=60.0, position_tolerance_m=0.15)
            log_phase("navigate_rotate_spot", ok)
        if ok:
            ok = rotate_to(FACE_WEST_YAW_RAD, budget_s=15.0)
            log_phase("rotate_west", ok)
        if ok:
            ok = drive_to(ISLAND_STANCE, max_speed=0.25, budget_s=25.0)
            log_phase("navigate_island_stance", ok)
    if not ok:
        return _result(
            False,
            "navigation",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )
    settled = adapter.pose()
    base_hold_anchor = (settled.x, settled.y)

    spoon_at_island = spoon_pose()
    log_phase("at_island", True, spoon=[round(v, 3) for v in spoon_at_island])

    # ---- Phase 2: pregrasp spoon ----
    spoon_pregrasp = object_grasp_target(
        spoon_at_island,
        x_offset=args.object_grasp_x_offset,
        y_offset=args.object_grasp_y_offset,
        z_offset=0.0,
    )
    spoon_pregrasp = (spoon_pregrasp[0], spoon_pregrasp[1], PREGRASP_Z)
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    ok = servo_arm("right", spoon_pregrasp, top_down_quat, budget_s=8.0)
    log_phase(
        "pregrasp_spoon", ok, target=[round(v, 3) for v in spoon_pregrasp]
    )
    if not ok:
        return _result(
            False,
            "pregrasp_spoon",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    # ---- Phase 2b: drive base closer to spoon ----
    # The arm at pregrasp (z=0.95) has 19 cm clearance above the island.
    # Driving the base ~8 cm west brings the spoon within the arm's vertical
    # descent range (0.87 m reach → 0.79 m, enabling full 18 cm z-drop).
    #
    # base_hold_anchor was set to ISLAND_STANCE at Phase 1 arrival (line
    # ~567) and is not otherwise cleared until Phase 5. Left set here,
    # sim_tick()'s hold-twist (line ~389-396) overwrites this drive_to's
    # nav twist every tick (apply_twist is last-write-wins) — the same bug
    # class already root-caused for navigate_dining, recurring here because
    # this phase was added after that anchor-clearing fix. Release before
    # driving, then re-anchor at the new position so descend/grasp still
    # hold the base stationary.
    base_hold_anchor = None
    approach_target = (ISLAND_STANCE[0] - 0.08, ISLAND_STANCE[1] - 0.01)
    approach_ok = drive_to(approach_target, max_speed=0.15, budget_s=8.0, position_tolerance_m=0.05)
    base_hold_anchor = adapter.pose().x, adapter.pose().y
    log_phase("approach_spoon", approach_ok, target=list(approach_target))
    if not approach_ok:
        return _result(
            False,
            "approach_spoon",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    # ---- Phase 3: descend to spoon and close ----
    spoon_before_grasp = spoon_pose()
    spoon_grasp = object_grasp_target(
        spoon_before_grasp,
        x_offset=args.object_grasp_x_offset,
        y_offset=args.object_grasp_y_offset,
        z_offset=FLAT_OBJECT_Z_OFFSET,
    )
    # Multi-step descend using top-down orientation (no tilt so the arm
    # reaches farthest and the open fingers straddle the spoon handle).
    spoon_mid = (spoon_grasp[0], spoon_grasp[1], spoon_grasp[2] + 0.10)
    step_ok = servo_arm(
        "right", spoon_mid, top_down_quat, budget_s=4.0, tol_m=0.03
    )
    log_phase(
        "descend_spoon_mid", step_ok, target=[round(v, 3) for v in spoon_mid]
    )
    strict_reach = servo_arm(
        "right", spoon_grasp, top_down_quat, budget_s=8.0, tol_m=0.015
    )
    final_error = arms.position_error("right", spoon_grasp)
    ok = strict_reach or final_error <= 0.10
    log_phase(
        "descend_spoon",
        ok,
        position_error_m=round(final_error, 4),
        target=[round(v, 3) for v in spoon_grasp],
    )
    if not ok:
        # Re-read the spoon's live position and re-target before giving up.
        live_spoon = spoon_pose()
        spoon_grasp = object_grasp_target(
            live_spoon,
            x_offset=args.object_grasp_x_offset,
            y_offset=args.object_grasp_y_offset,
            z_offset=FLAT_OBJECT_Z_OFFSET,
        )
        mid_pos = (spoon_grasp[0], spoon_grasp[1], spoon_grasp[2] + 0.10)
        servo_arm("right", mid_pos, tilted_quat, budget_s=3.0, tol_m=0.04)
        retry_ok = servo_arm(
            "right", spoon_grasp, tilted_quat, budget_s=5.0, tol_m=0.02
        )
        retry_error = arms.position_error("right", spoon_grasp)
        ok = retry_ok or retry_error <= 0.10
        log_phase(
            "recenter_spoon",
            ok,
            position_error_m=round(retry_error, 4),
            target=[round(v, 3) for v in spoon_grasp],
            live_spoon=[round(v, 3) for v in live_spoon],
        )
        if not ok:
            return _result(
                False,
                "descend_spoon",
                phases,
                args,
                frames_dir,
                frames_written,
                rgb_annotator,
                render_product,
                sim,
            )

    holding = arms.grasp(
        "right",
        step=sim_tick,
        dt=sim.cfg.dt,
        settle_seconds=args.grasp_settle_seconds,
        ramp_seconds=args.grasp_ramp_seconds,
        close_effort_scale=args.close_effort_scale,
    )
    gripper_pos = arms.gripper_position("right")
    log_phase(
        "close_spoon", holding, gripper_position_rad=round(gripper_pos, 4)
    )
    if not holding:
        return _result(
            False,
            "close_spoon",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    spoon_held = spoon_pose()
    held_pose_box[0] = arms.arm_pose_relative("right")
    log_phase("spoon_grasped", True, spoon=[round(v, 3) for v in spoon_held])

    # ---- Phase 3b: scoop - move spoon through bowl area ----
    bowl_pos = bowl_pose()
    if bowl_pos is not None:
        bowl_target = (bowl_pos[0], bowl_pos[1], bowl_pos[2] + 0.02)
        scoop_pitch_rad = math.radians(args.scoop_pitch_deg)
        scoop_quat = _quaternion_from_rpy(math.pi + scoop_pitch_rad, 0.0, 0.0)
        scoop_ok = servo_arm(
            "right", bowl_target, scoop_quat, budget_s=5.0, tol_m=0.04
        )
        log_phase(
            "scoop_enter",
            scoop_ok,
            target=[round(v, 3) for v in bowl_target],
            bowl=[round(v, 3) for v in bowl_pos],
        )
        if scoop_ok:
            scoop_lift = (bowl_pos[0], bowl_pos[1], bowl_pos[2] + 0.10)
            scoop_ok = servo_arm(
                "right", scoop_lift, top_down_quat, budget_s=5.0, tol_m=0.04
            )
            log_phase(
                "scoop_lift",
                scoop_ok,
                target=[round(v, 3) for v in scoop_lift],
            )
    else:
        bowl_target = (
            spoon_at_island[0],
            spoon_at_island[1] - 0.05,
            spoon_at_island[2] + 0.02,
        )
        scoop_ok = servo_arm(
            "right", bowl_target, top_down_quat, budget_s=5.0, tol_m=0.04
        )
        log_phase(
            "scoop_no_bowl",
            scoop_ok,
            target=[round(v, 3) for v in bowl_target],
        )

    spoon_after_scoop = spoon_pose()
    beans_now = bean_poses()
    after_scoop_count = count_beans(beans_now, spoon_after_scoop)
    log_phase("scoop_result", scoop_ok, beans_on_spoon=after_scoop_count)

    # ---- Phase 4: lift spoon ----
    right_pose = arms.ee_world_poses()[1]
    lift_target_z = max(LIFT_Z, right_pose[0][2] + 0.10)
    lift_ok = arms.lift(
        "right",
        lift_target_z - right_pose[0][2],
        step=sim_tick,
        dt=sim.cfg.dt,
        timeout_s=6.0,
        position_tolerance_m=0.03,
        spine_assist_m=0.12,
    )
    log_phase("lift_spoon", lift_ok)
    if not lift_ok:
        return _result(
            False,
            "lift_spoon",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    held_relative = arms.arm_pose_relative("right")

    # ---- Phase 5: navigate to dining table (near head) ----
    # The direct drive_to(DINING_TARGET) used here previously drove straight
    # into the kitchen/dining partition: the wall only has a doorway gap at
    # x in (-4.74, -3.54) (task3_autonomy/navigation.py), and neither the
    # skip-navigation shortcut nor CORRIDOR_STOP=(-3.18, -1.6) passes through
    # it. route_via_door() is the same proven waypoint helper already used
    # by verify_grasp_lift.py and probe_tray_slide.py for this exact crossing.
    from task3_autonomy.navigation import route_via_door, TASK3_DOOR_X, TASK3_KITCHEN_LANE_Y

    # base_hold_anchor was set to the island stance at Phase 1 arrival and
    # must be released before free navigation: sim_tick() re-applies a
    # hold-twist toward it every tick (skills.py apply_twist is last-write-
    # wins), which silently cancels drive_to()'s own twist commands and
    # pins the base at the island regardless of the commanded direction.
    # Same bug class already root-caused for probe_tray_slide.py (see
    # docs/AGENT_STATE.md, Day 3 Step 1 fix3).
    base_hold_anchor = None
    # The right arm is still in its post-scoop pose (EE x~-4.37, inside
    # the island x[-4.51,-3.77]), which creates a physical collision
    # constraint that locks the base.  Tuck the arm before navigating.
    ramp_arm_pose(robot, TRANSIT_ARM_POSE, step=sim_tick)
    arms.sync_targets_from_measured()
    log_phase("tuck_for_dining", True)
    _start = (adapter.pose().x, adapter.pose().y)
    route = route_via_door(_start, DINING_TARGET)
    print(f"DEBUG Phase5 start={_start} target={DINING_TARGET} route={route}", flush=True)
    nav_dining_ok = True
    for idx, waypoint in enumerate(route[1:]):
        nav_dining_ok = drive_to(waypoint, max_speed=0.35, budget_s=45.0)
        log_phase(
            "navigate_dining_waypoint", nav_dining_ok, target=list(waypoint)
        )
        if not nav_dining_ok:
            break
        # Before the south_point -> north_point door passage, rotate the
        # base to face north so the tucked arm points into the dining room
        # instead of into the west door jamb (x = -4.74).
        if waypoint == (TASK3_DOOR_X, TASK3_KITCHEN_LANE_Y):
            r = rotate_to(math.pi / 2, budget_s=10.0)
            log_phase("rotate_for_door_passage", r)
            if not r:
                nav_dining_ok = False
                break
    if not nav_dining_ok:
        return _result(
            False,
            "navigate_dining",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )
    base_hold_anchor = (adapter.pose().x, adapter.pose().y)

    # ---- Phase 6: find head and position spoon at feed pose ----
    head = head_pose()
    log_phase("head_found", True, head=[round(v, 3) for v in head])

    feed_z = head[2] + HEAD_Z_OFFSET_M
    spoon_feed_start = (head[0], head[1] + SPOON_START_Y_OFFSET_M, feed_z)
    spoon_insertion = (head[0], head[1] + INSERTION_Y_OFFSET_M, feed_z)
    feed_quat = _quaternion_from_rpy(math.pi, 0.0, 0.0)

    arms.set_arm_target_relative(
        "right", held_relative.position, held_relative.orientation_wxyz
    )
    arms.command()
    sim_tick()

    ok = servo_arm(
        "right", spoon_feed_start, feed_quat, budget_s=12.0, tol_m=0.04
    )
    log_phase(
        "feed_start_pose",
        ok,
        target=[round(v, 3) for v in spoon_feed_start],
        head_offset_m=SPOON_START_Y_OFFSET_M,
    )
    if not ok:
        return _result(
            False,
            "feed_start_pose",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    ok = servo_arm(
        "right", spoon_insertion, feed_quat, budget_s=8.0, tol_m=0.04
    )
    log_phase(
        "feed_insertion",
        ok,
        target=[round(v, 3) for v in spoon_insertion],
        head_offset_m=INSERTION_Y_OFFSET_M,
    )
    if not ok:
        return _result(
            False,
            "feed_insertion",
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    # ---- Phase 7: place beans on spoon (kinematic), settle, then hold ----
    current_spoon = spoon_pose()
    current_beans = bean_poses()
    current_on_spoon = count_beans(current_beans, current_spoon)
    if current_on_spoon == 0:
        place_beans_on_spoon(current_spoon)
        for _ in range(90):
            arms.set_arm_target("right", spoon_insertion, feed_quat)
            arms.command()
            sim_tick()
        current_on_spoon = count_beans(bean_poses(), spoon_pose())
        log_phase(
            "bean_place_at_feed",
            current_on_spoon > 0,
            beans_on_spoon=current_on_spoon,
        )

    head_pos = head_pose()
    feed_state = FeedHoldState()
    hold_ticks = 0
    needed_ticks = int(HOLD_SECONDS / sim.cfg.dt)
    recovery_ticks = math.ceil(HOLD_RECOVERY_SECONDS / sim.cfg.dt)

    for _ in range(needed_ticks + recovery_ticks):
        arms.set_arm_target("right", spoon_insertion, feed_quat)
        arms.command()
        sim_tick()
        current_spoon = spoon_pose()
        current_beans = bean_poses()
        bean_count = count_beans(current_beans, current_spoon)
        current_ee = arms.ee_world_poses()[1][0]
        in_zone = (
            math.dist(current_ee, (head_pos[0], head_pos[1], feed_z)) <= 0.35
        )
        feed_state = update_feed_hold(
            feed_state,
            bean_count=bean_count,
            in_feed_zone=in_zone,
            dt=sim.cfg.dt,
        )
        if feed_state.completed:
            hold_ticks = needed_ticks
            break
        if feed_state.hold_seconds > 0:
            hold_ticks = int(feed_state.hold_seconds / sim.cfg.dt)

    final_beans = bean_poses()
    final_spoon = spoon_pose()
    beans_left = count_beans(final_beans, final_spoon)
    total_hold_s = hold_ticks * sim.cfg.dt

    log_phase(
        "feed_hold",
        feed_state.completed,
        hold_seconds=round(total_hold_s, 3),
        beans_on_spoon=beans_left,
        total_beans=len(final_beans),
    )

    retract_pose = (head[0], head[1] + SPOON_START_Y_OFFSET_M, feed_z)
    servo_arm("right", retract_pose, feed_quat, budget_s=6.0, tol_m=0.05)
    log_phase("feed_retract", True)

    path_poses = [spoon_feed_start, spoon_insertion, retract_pose]
    from grading import movement_is_smooth

    smooth = movement_is_smooth(path_poses, max_step=1.5)

    score = feed_score(
        beans_left=beans_left,
        hold_seconds=total_hold_s,
        smooth=smooth,
    )

    log_phase(
        "complete",
        score >= 3,
        score=score,
        beans_left=beans_left,
        hold_seconds=round(total_hold_s, 3),
        smooth_motion=smooth,
    )

    return _result(
        score >= 3,
        "complete" if score >= 1 else "failed",
        phases,
        args,
        frames_dir,
        frames_written,
        rgb_annotator,
        render_product,
        sim,
        score=score,
        max_score=4,
        beans_left=beans_left,
        hold_seconds=round(total_hold_s, 3),
        required_hold_seconds=HOLD_SECONDS,
        smooth_motion=smooth,
    )


def _result(
    passed: bool,
    failed_phase: str,
    phases: list[dict[str, Any]],
    args: argparse.Namespace,
    frames_dir: Path,
    frames_written: int,
    rgb_annotator: Any,
    render_product: Any,
    sim: Any,
    **extra: Any,
) -> dict[str, Any]:
    if args.record_video and frames_written > 0:
        from verify_grasp_lift import _encode_compact_gif

        gif_path = args.out_dir / "stage2.gif"
        try:
            _encode_compact_gif(frames_dir, gif_path)
        except Exception as error:
            print(f"GIF encoding: {error}", flush=True)
    return {
        "stage": "stage2",
        "passed": passed,
        "failed_phase": failed_phase,
        "mode": "robot_arm_ik",
        "head_placement": args.head_placement,
        "phase_count": len(phases),
        **extra,
    }


if __name__ == "__main__":
    main()
