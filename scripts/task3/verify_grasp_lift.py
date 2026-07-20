#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 2 critical gate: navigate to the island, grasp the cup, lift it.

Scripted phase sequence over the proven pieces (NavigateTo/RotateTo base
skills, ramp_arm_pose transit tuck, DualArmController IK) with the cup's
PhysX pose as ground truth. Prints one GRASP_RESULT JSON line; exit 0 iff
the cup rose >= --min-lift-m and stayed held for --hold-seconds.

Geometry (measured 2026-07-17, see task3_autonomy/navigation.py):
cup at (-4.18, -1.75) on the island counter (top z 0.747, rim z 0.83);
island east face x=-3.77; wall corridor east of it 1.18 m wide. Travel
happens tucked with the measured spine at 0.45 m, which puts the right EE
around z 1.4 — above the island's tallest section (~1.15) — while retaining
vertical IK workspace for the later cup descent.
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

from run_episode import (  # noqa: E402  (same directory)
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    _fix_single_articulation_root,
    _save_rgb_frame,
    make_headless_robot_usd,
    prepare_rigid_body_view_path,
)

# Stance and waypoints (world frame).
CORRIDOR_STOP = (-3.18, -1.6)  # proven navigate target (phase2-navigate-live)
ROTATE_SPOT = (-3.0, -3.1)  # >= 1.0 m radial clearance, rotation-safe
STANCE = (-3.32, -1.72)  # base front 0.05 m off the island east face
FACE_WEST_YAW_RAD = math.pi
FACE_WEST_YAW_DEG = 180.0

CUP_GRASP_XY = (-4.145, -1.75)  # nominal east rim wall of the cup
CUP_RIM_X_OFFSET = 0.04
CUP_GRASP_Y_OFFSET = 0.06  # base-stable Run 14 left wrist 0.135 m south
PREGRASP_Z = 1.05
GRASP_Z = 0.815
GRASP_HEIGHT_ABOVE_CUP_ORIGIN = 0.068
FINAL_APPROACH_CONTACT_TOLERANCE_M = 0.10
LIFT_Z = 1.10
TRAVEL_SPINE_M = 0.45
VERIFY_VIDEO_FPS = 2

CAMERA_POSITION = (-1.6, -3.4, 2.2)
CAMERA_LOOK_AT = (-4.1, -1.7, 0.8)


def _grasp_gate_passed(
    *,
    holding: bool,
    lift_ok: bool,
    held_ticks: int,
    needed_ticks: int,
    lifted_m: float,
    min_lift_m: float,
) -> bool:
    """Combine the independent close, motion, and sustained-lift gates."""
    return (
        holding
        and lift_ok
        and held_ticks >= needed_ticks
        and lifted_m >= min_lift_m
    )


def _encode_compact_gif(frames_dir: Path, output_path: Path) -> None:
    """Encode the sparse verifier frames without the 184 MB Run 5 output."""
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
        duration=round(1000 / VERIFY_VIDEO_FPS),
        loop=0,
        optimize=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify grasp+lift of the cup on the real robot."
    )
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--livestream", action="store_true")
    parser.add_argument(
        "--probe-gripper",
        action="store_true",
        help="Close/reopen at pregrasp height before touching the cup.",
    )
    parser.add_argument(
        "--public-ip",
        default=os.environ.get("PUBLIC_IP"),
        help="Public WebRTC endpoint advertised in livestream mode.",
    )
    parser.add_argument("--min-lift-m", type=float, default=0.08)
    parser.add_argument("--hold-seconds", type=float, default=3.0)
    parser.add_argument(
        "--skip-navigation",
        action="store_true",
        help="Spawn at the clear rotation spot, tuck, then drive only the "
        "final stance leg (fast arm iteration; long nav is proven).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_verify_grasp_lift",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    frames_dir = out_dir / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.record_video:
        frames_dir.mkdir(parents=True, exist_ok=True)
        for stale in frames_dir.glob("rgb_*.png"):
            stale.unlink()

    started_at = time.time()

    if args.livestream:
        if not args.public_ip:
            raise ValueError("--livestream requires --public-ip or PUBLIC_IP")
        os.environ["PUBLIC_IP"] = str(args.public_ip)

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {
            "headless": True,
            "enable_cameras": bool(args.record_video or args.livestream),
            # Mode 1 advertises PUBLIC_IP for a public cloud endpoint. Mode 2
            # is private/NVCF and leaves a remote desktop client with blank
            # ICE.
            "livestream": 1 if args.livestream else -1,
        }
    )
    simulation_app = app_launcher.app
    try:
        result = _verify(args, simulation_app, frames_dir)
        result["wall_time_seconds"] = round(time.time() - started_at, 3)
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True)
        )
        print("GRASP_RESULT " + json.dumps(result, sort_keys=True), flush=True)
        sys.stdout.flush()
    except BaseException:
        traceback.print_exc()
        (out_dir / "crash_traceback.txt").write_text(traceback.format_exc())
        sys.stderr.flush()
        simulation_app.close()
        raise
    else:
        simulation_app.close()
        if not result["passed"]:
            raise SystemExit(1)


