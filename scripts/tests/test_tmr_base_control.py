# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from tmr_base_control import compensate_yaw_rate, compute_drive_targets


class _Robot:
    def __init__(self, steering_positions):
        self.data = type(
            "Data", (), {"joint_pos": torch.tensor([steering_positions])}
        )()


class _YawRobot:
    def __init__(self, yaw: float, yaw_rate: float = 0.0):
        self.data = type(
            "Data",
            (),
            {
                "root_quat_w": torch.tensor(
                    [[math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)]]
                ),
                "root_ang_vel_w": torch.tensor([[0.0, 0.0, yaw_rate]]),
            },
        )()


def test_drive_wheels_creep_while_modules_turn_to_new_direction():
    robot = _Robot([0.0, 0.0, 0.0, 0.0])

    _steering, drive = compute_drive_targets(
        robot,
        steering_ids=[0, 2],
        vx=0.0,
        vy=0.15,
        wz=0.0,
        num_envs=1,
        device="cpu",
    )

    assert torch.all(torch.abs(drive) > 0.0)


def test_steering_targets_stay_in_physx_revolute_drive_range():
    robot = _Robot([13.0, 0.0, -13.0, 0.0])

    steering, _drive = compute_drive_targets(
        robot,
        steering_ids=[0, 2],
        vx=0.15,
        vy=0.0,
        wz=0.0,
        num_envs=1,
        device="cpu",
    )

    assert torch.all(torch.abs(steering) < 2.0 * math.pi)


def test_heading_hold_can_remain_active_while_translation_is_stopped():
    robot = _YawRobot(yaw=0.2)

    wz, desired_yaw = compensate_yaw_rate(
        robot,
        vx=0.0,
        vy=0.0,
        wz=0.0,
        desired_yaw=0.0,
        manual_rotation=False,
        hold_while_stopped=True,
    )

    assert wz < 0.0
    assert desired_yaw == 0.0
