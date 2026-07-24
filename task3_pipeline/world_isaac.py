# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""IsaacWorld -- the real WorldAdapter (INTEGRATION STUB).

This is the ONE file that imports Isaac and the existing task3_autonomy
primitives. Every method has the same signature as MockWorld and must return
the same metrics keys, so the orchestrator/verifier/memory/policy code above
is reused unchanged.

Filling this in is the only GPU-side work: wire each method to the proven
helpers that already exist in the repo. The mapping is spelled out below so it
is a wiring job, not a design job. Develop the brain against MockWorld on CPU;
use GPU time only to make these methods return real measurements.
"""

from __future__ import annotations

from task3_pipeline import config


class IsaacWorld:
    """Wraps DualArmController + TmrBaseAdapter + NavigateTo + PhysX reads.

    Construct inside the running Isaac scene (see
    scripts/scenes/scene_robot_room_keyboard.py --task task3, which already
    builds the robot, IK, and base control that these methods call).
    """

    def __init__(self, *, record_video: bool = False, out_dir: str = "outputs/task3_pipeline"):
        raise NotImplementedError(
            "IsaacWorld is a wiring stub. Implement the methods below against "
            "the existing primitives. See the docstrings for the exact mapping."
        )

    # ------------------------------------------------------------------ #
    # WIRING MAP -- what each method should call (all helpers already exist)
    # ------------------------------------------------------------------ #

    def reset(self, *, seed: int, head_placement: str) -> None:
        # Build/reset the task3 scene with this seed + head placement.
        # Reuse scene_robot_room_keyboard.py's composition as a library.
        raise NotImplementedError

    def navigate_to(self, x, y, yaw=None, **p) -> dict:
        # Loop task3_autonomy.skills.NavigateTo.compute(pose) ->
        # TmrBaseAdapter.apply_twist(vx, vy) until done; ramp arms to
        # TRANSIT_ARM_POSE first (skills.ramp_arm_pose). Return:
        #   {"terminal_error_m": <dist to (x,y)>}
        raise NotImplementedError

    def reach(self, side, world_pose, **p) -> dict:
        # Set the stance implied by p["approach_stance"] (square the base to
        # the object -- this is the Stage-4 reachability fix), then
        # DualArmController.reach(side, world->base-frame pose). Return:
        #   {"position_error_m": controller.position_error(side, target),
        #    "strict_reach": <reached flag>, "ee_dy_m": <ee.y - target.y>}
        raise NotImplementedError

    def grasp(self, side, object_name, **p) -> dict:
        # DualArmController.grasp(side) with height p["grasp_height_above_origin_m"]
        # and y-offset p["grasp_y_offset"]. Use the PROVEN constants from
        # scripts/task3/verify_grasp_lift.py (10/10) as defaults. Return:
        #   {"gripper_rad": controller.gripper_position(side), "contact": <bool>}
        raise NotImplementedError

    def lift(self, side, dz, **p) -> dict:
        # Use verify_grasp_lift.py's proven fling-free lift (NOT the spine-to-
        # 0.57 ramp that caused the IK fling). Read object z before/after.
        #   {"object_rise_m": z_after - z_before, "ik_ok": <no IK failure>}
        raise NotImplementedError

    def hold(self, seconds, **p) -> dict:
        # Hold current pose for `seconds`; watch object z and head-force gate.
        #   {"z_drop_m": ..., "held_seconds": ..., "required_seconds": seconds,
        #    "watchdog": <head-force gate tripped?>}
        raise NotImplementedError

    def carry_object_to(self, object_name, x, y, **p) -> dict:
        # Stage-4 scorer exploit. method="base_carry": partial-grip + drive the
        # base so the object ends inside the sink rect at z>=tabletop; or
        # "controlled_slide": push with a hard stop. NO rim cage / lift needed.
        # Read final object pose to confirm. Return {"scored": <in sink?>}.
        raise NotImplementedError

    def scoop(self, side, **p) -> dict:
        # Spoon path: enter bowl at p["entry_pitch_deg"], drag p["drag_depth_m"]
        # through the bean pile, level, lift. Count beans on spoon.
        #   {"beans_on_spoon": <count>, "scored": <count>=4>}
        raise NotImplementedError

    def feed_hold(self, seconds, **p) -> dict:
        # Present spoon to the feed zone in front of the head; hold smoothly
        # `seconds` (approach slowly -- ISO/TS 15066 head-force is a hard fail).
        #   {"held_seconds": ..., "required_seconds": config.FEED_HOLD_SECONDS,
        #    "z_drop_m": ..., "beans_left": ..., "smooth": <bool>, "watchdog": ...}
        raise NotImplementedError

    def pour(self, side, x, y, **p) -> dict:
        # Tilt the bowl over the recovery region at p["pour_height_m"], rate
        # p["tilt_rate"]; count beans landing inside config.BEAN_RECOVERY_*.
        #   {"beans_delivered": ..., "ratio": inside/total, "scored": ratio>=0.8}
        raise NotImplementedError

    # reads -- use PhysX / Fabric tensor APIs, NOT stale USD attributes
    def object_xy(self, name): raise NotImplementedError
    def object_z(self, name): raise NotImplementedError

    def score_stage(self, stage: int):
        # Call the official scorers in scripts/evaluation/task3/grading.py with
        # live object poses. Return (score, max, details).
        raise NotImplementedError
