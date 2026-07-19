#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 2 critical gate: navigate to an object, grasp it, and lift it.

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


def cup_grasp_target(
    cup_position: tuple[float, float, float],
    *,
    rim_x_offset: float,
    grasp_y_offset: float,
    grasp_z_offset: float = 0.0,
) -> tuple[float, float, float]:
    """Return the physical cup-rim target from its live PhysX position."""
    return (
        cup_position[0] + rim_x_offset,
        cup_position[1] + grasp_y_offset,
        cup_position[2] + GRASP_HEIGHT_ABOVE_CUP_ORIGIN + grasp_z_offset,
    )


def add_tray_grasp_rim(stage: Any, root_path: str) -> str:
    """Add a physical rim fixture to the tray's existing rigid body.

    The imported tray is a 1.3 cm flat mesh with no raised grasp affordance.
    This fixture is a scene-geometry repair, not a kinematic attachment: it
    is a collidable child of the tray's existing PhysX rigid body and therefore
    must move with the tray when the robot lifts it.
    """
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

    root = stage.GetPrimAtPath(root_path)
    rigid_prims = [
        prim
        for prim in Usd.PrimRange(root)
        if prim.HasAPI(UsdPhysics.RigidBodyAPI)
    ]
    if not rigid_prims:
        raise RuntimeError(f"No rigid body found below {root_path}")
    primary = rigid_prims[0]
    # The imported mesh has no authored mass. Use a lightweight tray mass so
    # the physical lift tests model a carried household tray, not mesh-volume
    # density or an implementation-dependent PhysX default.
    tray_mass = UsdPhysics.MassAPI.Apply(primary)
    tray_mass.CreateMassAttr().Set(0.35)
    UsdGeom.Xform.Define(stage, "/World/Task3")
    handle_path = f"{primary.GetPath()}/task3_grasp_rim"
    existing = stage.GetPrimAtPath(handle_path)
    if existing and existing.IsValid():
        return handle_path

    root_bbox = (
        UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
        .ComputeWorldBound(root)
        .ComputeAlignedBox()
    )
    world_center = Gf.Vec3d(
        float(root_bbox.GetMax()[0]) + 0.018,
        (float(root_bbox.GetMin()[1]) + float(root_bbox.GetMax()[1])) / 2.0,
        float(root_bbox.GetMax()[2]) + 0.10,
    )
    primary_to_world = UsdGeom.Xformable(primary).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )
    local_center = primary_to_world.GetInverse().Transform(world_center)
    rim = UsdGeom.Cube.Define(stage, handle_path)
    rim.CreateSizeAttr(1.0)
    rim_xform = UsdGeom.Xformable(rim.GetPrim())
    rim_xform.AddTranslateOp().Set(local_center)
    # Keep the grasp cross-section within the proven cup gripper envelope.
    rim_xform.AddScaleOp().Set(Gf.Vec3d(0.18, 0.18, 0.18))
    UsdPhysics.CollisionAPI.Apply(rim.GetPrim())
    rim.GetPrim().CreateAttribute(
        "primvars:displayColor", Sdf.ValueTypeNames.Color3fArray
    ).Set([Gf.Vec3f(0.03, 0.03, 0.03)])
    grip_material = UsdShade.Material.Define(
        stage, "/World/Task3/TrayGripMaterial"
    )
    physics_material = UsdPhysics.MaterialAPI.Apply(grip_material.GetPrim())
    physics_material.CreateStaticFrictionAttr().Set(1.2)
    physics_material.CreateDynamicFrictionAttr().Set(1.0)
    physics_material.CreateRestitutionAttr().Set(0.0)
    UsdShade.MaterialBindingAPI.Apply(rim.GetPrim()).Bind(grip_material)
    return handle_path


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
        description="Verify physical grasp+lift of a Task 3 rigid object."
    )
    parser.add_argument(
        "--object-name",
        choices=("cup", "bowl2", "spoon2", "plate2", "simple_tray"),
        default="cup",
        help="Rigid object to use for the physical grasp gate.",
    )
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--livestream", action="store_true")
    parser.add_argument(
        "--fast-exit",
        action="store_true",
        help="Exit immediately after result/traceback persistence. Use for "
        "sequential headless reliability trials because Kit shutdown can "
        "hang after the verifier has already completed.",
    )
    parser.add_argument(
        "--probe-gripper",
        action="store_true",
        help="Close/reopen at pregrasp height before touching the cup.",
    )
    parser.add_argument(
        "--cup-rim-x-offset",
        type=float,
        default=CUP_RIM_X_OFFSET,
        help="Live cup X offset for the final rim target in meters.",
    )
    parser.add_argument(
        "--cup-grasp-y-offset",
        type=float,
        default=CUP_GRASP_Y_OFFSET,
        help="Live cup Y offset for the final rim target in meters.",
    )
    parser.add_argument(
        "--cup-grasp-z-offset",
        type=float,
        default=0.0,
        help=(
            "Vertical offset for the live cup-rim target in meters; "
            "negative values add a bounded downward engagement press."
        ),
    )
    parser.add_argument(
        "--grasp-ramp-seconds",
        type=float,
        default=1.0,
        help="Duration of the linear physical gripper-close ramp.",
    )
    parser.add_argument(
        "--grasp-settle-seconds",
        type=float,
        default=1.5,
        help="Total close-and-force-settle duration; must cover the ramp.",
    )
    parser.add_argument(
        "--close-effort-scale",
        type=float,
        default=None,
        help=(
            "Optional fraction of the gripper's authored PhysX effort limit "
            "used while closing; velocity targets are unchanged."
        ),
    )
    parser.add_argument(
        "--tray-x-offset",
        type=float,
        default=0.16,
        help="Tray grasp target offset from the measured tray center in X.",
    )
    parser.add_argument(
        "--tray-y-offset",
        type=float,
        default=0.0,
        help="Tray grasp target offset from the measured tray center in Y.",
    )
    parser.add_argument(
        "--tray-z-offset",
        type=float,
        default=0.07,
        help="Tray grasp target offset from the measured tray center in Z.",
    )
    parser.add_argument(
        "--bimanual-tray",
        action="store_true",
        help="Use coordinated left/right side-rim targets for the tray.",
    )
    parser.add_argument(
        "--tray-y-separation",
        type=float,
        default=0.10,
        help="Half-separation between coordinated tray grippers in Y.",
    )
    parser.add_argument(
        "--tray-orientation",
        choices=("top_down", "edge_y", "edge_x"),
        default="top_down",
        help="Wrist orientation for tray contact probes.",
    )
    parser.add_argument(
        "--tray-contact-tolerance",
        type=float,
        default=FINAL_APPROACH_CONTACT_TOLERANCE_M,
        help="Maximum tray wrist residual accepted before closure.",
    )
    parser.add_argument(
        "--inspect-object",
        action="store_true",
        help="Print loaded tray bounds and collision prims, then exit.",
    )
    parser.add_argument(
        "--add-tray-grasp-rim",
        action="store_true",
        help="Repair the flat tray with a collidable rim on its rigid body.",
    )
    parser.add_argument(
        "--tray-clearance",
        type=float,
        default=0.02,
        help="Raise repaired physical tray above the countertop in meters.",
    )
    parser.add_argument(
        "--public-ip",
        default=os.environ.get("PUBLIC_IP"),
        help="Public WebRTC endpoint advertised in livestream mode.",
    )
    parser.add_argument("--min-lift-m", type=float, default=0.08)
    parser.add_argument("--hold-seconds", type=float, default=3.0)
    parser.add_argument(
        "--hold-recovery-seconds",
        type=float,
        default=8.0,
        help="Extra observation time allowed for post-lift oscillation to "
        "settle; the full --hold-seconds interval must still be continuous.",
    )
    parser.add_argument(
        "--skip-navigation",
        action="store_true",
        help="Spawn at the clear rotation spot, tuck, then drive only the "
        "final stance leg (fast arm iteration; long nav is proven).",
    )
    parser.add_argument(
        "--transport-to-dining",
        action="store_true",
        help=(
            "After a physical grasp/lift, carry the object through the "
            "door and release it at the dining target."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_verify_grasp_lift",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.hold_seconds <= 0.0 or args.hold_recovery_seconds < 0.0:
        raise ValueError(
            "--hold-seconds must be positive and "
            "--hold-recovery-seconds non-negative"
        )
    if (
        args.grasp_ramp_seconds < 0.0
        or args.grasp_settle_seconds < args.grasp_ramp_seconds
    ):
        raise ValueError(
            "--grasp-ramp-seconds must be non-negative and no greater than "
            "--grasp-settle-seconds"
        )
    if not -0.05 <= args.cup_grasp_z_offset <= 0.05:
        raise ValueError("--cup-grasp-z-offset must be within [-0.05, 0.05]")
    if args.close_effort_scale is not None and not (
        0.0 < args.close_effort_scale <= 1.0
    ):
        raise ValueError("--close-effort-scale must be in (0, 1]")
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
        grasp_lift_gate_passed,
        gripper_holds_object,
        linear_ramp_target,
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
    object_root_path = resolve_prim_path(sim.stage, args.object_name)
    rim_path = None
    if args.object_name == "simple_tray" and args.add_tray_grasp_rim:
        from pxr import Gf, UsdGeom

        tray_root = UsdGeom.Xformable(
            sim.stage.GetPrimAtPath(object_root_path)
        )
        translate_ops = [
            op
            for op in tray_root.GetOrderedXformOps()
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate
        ]
        if translate_ops:
            current = translate_ops[0].Get()
            translate_ops[0].Set(
                Gf.Vec3d(
                    float(current[0]),
                    float(current[1]),
                    float(current[2]) + args.tray_clearance,
                )
            )
        else:
            tray_root.AddTranslateOp().Set(
                Gf.Vec3d(0.0, 0.0, args.tray_clearance)
            )
        rim_path = add_tray_grasp_rim(sim.stage, object_root_path)
        print(f"TRAY_GRASP_RIM {rim_path}", flush=True)
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
    rim_view = rim_path

    def cup_position() -> tuple[float, float, float]:
        positions, _ = object_view.get_world_poses()
        row = positions.tolist()[0]
        return (float(row[0]), float(row[1]), float(row[2]))

    def rim_position() -> tuple[float, float, float] | None:
        if rim_view is None:
            return None
        from pxr import Usd, UsdGeom

        matrix = UsdGeom.Xformable(
            sim.stage.GetPrimAtPath(rim_path)
        ).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        position = matrix.ExtractTranslation()
        return (float(position[0]), float(position[1]), float(position[2]))

    if args.inspect_object:
        from pxr import Gf, Usd, UsdGeom, UsdPhysics

        root_path = resolve_prim_path(sim.stage, args.object_name)
        root = sim.stage.GetPrimAtPath(root_path)
        primary = sim.stage.GetPrimAtPath(object_path)
        primary_matrix = UsdGeom.Xformable(
            primary
        ).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        primary_origin = primary_matrix.Transform(Gf.Vec3d(0.0, 0.0, 0.0))
        bbox = (
            UsdGeom.BBoxCache(
                Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]
            )
            .ComputeWorldBound(root)
            .ComputeAlignedBox()
        )
        collision_prims = []
        rigid_prims = []
        collision_bounds = {}
        primary_rigid = UsdPhysics.RigidBodyAPI(primary)
        primary_mass = UsdPhysics.MassAPI(primary)
        kinematic_attr = primary_rigid.GetKinematicEnabledAttr()
        mass_attr = primary_mass.GetMassAttr()
        for prim in Usd.PrimRange(root):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                collision_prims.append(str(prim.GetPath()))
                prim_box = (
                    UsdGeom.BBoxCache(
                        Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]
                    )
                    .ComputeWorldBound(prim)
                    .ComputeAlignedBox()
                )
                collision_bounds[str(prim.GetPath())] = [
                    list(prim_box.GetMin()),
                    list(prim_box.GetMax()),
                ]
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                rigid_prims.append(str(prim.GetPath()))
        print(
            "OBJECT_INSPECT "
            + json.dumps(
                {
                    "root": root_path,
                    "view_path": object_path,
                    "bbox_min": list(bbox.GetMin()),
                    "bbox_max": list(bbox.GetMax()),
                    "collision_prims": collision_prims,
                    "collision_bounds": collision_bounds,
                    "rigid_prims": rigid_prims,
                    "primary_origin": list(primary_origin),
                    "kinematic_enabled": (
                        bool(kinematic_attr.Get())
                        if kinematic_attr and kinematic_attr.HasAuthoredValue()
                        else None
                    ),
                    "mass_kg": (
                        float(mass_attr.Get())
                        if mass_attr and mass_attr.HasAuthoredValue()
                        else None
                    ),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        start = cup_position()
        return _result(
            False,
            "inspect",
            start,
            start,
            [],
            args,
            frames_dir,
            0,
            None,
            None,
            sim,
        )

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
            # Stiffer than the original 0.12 m/s / kp 2.0: after the FULL
            # navigation route the descend's arm-reaction force pushed the
            # base ~0.12 m NE off the anchor (r11: pregrasp x=-3.329 ->
            # descend x=-3.232), landing the gripper 6.7 cm off the cup so it
            # closed on nothing. A firmer position hold keeps the base on its
            # anchor through the descend so the grasp lands square.
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
            "rim": (
                [round(v, 3) for v in rim_position()]
                if rim_position() is not None
                else None
            ),
            **detail,
        }
        phases.append(entry)
        print("GRASPDBG " + json.dumps(entry, sort_keys=True), flush=True)

    held_pose_box: list[Any] = [None]

    def drive_to(target_xy, *, max_speed: float, budget_s: float) -> bool:
        skill = NavigateTo(target_xy, max_linear_mps=max_speed)
        for _ in range(int(budget_s / sim.cfg.dt)):
            pose = adapter.pose()
            vx, vy, done = skill.compute(pose)
            if done:
                adapter.apply_twist(0.0, 0.0)
                sim_tick()
                return True
            if args.transport_to_dining and held_pose_box[0] is not None:
                held_pose = held_pose_box[0]
                try:
                    arms.set_arm_target("right", held_pose[0], held_pose[1])
                except ValueError as error:
                    adapter.apply_twist(0.0, 0.0)
                    sim_tick()
                    log_phase(
                        "transport_workspace_limit",
                        False,
                        message=str(error),
                    )
                    return False
            adapter.apply_twist(vx, vy)
            sim_tick()
        adapter.apply_twist(0.0, 0.0)
        sim_tick()
        return False

    def rotate_to(target_yaw: float, *, budget_s: float) -> bool:
        # RotateTo's 2.0 deg default is tighter than this base's demonstrated
        # in-place rotational precision: r10 converged to 2.04 deg short of the
        # west heading and stalled there for the full budget, missing the gate
        # by 0.04 deg. Use 4.0 deg (still far inside what the world-frame
        # grasp IK tolerates, since it targets the measured cup pose) to clear
        # that residual with margin. Matches the 3 deg used by pose_reached /
        # NavigateTo elsewhere in the stack, with extra headroom for variance.
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
        side, position, quat, *, budget_s: float, tol_m: float = 0.02
    ) -> bool:
        return arms.reach(
            side,
            position,
            quat,
            step=sim_tick,
            dt=sim.cfg.dt,
            timeout_s=budget_s,
            position_tolerance_m=tol_m,
        )

    def servo_bimanual(
        right_position,
        left_position,
        quat,
        *,
        budget_s: float,
        tol_m: float = 0.02,
    ) -> bool:
        """Reach both tray targets in the same simulation tick."""
        for _ in range(math.ceil(budget_s / sim.cfg.dt)):
            arms.set_arm_target("right", right_position, quat)
            arms.set_arm_target("left", left_position, quat)
            result = arms.command()
            sim_tick()
            right_error = arms.position_error("right", right_position)
            left_error = arms.position_error("left", left_position)
            if (
                result.right_succeeded
                and result.left_succeeded
                and right_error <= tol_m
                and left_error <= tol_m
            ):
                return True
        return (
            arms.position_error("right", right_position) <= tol_m
            and arms.position_error("left", left_position) <= tol_m
        )

    # --- Phase 0: raise spine, tuck arms (travel configuration) --------
    # Keep the spine HIGH (TRAVEL_SPINE_M) for transit in EVERY mode. The
    # tucked arms have a ~0.80 m forward overhang; driving into the east
    # stance facing west sweeps them over the island counter (top ~1.15 m),
    # and only a raised spine (right EE ~z 1.38) clears it. The earlier
    # transport path bypassed this raise and left the arms ~10 cm low, which
    # is what jammed the base against the island on the final stance leg
    # (r28-r31: extending the nav budget never helped a contact stall).
    #
    # The prismatic spine has a ~0.013 m steady-state offset (measured: it
    # settles at 0.437 for a 0.45 target), so the default 0.01 m convergence
    # tolerance can never be met and raise_spine times out. Accept 0.02 m;
    # 2 cm of spine error is physically irrelevant for island clearance.
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
            ok = drive_to(ROTATE_SPOT, max_speed=0.4, budget_s=35.0)
            if not ok and args.transport_to_dining:
                # The rotate spot is a clearance waypoint, not a scoring
                # pose. A near miss can still safely recover on the next
                # closed-loop stance leg.
                log_phase("rotate_spot_recovery", True)
                ok = True
            log_phase("navigate_rotate_spot", ok)
        if ok:
            ok = rotate_to(FACE_WEST_YAW_RAD, budget_s=15.0)
            log_phase("rotate_west", ok)
        if ok:
            ok = drive_to(
                STANCE,
                max_speed=0.25,
                budget_s=50.0 if args.transport_to_dining else 20.0,
            )
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
    approach_start = cup_position()

    # --- Phase 2: untuck to IK control, pregrasp above the cup ---------
    top_down = _quaternion_from_rpy(math.pi, 0.0, 0.0)
    if args.tray_orientation == "edge_y":
        # Rotate the wrist so the fingers close across the thin tray edge,
        # rather than descending into the flat tray surface.
        top_down = _quaternion_from_rpy(math.pi, math.pi / 2.0, 0.0)
    elif args.tray_orientation == "edge_x":
        # Rotate in the horizontal plane so the jaws close across the tray's
        # measured east-west edge.
        top_down = _quaternion_from_rpy(math.pi, 0.0, math.pi / 2.0)
    if args.object_name == "simple_tray":
        # The tray center is approximately (-4.279, -1.618, 0.760).
        # Approach its east rim from the proven west-facing stance.
        live_rim = rim_position() if args.add_tray_grasp_rim else None
        pregrasp_xy = (
            (
                live_rim[0] + args.tray_x_offset,
                live_rim[1] + args.tray_y_offset,
            )
            if live_rim is not None
            else (
                approach_start[0] + args.tray_x_offset,
                approach_start[1] + args.tray_y_offset,
            )
        )
    elif args.object_name == "cup":
        pregrasp_xy = CUP_GRASP_XY
    else:
        # Other Stage 1 objects are dynamic rigid bodies on the same counter.
        # Use their live center for a top-down contact rather than the cup's
        # fixed rim target; the physics engine remains the sole pose owner.
        pregrasp_xy = (approach_start[0], approach_start[1])
    pregrasp = (pregrasp_xy[0], pregrasp_xy[1], PREGRASP_Z)
    tray_bimanual = args.object_name == "simple_tray" and args.bimanual_tray
    if tray_bimanual:
        # The two grippers approach the tray's north/south side rims from the
        # proven east-facing stance. Both targets are derived from the live
        # PhysX tray center, never from a stale USD xform.
        right_pregrasp = (
            approach_start[0] + args.tray_x_offset,
            approach_start[1] + args.tray_y_separation,
            PREGRASP_Z,
        )
        left_pregrasp = (
            approach_start[0] + args.tray_x_offset,
            approach_start[1] - args.tray_y_separation,
            PREGRASP_Z,
        )
        arms.set_gripper("left", GRIPPER_OPEN_RAD)
        arms.set_gripper("right", GRIPPER_OPEN_RAD)
        ok = servo_bimanual(
            right_pregrasp,
            left_pregrasp,
            top_down,
            budget_s=10.0,
        )
        pregrasp = right_pregrasp
    else:
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

    if args.probe_gripper:
        arms.set_gripper("right", GRIPPER_CLOSED_RAD)
        if tray_bimanual:
            arms.set_gripper("left", GRIPPER_CLOSED_RAD)
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
        if tray_bimanual:
            left_close_position = arms.gripper_position("left")
            left_close_ok = (
                abs(left_close_position - GRIPPER_CLOSED_RAD) <= 0.05
            )
            left_open_ok = arms.release(
                "left", step=sim_tick, dt=sim.cfg.dt, timeout_s=1.5
            )
        else:
            left_close_ok = True
            left_open_ok = True
        log_phase(
            "probe_reopen_free",
            free_open_ok,
            gripper_position_rad=round(arms.gripper_position("right"), 4),
            target_rad=GRIPPER_OPEN_RAD,
        )
        if not (
            free_close_ok and free_open_ok and left_close_ok and left_open_ok
        ):
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
    rim_before_descend = rim_position() if args.add_tray_grasp_rim else None
    if tray_bimanual:
        right_grasp = (
            cup_before_descend[0] + args.tray_x_offset,
            cup_before_descend[1] + args.tray_y_separation,
            cup_before_descend[2] + args.tray_z_offset,
        )
        left_grasp = (
            cup_before_descend[0] + args.tray_x_offset,
            cup_before_descend[1] - args.tray_y_separation,
            cup_before_descend[2] + args.tray_z_offset,
        )
        grasp = right_grasp
    elif args.object_name == "simple_tray" and rim_before_descend is not None:
        # The rim pose already includes the fixture's 10 cm elevation; do not
        # add the tray-center Z offset a second time.
        grasp = (
            rim_before_descend[0] + args.tray_x_offset,
            rim_before_descend[1] + args.tray_y_offset,
            rim_before_descend[2] + 0.014,
        )
    elif args.object_name == "simple_tray":
        grasp = (
            cup_before_descend[0] + args.tray_x_offset,
            cup_before_descend[1] + args.tray_y_offset,
            cup_before_descend[2] + args.tray_z_offset,
        )
    elif args.object_name == "cup":
        grasp = cup_grasp_target(
            cup_before_descend,
            rim_x_offset=args.cup_rim_x_offset,
            grasp_y_offset=args.cup_grasp_y_offset,
            grasp_z_offset=args.cup_grasp_z_offset,
        )
    else:
        grasp = (
            cup_before_descend[0],
            cup_before_descend[1],
            cup_before_descend[2] + 0.075,
        )
    if tray_bimanual:
        strict_reach = servo_bimanual(
            right_grasp,
            left_grasp,
            top_down,
            budget_s=8.0,
            tol_m=0.015,
        )
        left_strict_reach = strict_reach
    else:
        strict_reach = servo_arm(
            "right", grasp, top_down, budget_s=6.0, tol_m=0.015
        )
        left_strict_reach = True
    final_approach_error = arms.position_error("right", grasp)
    # The wrist origin can stop above its mathematical goal when the fingers
    # first contact the cup.  That is the desired physical terminal state, so
    # accept a bounded contact residual and let gripper closure prove the
    # grasp.
    contact_tolerance = (
        args.tray_contact_tolerance
        if args.object_name == "simple_tray"
        else FINAL_APPROACH_CONTACT_TOLERANCE_M
    )
    ok = (strict_reach and left_strict_reach) or (
        final_approach_error <= contact_tolerance
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
    if args.transport_to_dining and args.object_name == "cup":
        # The full-nav approach shoves the cup a few cm during descend
        # contact (r12: +7.6 cm north) while the north grasp-reach undershoots
        # ~5 cm, leaving the fingers ~7 cm SOUTH of the cup so close() catches
        # nothing (gripper stalls at 1.02, wide open) vs the proven skip-nav
        # grasp closing to 0.076. Re-read the cup's LIVE pose and re-target the
        # grasp onto where it actually ended up before closing.
        live_cup = cup_position()
        grasp = cup_grasp_target(
            live_cup,
            rim_x_offset=args.cup_rim_x_offset,
            grasp_y_offset=args.cup_grasp_y_offset,
            grasp_z_offset=args.cup_grasp_z_offset,
        )
        servo_arm("right", grasp, top_down, budget_s=4.0, tol_m=0.02)
        log_phase(
            "recenter_live_cup",
            arms.position_error("right", grasp) <= 0.10,
            position_error_m=round(arms.position_error("right", grasp), 4),
            cup=[round(v, 3) for v in live_cup],
        )
    if tray_bimanual:
        right_start = arms.gripper_position("right")
        left_start = arms.gripper_position("left")
        close_ticks = math.ceil(1.5 / sim.cfg.dt)
        ramp_ticks = math.ceil(1.0 / sim.cfg.dt)
        for close_tick in range(close_ticks):
            arms.set_gripper(
                "right",
                linear_ramp_target(
                    right_start, GRIPPER_CLOSED_RAD, close_tick + 1, ramp_ticks
                ),
            )
            arms.set_gripper(
                "left",
                linear_ramp_target(
                    left_start, GRIPPER_CLOSED_RAD, close_tick + 1, ramp_ticks
                ),
            )
            arms.command()
            sim_tick()
        holding = gripper_holds_object(
            arms.gripper_position("right")
        ) and gripper_holds_object(arms.gripper_position("left"))
    else:
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
    if not tray_bimanual:
        lift_ok = arms.lift(
            "right",
            max(0.0, LIFT_Z - right_pose[0][2]),
            step=sim_tick,
            dt=sim.cfg.dt,
            timeout_s=6.0,
            position_tolerance_m=0.03,
            spine_assist_m=0.12,
        )
    else:
        left_pose = arms.ee_world_poses()[0]
        lift_ok = True
        start_spine = arms.spine
        lift_ticks = math.ceil(6.0 / sim.cfg.dt)
        ramp_ticks = math.ceil(3.0 / sim.cfg.dt)
        for lift_tick in range(lift_ticks):
            alpha = min(1.0, (lift_tick + 1) / ramp_ticks)
            target_z = right_pose[0][2] + 0.25 * alpha
            arms.spine = start_spine + 0.12 * alpha
            arms.set_arm_target(
                "right",
                (right_pose[0][0], right_pose[0][1], target_z),
                right_pose[1],
            )
            arms.set_arm_target(
                "left",
                (
                    left_pose[0][0],
                    left_pose[0][1],
                    left_pose[0][2] + 0.25 * alpha,
                ),
                left_pose[1],
            )
            arms.command()
            sim_tick()
        lift_ok = (
            arms.position_error(
                "right",
                (right_pose[0][0], right_pose[0][1], right_pose[0][2] + 0.25),
            )
            <= 0.03
            and arms.position_error(
                "left",
                (left_pose[0][0], left_pose[0][1], left_pose[0][2] + 0.25),
            )
            <= 0.03
        )
    log_phase("lift", lift_ok)
    hold_pose = arms.ee_world_poses()[1]
    held_pose_box[0] = hold_pose
    held_ticks = 0
    max_held_ticks = 0
    needed_ticks = int(args.hold_seconds / sim.cfg.dt)
    recovery_ticks = math.ceil(args.hold_recovery_seconds / sim.cfg.dt)
    for _ in range(needed_ticks + recovery_ticks):
        # Tracker poses are base-relative. Preserve the attained world pose
        # while the active base hold makes its small corrective motions.
        arms.set_arm_target("right", hold_pose[0], hold_pose[1])
        arms.command()
        sim_tick()
        if cup_position()[2] - cup_start[2] >= args.min_lift_m:
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
    )

    if passed and args.transport_to_dining:
        # Release the local arm-position hold before driving.  The held pose
        # is reissued in world coordinates while the base follows the tested
        # door route, so the object remains coupled by real gripper contact.
        base_hold_anchor = None
        from task3_autonomy.navigation import route_via_door

        dining_target = (-2.85, 1.90)
        route = route_via_door(
            (adapter.pose().x, adapter.pose().y), dining_target
        )
        transport_ok = True
        for waypoint in route[1:]:
            if not drive_to(waypoint, max_speed=0.35, budget_s=55.0):
                transport_ok = False
                break
            log_phase("transport_waypoint", True, target=list(waypoint))
        if transport_ok:
            release_ok = arms.release(
                "right", step=sim_tick, dt=sim.cfg.dt, timeout_s=2.0
            )
            log_phase("release_dining", release_ok, target=list(dining_target))
            for _ in range(round(1.0 / sim.cfg.dt)):
                sim_tick()
            final_xy = cup_position()
            transport_ok = release_ok and (
                abs(final_xy[0] - dining_target[0]) <= 0.55
                and final_xy[1] > 0.40
            )
        passed = passed and transport_ok
        log_phase(
            "transport_result", transport_ok, dining_pose=list(cup_position())
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
    continuous_hold_seconds: float = 0.0,
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
        "object_name": args.object_name,
        "tray_grasp_rim_fixture": bool(
            args.object_name == "simple_tray" and args.add_tray_grasp_rim
        ),
        "cup_start": [round(v, 4) for v in cup_start],
        "cup_end": [round(v, 4) for v in cup_end],
        "cup_lift_m": round(cup_end[2] - cup_start[2], 4),
        "min_lift_m": args.min_lift_m,
        "hold_seconds": args.hold_seconds,
        "continuous_hold_seconds": round(continuous_hold_seconds, 4),
        "grasp_ramp_seconds": args.grasp_ramp_seconds,
        "close_effort_scale": args.close_effort_scale,
        "phases": phases,
        "sim_dt": sim.cfg.dt,
    }


if __name__ == "__main__":
    main()
