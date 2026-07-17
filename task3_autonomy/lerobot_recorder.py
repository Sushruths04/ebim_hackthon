# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""LeRobot v2 dataset recorder for Task 3 episodes.

Collects per-step observations (joint states, base pose, gripper, camera
streams) and actions (TeleopCommand stream) during an Isaac Sim episode,
then writes a LeRobot v2 compatible HDF5 dataset file.

Designed to be plugged into run_episode.py's --record-lerobot flag.  The
recorder is CPU-only (no Isaac imports at module level); the GPU-side
collection happens in the episode loop via LeRobotRecorder's collect()
method.

LeRobot v2 dataset layout (HDF5):
    data/
        action (N, action_dim)       # TeleopCommand values per step
        observation/
            joint_pos (N, 14)        # left 7 + right 7 joint positions
            joint_vel (N, 14)        # left 7 + right 7 joint velocities
            gripper_pos (N, 2)       # left + right gripper joint positions
            base_pose (N, 3)         # x, y, yaw
            base_velocity (N, 3)     # vx, vy, wz
    videos/
        observation.images.head (N, C, H, W)   # head camera frames
        observation.images.left_wrist (N, C, H, W)
        observation.images.right_wrist (N, C, H, W)
    metadata.json                   # task info, fps, git commit, etc.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Joint name patterns for the mobile FR3 Duo (matching run_episode.py's
# robot articulation).  Order matters: left arm 1-7, right arm 1-7.
LEFT_ARM_JOINTS = [f"left_fr3v2_joint{i}" for i in range(1, 8)]
RIGHT_ARM_JOINTS = [f"right_fr3v2_joint{i}" for i in range(1, 8)]
ARM_JOINTS = LEFT_ARM_JOINTS + RIGHT_ARM_JOINTS

# Gripper joints (ChangingTek gripper, 0..1 rad range)
LEFT_GRIPPER_JOINT = "left_gripper_joint"
RIGHT_GRIPPER_JOINT = "right_gripper_joint"

# TMR base joints for velocity readout
BASE_STEERING_JOINTS = ["wheel_front_left", "wheel_front_right",
                        "wheel_rear_left", "wheel_rear_right"]


@dataclass
class LeRobotFrame:
    """One timestep of recorded data."""
    # Arm joints: 14 floats (left 7 + right 7), radians
    joint_pos: list[float] = field(default_factory=lambda: [0.0] * 14)
    joint_vel: list[float] = field(default_factory=lambda: [0.0] * 14)
    # Gripper: 2 floats (left, right), radians
    gripper_pos: list[float] = field(default_factory=lambda: [0.0] * 2)
    # Base: x, y, yaw (world frame)
    base_pose: list[float] = field(default_factory=lambda: [0.0] * 3)
    # Base velocity: vx, vy, wz (body frame)
    base_velocity: list[float] = field(default_factory=lambda: [0.0] * 3)
    # Action:TeleopCommand values sent at this step (left_pose + right_pose
    # as 6D deltas [x,y,z,roll,pitch,yaw] each = 12, gripper bools = 2,
    # base twist = 3 => 17 total)
    action: list[float] = field(default_factory=lambda: [0.0] * 17)
    # Camera frames (optional, stored as raw arrays in videos/)
    camera_frames: dict[str, Any] = field(default_factory=dict)


