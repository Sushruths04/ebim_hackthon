# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""SelfCorrectingSkill: the fast loop around one primitive.

    execute chosen params  ->  verify outcome  ->  if failed, ask the policy
    for the next params (using memory + the diagnosis)  ->  retry  ->  record
    everything to memory.

This is the single mechanism that replaces "human watches GIF, edits a
constant, reruns" -- applied uniformly to every skill in every stage. No
training. Returns the first SUCCESS, or the best partial attempt if the retry
budget is exhausted (partial points beat a hang).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from task3_pipeline.memory import ParamMemory
from task3_pipeline.outcomes import SkillOutcome, SkillReport, classify
from task3_pipeline.policy import RetryPolicy

# invoke(params) -> raw metrics dict from the world
Invoke = Callable[[dict], dict]
# optional partial-credit reward in [0,1] from metrics (for memory ranking)
RewardFn = Callable[[dict], float]


@dataclass
class SelfCorrectingSkill:
    world: object
    memory: ParamMemory
    policy: RetryPolicy

    def run(
        self,
        skill: str,
        invoke: Invoke,
        *,
        object_name: str = "-",
        reward_fn: RewardFn | None = None,
        on_attempt: Callable[[SkillReport], None] | None = None,
    ) -> SkillReport:
        head = getattr(self.world, "head_placement", "-")
        tried: list[dict] = []
        last: SkillReport | None = None
        best: SkillReport | None = None
        best_reward = -1.0

        for _ in range(self.policy.budget + 1):
            plan = self.policy.plan(
                skill, head_placement=head, object_name=object_name, last=last
            )
            params = next((p for p in plan if p not in tried), None)
            if params is None:
                break
            tried.append(params)

            metrics = invoke(params)
            outcome, diag = classify(skill, metrics)
            report = SkillReport(skill, outcome, dict(params), dict(metrics), diag)
            reward = 1.0 if report.ok else (reward_fn(metrics) if reward_fn else 0.0)
            self.memory.record(report, reward=reward,
                               head_placement=head, object_name=object_name)
            if on_attempt:
                on_attempt(report)

            if reward > best_reward:
                best, best_reward = report, reward
            if report.ok:
                self.memory.save()
                return report
            last = report

        self.memory.save()
        return best if best is not None else SkillReport(
            skill, SkillOutcome.TIMEOUT, {}, {}, "no attempts made"
        )
