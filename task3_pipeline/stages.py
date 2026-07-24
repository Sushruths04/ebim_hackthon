# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""The four Task 3 stage plans, aligned to the organizer prose rules (the
objective truth -- ``scripts/evaluation/task3/grading.py`` is only a dev
smoke-test, see ``config.py``).

A stage plan is a short sequence of self-correcting skill calls that drives the
world into a state the scorer accepts. The plans encode the *strategy*
decisions from the analysis:

* Stage 1 -- per object (plate, cup, bowl+beans, spoon -- NO tray): navigate
  to a reach-safe kitchen stance, reach, grasp, then carry/place at its
  assigned seat (see ``seats.py``).
* Stage 2 -- scoop with a 30-45 deg entry + deep drag, present smoothly, hold 3 s.
* Stage 3 -- pour the beans back into the recovery sphere low and slow (ratio game).
* Stage 4 -- honest grasp + place of each utensil into the marked sink region
  (navigate -> grasp -> carry/place -> verify). A controlled carry/place is
  legal and sufficient (the scorer needs no cage), but it follows a real,
  verified grasp -- not a physics exploit.

Each returns a StageResult. The orchestrator chains them and sums the score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from task3_pipeline import config
from task3_pipeline.outcomes import SkillReport
from task3_pipeline.seats import assigned_seats, object_to_seat
from task3_pipeline.skills import SelfCorrectingSkill


@dataclass
class StageResult:
    stage: int
    score: int
    max_score: int
    reports: list[SkillReport] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        # "completed" for the chain FSM = the stage was attempted and scored
        # at least partial credit. Ranking rewards reaching higher stages, so
        # we always progress regardless (see orchestrator).
        return self.score > 0


# reward helpers for the memory ranking (partial credit in [0,1])
def _r_lower_better(metrics, key, scale):  # e.g. gripper rad, error
    return max(0.0, 1.0 - float(metrics.get(key, scale)) / scale)


def _run(runner, skill, invoke, **kw):
    return runner.run(skill, invoke, **kw)


def plan_stage1(runner: SelfCorrectingSkill, world) -> StageResult:
    """Per-object pick -> carry -> place at the assigned seats.

    NO tray, NO single dining-drop point: the organizer rules require the 4
    real objects (config.STAGE1_OBJECTS) to individually end up at 3 of 6
    randomly-assigned seats (seats.py). Seats + the object->seat mapping are
    computed once per stage attempt (not hardcoded per-episode values).
    """
    reports = []
    seats = assigned_seats(seed=getattr(world, "seed", None))
    mapping = object_to_seat(list(config.STAGE1_OBJECTS), seats)

    for obj in config.STAGE1_OBJECTS:
        seat = mapping[obj]
        kitchen_xy = world.object_xy(obj)  # reach-safe kitchen stance target

        reports.append(_run(
            runner, "navigate",
            lambda p, xy=kitchen_xy: world.navigate_to(*xy, **p),
            object_name=obj,
            reward_fn=lambda m: _r_lower_better(m, "terminal_error_m", 0.2),
        ))
        reports.append(_run(
            runner, "reach",
            lambda p, o=obj: world.reach("right", o, **p),
            object_name=obj,
        ))
        reports.append(_run(
            runner, "grasp",
            lambda p, o=obj: world.grasp("right", o, **p),
            object_name=obj,
            reward_fn=lambda m: _r_lower_better(m, "gripper_rad", 0.8),
        ))
        # Carry/place at the object's assigned seat target.
        reports.append(_run(
            runner, "cleanup",  # reuse carry mechanism
            lambda p, o=obj, s=seat: world.carry_object_to(
                o, s.x, s.y, s.z, **p),
            object_name=obj,
        ))

    score, mx, details = world.score_stage(1)
    details = dict(details, assigned_seats=[s.seat_id for s in seats])
    return StageResult(1, score, mx, reports, details)


def plan_stage2(runner: SelfCorrectingSkill, world) -> StageResult:
    reports = []
    reports.append(_run(runner, "scoop",
                        lambda p: world.scoop("right", **p),
                        reward_fn=lambda m: min(1.0, float(m.get("beans_on_spoon", 0)) / 6.0)))
    # Present to the feed zone and hold >= 3 s smoothly (head-force safe).
    reports.append(_run(runner, "hold",
                        lambda p: world.feed_hold(config.FEED_HOLD_SECONDS, **p)))
    score, mx, details = world.score_stage(2)
    return StageResult(2, score, mx, reports, details)


def plan_stage3(runner: SelfCorrectingSkill, world) -> StageResult:
    reports = []
    reports.append(_run(runner, "pour",
                        lambda p: world.pour("right", *config.BEAN_SPAWN_XY, **p),
                        reward_fn=lambda m: float(m.get("ratio", 0.0))))
    score, mx, details = world.score_stage(3)
    return StageResult(3, score, mx, reports, details)


def plan_stage4(runner: SelfCorrectingSkill, world) -> StageResult:
    """Honest grasp + place of each of the 4 utensils into the sink region.

    Per utensil: navigate to a reach-safe stance -> grasp (verified, see
    outcomes.classify_grasp) -> carry/place into the sink region -> verify.
    A controlled carry/place is legal and sufficient (the scorer checks the
    object ends in-region at height, not a held cage) -- but it follows a
    real, verified grasp rather than a physics exploit.
    """
    reports = []
    for obj in config.STAGE1_OBJECTS:
        kitchen_xy = world.object_xy(obj)
        reports.append(_run(
            runner, "navigate",
            lambda p, xy=kitchen_xy: world.navigate_to(*xy, **p),
            object_name=obj,
            reward_fn=lambda m: _r_lower_better(m, "terminal_error_m", 0.2),
        ))
        reports.append(_run(
            runner, "grasp",
            lambda p, o=obj: world.grasp("right", o, **p),
            object_name=obj,
            reward_fn=lambda m: _r_lower_better(m, "gripper_rad", 0.8),
        ))
        reports.append(_run(
            runner, "cleanup",
            lambda p, o=obj: world.carry_object_to(
                o, *config.SINK_CENTER_XY, config.SINK_TABLETOP_Z, **p),
            object_name=obj,
        ))
    score, mx, details = world.score_stage(4)
    return StageResult(4, score, mx, reports, details)


STAGE_PLANS = {1: plan_stage1, 2: plan_stage2, 3: plan_stage3, 4: plan_stage4}
