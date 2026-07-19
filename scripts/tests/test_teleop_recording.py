# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from teleop_recording import TeleopEpisodeRecorder


def _pose() -> SimpleNamespace:
    return SimpleNamespace(
        position=(1.0, 2.0, 3.0),
        orientation_wxyz=(1.0, 0.0, 0.0, 0.0),
    )


def _sample() -> dict:
    pose = _pose()
    return {
        "step": 0,
        "sim_time": 0.0,
        "keys": {"1"},
        "command": SimpleNamespace(
            base_twist=(0.0, 0.0, 0.0),
            toggle_left_gripper=False,
            toggle_right_gripper=False,
        ),
        "targets": SimpleNamespace(
            left=pose,
            right=pose,
            left_gripper=0.2,
            right_gripper=0.3,
            spine=0.4,
        ),
        "root_position": (0.0, 0.0, 0.0),
        "root_orientation": (1.0, 0.0, 0.0, 0.0),
        "left_world": pose,
        "right_world": pose,
    }


def test_recorder_writes_marker_sample_and_summary(tmp_path):
    recorder = TeleopEpisodeRecorder(tmp_path, "probe", sample_every_steps=10)
    recorder.record(**_sample())
    recorder.close(reason="test")

    record = json.loads((tmp_path / "probe" / "teleop.jsonl").read_text())
    summary = json.loads((tmp_path / "probe" / "summary.json").read_text())
    assert record["markers"] == ["probe_start"]
    assert record["targets"]["left_gripper"] == pytest.approx(0.2)
    assert summary["reason"] == "test"
    assert summary["records_written"] == 1


def test_recorder_refuses_overwrite(tmp_path):
    TeleopEpisodeRecorder(tmp_path, "probe").close()

    with pytest.raises(FileExistsError):
        TeleopEpisodeRecorder(tmp_path, "probe")


def test_recorder_rejects_nested_episode_name(tmp_path):
    with pytest.raises(ValueError):
        TeleopEpisodeRecorder(tmp_path, "nested/probe")
