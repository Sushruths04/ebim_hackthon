#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Optimize physical cup-grasp parameters with fresh Isaac processes."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER = REPO_ROOT / "scripts" / "task3" / "verify_grasp_lift.py"

TARGET_LIFT_M = 0.08
TARGET_HOLD_S = 3.0
SUCCESS_LIFT_M = 0.02
SUCCESS_HOLD_S = 1.0
CONTACT_MIN_RAD = 0.05
CONTACT_MAX_RAD = 0.90


@dataclass(frozen=True)
class GraspParameters:
    """One physical grasp trial's tunable controls."""

    y_offset: float
    close_ramp_seconds: float
    close_effort_scale: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def contact_strength(result: dict[str, Any]) -> float:
    """Score a blocked close while rejecting empty and fully closed jaws."""
    for phase in result.get("phases", []):
        if phase.get("phase") != "close":
            continue
        position = phase.get("gripper_position_rad")
        if not isinstance(position, (float, int)):
            return 0.0
        position = float(position)
        if not CONTACT_MIN_RAD < position < CONTACT_MAX_RAD:
            return 0.0
        span = CONTACT_MAX_RAD - CONTACT_MIN_RAD
        return 1.0 - _clamp((position - CONTACT_MIN_RAD) / span, 0.0, 1.0)
    return 0.0


def score_result(result: dict[str, Any]) -> tuple[float, bool]:
    """Return continuous optimization score and the lower binary gate."""
    lift = float(result.get("cup_lift_m", 0.0))
    hold = float(result.get("continuous_hold_seconds", 0.0))
    score = (
        0.4 * _clamp(lift / TARGET_LIFT_M, 0.0, 1.0)
        + 0.3 * _clamp(hold / TARGET_HOLD_S, 0.0, 1.0)
        + 0.3 * contact_strength(result)
    )
    success = lift >= SUCCESS_LIFT_M and hold >= SUCCESS_HOLD_S
    return score, success


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "grasp_opt",
    )
    parser.add_argument(
        "--proof-dir",
        type=Path,
        default=REPO_ROOT / "proofs" / "grasp_optimization",
    )
    parser.add_argument(
        "--launcher",
        type=Path,
        default=Path("/workspace/isaaclab/isaaclab.sh"),
    )
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    return parser.parse_args()


def run_trial(
    *,
    trial: int,
    parameters: GraspParameters,
    output_dir: Path,
    launcher: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Launch one full-route verifier process and persist its summary."""
    trial_dir = output_dir / f"trial_{trial:03d}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    log_path = trial_dir / "run.log"
    command = [
        str(launcher),
        "-p",
        str(VERIFIER),
        "--object-name",
        "cup",
        "--transport-to-dining",
        "--record-video",
        "--fast-exit",
        "--min-lift-m",
        f"{SUCCESS_LIFT_M:.6f}",
        "--cup-grasp-y-offset",
        f"{parameters.y_offset:.6f}",
        "--grasp-ramp-seconds",
        f"{parameters.close_ramp_seconds:.6f}",
        "--close-effort-scale",
        f"{parameters.close_effort_scale:.6f}",
        "--out-dir",
        str(trial_dir),
    ]
    started = time.monotonic()
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_seconds,
            )
        result_path = trial_dir / "result.json"
        raw_result = (
            json.loads(result_path.read_text(encoding="utf-8"))
            if result_path.exists()
            else {"returncode": completed.returncode, "status": "NO_RESULT"}
        )
    except subprocess.TimeoutExpired:
        raw_result = {"status": "TIMEOUT"}
    score, success = score_result(raw_result)
    record = {
        "trial": trial,
        "parameters": asdict(parameters),
        "result": raw_result,
        "score": round(score, 6),
        "success": success,
        "wall_time_seconds": round(time.monotonic() - started, 3),
    }
    (output_dir / f"trial_{trial:03d}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def main() -> None:
    args = parse_args()
    if args.trials < 5:
        raise ValueError("--trials must be at least 5 for GP initialization")
    if args.timeout_seconds <= 0.0:
        raise ValueError("--timeout-seconds must be positive")
    try:
        from skopt import gp_minimize
        from skopt.space import Real
    except ImportError as error:
        raise RuntimeError(
            "Install requirements-task3-optimizer.txt before running this "
            "optimizer."
        ) from error

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trials: list[dict[str, Any]] = []

    def objective(values: list[float]) -> float:
        parameters = GraspParameters(
            y_offset=values[0],
            close_ramp_seconds=values[1],
            close_effort_scale=values[2],
        )
        record = run_trial(
            trial=len(trials) + 1,
            parameters=parameters,
            output_dir=args.output_dir,
            launcher=args.launcher,
            timeout_seconds=args.timeout_seconds,
        )
        trials.append(record)
        print(
            "TRIAL "
            f"{record['trial']}: y={parameters.y_offset:.4f} "
            f"ramp={parameters.close_ramp_seconds:.2f}s "
            f"force={parameters.close_effort_scale:.3f} "
            f"→ score={record['score']:.3f} "
            f"success={record['success']}",
            flush=True,
        )
        return -float(record["score"])

    result = gp_minimize(
        objective,
        [
            Real(0.04, 0.06, name="y_offset"),
            Real(0.5, 2.0, name="close_ramp_seconds"),
            Real(0.05, 0.25, name="close_effort_scale"),
        ],
        n_calls=args.trials,
        n_initial_points=5,
        random_state=42,
    )
    best = GraspParameters(*result.x)
    success_rate = sum(bool(trial["success"]) for trial in trials) / len(
        trials
    )
    summary = {
        "best_parameters": asdict(best),
        "best_score": round(-float(result.fun), 6),
        "success_rate": success_rate,
        "trials": trials,
    }
    args.proof_dir.mkdir(parents=True, exist_ok=True)
    (args.proof_dir / "result.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "BEST: "
        f"y={best.y_offset:.4f} "
        f"ramp={best.close_ramp_seconds:.2f}s "
        f"force={best.close_effort_scale:.3f} "
        f"(success rate: {success_rate:.2%})",
        flush=True,
    )


if __name__ == "__main__":
    main()
