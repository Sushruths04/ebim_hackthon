# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU unit tests for the Task 3 self-correcting pipeline.

Run: python -m pytest task3_pipeline/tests -q
  or: python -B task3_pipeline/tests/test_pipeline.py   (no pytest needed)

These prove the *logic* (verifier, memory, retry, orchestration) without Isaac.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

from task3_pipeline import config
from task3_pipeline.memory import ParamMemory
from task3_pipeline.outcomes import SkillOutcome, SkillReport, classify
from task3_pipeline.policy import RetryPolicy
from task3_pipeline.seats import TABLE_SEAT_POSITIONS, assigned_seats, object_to_seat
from task3_pipeline.skills import SelfCorrectingSkill
from task3_pipeline.orchestrator import Task3Pipeline
from task3_pipeline.stages import plan_stage1
from task3_pipeline.world import MockWorld


def _load_grading_module():
    """Import the organizers' pure-Python grading helpers by file path.

    ``scripts/evaluation/task3/grading.py`` is not part of an importable
    package (no ``__init__.py`` anywhere under ``scripts/``), so it is loaded
    directly like the organizers' own
    ``scripts/evaluation/task3/tests/test_grading.py`` does (via sys.path).
    It has zero Isaac imports (see its own module docstring), so this works
    on plain CPU Python.
    """
    repo_root = Path(__file__).resolve().parents[2]
    grading_path = repo_root / "scripts" / "evaluation" / "task3" / "grading.py"
    spec = importlib.util.spec_from_file_location(
        "task3_grading_for_seat_tests", grading_path
    )
    module = importlib.util.module_from_spec(spec)
    # dataclasses' frozen(eq=True) processing looks the module up in
    # sys.modules by name, so it must be registered before exec_module runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_grading = _load_grading_module()


# ---- verifier ----------------------------------------------------------- #

def test_verifier_labels_weak_grasp():
    outcome, diag = classify("grasp", {"gripper_rad": 0.63, "contact": True})
    assert outcome is SkillOutcome.WEAK_GRASP
    assert "0.63" in diag


def test_verifier_labels_firm_grasp_success():
    # Honest SUCCESS requires proof of an actual hold, not just a closed cage.
    outcome, _ = classify("grasp", {
        "gripper_rad": 0.076, "contact": True,
        "object_follows_ee": True, "object_ee_dist_m": 0.01,
    })
    assert outcome is SkillOutcome.SUCCESS


def test_verifier_flags_ik_fail_on_bad_reach():
    outcome, _ = classify("reach", {"position_error_m": 0.079, "strict_reach": False})
    assert outcome is SkillOutcome.IK_FAIL


def test_verifier_grasp_closed_on_empty_air_is_weak_not_success():
    # The recurring project bug: gripper cage angle looks tight (below the
    # cage threshold) and contact was reported, but the object is NOT
    # following the end-effector and is far away -- this must NOT be
    # classified SUCCESS.
    outcome, diag = classify("grasp", {
        "gripper_rad": 0.076, "contact": True,
        "object_follows_ee": False, "object_ee_dist_m": 0.22,
    })
    assert outcome is SkillOutcome.WEAK_GRASP
    assert "not held" in diag
    assert "0.076" in diag


def test_verifier_grasp_missing_hold_evidence_is_weak_not_success():
    # No object_follows_ee / object_ee_dist_m supplied at all -- a closed
    # cage alone is not proof of a hold, so this must not default to SUCCESS.
    outcome, _ = classify("grasp", {"gripper_rad": 0.076, "contact": True})
    assert outcome is SkillOutcome.WEAK_GRASP


# ---- memory ------------------------------------------------------------- #

def test_memory_roundtrip_and_best_params(tmp_path=None):
    path = (tmp_path or tempfile.mkdtemp()).__str__() + "/mem.json" \
        if tmp_path else tempfile.mktemp(suffix=".json")
    mem = ParamMemory(path=path)
    mem.record(SkillReport("grasp", SkillOutcome.WEAK_GRASP, {"approach_stance": "east"}),
               reward=0.2, object_name="cup")
    mem.record(SkillReport("grasp", SkillOutcome.SUCCESS, {"approach_stance": "north"}),
               reward=1.0, object_name="cup")
    mem.save()
    reloaded = ParamMemory.load(path)
    assert reloaded.best_params("grasp", object_name="cup") == {"approach_stance": "north"}
    assert {"approach_stance": "east"} in reloaded.failed_params("grasp", object_name="cup")


# ---- policy ------------------------------------------------------------- #

