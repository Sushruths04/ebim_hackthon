# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for task3_autonomy.lerobot_recorder (CPU-only, no Isaac Sim)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from task3_autonomy.lerobot_recorder import (
    ARM_JOINTS,
    LeRobotFrame,
    LeRobotRecorder,
    collect_frame_cpu,
)


class TestLeRobotFrame:
    def test_default_shape(self) -> None:
        f = LeRobotFrame()
        assert len(f.joint_pos) == 14
        assert len(f.joint_vel) == 14
        assert len(f.gripper_pos) == 2
        assert len(f.base_pose) == 3
        assert len(f.base_velocity) == 3
        assert len(f.action) == 17

    def test_custom_values(self) -> None:
        f = LeRobotFrame(
            joint_pos=[0.1 * i for i in range(14)],
            gripper_pos=[0.5, 0.8],
            base_pose=[1.0, 2.0, 0.5],
        )
        assert f.joint_pos[0] == 0.0
        assert f.joint_pos[13] == 1.3
        assert f.gripper_pos == [0.5, 0.8]
        assert f.base_pose == [1.0, 2.0, 0.5]


class TestCollectFrameCpu:
    def test_all_zeros(self) -> None:
        f = collect_frame_cpu(
            joint_names=[],
            joint_pos_all=[],
            joint_vel_all=[],
            gripper_left_pos=0.0,
            gripper_right_pos=0.0,
            base_x=0.0, base_y=0.0, base_yaw=0.0,
            base_vx=0.0, base_vy=0.0, base_wz=0.0,
        )
        assert f.joint_pos == [0.0] * 14
        assert f.gripper_pos == [0.0, 0.0]
        assert f.base_pose == [0.0, 0.0, 0.0]

    def test_arm_joint_mapping(self) -> None:
        names = ["left_fr3v2_joint1", "right_fr3v2_joint3"]
        pos = [1.57, 2.34]
        vel = [0.1, 0.2]
        f = collect_frame_cpu(
            joint_names=names,
            joint_pos_all=pos,
            joint_vel_all=vel,
            gripper_left_pos=0.5,
            gripper_right_pos=0.3,
            base_x=1.0, base_y=2.0, base_yaw=0.5,
            base_vx=0.1, base_vy=0.2, base_wz=0.05,
        )
        # left_fr3v2_joint1 -> index 0
        assert f.joint_pos[0] == 1.57
        # right_fr3v2_joint3 -> index 9 (right starts at 7, joint3 = 7+2)
        assert f.joint_pos[9] == 2.34
        assert f.joint_vel[0] == 0.1
        assert f.joint_vel[9] == 0.2
        assert f.gripper_pos == [0.5, 0.3]
        assert f.base_pose == [1.0, 2.0, 0.5]

    def test_unknown_joints_ignored(self) -> None:
        f = collect_frame_cpu(
            joint_names=["some_random_joint", "left_fr3v2_joint2"],
            joint_pos_all=[99.0, 0.77],
            joint_vel_all=[0.0, 0.0],
            gripper_left_pos=0.0,
            gripper_right_pos=0.0,
            base_x=0.0, base_y=0.0, base_yaw=0.0,
            base_vx=0.0, base_vy=0.0, base_wz=0.0,
        )
        # some_random joint ignored; left_fr3v2_joint2 -> index 1
        assert f.joint_pos[0] == 0.0  # not 99.0
        assert f.joint_pos[1] == 0.77

    def test_action_passthrough(self) -> None:
        action = [float(i) for i in range(17)]
        f = collect_frame_cpu(
            joint_names=[], joint_pos_all=[], joint_vel_all=[],
            gripper_left_pos=0.0, gripper_right_pos=0.0,
            base_x=0.0, base_y=0.0, base_yaw=0.0,
            base_vx=0.0, base_vy=0.0, base_wz=0.0,
            action=action,
        )
        assert f.action == action


class TestLeRobotRecorder:
    def test_add_and_len(self) -> None:
        rec = LeRobotRecorder(fps=20)
        assert len(rec) == 0
        rec.add_frame(LeRobotFrame())
        rec.add_frame(LeRobotFrame())
        assert len(rec) == 2

    def test_save_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = LeRobotRecorder(fps=10, out_dir=tmpdir)
            rec.add_frame(LeRobotFrame(
                joint_pos=[float(i) for i in range(14)],
                gripper_pos=[0.5, 0.3],
                base_pose=[1.0, 2.0, 0.5],
            ))
            rec.add_frame(LeRobotFrame())
            path = rec.save(metadata={"task": "test_task"})

            assert path.exists()
            # Check metadata
            meta_path = Path(tmpdir) / "lerobot_dataset" / "metadata.json"
            assert meta_path.exists()
            meta = json.loads(meta_path.read_text())
            assert meta["fps"] == 10
            assert meta["total_frames"] == 2
            assert meta["task"] == "test_task"

            # Check data format (HDF5 if h5py available, else JSONL)
            try:
                import h5py
                with h5py.File(path, "r") as f:
                    assert f["data"]["joint_pos"].shape == (2, 14)
                    assert f["data"]["action"].shape == (2, 17)
                    assert f["data"]["joint_pos"][0][0] == 0.0
                    assert f["data"]["joint_pos"][0][13] == 13.0
                    assert f["data"]["gripper_pos"][0][0] == 0.5
                    assert f["data"]["gripper_pos"][0][1] == 0.3
            except ImportError:
                lines = path.read_text().strip().split("\n")
                assert len(lines) == 2
                row0 = json.loads(lines[0])
                assert len(row0["joint_pos"]) == 14
                assert row0["joint_pos"][0] == 0.0
                assert row0["joint_pos"][13] == 13.0
                assert row0["gripper_pos"] == [0.5, 0.3]

    def test_save_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rec = LeRobotRecorder(fps=20, out_dir=tmpdir)
            path = rec.save()
            assert path.exists()
            meta = json.loads(
                (Path(tmpdir) / "lerobot_dataset" / "metadata.json").read_text()
            )
            assert meta["total_frames"] == 0

    def test_arm_joint_constants(self) -> None:
        assert len(ARM_JOINTS) == 14
        assert ARM_JOINTS[0] == "left_fr3v2_joint1"
        assert ARM_JOINTS[6] == "left_fr3v2_joint7"
        assert ARM_JOINTS[7] == "right_fr3v2_joint1"
        assert ARM_JOINTS[13] == "right_fr3v2_joint7"
