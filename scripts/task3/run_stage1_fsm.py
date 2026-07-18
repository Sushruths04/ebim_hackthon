#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Run the bounded Stage 1 FSM against the Task 3 scene adapter.

The adapter uses the existing deterministic kinematic grading motion for the
tray group. This validates the FSM ordering, budgets, head-placement matrix,
and official scoring path; it is not a claim that rigid tray contact has been
validated in PhysX. The physical tray-grasp adapter remains the next upgrade.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import traceback
from contextlib import suppress
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TASK3_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
for import_path in (TASK3_DIR, SCENES_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from grading import DEFAULT_STAGE1_OBJECTS, Point3D, score_stage1_table_setup
from integration_test import (
    create_task3_stage,
    drive_group_translation,
    get_prim_position,
    resolve_prim_path,
    y_then_x_path,
)

from task3_autonomy.stage1_fsm import (
    Stage1Action,
    Stage1FSM,
    Stage1Observation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument(
        "--head-placements",
        nargs="+",
        default=["a", "b", "c"],
        help="Placement matrix. Trials cycle through these values.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_stage1_fsm",
    )
    parser.add_argument("--record-video", action="store_true")
    return parser.parse_args()


def _capture_callback(out_dir: Path, index: int):
    import numpy as np
    from PIL import Image
    next_index = index

    def capture(_step: int) -> None:
        nonlocal next_index
        # Replicator data is pulled only at selected adapter milestones, which
        # avoids the BasicWriter runaway that invalidated earlier videos.
        try:
            import omni.replicator.core as rep

            rep.orchestrator.step()
            data = np.asarray(capture.annotator.get_data())
        except Exception:
            return
        if data.size == 0:
            return
        if data.shape[-1] == 4:
            data = data[..., :3]
        Image.fromarray(data.astype(np.uint8)).save(
            out_dir / f"rgb_{next_index:04d}.png"
        )
        next_index += 1

    return capture


def _encode_gif(frames_dir: Path, output: Path) -> None:
    from PIL import Image

    images = [
        Image.open(path).convert("P", palette=Image.Palette.ADAPTIVE)
        for path in sorted(frames_dir.glob("rgb_*.png"))
    ]
    if not images:
        raise RuntimeError("No frames were captured for Stage 1 proof")
    images[0].save(
        output,
        save_all=True,
        append_images=images[1:],
        duration=400,
        loop=0,
        optimize=True,
    )


def _run_trial(
    app: Any,
    scene_module: Any,
    trial: int,
    head_placement: str,
    frames: int,
    capture_factory: Any | None,
) -> dict[str, Any]:
    stage = create_task3_stage(
        app,
        scene_module,
        frames,
        head_placement=head_placement,
        disable_utensil_rigid_bodies=True,
        include_beans=True,
    )
    object_paths = {
        name: resolve_prim_path(stage, name)
        for name in DEFAULT_STAGE1_OBJECTS
    }
    start_positions = {
        name: get_prim_position(stage, path)
        for name, path in object_paths.items()
    }
    start = start_positions["simple_tray"]
    target = Point3D(-2.85, 1.90, start.z)
    fsm = Stage1FSM()
    capture = capture_factory() if capture_factory is not None else None
    action = fsm.step(Stage1Observation(at_pickup=True), 0.1)
    if capture is not None:
        capture(0)

    if action is not Stage1Action.GRASP_TRAY:
        return _failed_result(trial, head_placement, fsm, "pickup")
    action = fsm.step(Stage1Observation(tray_held=True), 0.1)
    if action is not Stage1Action.TRANSPORT_TO_DINING:
        return _failed_result(trial, head_placement, fsm, "grasp")

    path = y_then_x_path(start, target, steps_per_axis=24)
    if capture is not None:
        drive_group_translation(
            app,
            stage,
            object_paths,
            start_positions,
            path,
            frames_per_step=max(1, frames // 4),
            on_step=capture,
        )
    else:
        drive_group_translation(
            app,
            stage,
            object_paths,
            start_positions,
            path,
            frames_per_step=max(1, frames // 4),
        )
    action = fsm.step(Stage1Observation(at_dining=True), 0.1)
    if action is not Stage1Action.PLACE_OBJECTS:
        return _failed_result(trial, head_placement, fsm, "transport")

    final_positions = {
        name: get_prim_position(stage, path)
        for name, path in object_paths.items()
    }
    score = score_stage1_table_setup(final_positions)
    placed = score.score >= 4
    action = fsm.step(Stage1Observation(placed=placed), 0.1)
    if action is not Stage1Action.RELEASE_TRAY:
        return _failed_result(trial, head_placement, fsm, "place")
    action = fsm.step(Stage1Observation(released=True), 0.1)
    if action is not Stage1Action.RETREAT:
        return _failed_result(trial, head_placement, fsm, "release")
    fsm.step(Stage1Observation(retreated=True), 0.1)
    if capture is not None:
        capture(9999)
        with suppress(Exception):
            capture.annotator.detach()
        with suppress(Exception):
            capture.render_product.destroy()
    return {
        "trial": trial,
        "head_placement": head_placement,
        "mode": "kinematic_scene_adapter",
        "score": score.score,
        "max_score": score.max_score,
        "passed": fsm.succeeded and score.score >= 4,
        "objects_passed": score.passed,
        "objects_failed": score.failed,
        "fsm_state": fsm.state.value,
        "fsm_history": [state.value for state in fsm.history],
        "final_positions": {
            name: [position.x, position.y, position.z]
            for name, position in final_positions.items()
        },
    }


def _failed_result(
    trial: int, head_placement: str, fsm: Stage1FSM, phase: str
) -> dict[str, Any]:
    return {
        "trial": trial,
        "head_placement": head_placement,
        "mode": "kinematic_scene_adapter",
        "score": 0,
        "max_score": 5,
        "passed": False,
        "failure_phase": phase,
        "fsm_state": fsm.state.value,
        "fsm_history": [state.value for state in fsm.history],
    }


def main() -> None:
    args = parse_args()
    if args.trials <= 0 or not args.head_placements:
        raise ValueError("trials and head-placements must be non-empty")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = args.out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("rgb_*.png"):
        stale.unlink()

    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True, "width": 960, "height": 540})
    frame_index = 0
    try:
        import scene_robot_room_keyboard as scene_module

        runs = []
        print("STAGE1_RUNNER scene_imported", flush=True)
        capture_factory = None
        if args.record_video:
            def capture_factory() -> Any:
                import omni.replicator.core as rep

                print("STAGE1_VIDEO_SETUP start", flush=True)
                camera = rep.create.camera(
                    position=(-1.6, -3.4, 2.2),
                    look_at=(-3.4, 0.0, 0.8),
                )
                render_product = rep.create.render_product(
                    camera, (960, 540)
                )
                annotator = rep.AnnotatorRegistry.get_annotator("rgb")
                annotator.attach([render_product])
                capture = _capture_callback(frames_dir, frame_index)
                capture.annotator = annotator
                capture.render_product = render_product
                print("STAGE1_VIDEO_SETUP ready", flush=True)
                return capture

        for trial in range(1, args.trials + 1):
            placement = args.head_placements[
                (trial - 1) % len(args.head_placements)
            ]
            runs.append(
                _run_trial(
                    app,
                    scene_module,
                    trial,
                    placement,
                    frames=12,
                    capture_factory=capture_factory,
                )
            )
            print("STAGE1_FSM_RUN " + json.dumps(runs[-1], sort_keys=True))

        passed = sum(bool(run["passed"]) for run in runs)
        summary = {
            "trials": args.trials,
            "required_passes": 7,
            "pass_count": passed,
            "pass_rate": passed / args.trials,
            "head_placements": sorted({run["head_placement"] for run in runs}),
            "required_head_placements": 3,
            "gate_passed": passed >= 7
            and len({run["head_placement"] for run in runs}) >= 3,
            "mode": "kinematic_scene_adapter",
            "runs": runs,
        }
        (args.out_dir / "result.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
        )
        if args.record_video:
            _encode_gif(frames_dir, args.out_dir / "stage1_fsm.gif")
        print("STAGE1_FSM_RESULT " + json.dumps(summary, sort_keys=True))
        raise SystemExit(0 if summary["gate_passed"] else 1)
    except BaseException:
        traceback.print_exc()
        (args.out_dir / "crash_traceback.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        raise
    finally:
        app.close()


if __name__ == "__main__":
    random.seed(42)
    main()
