#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Run or print the reduced Task 3 head-placement/seed matrix.

This is a sequential launcher because a single GPU VM is the project
constraint.  It does not assume that a failed run produced a result file and
records process status alongside every episode.  Use ``--dry-run`` on a CPU
machine to inspect the exact commands without starting Isaac Sim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "scripts" / "task3" / "run_episode.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4]
    )
    parser.add_argument(
        "--head-placements", nargs="+", default=["a", "b", "c"]
    )
    parser.add_argument(
        "--policy", choices=("idle", "scripted"), default="scripted"
    )
    parser.add_argument(
        "--launcher",
        type=str,
        default="/workspace/isaaclab/isaaclab.sh",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_matrix",
    )
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.seeds or not args.head_placements:
        raise ValueError("seeds and head placements must be non-empty")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    started = time.time()
    for seed in args.seeds:
        for placement in args.head_placements:
            command = [
                str(args.launcher),
                "-p",
                str(RUNNER),
                "--seed",
                str(seed),
                "--head-placement",
                placement,
                "--policy",
                args.policy,
                "--max-seconds",
                str(args.max_seconds),
                "--out-dir",
                str(args.out_dir),
            ]
            if args.record_video:
                command.append("--record-video")
            record = {
                "seed": seed,
                "head_placement": placement,
                "command": command,
            }
            print(
                "MATRIX_RUN " + json.dumps(record, sort_keys=True), flush=True
            )
            if not args.dry_run:
                run_started = time.time()
                completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
                record["returncode"] = completed.returncode
                record["wall_time_seconds"] = round(
                    time.time() - run_started, 3
                )
                result = (
                    args.out_dir / f"seed{seed}_{placement}" / "result.json"
                )
                record["result_path"] = str(result)
                if result.is_file():
                    record["result"] = json.loads(
                        result.read_text(encoding="utf-8")
                    )
            records.append(record)
    summary = {
        "seeds": args.seeds,
        "head_placements": args.head_placements,
        "policy": args.policy,
        "dry_run": args.dry_run,
        "episodes": records,
        "wall_time_seconds": round(time.time() - started, 3),
    }
    summary_path = args.out_dir / "matrix_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("MATRIX_RESULT " + json.dumps(summary, sort_keys=True), flush=True)
    if not args.dry_run and any(
        record.get("returncode", 1) != 0 for record in records
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
