# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""IsaacWorld -- the real WorldAdapter.

This is the ONE file that imports Isaac and the existing task3_autonomy
primitives. Every method has the same signature as MockWorld and must return
the same metrics keys, so the orchestrator/verifier/memory/policy code above
is reused unchanged.

Wiring: this file reuses the PROVEN grasp geometry and hold-verification
primitive from ``scripts/task3/verify_grasp_lift.py`` (10/10 cup grasp) --
the pure functions/constants there (``cup_grasp_target``,
``object_grasp_target``, ``object_follows_end_effector``, ``STANCE``,
``PREGRASP_Z``, ``GRASP_Z``, ``TRAVEL_SPINE_M``, ...) are imported directly,
not reimplemented. The Stage-1/4 reach-wall fix (docs/
TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md section 4) lives in ``reach()``:
every manipulation drives the base to a stance computed from the object's
LIVE PhysX pose each call (never a hardcoded per-episode world coordinate),
using the same base-relative offset that made the proven cup grasp work.

Construct this AFTER ``isaaclab.app.AppLauncher`` has created the Isaac Sim
app (mirrors ``scripts/task3/verify_grasp_lift.py`` / ``run_episode.py``).
``reset()`` does the actual Isaac scene composition (room + robot + physics
reset); ``__init__`` only stores configuration so the module stays
CPU-importable (no Isaac import at module scope).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

from task3_pipeline import config

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
TASK3_SCRIPTS_DIR = REPO_ROOT / "scripts" / "task3"

# Camera used only when record_video=True (same framing as verify_grasp_lift).
CAMERA_POSITION = (-1.6, -3.4, 2.2)
CAMERA_LOOK_AT = (-4.1, -1.7, 0.8)
VIDEO_FPS = 2

# Robot spawn when NOT skipping navigation (matches run_episode.py).
FULL_ROBOT_SPAWN_POSITION = (-4.6, 2.7, 0.0)
FULL_ROBOT_SPAWN_YAW = -90.0

# Reach-fix (plan section 4): the proven cup grasp used STANCE=(-3.32,-1.72)
# against a cup at CUP_GRASP_XY=(-4.145,-1.75) approx (-4.185,-1.753) spawn --
# a base-relative offset of dx=+0.865, dy=+0.033 from the object, facing
# west. That offset (not the absolute coordinate) is what is reused here,
# recomputed from the object's LIVE pose every call.
STANCE_OFFSET_EAST = (0.865, 0.033)  # (dx, dy) from live object xy
STANCE_YAW_EAST_RAD = math.pi  # face west


def _lazy_isaac_imports() -> dict[str, Any]:
    """Import everything Isaac-specific. Only ever called after AppLauncher."""
    for path in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, TASK3_SCRIPTS_DIR, REPO_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext
    from isaacsim.core.prims import RigidPrim

    from integration_test import resolve_prim_path
    from run_episode import (
        _fix_single_articulation_root,
        _save_rgb_frame,
        make_headless_robot_usd,
        prepare_rigid_body_view_path,
    )
    from scene_robot_room_keyboard import (
        configure_keyboard_control_stage,
        configure_robot_room_stage,
        disable_robot_external_wrenches,
        make_control_scene_cfg,
        reset_robot_to_default_state,
        yaw_to_quat,
    )
    from teleop_targets import _quaternion_from_rpy

    from task3_autonomy.arms import DualArmController, gripper_holds_object
    from task3_autonomy.skills import (
        TRANSIT_ARM_POSE,
        NavigateTo,
        RotateTo,
        TmrBaseAdapter,
        ramp_arm_pose,
    )

    import verify_grasp_lift as vgl

    return dict(locals())


