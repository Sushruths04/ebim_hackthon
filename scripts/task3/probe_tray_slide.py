#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Physical-only Step 1 probe: slide the flat tray to an edge and pinch it.

The tray remains the organizer asset. This script uses only robot joint
targets, contact, and PhysX pose reads. It intentionally contains no
kinematic object motion, added geometry, mass override, or fixed joint.

Fix round 1 (2026-07-18): the first trial failed at ``push_precontact``
because a single direct reach targeted a pose ~1.0 m from the stance --
past the proven ~0.83 m dead-ahead envelope from the cup pipeline -- and
swept the outstretched arm through the tray airspace. That revision mirrors
the proven cup pipeline instead: a local ``TRAY_STANCE`` puts the contact
point dead ahead (~0.86 m), a pregrasp-above reach is followed by a
closed-fist ramped vertical descend onto the tray top (not a single
``reach()``, which would never converge into contact), then a synchronized
north drag that ramps the arm's push target and the base hold anchor by the
same offset every tick so the commanded arm/base separation never grows. 4
bounded trials found the reach fix worked (0 IK failures at descend_ee_z in
[0.815, 0.83]) and fixed a real navigation bug (``hold_anchor`` left set
after manipulation silently overrode every subsequent ``NavigateTo``
command), but surfaced three more issues, fixed here in round 2:

1. ``tray_bounds()`` via ``UsdGeom.BBoxCache`` returned an IDENTICAL,
   spawn-pose-stale bounding box across all 4 trials regardless of the
   tray's live PhysX pose. Overhang is now computed directly from the live
   ``RigidPrim`` tray-center y plus the Step 0 measured static half-extent
   (``north_overhang_m()``), never from ``UsdGeom.BBoxCache``.
2. Single-stroke coupling between the commanded arm drag and the actual
   tray displacement was only ~28-47% (slipping, not dragging). Up to
   ``MAX_PUSH_STROKES`` press-drag strokes now run in sequence, each one
   re-reading the live tray pose, re-aligning the base if the contact
   point drifted, and stopping early once the overhang/slide gate is met.
