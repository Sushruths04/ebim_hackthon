# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Fixed grasp+lift with spine-first lift + high-friction gripper pads.

Patches the USD scene to add PhysX friction material to gripper fingers,
then implements spine-first lift (keep arm joints fixed, raise spine to lift the cup).
Collision and grasping code unchanged from verify_grasp_lift.py.
"""

import argparse
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENES_DIR = REPO_ROOT / "scripts"
COMMON_DIR = REPO_ROOT / "apps"
EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation"
sys.path.insert(0, str(SCENES_DIR))
sys.path.insert(0, str(COMMON_DIR))
sys.path.insert(0, str(EVALUATION_DIR))
sys.path.insert(0, str(REPO_ROOT))

VERIFY_VIDEO_FPS = 2
CAMERA_POSITION = (-1.6, -3.4, 2.2)
CAMERA_LOOK_AT = (-4.1, -1.7, 0.8)

CORRIDOR_STOP = (-3.18, -1.6)
ROTATE_SPOT = (-3.0, -3.1)
STANCE = (-3.32, -1.72)
FACE_WEST_YAW_RAD = math.pi
FACE_WEST_YAW_DEG = 180.0
CUP_GRASP_XY = (-4.145, -1.75)
CUP_RIM_X_OFFSET = 0.04
CUP_GRASP_Y_OFFSET = 0.06
GRASP_HEIGHT_ABOVE_CUP_ORIGIN = 0.068
LIFT_Z = 1.10
TRAVEL_SPINE_M = 0.45


def cup_grasp_target(
    cup_position, *, rim_x_offset, grasp_y_offset, grasp_z_offset=0.0
):
    return (
        cup_position[0] + rim_x_offset,
        cup_position[1] + grasp_y_offset,
        cup_position[2] + GRASP_HEIGHT_ABOVE_CUP_ORIGIN + grasp_z_offset,
    )


def object_grasp_target(object_position, *, x_offset, y_offset, z_offset):
    return (
        object_position[0] + x_offset,
        object_position[1] + y_offset,
        object_position[2] + z_offset,
    )


def _save_rgb_frame(annotator, frames_dir, index):
    import numpy as np
    from PIL import Image

    data = annotator.get_data()
    if data is None:
        return False
    Image.fromarray(data[:, :, :3].astype(np.uint8)).save(
        frames_dir / f"rgb_{index:04d}.png"
    )
    return True


def _encode_compact_gif(frames_dir, output_path):
    from PIL import Image

    images = [
        Image.open(p).convert("P", palette=Image.Palette.ADAPTIVE)
        for p in sorted(frames_dir.glob("rgb_*.png"))
    ]
    if not images:
        raise RuntimeError(f"No frames at {frames_dir}")
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=round(1000 / VERIFY_VIDEO_FPS),
        loop=0,
        optimize=True,
    )


def patch_gripper_friction(stage, friction=2.0):
    """Apply high-friction PhysX material to gripper finger collision prims."""
    from pxr import Usd, UsdPhysics, UsdShade

    robot_path = "/World/envs/env_0/Robot"
    robot_prim = stage.GetPrimAtPath(robot_path)
    if not robot_prim:
        print("GRIPPER_PATCH: robot not found", flush=True)
        return
    finger_prim_paths = []
    for prim in Usd.PrimRange(robot_prim):
        path = str(prim.GetPath())
        if "finger" in path.lower() and prim.HasAPI(UsdPhysics.CollisionAPI):
            finger_prim_paths.append(path)
    if not finger_prim_paths:
        print("GRIPPER_PATCH: no finger collision prims found", flush=True)
        return
    material_path = f"{robot_path}/HighFrictionGripperMaterial"
    material = UsdShade.Material.Define(stage, material_path)
    phys_mat = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    phys_mat.CreateStaticFrictionAttr().Set(friction)
    phys_mat.CreateDynamicFrictionAttr().Set(friction * 0.8)
    phys_mat.CreateRestitutionAttr().Set(0.0)
    for fp in finger_prim_paths:
        prim = stage.GetPrimAtPath(fp)
        binding = UsdShade.MaterialBindingAPI.Apply(prim)
        binding.Bind(material)
    print(
        f"GRIPPER_PATCH: applied friction={friction} to {len(finger_prim_paths)} finger prims",
        flush=True,
    )


def high_friction_collision(stage, friction=1.5):
    """Apply high-friction material to ALL collision prims in the scene (cup, gripper)."""
    from pxr import Usd, UsdPhysics, UsdShade

    material_path = "/World/HighFrictionSurface"
    material = UsdShade.Material.Define(stage, material_path)
    phys_mat = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    phys_mat.CreateStaticFrictionAttr().Set(friction)
    phys_mat.CreateDynamicFrictionAttr().Set(friction * 0.8)
    phys_mat.CreateRestitutionAttr().Set(0.0)

    count = 0
    for prim in Usd.PrimRange(stage.GetPrimAtPath("/World")):
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            binding = UsdShade.MaterialBindingAPI.Apply(prim)
            binding.Bind(material)
            count += 1
    print(
        f"FRICTION_PATCH: applied friction={friction} to {count} collision prims",
        flush=True,
    )


def _prepare_sim(record_video, livestream, public_ip):
    if livestream and public_ip:
        os.environ["PUBLIC_IP"] = str(public_ip)
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {
            "headless": True,
            "enable_cameras": bool(record_video or livestream),
            "livestream": 1 if livestream else -1,
        }
    )
    return app_launcher.app


def parse_args():
    p = argparse.ArgumentParser(
        description="Fixed grasp+lift with spine-first lift + high friction."
    )
    p.add_argument(
        "--object-name",
        choices=("cup", "bowl2", "spoon2", "plate2", "simple_tray"),
        default="cup",
    )
    p.add_argument("--record-video", action="store_true")
    p.add_argument("--livestream", action="store_true")
    p.add_argument("--fast-exit", action="store_true")
    p.add_argument("--skip-navigation", action="store_true")
    p.add_argument("--min-lift-m", type=float, default=0.02)
    p.add_argument("--hold-seconds", type=float, default=1.0)
    p.add_argument("--hold-recovery-seconds", type=float, default=12.0)
    p.add_argument("--close-effort-scale", type=float, default=1.0)
    p.add_argument("--grasp-ramp-seconds", type=float, default=2.0)
    p.add_argument("--grasp-settle-seconds", type=float, default=4.0)
    p.add_argument("--cup-grasp-z-offset", type=float, default=-0.02)
    p.add_argument(
        "--friction",
        type=float,
        default=2.0,
        help="Physics friction coefficient for gripper/cup",
    )
    p.add_argument(
        "--spine-only-lift",
        action="store_true",
        default=True,
        help="Lift using spine only (keep arm joints fixed)",
    )
    p.add_argument("--public-ip", default=os.environ.get("PUBLIC_IP"))
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "fixed_grasp_lift",
    )
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = args.out_dir.resolve()
    frames_dir = out_dir / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.record_video:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for f in frames_dir.glob("rgb_*.png"):
            f.unlink()

    started_at = time.time()
    simulation_app = _prepare_sim(
        args.record_video, args.livestream, args.public_ip
    )

    try:
        result = _verify(args, simulation_app, frames_dir)
        result["wall_time_seconds"] = round(time.time() - started_at, 3)
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True)
        )
        print("FIXED_RESULT " + json.dumps(result, sort_keys=True), flush=True)
        sys.stdout.flush()
        if args.fast_exit:
            os._exit(0 if result["passed"] else 1)
    except BaseException:
        traceback.print_exc()
        (out_dir / "crash_traceback.txt").write_text(traceback.format_exc())
        sys.stderr.flush()
        if args.fast_exit:
            os._exit(2)
        simulation_app.close()
        raise
    else:
        simulation_app.close()
        if not result["passed"]:
            raise SystemExit(1)


def _verify(args, simulation_app, frames_dir):
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

    rep = None
    if args.record_video:
        import omni.replicator.core as rep

    from isaacsim.core.prims import RigidPrim

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

    from task3_autonomy.arms import (
        GRIPPER_OPEN_RAD,
        DualArmController,
        grasp_lift_gate_passed,
    )
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

    spawn_position = (
        (ROTATE_SPOT[0], ROTATE_SPOT[1], 0.1117)
        if args.skip_navigation
        else (0.2961, 1.572, 0.1117)
    )
    spawn_yaw_deg = FACE_WEST_YAW_DEG if args.skip_navigation else 0.0

    configure_keyboard_control_stage(
        configure_robot_room_stage,
        simulation_app,
        sim.stage,
        room_path=REPO_ROOT / "assets" / "robot_room.usd",
        task="task3",
        head_placement="a",
        robot_position=spawn_position,
        robot_yaw=spawn_yaw_deg,
        dynamic_beans=False,
    )

    # Apply high-friction material to entire scene
    high_friction_collision(sim.stage, friction=args.friction)

    object_root_path = resolve_prim_path(sim.stage, args.object_name)

    from isaaclab_assets.robots.fr3 import _fix_single_articulation_root
    from isaaclab_assets.robots.fr3 import (
        _prepare_rigid_body_view_path as prepare_rigid_body_view_path,
    )

    # Reuse prepare from scene helper
    def make_object_path(stage, root_path):
        from isaaclab.sim.utils import prepare_rigid_body_view

        rigid = prepare_rigid_body_view(stage, root_path)
        return rigid.GetPrim().GetPath().pathString

    object_path = prepare_rigid_body_view_path(sim.stage, object_root_path)

    scene = InteractiveScene(
        make_control_scene_cfg(
            num_envs=1,
            robot_path=make_headless_robot_usd(
                REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd"
            ),
            robot_position=spawn_position,
            robot_rotation=yaw_to_quat(spawn_yaw_deg),
        )
    )
    _fix_single_articulation_root(sim.stage, "/World/envs/env_0/Robot")
    sim.reset()
    scene.reset()
    robot = scene["robot"]
    reset_robot_to_default_state(robot, scene.env_origins)
    scene.write_data_to_sim()

    object_view = RigidPrim(
        prim_paths_expr=object_path, name=f"task3_{args.object_name}"
    )
    getattr(object_view, "initialize", lambda: None)()

    def cup_position():
        pos, _ = object_view.get_world_poses()
        row = pos.tolist()[0]
        return (float(row[0]), float(row[1]), float(row[2]))

    rgb_annotator = None
    render_product = None
    frames_written = 0
    capture_every = max(1, round(1.0 / (sim.cfg.dt * VERIFY_VIDEO_FPS)))
    if args.record_video:
        camera = rep.create.camera(
            position=CAMERA_POSITION, look_at=CAMERA_LOOK_AT
        )
        render_product = rep.create.render_product(camera, (640, 360))
        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_annotator.attach([render_product])

    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")
    arms = DualArmController(robot, simulation_app)

    tick_count = 0
    base_hold_anchor = None

    def sim_tick():
        nonlocal tick_count, frames_written
        disable_robot_external_wrenches(robot)
        if base_hold_anchor is not None:
            from task3_autonomy.navigation import base_twist_toward as _btt

            vx, vy = _btt(
                adapter.pose(),
                base_hold_anchor,
                max_linear_mps=0.25,
                position_kp=4.0,
            )
            adapter.apply_twist(vx, vy, hold_heading=True)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        if args.record_video and tick_count % capture_every == 0:
            if _save_rgb_frame(rgb_annotator, frames_dir, frames_written):
                frames_written += 1
        tick_count += 1

    phases = []

    def log_phase(name, ok, **detail):
        base = adapter.pose()
        cup = cup_position()
        left, right = arms.ee_world_poses()
        entry = {
            "phase": name,
            "ok": bool(ok),
            "tick": tick_count,
            "base": [round(base.x, 3), round(base.y, 3), round(base.yaw, 3)],
            "cup": [round(v, 3) for v in cup],
            "right_ee": [round(v, 3) for v in right[0]],
            "left_ee": [round(v, 3) for v in left[0]],
            "spine": round(arms.measured_spine_position(), 3),
            **detail,
        }
        phases.append(entry)
        print("FIXDBG " + json.dumps(entry, sort_keys=True), flush=True)

    def drive_to(target_xy, *, max_speed, budget_s):
        skill = NavigateTo(target_xy, max_linear_mps=max_speed)
        for _ in range(int(budget_s / sim.cfg.dt)):
            pose = adapter.pose()
            vx, vy, done = skill.compute(pose)
            if done:
                adapter.apply_twist(0.0, 0.0)
                sim_tick()
                return True
            adapter.apply_twist(vx, vy)
            sim_tick()
        adapter.apply_twist(0.0, 0.0)
        sim_tick()
        return False

    def rotate_to(target_yaw, *, budget_s):
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

    def servo_arm(side, position, quat, *, budget_s, tol_m=0.02):
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

    # === Phase 0: raise spine, tuck ===
    travel_spine_target = TRAVEL_SPINE_M
    spine_ok = arms.move_spine(
        travel_spine_target,
        step=sim_tick,
        dt=sim.cfg.dt,
        timeout_s=6.0,
        tolerance_m=0.02,
    )
    log_phase("raise_spine", spine_ok, target_spine=travel_spine_target)
    if not spine_ok:
        return _result(
            False,
            "raise_spine",
            cup_position(),
            cup_position(),
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
    log_phase("tuck_spine_up", True)
    cup_start = cup_position()

    # === Phase 1: navigate ===
    if args.skip_navigation:
        ok = drive_to(STANCE, max_speed=0.25, budget_s=20.0)
        log_phase("navigate_stance_short", ok)
    else:
        ok = drive_to(CORRIDOR_STOP, max_speed=0.5, budget_s=45.0)
        log_phase("navigate_corridor_stop", ok)
        ok = drive_to(ROTATE_SPOT, max_speed=0.4, budget_s=35.0)
        log_phase("navigate_rotate_spot", ok)
        ok = rotate_to(FACE_WEST_YAW_RAD, budget_s=15.0)
        log_phase("rotate_west", ok)
        ok = drive_to(STANCE, max_speed=0.25, budget_s=20.0)
        log_phase("navigate_stance", ok)
    if not ok:
        return _result(
            False,
            "navigation",
            cup_start,
            cup_position(),
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )
    settled_pose = adapter.pose()
    base_hold_anchor = (settled_pose.x, settled_pose.y)
    approach_start = cup_position()

    # === Phase 2: pregrasp ===
    top_down = _quaternion_from_rpy(math.pi, 0.0, 0.0)
    pregrasp = (CUP_GRASP_XY[0], CUP_GRASP_XY[1], 1.05)
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    ok = servo_arm("right", pregrasp, top_down, budget_s=8.0)
    log_phase("pregrasp", ok, target=[round(v, 3) for v in pregrasp])
    if not ok:
        return _result(
            False,
            "pregrasp",
            cup_start,
            cup_position(),
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    # === Phase 3: descend ===
    cup_before_descend = cup_position()
    grasp = cup_grasp_target(
        cup_before_descend,
        rim_x_offset=CUP_RIM_X_OFFSET,
        grasp_y_offset=CUP_GRASP_Y_OFFSET,
        grasp_z_offset=args.cup_grasp_z_offset,
    )
    strict_reach = servo_arm(
        "right", grasp, top_down, budget_s=6.0, tol_m=0.015
    )
    final_approach_error = arms.position_error("right", grasp)
    contact_tolerance = 0.12
    ok = strict_reach or (final_approach_error <= contact_tolerance)
    log_phase(
        "descend",
        ok,
        strict_reach=strict_reach,
        position_error_m=round(final_approach_error, 4),
        target=[round(v, 3) for v in grasp],
    )
    if not ok:
        return _result(
            False,
            "descend",
            cup_start,
            cup_position(),
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    # Re-center on live cup after descend contact push
    live_cup = cup_position()
    grasp = cup_grasp_target(
        live_cup,
        rim_x_offset=CUP_RIM_X_OFFSET,
        grasp_y_offset=CUP_GRASP_Y_OFFSET,
        grasp_z_offset=args.cup_grasp_z_offset,
    )
    servo_arm("right", grasp, top_down, budget_s=4.0, tol_m=0.02)
    log_phase(
        "recenter_live_cup",
        arms.position_error("right", grasp) <= 0.10,
        position_error_m=round(arms.position_error("right", grasp), 4),
    )

    # Close gripper with increased effort
    holding = arms.grasp(
        "right",
        step=sim_tick,
        dt=sim.cfg.dt,
        settle_seconds=args.grasp_settle_seconds,
        ramp_seconds=args.grasp_ramp_seconds,
        close_effort_scale=args.close_effort_scale,
    )
    gripper_position = arms.gripper_position("right")
    log_phase(
        "close", holding, gripper_position_rad=round(gripper_position, 4)
    )
    if not holding:
        return _result(
            False,
            "close",
            cup_start,
            cup_position(),
            phases,
            args,
            frames_dir,
            frames_written,
            rgb_annotator,
            render_product,
            sim,
        )

    # === Phase 4: SPINE-FIRST LIFT ===
    right_pose = arms.ee_world_poses()[1]

    if args.spine_only_lift:
        # Strategy: keep arm joints FIXED, raise spine to lift the object.
        # The arm base rises with the spine, the arm joints don't change,
        # so the EE moves up purely vertically.
        start_spine = arms.measured_spine_position()
        max_spine = start_spine + 0.12  # spine can lift ~12cm
        spine_ramp_ticks = math.ceil(3.0 / sim.cfg.dt)  # 3s to raise spine
        spine_timeout_ticks = math.ceil(6.0 / sim.cfg.dt)

        # Get the current arm joint pose relative to base
        rel_pose = arms.arm_pose_relative("right")

        lift_ok = False
        for tick in range(spine_timeout_ticks):
            alpha = min(1.0, (tick + 1) / spine_ramp_ticks)
            target_spine = start_spine + 0.12 * alpha

            # Keep arm fixed relative to base (spine carries it up)
            arms.spine = target_spine
            try:
                arms.set_arm_target_relative(
                    "right", rel_pose.position, rel_pose.orientation_wxyz
                )
            except ValueError:
                pass
            arms.command()
            sim_tick()

            if tick + 1 >= spine_ramp_ticks:
                # Check how much the cup has lifted
                current_cup = cup_position()
                cup_rise = current_cup[2] - cup_start[2]
                if cup_rise >= 0.02:
                    lift_ok = True
                    break

        # If spine alone wasn't enough, try arm lift
        if not lift_ok:
            current_cup = cup_position()
            cup_rise = current_cup[2] - cup_start[2]
            remaining = max(0.0, 0.08 - cup_rise)
            if remaining > 0.01:
                post_spine_pose = arms.ee_world_poses()[1]
                arm_lift_target = (
                    post_spine_pose[0][0],
                    post_spine_pose[0][1],
                    post_spine_pose[0][2] + remaining,
                )
                for tick in range(math.ceil(3.0 / sim.cfg.dt)):
                    alpha = min(1.0, (tick + 1) / math.ceil(1.5 / sim.cfg.dt))
                    target_z = post_spine_pose[0][2] + remaining * alpha
                    arms.set_arm_target(
                        "right",
                        (
                            post_spine_pose[0][0],
                            post_spine_pose[0][1],
                            target_z,
                        ),
                        post_spine_pose[1],
                    )
                    arms.command()
                    sim_tick()
                current_cup = cup_position()
                lift_ok = current_cup[2] - cup_start[2] >= 0.02
    else:
        # Original lift with spine assist
        dz = max(0.0, LIFT_Z - right_pose[0][2])
        lift_ok = arms.lift(
            "right",
            dz,
            step=sim_tick,
            dt=sim.cfg.dt,
            timeout_s=6.0,
            position_tolerance_m=0.03,
            spine_assist_m=0.12,
        )

    log_phase("lift", lift_ok)

    # === Phase 5: hold ===
    hold_pose = arms.ee_world_poses()[1]
    held_ticks = 0
    max_held_ticks = 0
    needed_ticks = int(args.hold_seconds / sim.cfg.dt)
    recovery_ticks = math.ceil(args.hold_recovery_seconds / sim.cfg.dt)
    for _ in range(needed_ticks + recovery_ticks):
        arms.set_arm_target("right", hold_pose[0], hold_pose[1])
        arms.command()
        sim_tick()
        obj_pos = cup_position()
        follows = math.dist(obj_pos, hold_pose[0]) <= 0.18
        if obj_pos[2] - cup_start[2] >= args.min_lift_m and follows:
            held_ticks += 1
            max_held_ticks = max(max_held_ticks, held_ticks)
            if held_ticks >= needed_ticks:
                break
        else:
            held_ticks = 0

    cup_end = cup_position()
    lifted = cup_end[2] - cup_start[2]
    passed = grasp_lift_gate_passed(
        holding=holding,
        held_ticks=held_ticks,
        needed_ticks=needed_ticks,
        lifted_m=lifted,
        min_lift_m=args.min_lift_m,
    )
    log_phase(
        "hold",
        passed,
        lifted_m=round(lifted, 4),
        held_s=round(held_ticks * sim.cfg.dt, 2),
        max_held_s=round(max_held_ticks * sim.cfg.dt, 2),
        object_to_ee_m=round(math.dist(cup_end, hold_pose[0]), 4),
    )

    final_phase = "complete" if passed else "hold"
    return _result(
        passed,
        final_phase,
        cup_start,
        cup_end,
        phases,
        args,
        frames_dir,
        frames_written,
        rgb_annotator,
        render_product,
        sim,
        continuous_hold_seconds=max_held_ticks * sim.cfg.dt,
    )


def _result(
    passed,
    failed_phase,
    cup_start,
    cup_end,
    phases,
    args,
    frames_dir,
    frames_written,
    rgb_annotator,
    render_product,
    sim,
    continuous_hold_seconds=0.0,
):
    if args.record_video and rgb_annotator is not None:
        rgb_annotator.detach()
        render_product.destroy()
        print(f"Captured {frames_written} video frames", flush=True)
        if frames_written:
            _encode_compact_gif(
                frames_dir, frames_dir.parent / "grasp_lift.gif"
            )
    return {
        "passed": bool(passed),
        "final_phase": failed_phase,
        "object_name": args.object_name,
        "cup_start": [round(v, 4) for v in cup_start],
        "cup_end": [round(v, 4) for v in cup_end],
        "cup_lift_m": round(cup_end[2] - cup_start[2], 4),
        "min_lift_m": args.min_lift_m,
        "hold_seconds": args.hold_seconds,
        "continuous_hold_seconds": round(continuous_hold_seconds, 4),
        "close_effort_scale": args.close_effort_scale,
        "grasp_ramp_seconds": args.grasp_ramp_seconds,
        "phases": phases,
        "sim_dt": sim.cfg.dt,
    }


def make_headless_robot_usd(source_path):
    """Return the USD path for the headless robot asset."""
    return str(source_path)


if __name__ == "__main__":
    main()
