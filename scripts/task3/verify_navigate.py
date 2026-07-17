#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 2 gate: drive the real robot base with NavigateTo and verify it.

Builds the exact Task 3 scene of run_episode.py (same wrapper-USD robot,
same hierarchy repairs), then closes the loop live: NavigateTo emits body
twists, TmrBaseAdapter turns them into TMR steering/wheel targets, PhysX
integrates. Passes when the base stops within tolerance of the target.
Prints one NAVIGATE_RESULT JSON line and exits nonzero on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"

from run_episode import (  # noqa: E402  (same directory)
    CAMERA_LOOK_AT,
    CAMERA_POSITION,
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    VIDEO_FPS,
    _encode_gif,
    _fix_single_articulation_root,
    _save_rgb_frame,
    make_headless_robot_usd,
    prepare_rigid_body_view_path,  # noqa: F401  (re-export for FSM reuse)
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the live NavigateTo skill on the real base."
    )
    parser.add_argument("--target-x", type=float, default=-2.0)
    parser.add_argument("--target-y", type=float, default=-1.5)
    parser.add_argument("--tolerance-m", type=float, default=0.10)
    parser.add_argument("--max-seconds", type=float, default=40.0)
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--livestream", action="store_true")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_verify_navigate",
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

    from isaaclab.app import AppLauncher

    # Cameras only when actually needed: enable_cameras makes sim.step()
    # run full app updates whose USD sync can interfere with tensor-API
    # joint targets (2026-07-17 investigation) -- and it triples wall time.
    app_launcher = AppLauncher(
        {
            "headless": True,
            "enable_cameras": bool(args.record_video or args.livestream),
            "livestream": 2 if args.livestream else -1,
        }
    )
    simulation_app = app_launcher.app
    # Persist results BEFORE close(): Kit's fastShutdown kills the process
    # inside close(), so any code after it never runs (proven 2026-07-17
    # in run_episode.py).
    try:
        result = _verify(args, simulation_app, frames_dir)
        result["wall_time_seconds"] = round(time.time() - started_at, 3)
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True)
        )
        print(
            "NAVIGATE_RESULT " + json.dumps(result, sort_keys=True),
            flush=True,
        )
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


def _verify(
    args: argparse.Namespace, simulation_app: Any, frames_dir: Path
) -> dict[str, Any]:
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

    # omni.replicator only exists when the app started with cameras.
    rep = None
    if args.record_video:
        import omni.replicator.core as rep

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

    from task3_autonomy.skills import NavigateTo, TmrBaseAdapter

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

    rgb_annotator = None
    render_product = None
    frames_written = 0
    capture_every = max(1, round(1.0 / (sim.cfg.dt * VIDEO_FPS)))
    if args.record_video:
        camera = rep.create.camera(
            position=CAMERA_POSITION, look_at=CAMERA_LOOK_AT
        )
        render_product = rep.create.render_product(camera, (960, 540))
        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_annotator.attach([render_product])

    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")
    skill = NavigateTo((args.target_x, args.target_y))

    total_steps = max(1, round(args.max_seconds / sim.cfg.dt))
    done = False
    for step in range(total_steps):
        pose = adapter.pose()
        vx, vy, done = skill.compute(pose)
        if done:
            break
        adapter.apply_twist(vx, vy)
        disable_robot_external_wrenches(robot)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        if args.record_video and step % capture_every == 0:
            if _save_rgb_frame(rgb_annotator, frames_dir, frames_written):
                frames_written += 1

    final_pose = adapter.pose()
    error_m = (
        (final_pose.x - args.target_x) ** 2
        + (final_pose.y - args.target_y) ** 2
    ) ** 0.5

    if args.record_video:
        rgb_annotator.detach()
        render_product.destroy()
        print(f"Captured {frames_written} video frames", flush=True)
        if frames_written:
            _encode_gif(frames_dir, frames_dir.parent / "navigate.gif")

    return {
        "passed": bool(done and error_m <= args.tolerance_m),
        "skill_reported_done": bool(done),
        "target": [args.target_x, args.target_y],
        "final_pose": [final_pose.x, final_pose.y, final_pose.yaw],
        "position_error_m": round(error_m, 4),
        "tolerance_m": args.tolerance_m,
        "sim_dt": sim.cfg.dt,
        "steps_used": step + 1,
        "max_seconds": args.max_seconds,
    }


if __name__ == "__main__":
    main()
