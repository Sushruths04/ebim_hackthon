#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Capture one static Task 3 room image without running the task simulation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK3_EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save one off-screen image of the static EBiM Task 3 room."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_static_view",
        help="Directory where Isaac Sim writes the PNG.",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Image width in pixels."
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Image height in pixels."
    )
    parser.add_argument(
        "--camera-x",
        type=float,
        default=None,
        help="Optional world X coordinate for an explicit measurement camera.",
    )
    parser.add_argument(
        "--camera-y",
        type=float,
        default=None,
        help="Optional world Y coordinate for an explicit measurement camera.",
    )
    parser.add_argument(
        "--camera-z",
        type=float,
        default=None,
        help="Optional world Z coordinate for an explicit measurement camera.",
    )
    parser.add_argument(
        "--look-at-x",
        type=float,
        default=None,
        help="Optional world X coordinate for the measurement-camera target.",
    )
    parser.add_argument(
        "--look-at-y",
        type=float,
        default=None,
        help="Optional world Y coordinate for the measurement-camera target.",
    )
    parser.add_argument(
        "--look-at-z",
        type=float,
        default=None,
        help="Optional world Z coordinate for the measurement-camera target.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # SimulationApp must start before importing Omniverse/Isaac modules.
    from isaacsim import SimulationApp

    app = SimulationApp(
        {"headless": True, "width": args.width, "height": args.height}
    )
    try:
        for module_dir in (TASK3_EVALUATION_DIR, SCENES_DIR):
            if str(module_dir) not in sys.path:
                sys.path.insert(0, str(module_dir))

        import scene_robot_room_keyboard as scene
        from integration_test import create_task3_stage

        import omni.replicator.core as rep

        # This is the benchmark's Stage 4 setup with its 300 dynamic beans removed.
        create_task3_stage(app, scene, frames=1, include_beans=False)

        position, _ = scene.INITIAL_VIEW_POSE
        # Replicator uses a different Euler convention than the interactive viewport.
        # The target below is the workspace point in front of the benchmark camera.
        if any(
            value is not None
            for value in (args.camera_x, args.camera_y, args.camera_z)
        ):
            if any(
                value is None
                for value in (args.camera_x, args.camera_y, args.camera_z)
            ):
                raise ValueError(
                    "--camera-x, --camera-y, and --camera-z must be supplied together"
                )
            position = (args.camera_x, args.camera_y, args.camera_z)
        look_at = (-4.46, -0.21, 1.35)
        if any(
            value is not None
            for value in (args.look_at_x, args.look_at_y, args.look_at_z)
        ):
            if any(
                value is None
                for value in (args.look_at_x, args.look_at_y, args.look_at_z)
            ):
                raise ValueError(
                    "--look-at-x, --look-at-y, and --look-at-z must be supplied together"
                )
            look_at = (args.look_at_x, args.look_at_y, args.look_at_z)
        camera = rep.create.camera(
            position=position,
            look_at=look_at,
        )
        render_product = rep.create.render_product(
            camera, (args.width, args.height)
        )
        writer = rep.writers.get("BasicWriter")
        writer.initialize(output_dir=str(args.output_dir), rgb=True)
        writer.attach([render_product])

        for _ in range(5):
            app.update()
        rep.orchestrator.step(rt_subframes=4)
        rep.orchestrator.wait_until_complete()

        writer.detach()
        render_product.destroy()
        images = sorted(args.output_dir.glob("rgb_*.png"))
        if not images:
            raise RuntimeError(
                f"Isaac Sim did not write an RGB image to {args.output_dir}"
            )
        print(f"STATIC_VIEW_IMAGE {images[-1]}", flush=True)
    finally:
        app.close()


if __name__ == "__main__":
    main()
