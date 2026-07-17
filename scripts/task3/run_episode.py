#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Headless Task 3 episode runner: seed, head placement, policy, video.

Builds the real (physics-simulated) Task 3 scene exactly like
scripts/task3/record_robot_demo.py, drives the robot for --max-seconds under
the selected policy, optionally records an off-screen video, then grades the
outcome with the pure functions in scripts/evaluation/task3/grading.py and
prints one EPISODE_RESULT JSON line (mirrors the STAGE_RESULT convention in
scripts/evaluation/task3/integration_test.py).

STATUS (2026-07-16): authored without live Isaac Sim GPU access (Lightning
studio SSH was down, GCP GPU quota not yet granted -- see
docs/gpu_budget_log.md). This has NOT been run. Do not check off the Phase 1
box in docs/task3_master_plan.md until it has actually produced two
identical-seed runs with video + result.json on a real GPU, per the
Definition-of-Done visual-proof protocol (section 7.2 of that plan).
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
TASK3_EVAL_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"

ROBOT_SPAWN_POSITION = (-4.6, 2.7, 0.0)
ROBOT_SPAWN_YAW = -90.0
CAMERA_POSITION = (-8.1, -3.3, 2.8)
CAMERA_LOOK_AT = (-4.1, 1.65, 0.85)
VIDEO_FPS = 20
HEAD_PLACEMENTS = ("a", "b", "c", "d", "e", "f", "g", "h", "i")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one headless Task 3 episode: build the scene, drive the "
            "robot with the selected policy, optionally record off-screen "
            "video, and grade the outcome."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Seeds Python's random module before scene composition, so "
        "head-placement 'random' resolution and bean-spawn jitter are "
        "both reproducible.",
    )
    parser.add_argument(
        "--head-placement",
        type=str,
        default="random",
        choices=(*HEAD_PLACEMENTS, "random"),
    )
    parser.add_argument(
        "--policy", choices=("idle", "scripted"), default="idle"
    )
    parser.add_argument("--max-seconds", type=float, default=8.0)
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument(
        "--livestream",
        action="store_true",
        help="Stream the run over WebRTC for live viewing (needs the "
        "streaming ports opened to the viewer's IP; watch with NVIDIA's "
        "Isaac Sim WebRTC Streaming Client pointed at the VM's IP).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_episodes",
    )
    return parser.parse_args()


def _fix_single_articulation_root(stage, robot_prim_path: str) -> None:
    """Keep exactly one UsdPhysics.ArticulationRootAPI under the robot.

    mobile_fr3_duo_v0_2.usd carries the API on both Robot/base and
    Robot/base_link; Isaac Lab's Articulation refuses ambiguous roots.
    Same pattern as task1/task2's _fix_single_articulation_root.
    """
    from pxr import Usd, UsdPhysics

    robot_prim = stage.GetPrimAtPath(robot_prim_path)
    if not robot_prim.IsValid():
        print(
            f"WARNING: articulation-root patch: prim not found {robot_prim_path}",
            file=sys.stderr,
        )
        return
    root_prims = [
        prim
        for prim in Usd.PrimRange(robot_prim)
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI)
    ]
    if len(root_prims) <= 1:
        return
    keep = None
    for preferred in (f"{robot_prim_path}/base", f"{robot_prim_path}/base_link"):
        candidate = stage.GetPrimAtPath(preferred)
        if candidate in root_prims:
            keep = candidate
            break
    if keep is None:
        keep = root_prims[0]
    for prim in root_prims:
        if prim != keep:
            prim.RemoveAPI(UsdPhysics.ArticulationRootAPI)
    print(f"Articulation root kept: {keep.GetPath()}", flush=True)


