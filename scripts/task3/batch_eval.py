#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Phase 5 batch evaluation: 3 head placements x 5 seeds = 15 headless runs.

Runs every combination headlessly, collects result.json per run, and
produces a summary table in docs/eval_results.md.  Designed for the
SIM-EVAL spot instance — runs sequentially to stay within the single-GPU
quota.

Usage (inside the Isaac Lab container on the GPU box):

  python scripts/task3/batch_eval.py \
      --policy scripted \
      --max-seconds 120 \
      --out-dir /workspace/EBiM_Challenge/outputs/phase5_batch

  # Or with idle policy for a quick sanity check:
  python scripts/task3/batch_eval.py --policy idle --max-seconds 8

The script calls run_episode.py for each run via subprocess.  If any
run crashes, the error is logged and the batch continues.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_EPISODE = REPO_ROOT / "scripts" / "task3" / "run_episode.py"
EVAL_RESULTS = REPO_ROOT / "docs" / "eval_results.md"

# Phase 5 matrix: 3 head placements x 5 seeds
HEAD_PLACEMENTS = ("a", "c", "e")
SEEDS = (42, 123, 456, 789, 2026)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Phase 5 evaluation matrix (15 headless runs)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--policy",
        choices=("idle", "scripted"),
        default="scripted",
    )
    p.add_argument("--max-seconds", type=float, default=120.0)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "phase5_batch",
    )
    p.add_argument(
        "--headless-app",
        type=str,
        default=None,
        help="Path to isaaclab.sh or the Isaac Lab launcher.  If None, "
        "runs run_episode.py directly (assumes the Kit/Isaac environment "
        "is already active, e.g. inside the container).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the run plan without executing.",
    )
    return p.parse_args()


