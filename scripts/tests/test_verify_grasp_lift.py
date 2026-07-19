# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU coverage for the live cup contact-target calibration helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "task3"))

from verify_grasp_lift import (  # noqa: E402
    GRASP_HEIGHT_ABOVE_CUP_ORIGIN,
    cup_grasp_target,
)


def test_cup_grasp_target_uses_live_pose_and_explicit_offsets():
    target = cup_grasp_target(
        (-4.184, -1.677, 0.777),
        rim_x_offset=0.04,
        grasp_y_offset=0.0,
    )

    assert target == pytest.approx(
        (-4.144, -1.677, 0.777 + GRASP_HEIGHT_ABOVE_CUP_ORIGIN)
    )
