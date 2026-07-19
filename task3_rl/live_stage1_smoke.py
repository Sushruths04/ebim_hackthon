#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Verify that Stage 1 training signals can read the live Isaac Sim scene."""

from __future__ import annotations

import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from task3_rl.stage1 import (
    Stage1TaskCfg,
    build_observation,
    evaluate_transition,
)

TASK3_TEST_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
for path in (TASK3_TEST_DIR, SCENES_DIR, COMMON_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def main() -> None:
    import integration_test
    import scene_robot_room_keyboard as scene

    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True})
    try:
        stage = integration_test.create_task3_stage(
            app,
            scene,
            frames=12,
            disable_utensil_rigid_bodies=True,
        )
        tray_path = integration_test.resolve_prim_path(stage, "simple_tray")
        tray = integration_test.get_prim_position(stage, tray_path)
        cfg = Stage1TaskCfg()
        tray_pose = torch.tensor(
            [[tray.x, tray.y, tray.z]], dtype=torch.float32
        )
        goal_xy = torch.tensor([cfg.goal_xy], dtype=torch.float32)
        base_pose = torch.tensor([[-4.6, 2.7, -1.5708]], dtype=torch.float32)
        observation = build_observation(
            base_pose,
            tray_pose,
            torch.zeros((1, 3), dtype=torch.float32),
            goal_xy,
        )
        reward, failed, success = evaluate_transition(
            tray_pose[:, :2], tray_pose, goal_xy, torch.tensor([False]), cfg
        )
        print(
            "LIVE_STAGE1 "
            f"tray=({tray.x:.3f},{tray.y:.3f},{tray.z:.3f}) "
            f"observation_shape={tuple(observation.shape)} "
            f"reward={float(reward[0]):.3f} "
            f"failed={bool(failed[0])} success={bool(success[0])}",
            flush=True,
        )
    finally:
        app.close()


if __name__ == "__main__":
    main()