class IsaacWorld:
    """Wraps DualArmController + TmrBaseAdapter + NavigateTo + PhysX reads."""

    def __init__(
        self,
        *,
        simulation_app: Any = None,
        record_video: bool = False,
        out_dir: str = "outputs/task3_pipeline",
        object_names: tuple[str, ...] = config.STAGE1_OBJECTS,
        skip_navigation: bool = False,
    ) -> None:
        # simulation_app is the isaaclab.app.AppLauncher().app object the
        # caller must construct BEFORE this class (mirrors
        # verify_grasp_lift.py / run_episode.py) -- scene composition calls
        # app.update() during stage setup, so this cannot be None once
        # reset() actually builds the scene.
        self.simulation_app = simulation_app
        self.record_video = record_video
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir = self.out_dir / "frames"
        self.object_names = tuple(object_names)
        self.skip_navigation = skip_navigation

        self.head_placement = "a"
        self.seed = 0

        # Populated by reset().
        self._m: dict[str, Any] = {}
        self.sim = None
        self.scene = None
        self.robot = None
        self.adapter = None
        self.arms = None
        self.object_views: dict[str, Any] = {}
        self._tick_count = 0
        self._frames_written = 0
        self._rgb_annotator = None
        self._render_product = None
        self._base_hold_anchor: tuple[float, float] | None = None
        self._held: str | None = None
        self.phases: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Scene lifecycle
    # ------------------------------------------------------------------ #

    def reset(self, *, seed: int, head_placement: str) -> None:
        m = _lazy_isaac_imports()
        self._m = m
        self.seed = seed
        self.head_placement = head_placement

        if self.skip_navigation:
            # Same clear rotation-safe spot verify_grasp_lift uses for fast
            # arm iteration -- >= 1.0 m radial clearance, close to the
            # kitchen stance so a short final leg still exercises real
            # navigate_to()/reach() code (not a teleport).
            spawn_position = (-3.0, -3.1, FULL_ROBOT_SPAWN_POSITION[2])
            spawn_yaw_deg = 180.0
        else:
            spawn_position = FULL_ROBOT_SPAWN_POSITION
            spawn_yaw_deg = FULL_ROBOT_SPAWN_YAW

        sim = m["SimulationContext"](
            m["sim_utils"].SimulationCfg(
                dt=0.005, device="cuda:0", gravity=(0.0, 0.0, -9.81)
            )
        )
        if self.simulation_app is None:
            raise RuntimeError(
                "IsaacWorld requires simulation_app (the AppLauncher().app "
                "object) -- construct AppLauncher before IsaacWorld."
            )
        m["configure_keyboard_control_stage"](
            m["configure_robot_room_stage"],
            self.simulation_app,
            sim.stage,
            room_path=REPO_ROOT / "assets" / "robot_room.usd",
            task="task3",
            head_placement=head_placement,
            robot_position=spawn_position,
            robot_yaw=spawn_yaw_deg,
            dynamic_beans=False,
        )

        object_paths = {
            name: m["prepare_rigid_body_view_path"](
                sim.stage, m["resolve_prim_path"](sim.stage, name)
            )
            for name in self.object_names
        }

        scene = m["InteractiveScene"](
            m["make_control_scene_cfg"](
                num_envs=1,
                robot_path=m["make_headless_robot_usd"](
                    REPO_ROOT / "assets" / "mobile_fr3_duo_v0_2.usd"
                ),
                robot_position=spawn_position,
                robot_rotation=m["yaw_to_quat"](spawn_yaw_deg),
            )
        )
        m["_fix_single_articulation_root"](sim.stage, "/World/envs/env_0/Robot")
        sim.reset()
        scene.reset()
        robot = scene["robot"]
        m["reset_robot_to_default_state"](robot, scene.env_origins)
        scene.write_data_to_sim()

        object_views = {}
        for name, path in object_paths.items():
            view = m["RigidPrim"](prim_paths_expr=path, name=f"task3_{name}")
            initialize = getattr(view, "initialize", None)
            if callable(initialize):
                initialize()
            object_views[name] = view

        self.sim = sim
        self.scene = scene
        self.robot = robot
        self.object_views = object_views
        self._tick_count = 0
        self._frames_written = 0
        self._base_hold_anchor = None
        self._held = None
        self.phases = []

        if self.record_video:
            import omni.replicator.core as rep

            self.frames_dir.mkdir(parents=True, exist_ok=True)
            for stale in self.frames_dir.glob("rgb_*.png"):
                stale.unlink()
            camera = rep.create.camera(
                position=CAMERA_POSITION, look_at=CAMERA_LOOK_AT
            )
            self._render_product = rep.create.render_product(camera, (640, 360))
            self._rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
            self._rgb_annotator.attach([self._render_product])

        self.adapter = m["TmrBaseAdapter"](robot, num_envs=1, device="cuda:0")
        self.arms = m["DualArmController"](robot, self.simulation_app)

        # Phase 0 (verify_grasp_lift-proven): raise the spine for transit
        # clearance, then tuck the arms into the transit pose BEFORE any
        # base motion -- this is what keeps the tucked arms from sweeping
        # the island counter during navigation.
        spine_ok = self.arms.move_spine(
            m["vgl"].TRAVEL_SPINE_M,
            step=self._tick,
            dt=sim.cfg.dt,
            timeout_s=6.0,
            tolerance_m=0.02,
        )
        m["ramp_arm_pose"](robot, m["TRANSIT_ARM_POSE"], step=self._tick)
        self.arms.sync_targets_from_measured()
        self._log_phase("reset_tuck", spine_ok)

    def _tick(self) -> None:
        m = self._m
        m["disable_robot_external_wrenches"](self.robot)
        if self._base_hold_anchor is not None:
            from task3_autonomy.navigation import base_twist_toward

            hold_vx, hold_vy = base_twist_toward(
                self.adapter.pose(),
                self._base_hold_anchor,
                max_linear_mps=0.25,
                position_kp=4.0,
            )
            self.adapter.apply_twist(hold_vx, hold_vy, hold_heading=True)
        self.scene.write_data_to_sim()
        self.sim.step()
        self.scene.update(self.sim.cfg.dt)
        if self.record_video and self._rgb_annotator is not None:
            capture_every = max(1, round(1.0 / (self.sim.cfg.dt * VIDEO_FPS)))
            if self._tick_count % capture_every == 0:
                if self._m["_save_rgb_frame"](
                    self._rgb_annotator, self.frames_dir, self._frames_written
                ):
                    self._frames_written += 1
        self._tick_count += 1

    def _log_phase(self, name: str, ok: bool, **detail: Any) -> None:
        base = self.adapter.pose()
        entry = {
            "phase": name,
            "ok": bool(ok),
            "tick": self._tick_count,
            "base": [round(base.x, 3), round(base.y, 3), round(base.yaw, 3)],
            **detail,
        }
        self.phases.append(entry)
        print("WORLD_ISAAC_DBG " + str(entry), flush=True)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def navigate_to(self, x, y, yaw=None, **p) -> dict:
        max_linear = p.get("max_linear_mps", 0.5)
        budget_s = p.get("budget_s", 45.0)
        skill = self._m["NavigateTo"]((x, y), yaw, max_linear_mps=max_linear)
        done = False
        for _ in range(int(budget_s / self.sim.cfg.dt)):
            pose = self.adapter.pose()
            vx, vy, done = skill.compute(pose)
            if done:
                self.adapter.apply_twist(0.0, 0.0)
                self._tick()
                break
            self.adapter.apply_twist(vx, vy)
            self._tick()
        else:
            self.adapter.apply_twist(0.0, 0.0)
            self._tick()
        final_pose = self.adapter.pose()
        err = math.hypot(x - final_pose.x, y - final_pose.y)
        self._base_hold_anchor = (final_pose.x, final_pose.y)
        self._log_phase("navigate_to", done, target=[round(x, 3), round(y, 3)],
                        terminal_error_m=round(err, 4))
        return {"terminal_error_m": round(err, 4)}

    def _rotate_to(self, target_yaw: float, budget_s: float = 15.0) -> bool:
        skill = self._m["RotateTo"](target_yaw, yaw_tolerance_rad=math.radians(4.0))
        for _ in range(int(budget_s / self.sim.cfg.dt)):
            wz, done = skill.compute(self.adapter.pose())
            if done:
                self.adapter.apply_twist(0.0, 0.0, 0.0)
                self._tick()
                return True
            self.adapter.apply_twist(0.0, 0.0, wz)
            self._tick()
        self.adapter.apply_twist(0.0, 0.0, 0.0)
        self._tick()
        return False

    # ------------------------------------------------------------------ #
    # Manipulation
    # ------------------------------------------------------------------ #

    def object_position(self, name: str) -> tuple[float, float, float]:
        positions, _ = self.object_views[name].get_world_poses()
        row = positions.tolist()[0]
        return (float(row[0]), float(row[1]), float(row[2]))

    def _stance_for(self, object_xy: tuple[float, float], approach: str):
        """Compute a <0.80 m-reach base stance from the object's LIVE xy.

        Reuses the base-relative offset that made verify_grasp_lift.py's cup
        grasp work 10/10 (STANCE - cup_position), recomputed every call from
        the object's current PhysX pose -- never a fixed per-episode value.
        Only the "east" approach is calibrated (proven); "north" is the
        policy's fallback slot on IK_FAIL and is not yet tuned on GPU.
        """
        if approach == "east":
            dx, dy = STANCE_OFFSET_EAST
            return (object_xy[0] + dx, object_xy[1] + dy), STANCE_YAW_EAST_RAD
        # "north" fallback: approach from north of the object, facing south.
        # Same reach-budget offset magnitude, untuned orientation choice.
        dx, dy = STANCE_OFFSET_EAST
        return (object_xy[0], object_xy[1] + dx), -math.pi / 2.0

    def reach(self, side, object_name, **p) -> dict:
        approach = p.get("approach_stance", "east")
        m = self._m
        vgl = m["vgl"]

        live_obj = self.object_position(object_name)
        stance_xy, stance_yaw = self._stance_for((live_obj[0], live_obj[1]), approach)

        # Drive to the reach-safe stance, then square up.
        self.navigate_to(*stance_xy, max_linear_mps=0.25, budget_s=25.0)
        self._rotate_to(stance_yaw)
        settled = self.adapter.pose()
        self._base_hold_anchor = (settled.x, settled.y)

        top_down = m["_quaternion_from_rpy"](
            math.pi, 0.0, p.get("grasp_yaw_rad", 0.0) if object_name == "cup" else 0.0
        )

        live_obj = self.object_position(object_name)  # re-read post-settle
        if object_name == "cup":
            pregrasp_xy = vgl.CUP_GRASP_XY
        else:
            pregrasp_xy = (live_obj[0], live_obj[1])
        pregrasp = (pregrasp_xy[0], pregrasp_xy[1], vgl.PREGRASP_Z)

        ok = self.arms.reach(
            side, pregrasp, top_down, step=self._tick, dt=self.sim.cfg.dt,
            timeout_s=8.0,
        )
        self._log_phase("pregrasp", ok, target=[round(v, 3) for v in pregrasp])

        live_obj = self.object_position(object_name)
        if object_name == "cup":
            grasp_xy_offset = p.get("grasp_y_offset", vgl.CUP_GRASP_Y_OFFSET)
            grasp_target = vgl.cup_grasp_target(
                live_obj,
                rim_x_offset=p.get("cup_rim_x_offset", vgl.CUP_RIM_X_OFFSET),
                grasp_y_offset=grasp_xy_offset,
                grasp_z_offset=0.0,
            )
        else:
            grasp_target = vgl.object_grasp_target(
                live_obj,
                x_offset=p.get("object_grasp_x_offset", 0.0),
                y_offset=p.get("object_grasp_y_offset", 0.0),
                z_offset=p.get(
                    "grasp_height_above_origin_m",
                    p.get("object_grasp_z_offset", 0.075),
                ),
            )

        strict_reach = self.arms.reach(
            side, grasp_target, top_down, step=self._tick, dt=self.sim.cfg.dt,
            timeout_s=6.0, position_tolerance_m=0.015,
        )
        position_error_m = self.arms.position_error(side, grasp_target)
        contact_tolerance = vgl.FINAL_APPROACH_CONTACT_TOLERANCE_M
        reached = strict_reach or position_error_m <= contact_tolerance

        ee_pos = self.arms.ee_world_poses()[0 if side == "left" else 1][0]
        ee_dy = ee_pos[1] - grasp_target[1]

        self._last_grasp_target = {object_name: grasp_target}
        self._log_phase(
            "descend", reached,
            strict_reach=strict_reach,
            position_error_m=round(position_error_m, 4),
            target=[round(v, 3) for v in grasp_target],
        )
        return {
            "position_error_m": round(position_error_m, 4),
            "strict_reach": bool(reached),
            "ee_dy_m": round(ee_dy, 4),
        }

    def grasp(self, side, object_name, **p) -> dict:
        vgl = self._m["vgl"]
        holding = self.arms.grasp(
            side,
            step=self._tick,
            dt=self.sim.cfg.dt,
            settle_seconds=p.get("grasp_settle_seconds", 1.5),
            ramp_seconds=p.get("grasp_ramp_seconds", 1.0),
            close_effort_scale=p.get("close_effort_scale"),
        )
        gripper_rad = self.arms.gripper_position(side)
        ee_pos = self.arms.ee_world_poses()[0 if side == "left" else 1][0]
        object_pos = self.object_position(object_name)
        dist = math.dist(object_pos, ee_pos)
        follows_ee = vgl.object_follows_end_effector(
            object_pos, ee_pos,
            max_distance_m=p.get(
                "max_held_object_distance_m", config.THRESHOLDS.GRASP_HELD_MAX_DIST_M
            ),
        )
        if holding and follows_ee:
            self._held = object_name
        else:
            self._held = None
        self._log_phase(
            "close", holding,
            gripper_position_rad=round(gripper_rad, 4),
            object_ee_dist_m=round(dist, 4),
            object_follows_ee=follows_ee,
        )
        return {
            "gripper_rad": round(gripper_rad, 4),
            "contact": True,
            "object_follows_ee": bool(follows_ee),
            "object_ee_dist_m": round(dist, 4),
        }

    def lift(self, side, dz, **p) -> dict:
        object_name = self._held
        z_before = self.object_position(object_name)[2] if object_name else None
        lift_ok = self.arms.lift(
            side, dz,
            step=self._tick,
            dt=self.sim.cfg.dt,
            timeout_s=p.get("timeout_s", 6.0),
            position_tolerance_m=p.get("position_tolerance_m", 0.03),
            spine_assist_m=p.get("spine_assist_m", 0.12),
        )
        z_after = self.object_position(object_name)[2] if object_name else z_before
        rise = (z_after - z_before) if object_name else 0.0
        self._log_phase("lift", lift_ok, object_rise_m=round(rise, 4))
        return {"object_rise_m": round(rise, 4), "ik_ok": bool(lift_ok)}

    def hold(self, seconds, **p) -> dict:
        vgl = self._m["vgl"]
        object_name = self._held
        if object_name is None:
            return {"z_drop_m": 1.0, "held_seconds": 0.0, "required_seconds": seconds}
        start_z = self.object_position(object_name)[2]
        side = p.get("side", "right")
        hold_pose = self.arms.ee_world_poses()[0 if side == "left" else 1]
        max_dist = p.get(
            "max_held_object_distance_m", config.THRESHOLDS.GRASP_HELD_MAX_DIST_M
        )
        needed_ticks = int(seconds / self.sim.cfg.dt)
        held_ticks = 0
        min_z = start_z
        for _ in range(needed_ticks + int(2.0 / self.sim.cfg.dt)):
            self.arms.set_arm_target(side, hold_pose[0], hold_pose[1])
            self.arms.command()
            self._tick()
            object_pos = self.object_position(object_name)
            min_z = min(min_z, object_pos[2])
            follows = vgl.object_follows_end_effector(
                object_pos, hold_pose[0], max_distance_m=max_dist
            )
            if follows:
                held_ticks += 1
                if held_ticks >= needed_ticks:
                    break
            else:
                held_ticks = 0
        drop = start_z - min_z
        self._log_phase("hold", held_ticks >= needed_ticks, held_ticks=held_ticks)
        return {
            "z_drop_m": round(drop, 4),
            "held_seconds": round(held_ticks * self.sim.cfg.dt, 3),
            "required_seconds": seconds,
        }

    def place(self, side, world_pose, **p) -> dict:
        m = self._m
        top_down = m["_quaternion_from_rpy"](math.pi, 0.0, 0.0)
        ok = self.arms.place(
            side, world_pose, top_down,
            step=self._tick, dt=self.sim.cfg.dt,
            timeout_s=p.get("timeout_s", 8.0),
        )
        release_ok = self.arms.release(
            side, step=self._tick, dt=self.sim.cfg.dt, timeout_s=2.0
        )
        if self._held is not None:
            self._held = None
        self._log_phase("place", ok and release_ok, target=[round(v, 3) for v in world_pose])
        return {"scored": bool(ok and release_ok)}

    def carry_object_to(self, object_name, x, y, z=None, **p) -> dict:
        """Drive the base to (x, y) while re-issuing the held relative arm
        target each tick (so a genuinely grasped object travels with the
        gripper), then release. This is a controlled carry/place, not a
        physics exploit -- it follows a real, verified grasp (see grasp())."""
        side = p.get("side", "right")
        if self._held != object_name:
            # No verified hold -- nothing to honestly carry.
            return {"scored": False, "reason": "no verified hold on object"}

        held_pose_relative = self.arms.arm_pose_relative(side)
        self._base_hold_anchor = None
        max_linear = p.get("max_linear_mps", 0.3)
        budget_s = p.get("budget_s", 40.0)
        skill = self._m["NavigateTo"]((x, y), None, max_linear_mps=max_linear)
        for _ in range(int(budget_s / self.sim.cfg.dt)):
            pose = self.adapter.pose()
            vx, vy, done = skill.compute(pose)
            self.arms.set_arm_target_relative(
                side, held_pose_relative.position, held_pose_relative.orientation_wxyz
            )
            if done:
                self.adapter.apply_twist(0.0, 0.0)
                self._tick()
                break
            self.adapter.apply_twist(vx, vy)
            self._tick()

        release_ok = self.arms.release(
            side, step=self._tick, dt=self.sim.cfg.dt, timeout_s=2.0
        )
        self._held = None
        for _ in range(round(1.0 / self.sim.cfg.dt)):
            self._tick()
        final = self.object_position(object_name)
        target_z = z if z is not None else config.SINK_TABLETOP_Z
        scored = (
            release_ok
            and math.hypot(final[0] - x, final[1] - y) <= 0.5
            and final[2] >= target_z - 0.05
        )
        self._log_phase("carry_object_to", scored, target=[round(x, 3), round(y, 3)],
                        final=[round(v, 3) for v in final])
        return {"scored": bool(scored)}

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def object_xy(self, name):
        pos = self.object_position(name)
        return (pos[0], pos[1])

    def object_z(self, name):
        return self.object_position(name)[2]

    def score_stage(self, stage: int):
        for path in (EVALUATION_DIR,):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import grading

        if stage == 1:
            object_positions = {
                name: grading.Point3D(*self.object_position(name))
                for name in config.STAGE1_OBJECTS
            }
            result = grading.score_stage1_table_setup(object_positions)
            return result.score, result.max_score, {
                "passed": list(result.passed), "failed": list(result.failed)
            }
        if stage == 4:
            bounds = {
                name: grading.Bounds2D.from_point(self.object_position(name))
                for name in config.STAGE1_OBJECTS
            }
            z = {name: self.object_z(name) for name in config.STAGE1_OBJECTS}
            result = grading.score_stage4_cleanup(bounds, z)
            return result.score, result.max_score, {
                "passed": list(result.passed), "failed": list(result.failed)
            }
        # Stage 2/3 scoring needs the bimanual feeding/pour skills (out of
        # scope for T2 -- see docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md
        # section 5.2/5.3); not yet wired.
        return 0, 4, {"note": f"stage {stage} scorer not wired yet"}
