# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU tests for the fresh-process Bayesian grasp optimizer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "task3"))

import grasp_optimizer as optimizer  # noqa: E402


def test_score_result_rewards_lift_hold_and_blocked_close():
    score, success = optimizer.score_result(
        {
            "cup_lift_m": 0.08,
            "continuous_hold_seconds": 3.0,
            "phases": [{"phase": "close", "gripper_position_rad": 0.20}],
        }
    )
    assert score > 0.9
    assert success


def test_score_result_rejects_empty_close():
    score, success = optimizer.score_result(
        {
            "cup_lift_m": 0.0,
            "continuous_hold_seconds": 0.0,
            "phases": [{"phase": "close", "gripper_position_rad": 1.0}],
        }
    )
    assert score == 0.0
    assert not success


def test_run_trial_writes_trial_record(monkeypatch, tmp_path):
    def fake_run(command, **kwargs):
        trial_dir = Path(command[command.index("--out-dir") + 1])
        (trial_dir / "result.json").write_text(
            json.dumps(
                {
                    "cup_lift_m": 0.03,
                    "continuous_hold_seconds": 1.2,
                    "phases": [
                        {"phase": "close", "gripper_position_rad": 0.2}
                    ],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(optimizer.subprocess, "run", fake_run)
    record = optimizer.run_trial(
        trial=1,
        parameters=optimizer.GraspParameters(0.055, 1.0, 0.2),
        output_dir=tmp_path,
        launcher=Path("isaaclab.sh"),
        timeout_seconds=1.0,
    )
    persisted = json.loads((tmp_path / "trial_001.json").read_text())
    assert record["success"]
    assert persisted["parameters"]["close_effort_scale"] == 0.2


def test_load_resume_trials_stops_before_invalid_record(tmp_path):
    for trial, result in (
        (1, {"cup_lift_m": 0.03}),
        (2, {"status": "TIMEOUT"}),
        (3, {"cup_lift_m": 0.04}),
    ):
        (tmp_path / f"trial_{trial:03d}.json").write_text(
            json.dumps(
                {
                    "trial": trial,
                    "parameters": {
                        "y_offset": 0.05,
                        "close_ramp_seconds": 1.0,
                        "close_effort_scale": 0.2,
                    },
                    "result": result,
                    "score": 0.1,
                }
            ),
            encoding="utf-8",
        )

    records = optimizer.load_resume_trials(tmp_path)

    assert [record["trial"] for record in records] == [1]
