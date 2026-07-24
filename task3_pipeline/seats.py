# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Seat-target interface for Task 3 Stage 1 (Table Setup).

The organizer prose rules (the objective truth -- NOT ``grading.py``, which is
only a dev smoke-test) require carrying 4 objects (plate, cup, bowl+beans,
spoon) from the kitchen to **3 of 6 seats, randomly assigned per episode**.
This module is the seat-target interface the rest of the pipeline
(``stages.py::plan_stage1``) consumes.

TODO(T1): the real 6 seat coordinates + the per-episode 3-of-6 assignment
mechanism must be read from ``robot_room.usd`` (the chair/seat prim paths and
the tabletop placement point in front of each chair) and from whatever
privileged episode state exposes the random per-episode assignment (scene
builder / task config / the organizers' ``integration_test.py``) -- see
``docs/TASK3_MASTER_EXECUTION_PLAN_2026-07-24.md`` Section 5.1, Task 1.0.
Until that discovery task lands, ``assigned_seats()`` returns the documented
``MOCK_SEATS`` below so the rest of the pipeline (and its tests) has a stable,
importable interface to build against. Real coordinates will replace the mock
without changing this module's public shape.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class SeatTarget:
    """One seat's object-placement target: the tabletop point in front of the
    chair where a carried object should land."""

    seat_id: str
    x: float
    y: float
    z: float


# Mock data: 6 plausible seats spread around the dining area center
# (-2.85, 1.9) (see config.DINING_AREA), z=0.75 tabletop height (matches
# config.SINK_TABLETOP_Z ballpark). These are PLACEHOLDERS, not read from the
# scene -- see the module TODO(T1) above. They exist only so ``seats.py`` has
# a stable shape to develop and unit-test against.
MOCK_SEATS: tuple[SeatTarget, ...] = (
    SeatTarget("seat_1", -4.20, 2.60, 0.75),
    SeatTarget("seat_2", -2.85, 2.90, 0.75),
    SeatTarget("seat_3", -1.50, 2.60, 0.75),
    SeatTarget("seat_4", -4.20, 1.20, 0.75),
    SeatTarget("seat_5", -2.85, 0.90, 0.75),
    SeatTarget("seat_6", -1.50, 1.20, 0.75),
)


def assigned_seats(
    episode=None, *, seed: int | None = None
) -> list[SeatTarget]:
    """Return the 3 seats assigned for this episode.

    TODO(T1): replace this mock with a real read of per-episode seat
    assignment from privileged episode state / ``robot_room.usd`` (see the
    module docstring). Until then:

    * If ``episode`` already exposes an ``assigned_seats`` attribute (a
      forward-compatible hook for when T1 lands), use it directly.
    * Otherwise deterministically pick 3 of the 6 ``MOCK_SEATS``: with no
      ``seed``, the first 3; with a ``seed``, a seeded sample (so CPU tests /
      mock episodes can still exercise different seat combinations without
      hitting real per-episode randomness).
    """
    if episode is not None and hasattr(episode, "assigned_seats"):
        return list(episode.assigned_seats)

    seats = list(MOCK_SEATS)
    if seed is None:
        return seats[:3]
    rng = random.Random(seed)
    return rng.sample(seats, 3)


def object_to_seat(
    objects: list[str], seats: list[SeatTarget]
) -> dict[str, SeatTarget]:
    """Map each object to one of the assigned seats.

    ASSUMPTION: the organizer rules do not dictate a specific object<->seat
    pairing -- only that each of the 4 objects ends up at one of the 3
    assigned seats (plan Section 5.1, Task 1.0b: "any bijection of the 4
    objects to 3 seats that satisfies 'each object at an assigned seat' is
    fine"). With 4 objects and 3 seats this cannot be a strict bijection, so
    seats are cycled and at least one seat receives two objects. Every object
    lands at an assigned seat, which is the acceptance criterion.
    """
    if not seats:
        raise ValueError("object_to_seat requires at least one seat")
    return {obj: seats[i % len(seats)] for i, obj in enumerate(objects)}