def _verify(  # noqa: C901 - linear simulator orchestration is phase-explicit
    args: argparse.Namespace, simulation_app: Any, frames_dir: Path
) -> dict[str, Any]:
    for path in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, REPO_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from integration_test import resolve_prim_path  # noqa: E402
    from scene_robot_room_keyboard import (  # noqa: E402
        configure_keyboard_control_stage,
        configure_robot_room_stage,
        disable_robot_external_wrenches,
        make_control_scene_cfg,
        reset_robot_to_default_state,
        yaw_to_quat,
    )
    from teleop_targets import _quaternion_from_rpy  # noqa: E402

    rep = None
    if args.record_video:
        import omni.replicator.core as rep

    from isaacsim.core.prims import RigidPrim

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
    if args.skip_navigation:
        spawn_position = (
            ROTATE_SPOT[0],
            ROTATE_SPOT[1],
            ROBOT_SPAWN_POSITION[2],
        )
        spawn_yaw_deg = FACE_WEST_YAW_DEG
    else:
        spawn_position = ROBOT_SPAWN_POSITION
        spawn_yaw_deg = ROBOT_SPAWN_YAW
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
    cup_path = prepare_rigid_body_view_path(
        sim.stage, resolve_prim_path(sim.stage, "cup")
    )
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

    cup_view = RigidPrim(prim_paths_expr=cup_path, name="task3_cup")
    getattr(cup_view, "initialize", lambda: None)()

    def cup_position() -> tuple[float, float, float]:
        positions, _ = cup_view.get_world_poses()
        row = positions.tolist()[0]
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
    base_hold_anchor: tuple[float, float] | None = None

    def sim_tick() -> None:
        nonlocal tick_count, frames_written
        disable_robot_external_wrenches(robot)
        if base_hold_anchor is not None:
            # The TMR remains a floating body when wheel velocity is zero.
            # Close the position loop against arm reaction forces while the
            # adapter's existing yaw compensator holds the final heading.
            hold_vx, hold_vy = base_twist_toward(
                adapter.pose(),
                base_hold_anchor,
                max_linear_mps=0.12,
                position_kp=2.0,
            )
            adapter.apply_twist(hold_vx, hold_vy)
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
        cup = cup_position()
        left, right = arms.ee_world_poses()
        entry = {
            "phase": name,
            "ok": bool(ok),
            "tick": tick_count,
            "base": [round(base.x, 3), round(base.y, 3), round(base.yaw, 3)],
            "cup": [round(v, 3) for v in cup],
            "right_ee": [round(v, 3) for v in right[0]],
            "spine": round(arms.measured_spine_position(), 3),
            **detail,
        }
        phases.append(entry)
        print("GRASPDBG " + json.dumps(entry, sort_keys=True), flush=True)

    def drive_to(target_xy, *, max_speed: float, budget_s: float) -> bool:
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

    def rotate_to(target_yaw: float, *, budget_s: float) -> bool:
        skill = RotateTo(target_yaw)
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
        position, quat, *, budget_s: float, tol_m: float = 0.02
    ) -> bool:
        return arms.reach(
            "right",
            position,
            quat,
            step=sim_tick,
            dt=sim.cfg.dt,
            timeout_s=budget_s,
            position_tolerance_m=tol_m,
        )

    # --- Phase 0: raise spine, tuck arms (travel configuration) --------
    spine_ok = arms.move_spine(
        TRAVEL_SPINE_M, step=sim_tick, dt=sim.cfg.dt, timeout_s=6.0
    )
    log_phase("raise_spine", spine_ok, target_spine=TRAVEL_SPINE_M)
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
    # ramp_arm_pose bypasses the Cartesian target tracker intentionally;
    # re-anchor it to the settled transit/spine configuration before Lula
    # owns the arms again.
    arms.sync_targets_from_measured()
    log_phase("tuck_spine_up", True)

    cup_start = cup_position()

    # --- Phase 1: navigate to the island (proven chain + extension) ----
    if args.skip_navigation:
        ok = drive_to(STANCE, max_speed=0.25, budget_s=20.0)
        log_phase("navigate_stance_short", ok)
        navigation_failure = "navigation_short"
    else:
        ok = drive_to(CORRIDOR_STOP, max_speed=0.5, budget_s=45.0)
        log_phase("navigate_corridor_stop", ok)
        if ok:
            ok = drive_to(ROTATE_SPOT, max_speed=0.4, budget_s=20.0)
            log_phase("navigate_rotate_spot", ok)
        if ok:
            ok = rotate_to(FACE_WEST_YAW_RAD, budget_s=15.0)
            log_phase("rotate_west", ok)
        if ok:
            ok = drive_to(STANCE, max_speed=0.25, budget_s=20.0)
            log_phase("navigate_stance", ok)
        navigation_failure = "navigation"
    if not ok:
        return _result(
            False,
            navigation_failure,
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

    # --- Phase 2: untuck to IK control, pregrasp above the cup ---------
    top_down = _quaternion_from_rpy(math.pi, 0.0, 0.0)
    pregrasp = (CUP_GRASP_XY[0], CUP_GRASP_XY[1], PREGRASP_Z)
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    ok = servo_arm(pregrasp, top_down, budget_s=8.0)
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

    if args.probe_gripper:
        arms.set_gripper("right", GRIPPER_CLOSED_RAD)
        for _ in range(round(1.5 / sim.cfg.dt)):
            arms.command()
            sim_tick()
        free_close_position = arms.gripper_position("right")
        free_close_ok = abs(free_close_position - GRIPPER_CLOSED_RAD) <= 0.05
        log_phase(
            "probe_close_free",
            free_close_ok,
            gripper_position_rad=round(free_close_position, 4),
            target_rad=GRIPPER_CLOSED_RAD,
        )
        free_open_ok = arms.release(
            "right", step=sim_tick, dt=sim.cfg.dt, timeout_s=1.5
        )
        log_phase(
            "probe_reopen_free",
            free_open_ok,
            gripper_position_rad=round(arms.gripper_position("right"), 4),
            target_rad=GRIPPER_OPEN_RAD,
        )
        if not (free_close_ok and free_open_ok):
            return _result(
                False,
                "probe_gripper",
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

    # --- Phase 3: descend to the rim and close ------------------------
    cup_before_descend = cup_position()
    grasp = (
        cup_before_descend[0] + CUP_RIM_X_OFFSET,
        cup_before_descend[1] + CUP_GRASP_Y_OFFSET,
        cup_before_descend[2] + GRASP_HEIGHT_ABOVE_CUP_ORIGIN,
    )
    strict_reach = servo_arm(grasp, top_down, budget_s=6.0, tol_m=0.015)
    final_approach_error = arms.position_error("right", grasp)
    # The wrist origin can stop above its mathematical goal when the fingers
    # first contact the cup.  That is the desired physical terminal state, so
    # accept a bounded contact residual and let gripper closure prove the
    # grasp.
    ok = strict_reach or (
        final_approach_error <= FINAL_APPROACH_CONTACT_TOLERANCE_M
    )
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
    holding = arms.grasp(
        "right", step=sim_tick, dt=sim.cfg.dt, settle_seconds=1.5
    )
    gripper_position = arms.gripper_position("right")
    log_phase(
        "close",
        holding,
        gripper_position_rad=round(gripper_position, 4),
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

    # --- Phase 4: lift and hold ---------------------------------------
    right_pose = arms.ee_world_poses()[1]
    lift_ok = arms.lift(
        "right",
        max(0.0, LIFT_Z - right_pose[0][2]),
        step=sim_tick,
        dt=sim.cfg.dt,
        timeout_s=6.0,
        position_tolerance_m=0.03,
    )
    log_phase("lift", lift_ok)
    hold_pose = arms.ee_world_poses()[1]
    held_ticks = 0
    needed_ticks = int(args.hold_seconds / sim.cfg.dt)
    for _ in range(needed_ticks + 400):
        # Tracker poses are base-relative. Preserve the attained world pose
        # while the active base hold makes its small corrective motions.
        arms.set_arm_target("right", hold_pose[0], hold_pose[1])
        arms.command()
        sim_tick()
        if cup_position()[2] - cup_start[2] >= args.min_lift_m:
            held_ticks += 1
            if held_ticks >= needed_ticks:
                break
        else:
            held_ticks = 0
    cup_end = cup_position()
    lifted = cup_end[2] - cup_start[2]
    passed = _grasp_gate_passed(
        holding=holding,
        lift_ok=lift_ok,
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
) -> dict[str, Any]:
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
        "cup_start": [round(v, 4) for v in cup_start],
        "cup_end": [round(v, 4) for v in cup_end],
        "cup_lift_m": round(cup_end[2] - cup_start[2], 4),
        "min_lift_m": args.min_lift_m,
        "hold_seconds": args.hold_seconds,
        "phases": phases,
        "sim_dt": sim.cfg.dt,
    }


if __name__ == "__main__":
    main()
