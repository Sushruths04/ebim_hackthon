# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""CPU coverage for task3_autonomy/recording.py's pure parts.

RunRecorder's Isaac/Replicator-dependent methods (setup()/capture() real
frame pulls) cannot be exercised without Isaac Sim, which is not available
on this machine. This covers everything that can run on plain Python: the
GIF encoder, the text overlay, a disabled recorder's no-op guarantees, and
the max-frame-cap predicate that gates capture().
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from task3_autonomy.recording import (  # noqa: E402
    RunRecorder,
    _overlay,
    encode_gif,
    next_frame_path,
    should_capture,
)


def _make_png(
    path: Path,
    size: tuple[int, int] = (16, 12),
    color: tuple[int, int, int] = (10, 20, 30),
) -> None:
    from PIL import Image

    Image.new("RGB", size, color=color).save(path)


def test_encode_gif_produces_valid_multi_frame_gif(tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    colors = [(10, 20, 30), (200, 30, 40), (30, 200, 60)]
    for index, color in enumerate(colors):
        _make_png(next_frame_path(frames_dir, index), color=color)

    output = tmp_path / "run.gif"
    result = encode_gif(frames_dir, output, duration_ms=100)

    assert result == output
    assert output.exists()
    from PIL import Image

    with Image.open(output) as gif:
        assert gif.is_animated
        assert gif.n_frames == 3


def test_encode_gif_raises_on_empty_dir(tmp_path):
    frames_dir = tmp_path / "empty_frames"
    frames_dir.mkdir()
    with pytest.raises(RuntimeError):
        encode_gif(frames_dir, tmp_path / "run.gif")


def test_overlay_returns_same_size_image_and_mutates_pixels():
    from PIL import Image

    width, height = 64, 48
    original = Image.new("RGB", (width, height), color=(0, 0, 0))
    fresh = Image.new("RGB", (width, height), color=(0, 0, 0))

    result = _overlay(original, "edge_pinch", ["tick 42", "overhang 5.0 cm"])

    assert result is original
    assert result.size == (width, height)
    assert list(result.convert("RGB").getdata()) != list(
        fresh.convert("RGB").getdata()
    )


def test_overlay_handles_no_lines():
    from PIL import Image

    image = Image.new("RGB", (32, 32), color=(255, 255, 255))
    result = _overlay(image, "push_result")
    assert result.size == (32, 32)


def test_disabled_recorder_setup_is_a_safe_noop(tmp_path):
    recorder = RunRecorder(tmp_path / "run_out", enabled=False)
    assert recorder.setup() is None
    assert not (tmp_path / "run_out").exists()


def test_disabled_recorder_capture_is_a_safe_noop(tmp_path):
    recorder = RunRecorder(tmp_path / "run_out", enabled=False)
    recorder.setup()
    assert recorder.capture("some_phase", lines=["tick 1"]) is None
    assert not (tmp_path / "run_out").exists()


def test_disabled_recorder_finish_is_a_safe_noop_returning_none(tmp_path):
    recorder = RunRecorder(tmp_path / "run_out", enabled=False)
    recorder.setup()
    recorder.capture("some_phase")
    assert recorder.finish("run.gif") is None
    assert not (tmp_path / "run_out").exists()


def test_disabled_recorder_creates_no_files_end_to_end(tmp_path):
    output_dir = tmp_path / "run_out"
    recorder = RunRecorder(output_dir, enabled=False)
    recorder.setup()
    for name in ("phase_a", "phase_b", "phase_c"):
        recorder.capture(name, lines=[f"tick {name}"])
    gif_path = recorder.finish("run.gif")
    assert gif_path is None
    assert not output_dir.exists()


def test_should_capture_predicate_respects_max_frames_cap():
    max_frames = 3
    frame_count = 0
    attempts = 10
    captured = 0
    for _ in range(attempts):
        if should_capture(frame_count, max_frames):
            frame_count += 1
            captured += 1
    assert captured == max_frames
    assert frame_count == max_frames


def test_next_frame_path_zero_pads_and_increments(tmp_path):
    assert next_frame_path(tmp_path, 0) == tmp_path / "rgb_0000.png"
    assert next_frame_path(tmp_path, 42) == tmp_path / "rgb_0042.png"
    assert next_frame_path(tmp_path, 9999) == tmp_path / "rgb_9999.png"


def test_run_recorder_default_construction_does_not_touch_disk(tmp_path):
    # Constructing (not calling setup()) must never create anything, even
    # when enabled -- all Isaac/PIL work is deferred to setup()/capture().
    output_dir = tmp_path / "never_created"
    recorder = RunRecorder(output_dir)
    assert recorder.enabled is True
    assert recorder.frames_dir == output_dir / "frames"
    assert not output_dir.exists()