3. The north-side edge-pinch stance ``(STANCE[0], -0.75)`` was inherited,
   unvalidated legacy code that over-reached the tray by ~1.1-1.2 m once
   trials finally reached it. The north stance is now derived from the
   live post-slide tray pose (mirroring ``TRAY_STANCE``'s fix pattern),
   with the robot driving around the island (never through it) to a point
   dead ahead of the tray's north edge, then rotating to face south.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO_ROOT / "scripts" / "scenes"
COMMON_DIR = REPO_ROOT / "scripts" / "common"
EVALUATION_DIR = REPO_ROOT / "scripts" / "evaluation" / "task3"
for path in (SCENES_DIR, COMMON_DIR, EVALUATION_DIR, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from grading import classify_table_area  # noqa: E402
from integration_test import resolve_prim_path  # noqa: E402
from run_episode import (  # noqa: E402
    ROBOT_SPAWN_POSITION,
    ROBOT_SPAWN_YAW,
    _fix_single_articulation_root,
    make_headless_robot_usd,
    prepare_rigid_body_view_path,
)
from teleop_targets import _quaternion_from_rpy  # noqa: E402
from verify_grasp_lift import (  # noqa: E402
    CORRIDOR_STOP,
    FACE_WEST_YAW_RAD,
    ROTATE_SPOT,
    STANCE,
)

# Pure-math/constant helpers: no Isaac dependency, safe to import at module
# scope (also used by _run_push_stroke()/_run_edge_pinch() below, which stay
# module-level so their branching does not count toward _run()'s cyclomatic
# complexity).
from task3_autonomy.arms import (  # noqa: E402
    GRIPPER_CLOSED_RAD,
    GRIPPER_OPEN_RAD,
    linear_ramp_target,
    synchronized_drag_targets,
)
from task3_autonomy.navigation import route_via_door  # noqa: E402

TRAY_NAME = "simple_tray"
NORTH_COUNTER_EDGE_Y = -1.22
# Dining/kitchen partition south face, from the room-geometry comment in
# task3_autonomy/navigation.py ("partition runs along y in [0.10, 0.34]").
# The open "kitchen lane" the door-crossing route already relies on
# (TASK3_KITCHEN_LANE_Y = -0.37) sits strictly between this and
# NORTH_COUNTER_EDGE_Y -- any north-side stance must too.
KITCHEN_PARTITION_SOUTH_FACE_Y = 0.10
DINING_TARGET = (-2.85, 1.90)

# Same depth as the proven cup grasp (CUP_GRASP_XY = tray/cup center + 0.10 m
# in x from the proven west-facing stance); dead ahead from TRAY_STANCE.
CONTACT_X_OFFSET_M = 0.10
PREGRASP_EE_Z = 1.05
# Round 1 trials measured where a CLOSED fist actually stalls on the tray
# top: contact_measured_ee_z ~= 0.852-0.854 m, not the ~0.766-0.79 m implied
# by the OPEN-gripper cup-grasp fingertip offset. 0.80 m demanded a ~5 cm
# press-through that broke IK during lateral drag (fix1); 0.83 m was
# IK-safe but weak coupling (fix2, +0.072 m); 0.815 m was IK-safe with
# better coupling (fix3/fix4, +0.123 m) -- the best point found so far.
DESCEND_EE_Z = 0.815
CONTACT_STALL_EPS_M = 0.01
CONTACT_STALL_SECONDS = 0.3
SLIDE_MOVED_Y_GATE_M = 0.20
SLIDE_OVERHANG_GATE_M = 0.05

# Round 2: measured Step 0 tray bbox is 0.336644 x 0.436315 x 0.013141 m;
# half of the y (north-south) extent locates the tray's own north edge from
# its live PhysX center pose.
TRAY_HALF_EXTENT_Y_M = 0.436315 / 2.0

# Round 2: multi-stroke drag. Single-stroke coupling measured only 28-47%
# (fix2/fix3), so repeat the press-drag cycle, re-reading the live tray
# pose each time, until the slide gate is met or the stroke budget runs out.
MAX_PUSH_STROKES = 3
STROKE_REALIGN_DRIFT_M = 0.08
STROKE_STOP_MOVED_Y_M = 0.22

# Round 2: tray-relative north-side pinch stance (mirrors TRAY_STANCE's fix
# pattern). Standoff stays inside the proven ~0.83 m dead-ahead envelope;
# small margin under 0.86 m.
NORTH_PINCH_X_OFFSET_M = 0.0
NORTH_PINCH_STANDOFF_M = 0.8
FACE_SOUTH_YAW_RAD = -math.pi / 2.0
# Keep the stance comfortably inside the open lane, not flush against
# either the island or the partition.
SAFE_LANE_MARGIN_M = 0.10

# Round 3: the round-2 z-offset tuning (r2t2 +0.014->0.0, r2t3 0.0, r2t4
# -0.03) never fixed edge_close -- the wrist stalled at nearly the SAME
# measured height (0.813, 0.820, 0.826 m) across a 4.4 cm range of
# commanded targets, and the gripper always closed to ~0 rad (nothing
# caught). That is not a targeting problem; it is the closing AXIS.
# Verified with the repo's own quaternion math (_rotate_vector), not
# armchair rpy algebra: at top_down = rpy(pi,0,0) the fingers close along
# world Y (matches the empirical cup-grasp evidence, "south finger pushed
# cup +Y"). The round-1/2 edge_y = rpy(pi, pi/2, 0) PITCHES about Y --
# which is already the closing axis, so pitching about it changes nothing;
# _rotate_vector confirms edge_y's closing axis is STILL world Y
# (horizontal), identical to top_down's. A pure ROLL of +pi/2 instead
# (no pitch, no yaw) rotates local Y to world Z (vertical -- correct for
# straddling a horizontal 13 mm lip) and rotates local Z (the approach
# axis) to world -Y (south -- correct for reaching INTO the tray from the
# north stance). See scripts/tests/test_probe_tray_slide.py for the
# regression test encoding this verification.
EDGE_PINCH_ROLL_RAD = math.pi / 2.0
# Aim slightly south of the tray's own measured edge (into solid material)
# rather than exactly on the boundary, so the straddle has real material
# between the jaws rather than landing on a razor's-edge coordinate.
EDGE_PINCH_LIP_Y_MARGIN_M = 0.01
# Pregrasp-out: stage north of the lip with fingers open before reaching
# in horizontally, rather than descending vertically onto/near the tray.
EDGE_PINCH_OUT_STANDOFF_M = 0.15
# "Plausible" partial closure band: 0.9 rad <-> ~34 mm aperture, so a
# 13 mm lip should stall the joint partway, not close to ~0 (empty) or
# stay near fully open (barely touched).
EDGE_PINCH_PLAUSIBLE_MIN_RAD = 0.15
EDGE_PINCH_PLAUSIBLE_MAX_RAD = 0.55


def north_overhang_m(
    tray_y: float,
    *,
    half_extent_y: float = TRAY_HALF_EXTENT_Y_M,
    counter_edge_y: float = NORTH_COUNTER_EDGE_Y,
) -> float:
    """North overhang from the live tray-center y and its static half-extent.

    Replaces the ``UsdGeom.BBoxCache`` path: across all 4 round-1 trials,
    ``ComputeWorldBound`` returned the IDENTICAL spawn-pose bounding box
    regardless of the tray's actual (correctly live-read) PhysX pose, so the
    overhang gate was never trustworthy. This computes overhang directly
    from the live ``RigidPrim`` tray-center y (``tray_y``) plus the Step 0
    measured half-extent, matching the tray's actual footprint.
    """
    return (tray_y + half_extent_y) - counter_edge_y


def north_pinch_target(
    tray_x: float,
    tray_y: float,
    *,
    x_offset: float = NORTH_PINCH_X_OFFSET_M,
    half_extent_y: float = TRAY_HALF_EXTENT_Y_M,
) -> tuple[float, float]:
    """World (x, y) of the tray's own north edge -- the point to pinch."""
    return tray_x + x_offset, tray_y + half_extent_y


def north_pinch_stance(
    pinch_target: tuple[float, float],
    *,
    standoff_m: float = NORTH_PINCH_STANDOFF_M,
) -> tuple[float, float]:
    """Base (x, y) standing ``standoff_m`` north of ``pinch_target``.

    Same x as the pinch target so it is dead ahead once the base faces
    ``FACE_SOUTH_YAW_RAD`` -- the same "put the target dead ahead" pattern
    used for the south-side ``TRAY_STANCE``.
    """
    return pinch_target[0], pinch_target[1] + standoff_m


def stance_in_safe_lane(
    stance_y: float,
    *,
    lane_min_y: float = NORTH_COUNTER_EDGE_Y,
    lane_max_y: float = KITCHEN_PARTITION_SOUTH_FACE_Y,
    margin_m: float = SAFE_LANE_MARGIN_M,
) -> bool:
    """Whether ``stance_y`` sits inside the open kitchen lane.

    The lane is bounded by the island's north face (``NORTH_COUNTER_EDGE_Y``)
    and the dining/kitchen partition's south face
    (``KITCHEN_PARTITION_SOUTH_FACE_Y``) -- see the room-geometry comment in
    ``task3_autonomy/navigation.py``. A stance outside this band would put
    the base over the island or into the partition wall.
    """
    return (lane_min_y + margin_m) < stance_y < (lane_max_y - margin_m)


def stroke_needs_realign(
    contact_y: float,
    base_y: float,
    *,
    threshold_m: float = STROKE_REALIGN_DRIFT_M,
) -> bool:
    """Whether the base has drifted far enough from the contact point to
    need a small re-align drive before the next stroke."""
    return abs(contact_y - base_y) > threshold_m


def _reach_failure_detail(
    arms: Any,
    side: str,
    position: tuple[float, float, float],
    quat: tuple[float, ...],
) -> dict[str, Any]:
    """Measured EE pose, position/orientation error, and IK flag.

    Diagnostic-only IK solve: ``arms.command()`` here does not call
    ``step()``, so it does not advance physics or actuate anything -- it
    only reports whether Lula could converge on the failed target from the
    current configuration.
    """
    ik_result = arms.command()
    ik_succeeded = (
        ik_result.left_succeeded
        if side == "left"
        else ik_result.right_succeeded
    )
    ee_position, ee_quat = arms.ee_world_poses()[0 if side == "left" else 1]
    position_error, orientation_error = arms.pose_error(side, position, quat)
    return {
        "target": [round(v, 4) for v in position],
        "measured_ee_position": [round(v, 6) for v in ee_position],
        "measured_ee_quat": [round(v, 6) for v in ee_quat],
        "position_error_m": round(position_error, 6),
        "orientation_error_rad": round(orientation_error, 6),
        "ik_succeeded": bool(ik_succeeded),
    }


def _ramp_vertical_ee(
    arms: Any,
    step: Any,
    tray_pose_fn: Any,
    side: str,
    xy: tuple[float, float],
    quat: tuple[float, ...],
    start_z: float,
    end_z: float,
    seconds: float,
    dt: float,
    *,
    detect_contact: bool = False,
    stall_eps_m: float = CONTACT_STALL_EPS_M,
    stall_seconds: float = CONTACT_STALL_SECONDS,
) -> dict[str, Any]:
    """Time-bounded linear EE-z ramp, reissuing targets every tick.

    This intentionally does not use ``reach()``: descending into contact
    must never converge (the position PD is meant to keep pressing), and
    ``reach()`` would report a spurious timeout failure. When
    ``detect_contact`` is set, log the first tick where the measured EE z
    stalls above the (still-descending) commanded z for more than
    ``stall_seconds`` -- evidence the fingers are on the tray top.
    """
    ramp_ticks = max(1, math.ceil(seconds / dt))
    stall_start_tick: int | None = None
    contact_tick: int | None = None
    contact_measured_z: float | None = None
    contact_tray_pose: tuple[float, float, float] | None = None
    for tick_index in range(ramp_ticks):
        commanded_z = linear_ramp_target(
            start_z, end_z, tick_index + 1, ramp_ticks
        )
        arms.set_arm_target(side, (xy[0], xy[1], commanded_z), quat)
        arms.command()
        step()
        if not detect_contact:
            continue
        measured_z = arms.ee_world_poses()[0 if side == "left" else 1][0][2]
        if measured_z - commanded_z <= stall_eps_m:
            stall_start_tick = None
            continue
        if stall_start_tick is None:
            stall_start_tick = tick_index
        elif (
            contact_tick is None
            and (tick_index - stall_start_tick) * dt >= stall_seconds
        ):
            contact_tick = tick_index
            contact_measured_z = measured_z
            contact_tray_pose = tray_pose_fn()
    final_measured_z = arms.ee_world_poses()[0 if side == "left" else 1][0][2]
    return {
        "final_commanded_ee_z": round(end_z, 6),
        "final_measured_ee_z": round(final_measured_z, 6),
        "contact_detected": contact_tick is not None,
        "contact_tick": contact_tick,
        "contact_measured_ee_z": (
            round(contact_measured_z, 6)
            if contact_measured_z is not None
            else None
        ),
        "contact_tray_pose": (
            [round(v, 6) for v in contact_tray_pose]
            if contact_tray_pose is not None
            else None
        ),
    }


def _measure_fingertip_midpoint(
    robot: Any, side: str
) -> tuple[float, float, float] | None:
    """Live world-frame midpoint between the two named fingertip bodies.

    Reuses the exact body names the Step 0 probe measured
    (``scripts/task3/probe_stage0.py``): ``left_left_2_link``/
    ``left_right_2_link`` for the left arm, ``right_left_2_link``/
    ``right_iight_2_link`` (USD typo preserved) for the right arm. Reads
    directly off the articulation's own body poses (``robot.data.body_pos_w``),
    the same data source Step 0 used -- no extra RigidPrim view needed.
    Returns ``None`` if the expected bodies are not found (diagnosable
    rather than a silent wrong answer).
    """
    if side not in ("left", "right"):
        raise ValueError("side must be 'left' or 'right'")
    names = (
        ("left_left_2_link", "left_right_2_link")
        if side == "left"
        else ("right_left_2_link", "right_iight_2_link")
    )
    body_names = list(robot.body_names)
    if not all(name in body_names for name in names):
        return None
    positions = robot.data.body_pos_w[0]
    a = positions[body_names.index(names[0])]
    b = positions[body_names.index(names[1])]
    return (
        float((a[0] + b[0]) / 2.0),
        float((a[1] + b[1]) / 2.0),
        float((a[2] + b[2]) / 2.0),
    )


def _ramp_horizontal_ee(
    arms: Any,
    step: Any,
    tray_pose_fn: Any,
    side: str,
    xz: tuple[float, float],
    quat: tuple[float, ...],
    start_y: float,
    end_y: float,
    seconds: float,
    dt: float,
    *,
    detect_contact: bool = False,
    stall_eps_m: float = CONTACT_STALL_EPS_M,
    stall_seconds: float = CONTACT_STALL_SECONDS,
) -> dict[str, Any]:
    """Time-bounded linear EE-y ramp (x, z held fixed), reissuing targets
    every tick -- the reach-in sub-phase for the corrected (vertical
    closing-axis) edge pinch: the wrist approaches the lip HORIZONTALLY
    from the north rather than descending onto it, so only y has to
    converge while x and z (calibrated from the measured fingertip
    offset) stay fixed. Mirrors ``_ramp_vertical_ee()``: never uses
    ``reach()``, since driving into contact must not "fail" a timeout,
    and detects a y-stall (fingers caught on the lip while still
    commanded further south) the same way the vertical ramp detects a
    z-stall.
    """
    ramp_ticks = max(1, math.ceil(seconds / dt))
    stall_start_tick: int | None = None
    contact_tick: int | None = None
    contact_measured_y: float | None = None
    contact_tray_pose: tuple[float, float, float] | None = None
    for tick_index in range(ramp_ticks):
        commanded_y = linear_ramp_target(
            start_y, end_y, tick_index + 1, ramp_ticks
        )
        arms.set_arm_target(side, (xz[0], commanded_y, xz[1]), quat)
        arms.command()
        step()
        if not detect_contact:
            continue
        measured_y = arms.ee_world_poses()[0 if side == "left" else 1][0][1]
        # Moving south (y decreasing): a stall shows up as the measured y
        # staying north of (greater than) the still-decreasing commanded y.
        if measured_y - commanded_y <= stall_eps_m:
            stall_start_tick = None
            continue
        if stall_start_tick is None:
            stall_start_tick = tick_index
        elif (
            contact_tick is None
            and (tick_index - stall_start_tick) * dt >= stall_seconds
        ):
            contact_tick = tick_index
            contact_measured_y = measured_y
            contact_tray_pose = tray_pose_fn()
    final_measured_y = arms.ee_world_poses()[0 if side == "left" else 1][0][1]
    return {
        "final_commanded_ee_y": round(end_y, 6),
        "final_measured_ee_y": round(final_measured_y, 6),
        "contact_detected": contact_tick is not None,
        "contact_tick": contact_tick,
        "contact_measured_ee_y": (
            round(contact_measured_y, 6)
            if contact_measured_y is not None
            else None
        ),
        "contact_tray_pose": (
            [round(v, 6) for v in contact_tray_pose]
            if contact_tray_pose is not None
            else None
        ),
    }


def _run_edge_pinch(
    *,
    arms: Any,
    robot: Any,
    adapter: Any,
    reach: Any,
    ramp_vertical: Any,
    ramp_horizontal: Any,
    drive: Any,
    sim_tick: Any,
    log: Any,
    log_reach_failure: Any,
    tray_pose_fn: Any,
    hold_anchor_box: dict[str, tuple[float, float] | None],
    pinch_target_xy: tuple[float, float],
    tray_z: float,
    dt: float,
    args: argparse.Namespace,
) -> tuple[bool, str | None, dict[str, Any]]:
    """Corrected-orientation single-arm edge pinch; module-level so its
    own branching does not count toward ``_run()``'s cyclomatic
    complexity.

    Sequence: pregrasp-OUT (fingers open, closing axis vertical via
    ``EDGE_PINCH_ROLL_RAD``, held safely north of the lip) -> measure the
    live fingertip midpoint there to calibrate the wrist-to-fingertip
    offset for THIS orientation (never assume/guess it) -> reach-IN
    horizontally to the calibrated wrist target -> log the fingertip
    midpoint again immediately before closing (so a miss is diagnosable)
    -> ``grasp()`` -> ``lift()`` if holding. Returns
    ``(passed, failed_phase, info)``.

    r3t2 measured the base drifting substantially (yaw off south-facing by
    ~0.46 rad, x by 0.25 m) during the pregrasp_out reach -- the stale
    ``hold_anchor`` inherited from "at_north_stance" was not strong enough
    to hold against that reach's reaction torque, and the subsequent
    reach-in then had to fight that drift AND its own reaction torque
    against the SAME stale anchor, leaving the preclose fingertip midpoint
    8-13 cm off the lip target on every axis. Re-anchoring to wherever the
    base actually is after each of the two big reaches (mirroring the
    push phase's per-stroke re-anchor pattern) gives each subsequent step
    a stable, un-contested reference instead of a stale one.
    """
    edge_pinch_quat = _quaternion_from_rpy(EDGE_PINCH_ROLL_RAD, 0.0, 0.0)
    lip_xy = (
        pinch_target_xy[0],
        pinch_target_xy[1] - EDGE_PINCH_LIP_Y_MARGIN_M,
    )
    pregrasp_out = (
        lip_xy[0],
        lip_xy[1] + EDGE_PINCH_OUT_STANDOFF_M,
        PREGRASP_EE_Z,
    )
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    if not reach("right", pregrasp_out, edge_pinch_quat, 8.0):
        log_reach_failure(
            "edge_pregrasp_out", "right", pregrasp_out, edge_pinch_quat
        )
        return False, "edge_pregrasp_out", {}
    pose = adapter.pose()
    hold_anchor_box["value"] = (pose.x, pose.y)

    fingertip_mid = _measure_fingertip_midpoint(robot, "right")
    log(
        "edge_pregrasp_out",
        ok=True,
        target=list(pregrasp_out),
        fingertip_midpoint=(
            [round(v, 6) for v in fingertip_mid] if fingertip_mid else None
        ),
        base=[round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
    )
    if fingertip_mid is None:
        return False, "edge_fingertip_measurement", {}

    offset = tuple(fingertip_mid[i] - pregrasp_out[i] for i in range(3))
    lip_target = (lip_xy[0], lip_xy[1], tray_z)
    wrist_target = tuple(lip_target[i] - offset[i] for i in range(3))
    log(
        "edge_calibration",
        ok=True,
        wrist_to_fingertip_offset=[round(v, 6) for v in offset],
        lip_target=[round(v, 6) for v in lip_target],
        wrist_target=[round(v, 6) for v in wrist_target],
    )

    reach_in_info = ramp_horizontal(
        "right",
        (wrist_target[0], wrist_target[2]),
        edge_pinch_quat,
        pregrasp_out[1],
        wrist_target[1],
        args.reach_in_seconds,
        detect_contact=True,
    )
    pose = adapter.pose()
    hold_anchor_box["value"] = (pose.x, pose.y)
    log(
        "edge_reach_in",
        ok=True,
        **reach_in_info,
        base=[round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
    )

    fingertip_mid_preclose = _measure_fingertip_midpoint(robot, "right")
    ee_pose_preclose = arms.ee_world_poses()[1][0]
    log(
        "edge_preclose_fingertips",
        ok=True,
        fingertip_midpoint=(
            [round(v, 6) for v in fingertip_mid_preclose]
            if fingertip_mid_preclose
            else None
        ),
        measured_ee_position=[round(float(v), 6) for v in ee_pose_preclose],
        lip_target=[round(v, 6) for v in lip_target],
    )

    # Round 4: Round 3 reached the correct XY but the hand stopped with the
    # fingertip midpoint 5.94 cm above the lip. Use that measured error as a
    # bounded, physics-driven vertical settling stroke before closing. The
    # target is based on the actual current EE pose, not a guessed world Z;
    # contact/stall logging remains mandatory.
    if fingertip_mid_preclose is None:
        return False, "edge_fingertip_measurement", {}
    fingertip_z_error = fingertip_mid_preclose[2] - lip_target[2]
    lower_m = min(max(fingertip_z_error, 0.0), args.edge_lower_max_m)
    lower_info = ramp_vertical(
        "right",
        (float(ee_pose_preclose[0]), float(ee_pose_preclose[1])),
        edge_pinch_quat,
        float(ee_pose_preclose[2]),
        float(ee_pose_preclose[2]) - lower_m,
        args.edge_lower_seconds,
        detect_contact=True,
    )
    fingertip_mid_after_lower = _measure_fingertip_midpoint(robot, "right")
    log(
        "edge_lower_settle",
        ok=True,
        requested_lower_m=round(lower_m, 6),
        fingertip_z_error=round(fingertip_z_error, 6),
        fingertip_midpoint=(
            [round(v, 6) for v in fingertip_mid_after_lower]
            if fingertip_mid_after_lower
            else None
        ),
        **lower_info,
    )

    holding = arms.grasp("right", step=sim_tick, dt=dt, settle_seconds=1.5)
    gripper_rad = arms.gripper_position("right")
    pinch_plausible = (
        EDGE_PINCH_PLAUSIBLE_MIN_RAD
        <= gripper_rad
        <= EDGE_PINCH_PLAUSIBLE_MAX_RAD
    )
    log(
        "edge_close",
        ok=holding,
        gripper_rad=round(gripper_rad, 6),
        pinch_plausible=pinch_plausible,
    )
    lift_ok = False
    lift_m = 0.0
    if holding:
        before_lift_z = tray_pose_fn()[2]
        arms_lift_ok = arms.lift(
            "right",
            0.10,
            step=sim_tick,
            dt=dt,
            timeout_s=5.0,
            position_tolerance_m=0.04,
            spine_assist_m=0.08,
        )
        lift_m = tray_pose_fn()[2] - before_lift_z
        # The generic lift predicate also requires the wrist to converge to
        # its full +10 cm Cartesian target. A real tray can be physically
        # lifted and retained even when the cantilevered hand stalls short of
        # that ambitious target, so the object-space measurement is the legal
        # carry criterion here.
        lift_ok = lift_m >= 0.02
        log(
            "edge_lift",
            ok=lift_ok,
            controller_ok=arms_lift_ok,
            lift_m=round(lift_m, 6),
        )

    carry_ok = False
    dining_pose = tray_pose_fn()
    if holding and lift_ok:
        hold_anchor_box["value"] = None
        start_base = adapter.pose()
        for waypoint_index, waypoint in enumerate(
            route_via_door((start_base.x, start_base.y), DINING_TARGET)
        ):
            if waypoint == (start_base.x, start_base.y):
                continue
            waypoint_ok = drive(waypoint, 0.25, 35.0)
            dining_pose = tray_pose_fn()
            log(
                "carry_waypoint",
                ok=waypoint_ok,
                waypoint_index=waypoint_index,
                target=list(waypoint),
                tray_pose=[round(v, 6) for v in dining_pose],
            )
            if not waypoint_ok:
                break
        dining_pose = tray_pose_fn()
        carry_ok = (
            waypoint_ok and classify_table_area(dining_pose[:2]) == "dining"
        )
        log(
            "carry_dining",
            ok=carry_ok,
            tray_pose=[round(v, 6) for v in dining_pose],
            table_area=classify_table_area(dining_pose[:2]),
        )
        if carry_ok:
            release_ok = arms.release(
                "right", step=sim_tick, dt=dt, timeout_s=1.5
            )
            log("carry_release", ok=release_ok)
            carry_ok = release_ok and carry_ok

    passed = bool(holding and lift_ok and pinch_plausible and carry_ok)
    return (
        passed,
        None if passed else ("carry" if holding and lift_ok else "edge_pinch"),
        {
            "gripper_rad": round(gripper_rad, 6),
            "pinch_plausible": pinch_plausible,
            "lift_m": round(lift_m, 6),
            "carry_ok": carry_ok,
            "dining_pose": [round(v, 6) for v in dining_pose],
        },
    )


def _run_push_stroke(
    stroke_index: int,
    *,
    arms: Any,
    adapter: Any,
    reach: Any,
    drive: Any,
    ramp_vertical: Any,
    sim_tick: Any,
    log: Any,
    log_reach_failure: Any,
    tray_pose_fn: Any,
    hold_anchor_box: dict[str, tuple[float, float] | None],
    start_y: float,
    top_down: tuple[float, ...],
    dt: float,
    args: argparse.Namespace,
) -> tuple[bool, str | None]:
    """One press-drag-raise stroke; module-level so its own branching does
    not count toward ``_run()``'s cyclomatic complexity.

    Re-reads the live tray pose every stroke (never the stale start pose)
    so each stroke's contact point tracks wherever the tray actually ended
    up, and re-aligns the base first if that point drifted too far from
    the base's current position. Returns ``(gate_met, failed_phase)``.

    ``hold_anchor_box`` is a one-entry ``{"value": ...}`` dict shared with
    ``sim_tick()`` back in ``_run()`` -- a plain parameter would only
    rebind this function's own local copy, leaving ``sim_tick()`` (which
    reads ``_run()``'s variable directly) still driving toward the STALE
    anchor. That exact class of bug is what broke navigation in round-1
    trials 1-3; the shared mutable box is how both scopes see every update
    immediately, including the mid-function anchor-clear ahead of the
    realign drive below.
    """
    stroke_prefix = f"stroke{stroke_index + 1}"
    live_tray = tray_pose_fn()
    stroke_contact_x = live_tray[0] + CONTACT_X_OFFSET_M
    stroke_contact_y = live_tray[1]
    base_pose = adapter.pose()
    if stroke_needs_realign(stroke_contact_y, base_pose.y):
        realign_target = (STANCE[0], stroke_contact_y)
        hold_anchor_box["value"] = None
        realign_ok = drive(realign_target, 0.2, 10.0)
        pose = adapter.pose()
        hold_anchor_box["value"] = (pose.x, pose.y)
        log(
            f"{stroke_prefix}_realign",
            ok=realign_ok,
            target=list(realign_target),
            drift_m=round(abs(stroke_contact_y - base_pose.y), 6),
        )
        if not realign_ok:
            return False, f"{stroke_prefix}_realign"

    pregrasp_above = (stroke_contact_x, stroke_contact_y, PREGRASP_EE_Z)
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    if not reach("right", pregrasp_above, top_down, 8.0):
        log_reach_failure(
            f"{stroke_prefix}_pregrasp_above",
            "right",
            pregrasp_above,
            top_down,
        )
        return False, f"{stroke_prefix}_pregrasp_above"
    log(
        f"{stroke_prefix}_pregrasp_above", ok=True, target=list(pregrasp_above)
    )

    arms.set_gripper("right", GRIPPER_CLOSED_RAD)
    for _ in range(math.ceil(1.0 / dt)):
        arms.command()
        sim_tick()
    closed = arms.gripper_position("right")
    log(f"{stroke_prefix}_close", ok=True, gripper_rad=round(closed, 6))

    descend_info = ramp_vertical(
        "right",
        (stroke_contact_x, stroke_contact_y),
        top_down,
        PREGRASP_EE_Z,
        args.descend_ee_z,
        args.descend_seconds,
        detect_contact=True,
    )
    log(f"{stroke_prefix}_descend", ok=True, **descend_info)

    drag_start_anchor = hold_anchor_box["value"]
    drag_ramp_ticks = max(1, math.ceil(args.drag_seconds / dt))
    for tick_index in range(drag_ramp_ticks):
        arm_y, anchor_y = synchronized_drag_targets(
            stroke_contact_y,
            drag_start_anchor[1],
            args.push_distance,
            tick_index + 1,
            drag_ramp_ticks,
        )
        arms.set_arm_target(
            "right", (stroke_contact_x, arm_y, args.descend_ee_z), top_down
        )
        arms.command()
        hold_anchor_box["value"] = (drag_start_anchor[0], anchor_y)
        sim_tick()
    log(
        f"{stroke_prefix}_drag",
        ok=True,
        target_arm_y=round(stroke_contact_y + args.push_distance, 6),
        target_anchor=[
            round(drag_start_anchor[0], 6),
            round(drag_start_anchor[1] + args.push_distance, 6),
        ],
    )

    raise_info = ramp_vertical(
        "right",
        (stroke_contact_x, stroke_contact_y + args.push_distance),
        top_down,
        args.descend_ee_z,
        PREGRASP_EE_Z,
        args.raise_seconds,
    )
    arms.set_gripper("right", GRIPPER_OPEN_RAD)
    arms.command()
    sim_tick()
    pose = adapter.pose()
    hold_anchor_box["value"] = (pose.x, pose.y)
    log(f"{stroke_prefix}_raise", ok=True, **raise_info)

    after_stroke = tray_pose_fn()
    moved_y = after_stroke[1] - start_y
    overhang_north = north_overhang_m(after_stroke[1])
    stroke_gate_met = (
        moved_y >= STROKE_STOP_MOVED_Y_M
        or overhang_north >= SLIDE_OVERHANG_GATE_M
    )
    log(
        f"{stroke_prefix}_result",
        ok=stroke_gate_met,
        moved_y_m=round(moved_y, 6),
        north_overhang_m=round(overhang_north, 6),
        stroke_moved_y_m=round(after_stroke[1] - live_tray[1], 6),
    )
    return stroke_gate_met, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--head-placement", choices=("a", "b", "c"), default="a"
    )
    parser.add_argument("--push-distance", type=float, default=0.26)
    parser.add_argument("--descend-seconds", type=float, default=2.0)
    parser.add_argument("--drag-seconds", type=float, default=5.0)
    parser.add_argument("--raise-seconds", type=float, default=2.0)
    parser.add_argument("--descend-ee-z", type=float, default=DESCEND_EE_Z)
    parser.add_argument("--reach-in-seconds", type=float, default=2.0)
    parser.add_argument("--edge-lower-seconds", type=float, default=1.5)
    parser.add_argument("--edge-lower-max-m", type=float, default=0.08)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_stage1_tray_slide",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from isaaclab.app import AppLauncher

    simulation_app = AppLauncher(
        {"headless": True, "enable_cameras": False}
    ).app
    started = time.time()
    result: dict[str, Any]
    try:
        result = _run(args, simulation_app)
        result["wall_time_seconds"] = round(time.time() - started, 3)
        output = args.output_dir / "result.json"
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(
            "TRAY_SLIDE_RESULT " + json.dumps(result, sort_keys=True),
            flush=True,
        )
        # Isaac Kit shutdown is known to hang after result persistence. The
        # result is durable, so exit without starting another process.
        os._exit(0 if result["passed"] else 1)
    except BaseException:
        output = args.output_dir / "crash_traceback.txt"
        import traceback

        output.write_text(traceback.format_exc())
        raise
    finally:
        simulation_app.close()


def _run(args: argparse.Namespace, simulation_app: Any) -> dict[str, Any]:
    from scene_robot_room_keyboard import (
        configure_keyboard_control_stage,
        configure_robot_room_stage,
        disable_robot_external_wrenches,
        make_control_scene_cfg,
        reset_robot_to_default_state,
        yaw_to_quat,
    )

    from isaacsim.core.prims import RigidPrim

    import isaaclab.sim as sim_utils
    from isaaclab.scene import InteractiveScene
    from isaaclab.sim import SimulationContext

    from task3_autonomy.arms import DualArmController
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
    tray_root_path = resolve_prim_path(sim.stage, TRAY_NAME)
    tray_view_path = prepare_rigid_body_view_path(sim.stage, tray_root_path)
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
    tray_view = RigidPrim(
        prim_paths_expr=tray_view_path, name="task3_tray_slide"
    )
    initialize = getattr(tray_view, "initialize", None)
    if callable(initialize):
        initialize()

    def tray_pose() -> tuple[float, float, float]:
        positions, _ = tray_view.get_world_poses()
        return tuple(float(value) for value in positions.tolist()[0])

    # Local tray stance: put the contact point dead ahead so the reach stays
    # inside the proven ~0.83 m envelope (CUP_GRASP_XY dead-ahead distance
    # from STANCE), instead of the ~1.0 m diagonal reach that failed trial 1.
    initial_tray_pose = tray_pose()
    tray_stance = (STANCE[0], initial_tray_pose[1])

    adapter = TmrBaseAdapter(robot, num_envs=1, device="cuda:0")
    arms = DualArmController(robot, simulation_app)
    phases: list[dict[str, Any]] = []
    tick = 0
    # A one-entry box, not a plain variable: _run_push_stroke() (module-level,
    # so its own branching doesn't count toward this function's cyclomatic
    # complexity) needs to mutate the SAME anchor sim_tick() reads, not a
    # disconnected local copy -- see _run_push_stroke()'s docstring.
    hold_anchor_box: dict[str, tuple[float, float] | None] = {"value": None}

    def sim_tick() -> None:
        nonlocal tick
        disable_robot_external_wrenches(robot)
        if hold_anchor_box["value"] is not None:
            vx, vy = base_twist_toward(
                adapter.pose(),
                hold_anchor_box["value"],
                max_linear_mps=0.12,
                position_kp=2.0,
            )
            adapter.apply_twist(vx, vy, hold_heading=True)
        scene.write_data_to_sim()
        sim.step()
        scene.update(sim.cfg.dt)
        tick += 1

    def log(name: str, **detail: Any) -> None:
        base = adapter.pose()
        phase = {
            "phase": name,
            "tick": tick,
            "tray": [round(v, 6) for v in tray_pose()],
            "base": [round(base.x, 6), round(base.y, 6), round(base.yaw, 6)],
            **detail,
        }
        phases.append(phase)
        print(
            "TRAY_SLIDE_DBG " + json.dumps(phase, sort_keys=True), flush=True
        )

    def drive(
        target: tuple[float, float],
        speed: float,
        budget: float,
        accept_tolerance: float = 0.03,
    ) -> bool:
        skill = NavigateTo(target, max_linear_mps=speed)
        for _ in range(math.ceil(budget / sim.cfg.dt)):
            vx, vy, done = skill.compute(adapter.pose())
            if done:
                adapter.apply_twist(0.0, 0.0)
                sim_tick()
                return True
            adapter.apply_twist(vx, vy)
            sim_tick()
        adapter.apply_twist(0.0, 0.0)
        sim_tick()
        pose = adapter.pose()
        residual = math.hypot(pose.x - target[0], pose.y - target[1])
        return residual <= accept_tolerance

    def rotate(target: float, budget: float) -> bool:
        skill = RotateTo(target)
        for _ in range(math.ceil(budget / sim.cfg.dt)):
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

    def reach(
        side: str,
        position: tuple[float, float, float],
        quat: tuple[float, ...],
        budget: float,
    ) -> bool:
        return arms.reach(
            side,
            position,
            quat,
            step=sim_tick,
            dt=sim.cfg.dt,
            timeout_s=budget,
            position_tolerance_m=0.025,
        )

    def log_reach_failure(
        name: str,
        side: str,
        position: tuple[float, float, float],
        quat: tuple[float, ...],
        **detail: Any,
    ) -> None:
        log(
            name,
            ok=False,
            **_reach_failure_detail(arms, side, position, quat),
            **detail,
        )

    def ramp_vertical(
        side: str,
        xy: tuple[float, float],
        quat: tuple[float, ...],
        start_z: float,
        end_z: float,
        seconds: float,
        *,
        detect_contact: bool = False,
    ) -> dict[str, Any]:
        return _ramp_vertical_ee(
            arms,
            sim_tick,
            tray_pose,
            side,
            xy,
            quat,
            start_z,
            end_z,
            seconds,
            sim.cfg.dt,
            detect_contact=detect_contact,
        )

    def ramp_horizontal(
        side: str,
        xz: tuple[float, float],
        quat: tuple[float, ...],
        start_y: float,
        end_y: float,
        seconds: float,
        *,
        detect_contact: bool = False,
    ) -> dict[str, Any]:
        return _ramp_horizontal_ee(
            arms,
            sim_tick,
            tray_pose,
            side,
            xz,
            quat,
            start_y,
            end_y,
            seconds,
            sim.cfg.dt,
            detect_contact=detect_contact,
        )

    # Stabilize and tuck exactly as the proven cup pipeline does.
    spine_ok = arms.move_spine(
        0.45,
        step=sim_tick,
        dt=sim.cfg.dt,
        timeout_s=6.0,
        tolerance_m=0.03,
    )
    measured_spine = arms.measured_spine_position()
    if not spine_ok:
        log("raise_spine", ok=False, measured_spine=round(measured_spine, 6))
        return _result(
            False, "raise_spine", phases, tray_pose(), tray_pose(), args
        )
    log("raise_spine", ok=True, measured_spine=round(measured_spine, 6))
    ramp_arm_pose(robot, TRANSIT_ARM_POSE, step=sim_tick)
    arms.sync_targets_from_measured()
    corridor_ok = drive(CORRIDOR_STOP, 0.5, 45.0)
    log("navigate_corridor_stop", ok=corridor_ok)
    if not corridor_ok:
        return _result(
            False,
            "navigate_corridor_stop",
            phases,
            tray_pose(),
            tray_pose(),
            args,
        )
    spot_ok = drive(ROTATE_SPOT, 0.4, 35.0, accept_tolerance=0.15)
    log("navigate_rotate_spot", ok=spot_ok)
    if not spot_ok:
        return _result(
            False, "rotate_spot", phases, tray_pose(), tray_pose(), args
        )
    rotate_ok = rotate(FACE_WEST_YAW_RAD, 15.0)
    log("rotate_west", ok=rotate_ok)
    if not rotate_ok:
        return _result(
            False, "rotate_west", phases, tray_pose(), tray_pose(), args
        )
    if not drive(tray_stance, 0.25, 20.0):
        log("navigate_stance", ok=False, target=list(tray_stance))
        return _result(
            False, "navigate_stance", phases, tray_pose(), tray_pose(), args
        )
    pose = adapter.pose()
    hold_anchor_box["value"] = (pose.x, pose.y)
    log(
        "at_stance",
        base=[round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
        tray_stance=list(tray_stance),
    )

    start = tray_pose()
    top_down = _quaternion_from_rpy(math.pi, 0.0, 0.0)

    # Multi-stroke press-and-drag from the top of the tray: pregrasp above
    # the contact point, close the fist (a rigid pusher, never attached to
    # the tray), ramp down onto the tray top, then drag the contact point
    # (and the base under it) north together. This mirrors the proven cup
    # pipeline's pregrasp-above + ramped-descend structure instead of one
    # direct reach. Round 1 measured only ~28-47% coupling per stroke (the
    # fist slips rather than fully dragging the tray), so repeat up to
    # MAX_PUSH_STROKES times, re-reading the live tray pose every time and
    # stopping as soon as the slide gate is met.
    strokes_used = 0
    for stroke_index in range(MAX_PUSH_STROKES):
        strokes_used = stroke_index + 1
        gate_met, failure_phase = _run_push_stroke(
            stroke_index,
            arms=arms,
            adapter=adapter,
            reach=reach,
            drive=drive,
            ramp_vertical=ramp_vertical,
            sim_tick=sim_tick,
            log=log,
            log_reach_failure=log_reach_failure,
            tray_pose_fn=tray_pose,
            hold_anchor_box=hold_anchor_box,
            start_y=start[1],
            top_down=top_down,
            dt=sim.cfg.dt,
            args=args,
        )
        if failure_phase is not None:
            return _result(
                False, failure_phase, phases, start, tray_pose(), args
            )
        if gate_met:
            break

    after_push = tray_pose()
    moved_y = after_push[1] - start[1]
    overhang_north = north_overhang_m(after_push[1])
    slide_ok = (
        moved_y >= SLIDE_MOVED_Y_GATE_M
        or overhang_north >= SLIDE_OVERHANG_GATE_M
    )
    log(
        "push_result",
        ok=slide_ok,
        moved_y_m=round(moved_y, 6),
        north_overhang_m=round(overhang_north, 6),
        strokes_used=strokes_used,
    )

    # Move to a TRAY-RELATIVE north-side stance, then try a true thin-edge
    # pinch. The inherited fixed stance (STANCE[0], -0.75) was unvalidated
    # legacy code (all earlier trials failed upstream of it): once trial 4
    # actually reached it, the edge target was ~1.1-1.2 m away -- well past
    # the proven ~0.83 m envelope, and IK correctly refused to converge.
    # Mirror TRAY_STANCE's fix: derive the pinch target and stance from the
    # LIVE post-slide tray pose so the pinch point is dead ahead.
    tray_now = tray_pose()
    pinch_target_xy = north_pinch_target(tray_now[0], tray_now[1])
    north_stance = north_pinch_stance(pinch_target_xy)
    if not stance_in_safe_lane(north_stance[1]):
        # Do not force a stance the room geometry forbids -- log the
        # measured geometry (island north face NORTH_COUNTER_EDGE_Y,
        # partition south face KITCHEN_PARTITION_SOUTH_FACE_Y, and the
        # computed stance) and report back per the escalation protocol.
        log(
            "north_stance_geometry_blocked",
            ok=False,
            pinch_target=list(pinch_target_xy),
            computed_stance=list(north_stance),
            lane_min_y=NORTH_COUNTER_EDGE_Y,
            lane_max_y=KITCHEN_PARTITION_SOUTH_FACE_Y,
            safe_lane_margin_m=SAFE_LANE_MARGIN_M,
        )
        return _result(
            False,
            "north_stance_geometry_blocked",
            phases,
            start,
            tray_pose(),
            args,
        )
    # Bug fix (round 1 trials 1-3): hold_anchor was left set from the
    # manipulation phase, so sim_tick's own anchor-hold twist silently
    # overrode every NavigateTo command issued by drive() below -- the base
    # measurably barely moved (~0.01-0.02 m) across a 20 s budget. Clear it
    # before free navigation, then re-anchor once stopped.
    hold_anchor_box["value"] = None
    # Route around the island, never through it: first move north while
    # still east of it at the proven-safe transit x (STANCE[0] = -3.32,
    # matching every prior trial's actual post-push base x), THEN move west
    # along the now-clear lane to the tray-relative stance x.
    transit_point = (STANCE[0], north_stance[1])
    if not drive(transit_point, 0.25, 20.0):
        log("navigate_north_transit", ok=False, target=list(transit_point))
        return _result(
            False, "navigate_north_transit", phases, start, tray_pose(), args
        )
    if not drive(north_stance, 0.25, 20.0):
        log("navigate_north_stance", ok=False, target=list(north_stance))
        return _result(
            False, "navigate_north_stance", phases, start, tray_pose(), args
        )
    if not rotate(FACE_SOUTH_YAW_RAD, 15.0):
        log("rotate_south", ok=False)
        return _result(False, "rotate_south", phases, start, tray_pose(), args)
    pose = adapter.pose()
    hold_anchor_box["value"] = (pose.x, pose.y)
    log(
        "at_north_stance",
        base=[round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
        north_stance=list(north_stance),
        pinch_target=list(pinch_target_xy),
    )

    tray_now = tray_pose()  # tray does not move during navigate/rotate
    # Round 3: corrected closing-axis orientation (see EDGE_PINCH_ROLL_RAD
    # above) plus a horizontal pregrasp-out -> reach-in approach instead of
    # a vertical descend, with the wrist-to-fingertip offset measured live
    # (never assumed) at the pregrasp-out stance. Module-level so its own
    # branching does not count toward this function's cyclomatic
    # complexity.
    # edge_info is already captured via the edge_close/edge_lift phase
    # log entries above; nothing further is needed from it here.
    edge_passed, edge_failed_phase, _edge_info = _run_edge_pinch(
        arms=arms,
        robot=robot,
        adapter=adapter,
        reach=reach,
        ramp_vertical=ramp_vertical,
        ramp_horizontal=ramp_horizontal,
        drive=drive,
        sim_tick=sim_tick,
        log=log,
        log_reach_failure=log_reach_failure,
        tray_pose_fn=tray_pose,
        hold_anchor_box=hold_anchor_box,
        pinch_target_xy=pinch_target_xy,
        tray_z=tray_now[2],
        dt=sim.cfg.dt,
        args=args,
    )
    if edge_failed_phase is not None:
        return _result(
            False, edge_failed_phase, phases, start, tray_pose(), args
        )
    final = tray_pose()
    return _result(
        edge_passed,
        "complete" if edge_passed else "edge_pinch",
        phases,
        start,
        final,
        args,
    )


def _result(
    passed: bool,
    failed_phase: str,
    phases: list[dict[str, Any]],
    start: tuple[float, float, float],
    final: tuple[float, float, float],
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "passed": bool(passed),
        "failed_phase": failed_phase,
        "mode": "physics_contact_only",
        "object_name": TRAY_NAME,
        "head_placement": args.head_placement,
        "start_pose": [round(v, 6) for v in start],
        "final_pose": [round(v, 6) for v in final],
        "net_translation_m": [round(final[i] - start[i], 6) for i in range(3)],
        "push_distance_commanded_m": args.push_distance,
        "descend_ee_z_commanded_m": args.descend_ee_z,
        "north_edge_world_y": NORTH_COUNTER_EDGE_Y,
        "phases": phases,
    }


if __name__ == "__main__":
    main()
