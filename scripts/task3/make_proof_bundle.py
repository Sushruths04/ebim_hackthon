#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Assemble a proof bundle for a completed task.

Copies the video, result JSON, and repro command into proofs/<slug>/,
then appends a one-line entry to docs/eval_results.md.  Meant to be
called after a successful verification run.

Usage:
  python scripts/task3/make_proof_bundle.py \
      --slug phase3-stage1 \
      --task "Stage 1 FSM: pickup -> transport -> place" \
      --video outputs/task3_episodes/seed42_a/episode.gif \
      --result outputs/task3_episodes/seed42_a/result.json \
      --repro "python scripts/task3/run_episode.py --seed 42 --head-placement a --policy scripted --record-video"

  # Or pipe a repro.txt directly:
  python scripts/task3/make_proof_bundle.py \
      --slug phase2-skills \
      --task "reach/grasp/lift gate" \
      --video outputs/task3_grasp/run10/episode.gif \
      --result outputs/task3_grasp/run10/result.json \
      --repro-file outputs/task3_grasp/run10/repro.txt
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_RESULTS = REPO_ROOT / "docs" / "eval_results.md"
PROOFS_DIR = REPO_ROOT / "proofs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Assemble a proof bundle and log it in eval_results.md",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--slug",
        required=True,
        help="Directory name under proofs/ (e.g. phase3-stage1, v0.1-skills).",
    )
    p.add_argument(
        "--task",
        required=True,
        help="One-line task description for the eval_results table.",
    )
    p.add_argument("--video", type=Path, help="Path to the proof video/gif.")
    p.add_argument(
        "--result",
        type=Path,
        required=True,
        help="Path to the result.json (EPISODE_RESULT or test output).",
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--repro",
        type=str,
        help="One-line reproduce command (written to repro.txt).",
    )
    group.add_argument(
        "--repro-file",
        type=Path,
        help="Existing repro.txt to copy into the bundle.",
    )
    p.add_argument(
        "--extra",
        nargs="*",
        type=Path,
        help="Additional files to include (e.g. proof.txt, debug logs).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without writing anything.",
    )
    return p.parse_args()


def git_commit_hash() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def main() -> None:
    args = parse_args()
    bundle_dir = PROOFS_DIR / args.slug

    if args.dry_run:
        print(f"[dry-run] Would create {bundle_dir}/")
        if args.video:
            print(f"[dry-run]   video:  {args.video.name}")
        print(f"[dry-run]   result: {args.result.name}")
        if args.repro:
            print(f"[dry-run]   repro:  {args.repro}")
        print(f"[dry-run] Append to {EVAL_RESULTS}")
        return

    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Copy result JSON
    dst_result = bundle_dir / args.result.name
    shutil.copy2(args.result, dst_result)
    print(f"Copied {args.result.name} -> {dst_result}")

    # Copy or write video
    if args.video and args.video.exists():
        dst_video = bundle_dir / args.video.name
        shutil.copy2(args.video, dst_video)
        print(f"Copied {args.video.name} -> {dst_video}")

    # Copy or write repro
    if args.repro_file:
        shutil.copy2(args.repro_file, bundle_dir / "repro.txt")
        print(f"Copied repro.txt from {args.repro_file}")
    elif args.repro:
        (bundle_dir / "repro.txt").write_text(args.repro + "\n")
        print(f"Wrote repro.txt")

    # Copy extra files
    if args.extra:
        for extra_path in args.extra:
            if extra_path.exists():
                shutil.copy2(extra_path, bundle_dir / extra_path.name)
                print(f"Copied extra: {extra_path.name}")

    # Read result for the eval_results entry
    try:
        result_data = json.loads(dst_result.read_text())
    except (json.JSONDecodeError, OSError):
        result_data = {}

    score_parts = []
    for stage in result_data.get("stages", []):
        s = stage.get("score", "?")
        m = stage.get("max_score", "?")
        score_parts.append(f"{stage.get('stage','?')}={s}/{m}")
    score_str = ", ".join(score_parts) if score_parts else "n/a"

    commit = git_commit_hash()
    date_str = time.strftime("%Y-%m-%d")
    proof_link = f"`proofs/{args.slug}/`"

    entry = f"| {date_str} | {args.task} | {commit} | {score_str} | {proof_link} |"

    # Append to eval_results.md
    if EVAL_RESULTS.exists():
        content = EVAL_RESULTS.read_text()
    else:
        content = "# Task 3 Evaluation Results Log\n\n"

    # Ensure trailing newline
    if not content.endswith("\n"):
        content += "\n"
    content += entry + "\n"
    EVAL_RESULTS.write_text(content)
    print(f"Appended entry to {EVAL_RESULTS}")
    print(f"\nEntry:\n{entry}")


if __name__ == "__main__":
    main()
