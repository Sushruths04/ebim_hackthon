# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU regression coverage for Stage 4 grasp target selection."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "task3"))

from run_stage4_cleanup import grasp_targets, parse_args  # noqa: E402


def _args(*, arm_side: str, cup_grasp_y_offset: float | None):
    return SimpleNamespace(
        arm_side=arm_side,
        cup_rim_x_offset=0.04,
        cup_grasp_y_offset=cup_grasp_y_offset,
        cup_grasp_z_offset=0.0,
        object_grasp_x_offset=0.04,
        object_grasp_y_offset=0.04,
        object_grasp_z_offset=0.10,
    )


def test_cup_default_rim_target_is_mirrored_for_left_arm():
    cup = (-4.185, -1.753, 0.747)
    _, right_grasp, _ = grasp_targets(
        "cup", cup, _args(arm_side="right", cup_grasp_y_offset=None)
    )
    _, left_grasp, _ = grasp_targets(
        "cup", cup, _args(arm_side="left", cup_grasp_y_offset=None)
    )

    assert right_grasp == pytest.approx((-4.145, -1.693, 0.815))
    assert left_grasp == pytest.approx((-4.145, -1.813, 0.815))


def test_explicit_cup_rim_offset_overrides_arm_mirroring():
    cup = (-4.185, -1.753, 0.747)
    _, grasp, _ = grasp_targets(
        "cup", cup, _args(arm_side="left", cup_grasp_y_offset=0.02)
    )

    assert grasp == pytest.approx((-4.145, -1.733, 0.815))


def test_cup_grasp_yaw_is_an_explicit_cli_control(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_stage4_cleanup.py",
            "--object-name",
            "cup",
            "--cup-grasp-yaw-rad",
            "1.5708",
        ],
    )

    assert parse_args().cup_grasp_yaw_rad == pytest.approx(1.5708)


def test_edge_orientation_is_an_explicit_cli_control(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_stage4_cleanup.py", "--grasp-orientation", "edge_y"],
    )

    assert parse_args().grasp_orientation == "edge_y"


def test_cup_grasp_z_offset_lowers_live_rim_target():
    cup = (-4.185, -1.753, 0.747)
    args = _args(arm_side="right", cup_grasp_y_offset=None)
    args.cup_grasp_z_offset = -0.02

    _, grasp, _ = grasp_targets("cup", cup, args)

    assert grasp == pytest.approx((-4.145, -1.693, 0.795))
