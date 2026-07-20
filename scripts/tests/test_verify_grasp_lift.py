# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU coverage for the live cup contact-target calibration helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "task3"))

from verify_grasp_lift import (  # noqa: E402
    GRASP_HEIGHT_ABOVE_CUP_ORIGIN,
    cup_grasp_target,
    object_follows_end_effector,
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


def test_transport_route_is_importable_from_package_namespace():
    from task3_autonomy.navigation import route_via_door

    assert callable(route_via_door)


def test_object_follows_end_effector_rejects_counter_left_behind():
    assert object_follows_end_effector(
        (-4.10, -1.60, 0.99),
        (-4.08, -1.56, 1.06),
        max_distance_m=0.18,
    )
    assert not object_follows_end_effector(
        (-4.22, -1.36, 0.78),
        (-4.07, -1.56, 1.07),
        max_distance_m=0.18,
    )


def test_object_follows_end_effector_requires_positive_threshold():
    with pytest.raises(ValueError, match="positive"):
        object_follows_end_effector(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            max_distance_m=0.0,
        )