def test_policy_flips_stance_after_ik_fail():
    mem = ParamMemory()
    pol = RetryPolicy(mem)
    last = SkillReport("grasp", SkillOutcome.IK_FAIL, {"approach_stance": "east"})
    plan = pol.plan("grasp", object_name="cup", last=last)
    # The first candidate should NOT keep the failing stance.
    assert plan[0].get("approach_stance") == "north"


# ---- self-correcting skill --------------------------------------------- #

def test_skill_recovers_from_ik_fail_via_retry():
    world = MockWorld(seed=1)
    mem = ParamMemory()
    runner = SelfCorrectingSkill(world, mem, RetryPolicy(mem))
    # grasp defaults to east (fails); loop must find north and succeed.
    report = runner.run("grasp", lambda p: world.grasp("right", "cup", **p),
                        object_name="cup",
                        reward_fn=lambda m: max(0.0, 1 - m["gripper_rad"] / 0.8))
    assert report.outcome is SkillOutcome.SUCCESS
    assert report.params.get("approach_stance") == "north"


# ---- seats --------------------------------------------------------------- #

def test_assigned_seats_returns_distinct_seats_inside_dining_area():
    dining_area = _grading.TASK3_DINING_AREA
    seats = assigned_seats(seed=None)
    assert len(seats) == 3
    assert len({s.seat_id for s in seats}) == 3  # distinct
    for seat in seats:
        assert seat.seat_id in TABLE_SEAT_POSITIONS
        assert dining_area.contains_xy((seat.x, seat.y))


def test_assigned_seats_seeded_is_deterministic_and_distinct():
    seats_a = assigned_seats(seed=42, count=4)
    seats_b = assigned_seats(seed=42, count=4)
    assert [s.seat_id for s in seats_a] == [s.seat_id for s in seats_b]
    assert len({s.seat_id for s in seats_a}) == 4


def test_object_to_seat_targets_classify_as_dining_per_shipped_scorer():
    # This proves that placing the 4 real Stage-1 objects at their assigned
    # seat targets passes the ONLY real scorer that ships anywhere
    # (grading.py's dining-rectangle classifier) -- the local Stage-1
    # validation gate for T1.
    seats = assigned_seats(seed=None)
    mapping = object_to_seat(list(config.STAGE1_OBJECTS), seats)
    assert set(mapping) == set(config.STAGE1_OBJECTS)
    for obj, seat in mapping.items():
        area = _grading.classify_table_area((seat.x, seat.y))
        assert area == "dining", f"{obj} -> seat {seat.seat_id} classified as {area!r}"


# ---- end-to-end orchestration ------------------------------------------ #

def test_full_episode_reaches_70pct():
    world = MockWorld(seed=7, head_placement="a")
    pipe = Task3Pipeline(world, memory_path=None)
    result = pipe.run_episode(seed=7, head_placement="a")
    assert result.max_total == 16
    assert result.highest_stage == 4              # every stage attempted
    assert result.pct >= 0.70, result.as_json()   # >= 11/16


def test_plan_stage1_targets_4_objects_no_tray():
    # Real Stage 1 (organizer prose rules): 4 objects (plate, cup, bowl+beans,
    # spoon), NO tray, carried individually to assigned seats.
    world = MockWorld(seed=3, head_placement="a")
    mem = ParamMemory()
    runner = SelfCorrectingSkill(world, mem, RetryPolicy(mem))

    assert config.STAGE1_OBJECTS == ("plate2", "cup", "bowl2", "spoon2")
    assert "simple_tray" not in config.STAGE1_OBJECTS

    result = plan_stage1(runner, world)

    # The per-object loop runs navigate/reach/grasp/cleanup for each of the 4
    # real objects (4 skills * 4 objects = 16 reports minimum; retries only
    # add more) and must never touch "simple_tray".
    assert len(result.reports) >= 16
    for obj in config.STAGE1_OBJECTS:
        assert obj != "simple_tray"
        recorded = [k for k in mem._store if k.endswith(f"|{obj}")]
        assert recorded, f"expected memory entries recorded for object {obj}"
    assert "simple_tray" not in "".join(mem._store.keys())
    assert result.score >= 0


def test_matrix_majority_pass():
    world = MockWorld()
    pipe = Task3Pipeline(world, memory_path=None)
    pcts = []
    for hp in "abcdefghi":
        for seed in range(5):
            pcts.append(pipe.run_episode(seed=seed, head_placement=hp).pct)
    passed = sum(1 for p in pcts if p >= 0.70)
    assert passed / len(pcts) >= 0.70


ALL = [v for k, v in dict(globals()).items() if k.startswith("test_")]

if __name__ == "__main__":
    failures = 0
    for fn in ALL:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(ALL) - failures}/{len(ALL)} passed")
    raise SystemExit(1 if failures else 0)
