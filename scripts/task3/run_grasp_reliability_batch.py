#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Run the frozen grasp/lift verifier sequentially and summarize reliability.

This host/container-side wrapper launches a fresh Isaac process per trial.
The verifier's ``--fast-exit`` avoids Kit shutdown hangs after its result has
already been persisted.  No two trials overlap on the single GPU.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER = REPO_ROOT / "scripts" / "task3" / "verify_grasp_lift.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--required-rate", type=float, default=0.8)
    parser.add_argument(
        "--launcher",
        type=Path,
        default=Path("/workspace/isaaclab/isaaclab.sh"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "task3_grasp_reliability",
    )
    parser.add_argument("--timeout-seconds", type=float, default=480.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.trials <= 0 or not 0.0 < args.required_rate <= 1.0:
        raise ValueError("trials must be positive and required-rate in (0, 1]")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    required_passes = math.ceil(args.trials * args.required_rate)
    results: list[dict] = []
    batch_started = time.time()

    for trial in range(1, args.trials + 1):
        trial_dir = args.out_dir / f"trial_{trial:02d}"
        trial_dir.mkdir(parents=True, exist_ok=True)
        log_path = trial_dir / "run.log"
        command = [
            str(args.launcher),
            "-p",
            str(VERIFIER),
            "--skip-navigation",
            "--fast-exit",
            "--out-dir",
            str(trial_dir),
        ]
        started = time.time()
        print(
            f"GRASP_BATCH trial={trial}/{args.trials} status=START",
            flush=True,
        )
        try:
            with log_path.open("w", encoding="utf-8") as log_file:
                process = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    timeout=args.timeout_seconds,
                    check=False,
                )
            result_path = trial_dir / "result.json"
            if result_path.exists():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                result["status"] = "PASS" if result.get("passed") else "FAIL"
            else:
                result = {
                    "passed": False,
                    "status": "NO_RESULT",
                    "returncode": process.returncode,
                }
        except subprocess.TimeoutExpired:
            result = {"passed": False, "status": "TIMEOUT"}

        result["trial"] = trial
        result["batch_wall_time_seconds"] = round(time.time() - started, 3)
        results.append(result)
        pass_count = sum(bool(item.get("passed")) for item in results)
        print(
            "GRASP_BATCH "
            f"trial={trial}/{args.trials} status={result['status']} "
            f"lift_m={result.get('cup_lift_m')} passes={pass_count}",
            flush=True,
        )

    pass_count = sum(bool(item.get("passed")) for item in results)
    summary = {
        "trials": args.trials,
        "required_rate": args.required_rate,
        "required_passes": required_passes,
        "pass_count": pass_count,
        "pass_rate": pass_count / args.trials,
        "gate_passed": pass_count >= required_passes,
        "batch_wall_time_seconds": round(time.time() - batch_started, 3),
        "results": results,
    }
    (args.out_dir / "batch_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "GRASP_BATCH_RESULT " + json.dumps(summary, sort_keys=True),
        flush=True,
    )
    raise SystemExit(0 if summary["gate_passed"] else 1)


if __name__ == "__main__":
    main()
