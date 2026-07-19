# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Small, dependency-free recorder for interactive Task 3 teleop probes."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

MARKER_LABELS = {
    "1": "probe_start",
    "2": "overhang_reached",
    "3": "pinch_closed",
    "4": "lift_attempt",
    "5": "release_or_failure",
}


def _vector(values: Any) -> list[float]:
    return [float(value) for value in values]


def _pose(pose: Any) -> dict[str, list[float]]:
    return {
        "position": _vector(pose.position),
        "orientation_wxyz": _vector(pose.orientation_wxyz),
    }


class TeleopEpisodeRecorder:
    """Write sampled commands, targets, and operator phase markers.

    The output is intentionally plain JSONL rather than a training dataset.
    It is meant to make a successful human probe easy to inspect and transcribe
    into the autonomous FSM without claiming that it is LeRobot-compatible.
    """

    def __init__(
        self,
        output_dir: Path,
        episode_name: str,
        *,
        sample_every_steps: int = 10,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if sample_every_steps < 1:
            raise ValueError("sample_every_steps must be positive")
        if Path(episode_name).name != episode_name:
            raise ValueError("episode_name must be a single directory name")

        self.episode_dir = (output_dir / episode_name).resolve()
        if self.episode_dir.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing episode: {self.episode_dir}"
            )
        self.episode_dir.mkdir(parents=True, exist_ok=False)
        self.sample_every_steps = sample_every_steps
        self._previous_keys: set[str] = set()
        self._steps = 0
        self._records = 0
        self._started_at = time.time()
        self._closed = False
        self._samples = (self.episode_dir / "teleop.jsonl").open(
            "w", encoding="utf-8"
        )
        self._write_json(
            self.episode_dir / "metadata.json",
            {
                "schema_version": 1,
                "format": "ebim_task3_teleop_probe",
                "created_unix": self._started_at,
                "sample_every_steps": sample_every_steps,
                "marker_keys": MARKER_LABELS,
                **(metadata or {}),
            },
        )

    @property
    def output_path(self) -> Path:
        return self.episode_dir

    def record(
        self,
        *,
        step: int,
        sim_time: float,
        keys: set[str],
        command: Any,
        targets: Any,
        root_position: Any,
        root_orientation: Any,
        left_world: Any,
        right_world: Any,
    ) -> None:
        """Record one control iteration or a marker key edge."""
        if self._closed:
            raise RuntimeError("cannot record after close")

        normalized_keys = {str(key).lower() for key in keys}
        marker_edges = normalized_keys - self._previous_keys
        markers = [
            MARKER_LABELS[key]
            for key in sorted(marker_edges)
            if key in MARKER_LABELS
        ]
        self._previous_keys = normalized_keys
        self._steps = max(self._steps, step + 1)
        if step % self.sample_every_steps != 0 and not markers:
            return

        record = {
            "step": step,
            "sim_time": float(sim_time),
            "keys": sorted(normalized_keys),
            "markers": markers,
            "command": {
                "base_twist": _vector(command.base_twist),
                "toggle_left_gripper": bool(command.toggle_left_gripper),
                "toggle_right_gripper": bool(command.toggle_right_gripper),
            },
            "targets": {
                "left": _pose(targets.left),
                "right": _pose(targets.right),
                "left_gripper": float(targets.left_gripper),
                "right_gripper": float(targets.right_gripper),
                "spine": float(targets.spine),
            },
            "world": {
                "root_position": _vector(root_position),
                "root_orientation_wxyz": _vector(root_orientation),
                "left_ee": _pose(left_world),
                "right_ee": _pose(right_world),
            },
        }
        self._samples.write(json.dumps(record, separators=(",", ":")))
        self._samples.write("\n")
        self._records += 1

    def close(self, *, reason: str = "operator_exit") -> None:
        if self._closed:
            return
        self._closed = True
        self._samples.flush()
        self._samples.close()
        self._write_json(
            self.episode_dir / "summary.json",
            {
                "schema_version": 1,
                "reason": reason,
                "steps_seen": self._steps,
                "records_written": self._records,
                "duration_seconds": time.time() - self._started_at,
                "teleop_jsonl": str(self.episode_dir / "teleop.jsonl"),
            },
        )

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
