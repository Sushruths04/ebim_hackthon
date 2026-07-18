# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU coverage for probe_tray_slide.py's pure-math helpers.

The script's own module-level sys.path insertions make it importable
without Isaac Sim (all Isaac-dependent code lives inside main()/_run()).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "task3"))

from probe_tray_slide import (  # noqa: E402
    KITCHEN_PARTITION_SOUTH_FACE_Y,
    NORTH_COUNTER_EDGE_Y,
    TRAY_HALF_EXTENT_Y_M,
    north_overhang_m,
    north_pinch_stance,
    north_pinch_target,
    stance_in_safe_lane,
    stroke_needs_realign,
)


def test_north_overhang_zero_at_counter_edge():
    tray_y = NORTH_COUNTER_EDGE_Y - TRAY_HALF_EXTENT_Y_M
    assert north_overhang_m(tray_y) == pytest.approx(0.0, abs=1e-9)


def test_north_overhang_positive_past_the_edge():
    tray_y = NORTH_COUNTER_EDGE_Y - TRAY_HALF_EXTENT_Y_M + 0.06
    assert north_overhang_m(tray_y) == pytest.approx(0.06)


def test_north_overhang_negative_before_the_edge():
    # Matches the round-1 measured case: tray center well short of the
    # counter edge, so the tray's own north edge has not reached it yet.
    tray_y = -1.5
    expected = (tray_y + TRAY_HALF_EXTENT_Y_M) - NORTH_COUNTER_EDGE_Y
    assert north_overhang_m(tray_y) == pytest.approx(expected)
    assert north_overhang_m(tray_y) < 0.0


def test_north_pinch_target_is_trays_own_north_edge():
    target = north_pinch_target(-4.25, -1.35, x_offset=0.0)
    assert target == pytest.approx((-4.25, -1.35 + TRAY_HALF_EXTENT_Y_M))


def test_north_pinch_target_applies_x_offset():
    target = north_pinch_target(-4.25, -1.35, x_offset=0.05)
    assert target[0] == pytest.approx(-4.20)


def test_north_pinch_stance_is_north_of_target_and_dead_ahead():
    target = (-4.25, -1.2)
    stance = north_pinch_stance(target, standoff_m=0.8)
    assert stance[0] == pytest.approx(target[0])  # same x -> dead ahead
    assert stance[1] == pytest.approx(target[1] + 0.8)
    assert stance[1] > target[1]  # north of the pinch point


@pytest.mark.parametrize(
    "stance_y,expected",
    [
        (-0.5, True),  # squarely inside the lane
        (-1.22, False),  # exactly at the island's north face
        (-1.20, False),  # inside the margin
        (0.10, False),  # exactly at the partition's south face
        (0.05, False),  # inside the margin
        (-2.0, False),  # south of the island entirely
        (0.5, False),  # north of the partition entirely
    ],
)
def test_stance_in_safe_lane(stance_y, expected):
    assert stance_in_safe_lane(stance_y) is expected


def test_stance_in_safe_lane_uses_documented_room_geometry_defaults():
    # Sanity-check the defaults match the constants cited in the room
    # geometry comment (task3_autonomy/navigation.py): island north face
    # -1.22, partition south face 0.10.
    assert NORTH_COUNTER_EDGE_Y == -1.22
    assert KITCHEN_PARTITION_SOUTH_FACE_Y == 0.10


@pytest.mark.parametrize(
    "contact_y,base_y,expected",
    [
        (-1.4, -1.4, False),
        (-1.4, -1.45, False),  # 0.05 m drift, under threshold
        (-1.4, -1.49, True),  # 0.09 m drift, over threshold
        (-1.4, -1.31, True),  # 0.09 m drift the other way
    ],
)
def test_stroke_needs_realign(contact_y, base_y, expected):
    assert stroke_needs_realign(contact_y, base_y) is expected