def run_one(
    seed: int,
    head_placement: str,
    args: argparse.Namespace,
    run_index: int,
    total: int,
) -> dict:
    """Execute one episode and return its result dict (or an error dict)."""
    tag = f"[{run_index}/{total}] seed={seed} head={head_placement}"
    print(f"\n{'='*60}\n{tag}\n{'='*60}", flush=True)

    cmd = [
        sys.executable,
        str(RUN_EPISODE),
        "--seed", str(seed),
        "--head-placement", head_placement,
        "--policy", args.policy,
        "--max-seconds", str(args.max_seconds),
        "--record-video",
        "--out-dir", str(args.out_dir),
    ]
    if args.headless_app:
        cmd = [args.headless_app, "-p"] + cmd[1:]  # strip python; use launcher

    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(args.max_seconds * 3 + 120),  # generous timeout
            cwd=str(REPO_ROOT),
        )
        wall = time.time() - started

        # Parse EPISODE_RESULT from stdout
        result = None
        for line in proc.stdout.splitlines():
            if line.startswith("EPISODE_RESULT "):
                result = json.loads(line[len("EPISODE_RESULT "):])
                break

        if result is None:
            return {
                "seed": seed,
                "head_placement": head_placement,
                "status": "NO_RESULT",
                "wall_time_seconds": round(wall, 2),
                "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            }

        result["batch_wall_time_seconds"] = round(wall, 2)
        result["status"] = "OK"
        return result

    except subprocess.TimeoutExpired:
        return {
            "seed": seed,
            "head_placement": head_placement,
            "status": "TIMEOUT",
            "wall_time_seconds": round(time.time() - started, 2),
        }
    except Exception as exc:
        return {
            "seed": seed,
            "head_placement": head_placement,
            "status": f"ERROR: {exc}",
            "wall_time_seconds": round(time.time() - started, 2),
        }


def build_summary_table(results: list[dict]) -> str:
    """Build a markdown table summarizing the batch."""
    lines = [
        "| # | Seed | Head | Status | Stage1 | Stage3 | Stage4 | Wall (s) |",
        "|---|------|------|--------|--------|--------|--------|----------|",
    ]
    for i, r in enumerate(results, 1):
        status = r.get("status", "?")
        wall = r.get("batch_wall_time_seconds", r.get("wall_time_seconds", "?"))
        s1 = s3 = s4 = "-"
        for stage in r.get("stages", []):
            sn = stage.get("stage", "")
            sc = stage.get("score", "?")
            sm = stage.get("max_score", "?")
            if sn == "stage1":
                s1 = f"{sc}/{sm}"
            elif sn == "stage3":
                s3 = f"{sc}/{sm}"
            elif sn == "stage4":
                s4 = f"{sc}/{sm}"
        lines.append(f"| {i} | {r.get('seed','-')} | {r.get('head_placement','-')} | {status} | {s1} | {s3} | {s4} | {wall} |")

    # Aggregate stats
    ok = [r for r in results if r.get("status") == "OK"]
    if ok:
        lines.append("")
        lines.append(f"**{len(ok)}/{len(results)} runs completed successfully.**")
        # Average scores per stage
        for stage_name in ("stage1", "stage3", "stage4"):
            scores = []
            for r in ok:
                for s in r.get("stages", []):
                    if s.get("stage") == stage_name:
                        scores.append(s.get("score", 0))
            if scores:
                avg = sum(scores) / len(scores)
                mx = max((s.get("max_score", 0) for r in ok for s in r.get("stages", []) if s.get("stage") == stage_name), default=0)
                lines.append(f"- {stage_name}: avg {avg:.1f}/{mx}")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    runs = [
        (seed, hp)
        for hp in HEAD_PLACEMENTS
        for seed in SEEDS
    ]
    total = len(runs)

    print(f"Phase 5 batch: {total} runs "
          f"({len(HEAD_PLACEMENTS)} heads x {len(SEEDS)} seeds)")
    print(f"Policy: {args.policy}, max-seconds: {args.max_seconds}")
    print(f"Output: {args.out_dir}")

    if args.dry_run:
        for i, (seed, hp) in enumerate(runs, 1):
            print(f"  [{i}/{total}] seed={seed} head={hp}")
        return

    results = []
    batch_started = time.time()

    for i, (seed, hp) in enumerate(runs, 1):
        r = run_one(seed, hp, args, i, total)
        results.append(r)
        # Save individual result
        tag = f"seed{seed}_{hp}"
        individual_dir = args.out_dir / tag
        individual_dir.mkdir(parents=True, exist_ok=True)
        (individual_dir / "result.json").write_text(
            json.dumps(r, indent=2, sort_keys=True)
        )

    batch_wall = time.time() - batch_started

    # Save combined results
    summary = {
        "total_runs": total,
        "policy": args.policy,
        "max_seconds": args.max_seconds,
        "batch_wall_time_seconds": round(batch_wall, 2),
        "results": results,
    }
    (args.out_dir / "batch_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )

    # Build and print the table
    table = build_summary_table(results)
    print(f"\n{'='*60}\nBATCH SUMMARY\n{'='*60}")
    print(table)

    # Append to eval_results.md
    from datetime import time as dtime
    import subprocess as sp

    try:
        commit = sp.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT
        ).decode().strip()
    except Exception:
        commit = "unknown"

    date_str = time.strftime("%Y-%m-%d")
    ok_count = sum(1 for r in results if r.get("status") == "OK")
    entry = (
        f"| {date_str} | phase5-batch ({args.policy}) | {commit} | "
        f"{ok_count}/{total} runs OK | `proofs/phase5-batch/` |"
    )

    if EVAL_RESULTS.exists():
        content = EVAL_RESULTS.read_text()
    else:
        content = "# Task 3 Evaluation Results Log\n\n"
    if not content.endswith("\n"):
        content += "\n"
    content += entry + "\n"
    EVAL_RESULTS.write_text(content)

    print(f"\nAppended to {EVAL_RESULTS}: {entry}")
    print(f"Batch complete: {ok_count}/{total} OK in {batch_wall:.0f}s")


if __name__ == "__main__":
    main()