class LeRobotRecorder:
    """Collects frames during an episode and writes a LeRobot v2 HDF5 file.

    Usage in the episode loop:

        recorder = LeRobotRecorder(fps=20, out_dir=episode_dir)
        for step in range(total_steps):
            # ... run policy, step sim ...
            frame = collect_frame(robot, base_adapter, teleop_cmd)
            recorder.add_frame(frame)
        recorder.save(metadata={...})
    """

    def __init__(
        self,
        fps: int = 20,
        out_dir: Path | str | None = None,
        record_cameras: bool = True,
    ) -> None:
        self.fps = fps
        self.out_dir = Path(out_dir) if out_dir else Path(".")
        self.record_cameras = record_cameras
        self._frames: list[LeRobotFrame] = []

    def add_frame(self, frame: LeRobotFrame) -> None:
        self._frames.append(frame)

    def __len__(self) -> int:
        return len(self._frames)

    @property
    def frames(self) -> list[LeRobotFrame]:
        return self._frames

    def save(self, metadata: dict | None = None) -> Path:
        """Write the dataset to an HDF5 file and return its path.

        Falls back to a JSON-lines format if h5py is not available.
        """
        dataset_dir = self.out_dir / "lerobot_dataset"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata
        meta = {
            "fps": self.fps,
            "total_frames": len(self._frames),
            "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "features": {
                "action": {"shape": [17], "dtype": "float32"},
                "observation.joint_pos": {"shape": [14], "dtype": "float32"},
                "observation.joint_vel": {"shape": [14], "dtype": "float32"},
                "observation.gripper_pos": {"shape": [2], "dtype": "float32"},
                "observation.base_pose": {"shape": [3], "dtype": "float32"},
                "observation.base_velocity": {"shape": [3], "dtype": "float32"},
            },
        }
        if metadata:
            meta.update(metadata)
        (dataset_dir / "metadata.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True)
        )

        try:
            return self._save_hdf5(dataset_dir)
        except ImportError:
            print("h5py not available, falling back to JSON-lines format",
                  flush=True)
            return self._save_jsonl(dataset_dir)

    def _save_hdf5(self, dataset_dir: Path) -> Path:
        import h5py
        import numpy as np

        h5_path = dataset_dir / "data.hdf5"
        n = len(self._frames)
        with h5py.File(h5_path, "w") as f:
            data = f.create_group("data")
            data.create_dataset("action", shape=(n, 17), dtype="float32")
            data.create_dataset("joint_pos", shape=(n, 14), dtype="float32")
            data.create_dataset("joint_vel", shape=(n, 14), dtype="float32")
            data.create_dataset("gripper_pos", shape=(n, 2), dtype="float32")
            data.create_dataset("base_pose", shape=(n, 3), dtype="float32")
            data.create_dataset("base_velocity", shape=(n, 3), dtype="float32")

            for i, frame in enumerate(self._frames):
                data["action"][i] = np.array(frame.action, dtype=np.float32)
                data["joint_pos"][i] = np.array(frame.joint_pos, dtype=np.float32)
                data["joint_vel"][i] = np.array(frame.joint_vel, dtype=np.float32)
                data["gripper_pos"][i] = np.array(frame.gripper_pos, dtype=np.float32)
                data["base_pose"][i] = np.array(frame.base_pose, dtype=np.float32)
                data["base_velocity"][i] = np.array(frame.base_velocity, dtype=np.float32)

        return h5_path

    def _save_jsonl(self, dataset_dir: Path) -> Path:
        import numpy as np

        lines_path = dataset_dir / "data.jsonl"
        with open(lines_path, "w") as f:
            for frame in self._frames:
                row = {
                    "action": frame.action,
                    "joint_pos": frame.joint_pos,
                    "joint_vel": frame.joint_vel,
                    "gripper_pos": frame.gripper_pos,
                    "base_pose": frame.base_pose,
                    "base_velocity": frame.base_velocity,
                }
                f.write(json.dumps(row) + "\n")
        return lines_path


def collect_frame_cpu(
    joint_names: list[str],
    joint_pos_all: list[float],
    joint_vel_all: list[float],
    gripper_left_pos: float,
    gripper_right_pos: float,
    base_x: float,
    base_y: float,
    base_yaw: float,
    base_vx: float,
    base_vy: float,
    base_wz: float,
    action: list[float] | None = None,
) -> LeRobotFrame:
    """Build a LeRobotFrame from pre-extracted scalar values (CPU-safe).

    This is the pure-math version for unit testing; the GPU-side
    collect_frame() in run_episode.py calls this after extracting
    tensors from the Isaac Sim robot articulation.
    """
    # Extract arm joint positions/velocities by name lookup
    arm_pos = [0.0] * 14
    arm_vel = [0.0] * 14
    name_to_idx = {name: i for i, name in enumerate(ARM_JOINTS)}
    for i, name in enumerate(joint_names):
        if name in name_to_idx:
            idx = name_to_idx[name]
            arm_pos[idx] = joint_pos_all[i]
            arm_vel[idx] = joint_vel_all[i]

    return LeRobotFrame(
        joint_pos=arm_pos,
        joint_vel=arm_vel,
        gripper_pos=[gripper_left_pos, gripper_right_pos],
        base_pose=[base_x, base_y, base_yaw],
        base_velocity=[base_vx, base_vy, base_wz],
        action=action if action is not None else [0.0] * 17,
    )
