#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Read-only Day 3 Step 0 measurements in the unmodified Task 3 scene.

This probe composes the normal room and robot, normalizes only the runtime
PhysX rigid-body view hierarchy, opens both grippers to 0.9 rad, and records
runtime poses, world bounds, edge distances, and rigid-body masses. It does
not add tray geometry, author a mass, attach objects, or drive an object.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
for path in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_episode import (  # noqa: E402
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    _fix_single_articulation_root,
    make_headless_robot_usd,
    prepare_rigid_body_view_path,
)

OBJECTS = ("simple_tray", "bowl2", "spoon2", "plate2", "cup")
EAST_COUNTER_EDGE_X = -3.77
NORTH_COUNTER_EDGE_Y = -1.22


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head-placement", choices=("a", "b", "c"), default="a")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_stage0_probe_20260718",
    )
    parser.add_argument("--settle-seconds", type=float, default=1.0)
    return parser.parse_args()


def _to_float_list(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
        value = value[0]
    return [float(item) for item in value]


def _first_runtime_mass(view: Any) -> tuple[float | None, str | None]:
    for method_name in ("get_masses", "get_mass"):
        method = getattr(view, method_name, None)
        if callable(method):
            try:
                values = _to_float_list(method())
                if values:
                    return values[0], f"{type(view).__name__}.{method_name}"
            except Exception as exc:  # pragma: no cover - Isaac-version dependent
                return None, f"{type(view).__name__}.{method_name}: {exc}"
    for attr_name in ("_physics_view", "_root_physx_view", "root_physx_view"):
        physics_view = getattr(view, attr_name, None)
        if physics_view is None:
            continue
        method = getattr(physics_view, "get_masses", None)
        if callable(method):
            try:
                values = _to_float_list(method())
                if values:
                    return values[0], f"{type(physics_view).__name__}.get_masses"
            except Exception as exc:  # pragma: no cover - Isaac-version dependent
                return None, f"{type(physics_view).__name__}.get_masses: {exc}"
    return None, None


def _candidate_finger_bodies(robot: Any) -> list[dict[str, Any]]:
    positions = robot.data.body_pos_w[0]
    candidates = []
    for index, name in enumerate(robot.body_names):
        lowered = name.lower()
        if any(token in lowered for token in ("finger", "gripper", "pad", "tip")):
            candidates.append(
                {
                    "index": index,
                    "name": name,
                    "position_world": [
                        round(float(value), 6) for value in positions[index]
                    ],
                }
            )
    return candidates


def _pair_separation(left: dict[str, Any], right: dict[str, Any]) -> float:
    return math.sqrt(
        sum(
            (a - b) ** 2
            for a, b in zip(left["position_world"], right["position_world"])
        )
    )


def _measure_fingertips(robot: Any) -> dict[str, Any]:
    candidates = _candidate_finger_bodies(robot)
    pair_candidates = []
    for left in candidates:
        for right in candidates:
            if left["index"] >= right["index"]:
                continue
            name_pair = f"{left['name']} / {right['name']}".lower()
            if "left" not in name_pair and "right" not in name_pair:
                continue
            pair_candidates.append(
                {
                    "names": [left["name"], right["name"]],
                    "separation_m": round(_pair_separation(left, right), 6),
                }
            )
    return {
        "commanded_open_rad": 0.9,
        "body_candidates": candidates,
        "pair_candidates": pair_candidates,
        "note": "Choose the pair whose names identify the two fingertips; raw candidates are preserved.",
    }


def _world_bounds(stage: Any, root_path: str) -> tuple[list[float], list[float]]:
    from pxr import Usd, UsdGeom

    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
    )
    bounds = cache.ComputeWorldBound(stage.GetPrimAtPath(root_path)).ComputeAlignedBox()
    return [round(float(value), 6) for value in bounds.GetMin()], [
        round(float(value), 6) for value in bounds.GetMax()
    ]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    from isaaclab.app import AppLauncher

    simulation_app = AppLauncher({"headless": True, "enable_cameras": False}).app
    try:
        from integration_test import resolve_prim_path
        from isaacsim.core.prims import RigidPrim
        import isaaclab.sim as sim_utils
        from isaaclab.scene import InteractiveScene
        from isaaclab.sim import SimulationContext
        from scene_robot_room_keyboard import (
            configure_keyboard_control_stage,
            configure_robot_room_stage,
            make_control_scene_cfg,
            reset_robot_to_default_state,
            yaw_to_quat,
        )
        from task3_autonomy.arms import DualArmController, GRIPPER_OPEN_RAD

        sim = SimulationContext(
            sim_utils.SimulationCfg(dt=0.005, device="cuda:0", gravity=(0.0, 0.0, -9.81))
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
        object_paths = {
            name: prepare_rigid_body_view_path(
                sim.stage, resolve_prim_path(sim.stage, name)
            )
            for name in OBJECTS
        }
        _fix_single_articulation_root(sim.stage, "/World/envs/env_0/Robot")
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
        sim.reset()
        scene.reset()
        robot = scene["robot"]
        reset_robot_to_default_state(robot, scene.env_origins)
        scene.write_data_to_sim()
        views = {
            name: RigidPrim(prim_paths_expr=path, name=f"stage0_{name}")
            for name, path in object_paths.items()
        }
        for view in views.values():
            initialize = getattr(view, "initialize", None)
            if callable(initialize):
                initialize()

        def step_once() -> None:
            scene.write_data_to_sim()
            sim.step()
            scene.update(sim.cfg.dt)

        for _ in range(max(1, round(args.settle_seconds / sim.cfg.dt))):
            step_once()

        arms = DualArmController(robot, simulation_app)
        arms.set_gripper("left", GRIPPER_OPEN_RAD)
        arms.set_gripper("right", GRIPPER_OPEN_RAD)
        for _ in range(round(1.5 / sim.cfg.dt)):
            arms.command()
            step_once()

        fingertips = _measure_fingertips(robot)
        objects = {}
        for name, view in views.items():
            positions, _ = view.get_world_poses()
            position = _to_float_list(positions)
            bbox_min, bbox_max = _world_bounds(sim.stage, resolve_prim_path(sim.stage, name))
            mass_kg, mass_source = _first_runtime_mass(view)
            authored_mass = None
            from pxr import UsdPhysics

            mass_attr = UsdPhysics.MassAPI(sim.stage.GetPrimAtPath(object_paths[name])).GetMassAttr()
            if mass_attr and mass_attr.HasAuthoredValue():
                authored_mass = float(mass_attr.Get())
            objects[name] = {
                "physx_view_path": object_paths[name],
                "pose_world": [round(value, 6) for value in position],
                "bbox_min_world": bbox_min,
                "bbox_max_world": bbox_max,
                "bbox_size_m": [round(bbox_max[i] - bbox_min[i], 6) for i in range(3)],
                "distance_to_counter_east_edge_m": round(EAST_COUNTER_EDGE_X - bbox_max[0], 6),
                "distance_to_counter_north_edge_m": round(NORTH_COUNTER_EDGE_Y - bbox_max[1], 6),
                "runtime_mass_kg": None if mass_kg is None else round(mass_kg, 6),
                "runtime_mass_source": mass_source,
                "authored_mass_kg": authored_mass,
            }

        result = {
            "probe": "task3_stage0",
            "scene": "unmodified organizer scene; runtime nested-body normalization only",
            "head_placement": args.head_placement,
            "counter_edges_world": {
                "east_x": EAST_COUNTER_EDGE_X,
                "north_y": NORTH_COUNTER_EDGE_Y,
                "distance_definition": "edge coordinate minus object bbox max coordinate",
            },
            "gripper": {
                "left_joint_rad": round(arms.gripper_position("left"), 6),
                "right_joint_rad": round(arms.gripper_position("right"), 6),
                "fingertip_measurement": fingertips,
            },
            "objects": objects,
        }
        output_path = args.output_dir / "result.json"
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("STAGE0_RESULT " + json.dumps(result, sort_keys=True), flush=True)
    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