def make_headless_robot_usd(robot_usd: Path) -> Path:
    """Write a wrapper layer that deactivates the robot's OmniGraphs.

    mobile_fr3_duo_v0_2.usd ships ROS2/keyboard controller graphs in its
    root layer (Graph/ROS_JointStates and Graph/Steer_joint_Controller,
    each with its own ArticulationController).  Headless, the steering
    ScriptNode crashes after sim.reset() ("Attempted to access an invalid
    object" reading Desired_Linear_Velocity_X), and even a working graph
    would fight Isaac Lab's actuator commands.  Kit registers the graphs
    while composing the robot reference, so any post-load repair is too
    late (proven in 900520f, 221dffa, f71d32e, 69f5913).  The only safe
    point is before composition: reference this thin sibling wrapper,
    which sublayers the asset and overrides Graph with active=false.
    """
    from pxr import Sdf

    src = Sdf.Layer.FindOrOpen(str(robot_usd))
    if src is None:
        raise RuntimeError(f"Cannot open robot USD: {robot_usd}")
    default_prim = src.defaultPrim
    if not default_prim:
        raise RuntimeError(f"Robot USD has no defaultPrim: {robot_usd}")

    wrapper = Sdf.Layer.CreateAnonymous(".usda")
    # Relative sublayer path: the wrapper sits next to the asset, so it
    # composes identically on the Windows worktree and the VM's /workspace.
    wrapper.subLayerPaths.append(f"./{robot_usd.name}")
    wrapper.defaultPrim = default_prim
    for key in ("metersPerUnit", "upAxis", "kilogramsPerUnit"):
        if src.pseudoRoot.HasInfo(key):
            wrapper.pseudoRoot.SetInfo(key, src.pseudoRoot.GetInfo(key))
    graph_over = Sdf.CreatePrimInLayer(
        wrapper, f"/{default_prim}/Graph"
    )
    graph_over.active = False

    wrapper_path = robot_usd.with_name(robot_usd.stem + "_headless.usda")
    if not wrapper.Export(str(wrapper_path)):
        raise RuntimeError(f"Failed to write {wrapper_path}")
    return wrapper_path


def git_commit_hash() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def prepare_rigid_body_view_path(stage: Any, root_path: str) -> str:
    """Return one valid PhysX body below ``root_path`` for a live view.

    Several imported Task 3 props contain enabled RigidBodyAPI schemas both
    on their outer prop root and on a mesh child.  PhysX does not support
    enabled rigid bodies nested in one hierarchy: its tensor backend emits an
    unresolved-dynamic-index error and then a CUDA illegal-memory-access.
    Keep the outermost body and explicitly disable every nested body before
    the first physics reset.
    """
    from pxr import Usd, UsdPhysics

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        raise RuntimeError(f"Invalid rigid-body root: {root_path}")

    rigid_prims = []
    for prim in Usd.PrimRange(root):
        enabled_attr = prim.GetAttribute("physics:rigidBodyEnabled")
        if (
            prim.HasAPI(UsdPhysics.RigidBodyAPI)
            or (enabled_attr and enabled_attr.IsValid())
        ):
            rigid_prims.append(prim)
    if not rigid_prims:
        raise RuntimeError(f"No rigid body found below {root_path}")

    primary = rigid_prims[0]
    for nested in rigid_prims[1:]:
        UsdPhysics.RigidBodyAPI(nested).CreateRigidBodyEnabledAttr(False).Set(
            False
        )
        print(
            "Disabled nested rigid body: "
            f"{nested.GetPath()} (keeping {primary.GetPath()})",
            flush=True,
        )
    return str(primary.GetPath())


