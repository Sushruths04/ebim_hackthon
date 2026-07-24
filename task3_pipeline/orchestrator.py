# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Task3Pipeline: the end-to-end autonomous controller.

It sequences stages 1 -> 2 -> 3 -> 4 through the existing fail-closed
``Task3ChainFSM`` (safety events are terminal), runs each stage's plan through
the self-correcting skill loop, aggregates the score, and emits one
``EPISODE_RESULT`` JSON line (same convention as the repo's integration tests).

Nothing here imports Isaac. Swap ``MockWorld`` for ``IsaacWorld`` and the same
orchestrator runs the real robot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from task3_autonomy.chained_fsm import (
    ChainObservation,
    Task3ChainFSM,
    Task3Stage,
)

from task3_pipeline.config import DEFAULT_MEMORY_PATH
from task3_pipeline.memory import ParamMemory
from task3_pipeline.policy import RetryPolicy
from task3_pipeline.skills import SelfCorrectingSkill
from task3_pipeline.stages import STAGE_PLANS, StageResult


@dataclass
class EpisodeResult:
    seed: int
    head_placement: str
    stages: list[StageResult] = field(default_factory=list)
    aborted_at: int | None = None

    @property
    def total(self) -> int:
        return sum(s.score for s in self.stages)

    @property
    def max_total(self) -> int:
        return sum(s.max_score for s in self.stages) or 16

    @property
    def pct(self) -> float:
        return round(self.total / self.max_total, 3)

    @property
    def highest_stage(self) -> int:
        completed = [s.stage for s in self.stages if s.completed]
        return max(completed) if completed else 0

    def as_json(self) -> str:
        return json.dumps({
            "EPISODE_RESULT": True,
            "seed": self.seed,
            "head_placement": self.head_placement,
            "total_score": self.total,
            "max_score": self.max_total,
            "pct": self.pct,
            "highest_stage_completed": self.highest_stage,
            "aborted_at_stage": self.aborted_at,
            "per_stage": [
                {"stage": s.stage, "score": s.score, "max": s.max_score,
                 "details": s.details}
                for s in self.stages
            ],
        }, sort_keys=True)


class Task3Pipeline:
    def __init__(self, world, *, memory_path: str | None = DEFAULT_MEMORY_PATH,
                 retry_budget: int | None = None):
        self.world = world
        self.memory = ParamMemory.load(memory_path) if memory_path else ParamMemory()
        self.policy = RetryPolicy(self.memory)
        if retry_budget is not None:
            self.policy.budget = retry_budget
        self.runner = SelfCorrectingSkill(world, self.memory, self.policy)

    def run_episode(self, *, seed: int, head_placement: str,
                    order: tuple[int, ...] = (1, 2, 3, 4)) -> EpisodeResult:
        self.world.reset(seed=seed, head_placement=head_placement)
        chain = Task3ChainFSM()
        result = EpisodeResult(seed=seed, head_placement=head_placement)

        for stage in order:
            stage_result = STAGE_PLANS[stage](self.runner, self.world)
            result.stages.append(stage_result)

            # Feed the fail-closed chain: a safety event in any skill is
            # terminal; otherwise mark this stage attempted and advance.
            safety = _safety_flags(stage_result)
            obs = ChainObservation(**{f"stage{stage}_complete": True}, **safety)
            chain.step(obs)
            if chain.stage is Task3Stage.FAILED:
                result.aborted_at = stage
                break

        self.memory.save()
        return result


def _safety_flags(stage_result: StageResult) -> dict:
    """Map any skill-level safety metric into the chain's terminal predicates.
    (In the mock these are always clean; on Isaac the verifier fills them.)"""
    flags = {"watchdog_trip": False, "collision": False, "dropped_object": False}
    for report in stage_result.reports:
        m = report.metrics
        flags["collision"] = flags["collision"] or bool(m.get("collision"))
        flags["watchdog_trip"] = flags["watchdog_trip"] or bool(m.get("watchdog"))
        flags["dropped_object"] = flags["dropped_object"] or bool(m.get("dropped"))
    return flags