def main() -> None:
    args = parse_args()
    if args.policy != "idle":
        raise NotImplementedError(
            "policy='scripted' does not exist yet -- it is built in Phase "
            "2-4 (skills + FSM) of docs/task3_master_plan.md."
        )

    # Must precede any scene composition: resolve_head_placement()'s
    # random.choice() for --head-placement=random, and the bean-spawn radial
    # jitter in scene_robot_room_keyboard.bean_spawn_positions(), both draw
    # from this global random state. Seeding here is what makes --seed
    # reproduce identical spawn poses.
    random.seed(args.seed)

    episode_slug = f"seed{args.seed}_{args.head_placement}"
    episode_dir = (args.out_dir / episode_slug).resolve()
    frames_dir = episode_dir / "frames"
    episode_dir.mkdir(parents=True, exist_ok=True)
    if args.record_video:
        frames_dir.mkdir(parents=True, exist_ok=True)
        # A crashed or killed earlier run can leave frames behind; encoding
        # globs rgb_*.png, so stale files would silently corrupt the video.
        for stale in frames_dir.glob("rgb_*.png"):
            stale.unlink()

    started_at = time.time()

    # SimulationApp must start before importing Isaac Lab/Omniverse modules.
    from isaaclab.app import AppLauncher

    # enable_cameras is required for omni.replicator (off-screen video
    # recording) to exist in headless mode. livestream=2 is AppLauncher's
    # WebRTC mode; -1 leaves streaming disabled.
    app_launcher = AppLauncher(
        {
            "headless": True,
            "enable_cameras": True,
            "livestream": 2 if args.livestream else -1,
        }
    )
    simulation_app = app_launcher.app
    # Everything after close() is unreachable: Kit's fastShutdown kills the
    # process inside close() on this build (proven 2026-07-17 -- two runs
    # finished their episode yet never wrote result.json because the write
    # sat after close()). Persist ALL results before shutting the app down;
    # the same reasoning already applied to the crash traceback below.
    try:
        result = _run_episode(args, simulation_app, frames_dir)
        result["seed"] = args.seed
        result["head_placement"] = args.head_placement
        result["policy"] = args.policy
        result["git_commit"] = git_commit_hash()
        result["date"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        # Excludes Kit shutdown time, which can be nontrivial.
        result["wall_time_seconds"] = round(time.time() - started_at, 3)
        if args.record_video:
            result["video_frames_dir"] = str(frames_dir)
            result["video_gif"] = str(episode_dir / "episode.gif")

        result_path = episode_dir / "result.json"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True))
        print(
            "EPISODE_RESULT " + json.dumps(result, sort_keys=True),
            flush=True,
        )
        sys.stdout.flush()
    except BaseException:
        traceback.print_exc()
        (episode_dir / "crash_traceback.txt").write_text(
            traceback.format_exc()
        )
        sys.stderr.flush()
        simulation_app.close()
        raise
    else:
        simulation_app.close()


def _run_episode(
    args: argparse.Namespace, simulation_app: Any, frames_dir: Path
) -> dict[str, Any]:
    for path in (SCENES_DIR, COMMON_DIR, TASK3_EVAL_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from grading import (  # noqa: E402
        DEFAULT_STAGE1_OBJECTS,
        DEFAULT_UTENSIL_OBJECTS,
        TASK3_BEAN_RECOVERY_REGION,
        Bounds2D,
        Point3D,
        bean_recovery_score,
        count_points_in_sphere,
        score_stage1_table_setup,
        score_stage4_cleanup,
    )
    from integration_test import (  # noqa: E402
        percentage,
        resolve_prim_path,
        sorted_bean_paths,
        stage_result,
    )
    from scene_robot_room_keyboard import (  # noqa: E402
        configure_keyboard_control_stage,
        configure_robot_room_stage,
        disable_robot_external_wrenches,
        make_control_scene_cfg,
        reset_robot_to_default_state,
        yaw_to_quat,
    )

    import omni.replicator.core as rep
    from isaacsim.core.prims import RigidPrim

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

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
        dynamic_beans=True,
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
    legacy_graph = sim.stage.GetPrimAtPath("/World/envs/env_0/Robot/Graph")
    if legacy_graph.IsValid() and legacy_graph.IsActive():
        raise RuntimeError(
            "Legacy robot controller OmniGraph composed active despite the "
            "headless wrapper -- it would crash after sim.reset(). Check "
            "make_headless_robot_usd()."
        )
    print("Legacy robot controller OmniGraph deactivated pre-composition",
          flush=True)

    # --- Grading-object pose reading ---------------------------------
    # integration_test.get_prim_position() reads a UsdGeom.XformCache
    # local-to-world transform, which is only valid for that module's
    # kinematic (non-physics) grading tests. Here the tray/bowl/spoon/
    # plate/cup/beans are real dynamic rigid bodies driven by PhysX, so
    # their USD xform attributes go stale while the sim is playing (see
    # docs/task3_master_plan.md section 5, "State reading"). RigidPrim
    # queries PhysX/Fabric directly and must be used for every live pose
    # read below instead.  Resolve each prop to one valid physics body: the
    # imported room asset otherwise has nested enabled bodies that PhysX's
    # tensor backend cannot index.
    # (tray, bowl2, spoon2, plate2, cup)
    grading_object_names = DEFAULT_STAGE1_OBJECTS
    object_paths = {
        name: prepare_rigid_body_view_path(
            sim.stage, resolve_prim_path(sim.stage, name)
        )
        for name in grading_object_names
    }
    _fix_single_articulation_root(sim.stage, "/World/envs/env_0/Robot")
    sim.reset()
    scene.reset()
    robot = scene["robot"]
    reset_robot_to_default_state(robot, scene.env_origins)
    scene.write_data_to_sim()

    # Bind views before the first physics step; the hierarchy repair above
    # makes the valid rigid-body views safe to construct after reset.
    object_views = {
        name: RigidPrim(prim_paths_expr=path, name=f"task3_obj_{name}")
        for name, path in object_paths.items()
    }
    bean_paths = sorted_bean_paths(sim.stage)
    bean_view = None
    if bean_paths:
        bean_scope = bean_paths[0].rsplit("/", 1)[0]
        bean_view = RigidPrim(
            prim_paths_expr=f"{bean_scope}/Bean_.*", name="task3_beans"
        )
    for view in (*object_views.values(), bean_view):
        # Isaac Sim's prim-view classes require the PhysX simulation view to
        # exist (created by the sim.reset()/scene.reset() above) before they
        # can bind; older Isaac Sim releases additionally require an
        # explicit initialize() call. Guarded because the exact requirement
        # is version-dependent and unverified without a live GPU session.
        initialize = getattr(view, "initialize", None)
        if callable(initialize):
            initialize()

    def read_positions(view: Any) -> list[Point3D]:
        positions, _orientations = view.get_world_poses()
        return [
            Point3D(*[float(v) for v in row]) for row in positions.tolist()
        ]

    spawn_positions = {
        name: read_positions(view)[0] for name, view in object_views.items()
    }
    spawn_bean_positions = read_positions(bean_view) if bean_view else []

    # --- Video setup ---------------------------------------------------
    # No Replicator writer: with the timeline playing, an attached
    # BasicWriter captures on EVERY app update regardless of orchestrator
    # gating (two runs on 2026-07-17 each wrote >12k frames -- one reached
    # 139k frames / 93 GB -- instead of the expected ~160; even
    # set_capture_on_play(False) did not stop it). An annotator is pull-
    # based: a frame exists only when this loop asks for one.
    render_product = None
    rgb_annotator = None
    frames_written = 0
    total_steps = max(1, round(args.max_seconds / sim.cfg.dt))
    capture_every = max(1, round(1.0 / (sim.cfg.dt * VIDEO_FPS)))
    if args.record_video:
        camera = rep.create.camera(
            position=CAMERA_POSITION, look_at=CAMERA_LOOK_AT
        )
        render_product = rep.create.render_product(camera, (960, 540))
        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_annotator.attach([render_product])

    # --- Idle policy: hold the reset joint targets and just step physics.
    # A 'scripted' policy (Phase 2+) would command skills here instead.
    for step in range(total_steps):
        disable_robot_external_wrenches(robot)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        if args.record_video and step % capture_every == 0:
            if _save_rgb_frame(rgb_annotator, frames_dir, frames_written):
                frames_written += 1

    if args.record_video:
        rgb_annotator.detach()
        render_product.destroy()
        expected_frames = total_steps // capture_every + 1
        print(
            f"Captured {frames_written} video frames "
            f"(expected ~{expected_frames})",
            flush=True,
        )
        _encode_gif(frames_dir, frames_dir.parent / "episode.gif")

    # --- Grading (final-state snapshot; idle policy never moves anything,
    # so all stage scores are expected to be 0 -- that is the Phase 1 exit
    # criterion, not a bug. Stage 2 (feeding) needs a temporal hold-time
    # accumulator over a real feeding motion and is deferred to the Phase 4
    # FSM, where it will reuse grading.update_feed_hold()/feed_score().)
    final_positions = {
        name: read_positions(view)[0] for name, view in object_views.items()
    }
    final_bean_positions = read_positions(bean_view) if bean_view else []

    stage1_score = score_stage1_table_setup(final_positions)
    stage1_result = stage_result(
        "stage1", stage1_score.score, stage1_score.max_score,
        stage1_score.score == stage1_score.max_score,
    )
    stage1_result["objects_passed"] = stage1_score.passed
    stage1_result["objects_failed"] = stage1_score.failed

    beans_recovered = count_points_in_sphere(
        final_bean_positions, TASK3_BEAN_RECOVERY_REGION
    )
    stage3_points = bean_recovery_score(
        beans_recovered, len(final_bean_positions)
    )
    stage3_result = stage_result(
        "stage3", stage3_points, 4, stage3_points == 4
    )
    stage3_result["beans_recovered"] = beans_recovered
    stage3_result["beans_total"] = len(final_bean_positions)
    stage3_result["beans_recovered_percent"] = percentage(
        beans_recovered, len(final_bean_positions)
    )

    # Point-approximated bounds (Bounds2D.from_point): a real geometry-aware
    # bbox per object is not implemented yet. Documented limitation -- may
    # under-credit objects whose true footprint overlaps the sink region
    # while their center point does not.
    stage4_bounds = {
        name: Bounds2D.from_point(final_positions[name])
        for name in DEFAULT_UTENSIL_OBJECTS
        if name in final_positions
    }
    stage4_z = {
        name: final_positions[name].z
        for name in DEFAULT_UTENSIL_OBJECTS
        if name in final_positions
    }
    stage4_score = score_stage4_cleanup(stage4_bounds, stage4_z)
    stage4_result = stage_result(
        "stage4", stage4_score.score, stage4_score.max_score,
        stage4_score.score == stage4_score.max_score,
    )
    stage4_result["objects_passed"] = stage4_score.passed
    stage4_result["objects_failed"] = stage4_score.failed
    stage4_result["bounds_approximation"] = "point"

    return {
        "stages": [stage1_result, stage3_result, stage4_result],
        "stage2_note": "not scored: requires the Phase 4 feeding FSM",
        "spawn_positions": {
            name: [p.x, p.y, p.z] for name, p in spawn_positions.items()
        },
        "spawn_bean_count": len(spawn_bean_positions),
        "final_positions": {
            name: [p.x, p.y, p.z] for name, p in final_positions.items()
        },
        "max_seconds": args.max_seconds,
        "sim_dt": sim.cfg.dt,
        "total_steps": total_steps,
    }


def _save_rgb_frame(annotator: Any, frames_dir: Path, index: int) -> bool:
    """Pull the latest rendered RGB frame and write it as a PNG.

    Returns False (and writes nothing) while the annotator has no valid
    data yet -- the first render or two after attach can be empty.
    """
    import numpy as np
    from PIL import Image

    data = np.asarray(annotator.get_data())
    if data.ndim != 3 or data.shape[-1] < 3 or data.size == 0:
        return False
    Image.fromarray(data[..., :3]).save(frames_dir / f"rgb_{index:04d}.png")
    return True


def _encode_gif(frames_dir: Path, output_path: Path) -> None:
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
        duration=round(1000 / VIDEO_FPS),
        loop=0,
        optimize=False,
    )


if __name__ == "__main__":
    main()
