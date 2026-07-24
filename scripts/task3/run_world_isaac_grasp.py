#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""GPU harness for task3_pipeline.world_isaac.IsaacWorld -- T2 gate.

Exercises reach -> grasp -> lift -> hold for ONE Stage-1 object through the
newly-wired IsaacWorld (task3_pipeline/world_isaac.py), reusing the same
proven geometry as scripts/task3/verify_grasp_lift.py but routed through the
real WorldAdapter interface the orchestrator/verifier/policy use. Start with
--object-name cup (the proven 10/10 grasp); the reach-fix stance offset is
currently only calibrated for the "east" approach used by the cup.

Prints one WORLD_ISAAC_GRASP_RESULT JSON line; exit 0 iff the honest verifier
(task3_pipeline.outcomes.classify_grasp on the grasp metrics, plus a measured
lift) accepts the run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object-name", default="cup",
                        choices=("cup", "bowl2", "spoon2", "plate2"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--skip-navigation", action="store_true",
                        help="Spawn close to the kitchen stance for fast "
                        "GPU iteration (still drives the final reach leg "
                        "through real navigate_to/reach code).")
    parser.add_argument("--min-lift-m", type=float, default=0.05)
    parser.add_argument("--hold-seconds", type=float, default=3.0)
    parser.add_argument("--fast-exit", action="store_true")
    parser.add_argument(
        "--out-dir", type=Path,
        default=REPO_ROOT / "outputs" / "task3_world_isaac_grasp",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    started_at = time.time()

    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher({
        "headless": True,
        "enable_cameras": bool(args.record_video),
        "livestream": -1,
    })
    simulation_app = app_launcher.app
    try:
        result = _run(args, out_dir)
        result["wall_time_seconds"] = round(time.time() - started_at, 3)
        (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
        print("WORLD_ISAAC_GRASP_RESULT " + json.dumps(result, sort_keys=True), flush=True)
        sys.stdout.flush()
        if args.fast_exit:
            os._exit(0 if result["passed"] else 1)
    except BaseException:
        traceback.print_exc()
        (out_dir / "crash_traceback.txt").write_text(traceback.format_exc())
        sys.stderr.flush()
        if args.fast_exit:
            os._exit(2)
        simulation_app.close()
        raise
    else:
        simulation_app.close()
        if not result["passed"]:
            raise SystemExit(1)


def _run(args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    from task3_pipeline import config
    from task3_pipeline.outcomes import classify_grasp, classify_lift, classify_reach
    from task3_pipeline.world_isaac import IsaacWorld

    world = IsaacWorld(
        record_video=args.record_video,
        out_dir=str(out_dir),
        object_names=(args.object_name,),
        skip_navigation=args.skip_navigation,
    )
    world.reset(seed=args.seed, head_placement="a")

    object_start = world.object_position(args.object_name)

    reach_metrics = world.reach("right", args.object_name, approach_stance="east")
    reach_outcome, reach_diag = classify_reach(reach_metrics)

    grasp_metrics = world.grasp("right", args.object_name)
    grasp_outcome, grasp_diag = classify_grasp(grasp_metrics)

    # Lift toward the proven LIFT_Z (verify_grasp_lift.py), computed from the
    # live right-EE height so this is not a hardcoded per-episode value.
    vgl = world._m["vgl"]
    current_ee_z = world.arms.ee_world_poses()[1][0][2]
    dz = max(0.0, vgl.LIFT_Z - current_ee_z)
    lift_metrics = world.lift("right", dz)
    lift_outcome, lift_diag = classify_lift(lift_metrics)

    hold_metrics = world.hold(args.hold_seconds, side="right")

    object_end = world.object_position(args.object_name)

    passed = (
        reach_outcome.value == "success"
        and grasp_outcome.value == "success"
        and lift_outcome.value == "success"
        and hold_metrics["held_seconds"] >= args.hold_seconds
    )

    return {
        "passed": bool(passed),
        "object_name": args.object_name,
        "seed": args.seed,
        "skip_navigation": args.skip_navigation,
        "object_start": [round(v, 4) for v in object_start],
        "object_end": [round(v, 4) for v in object_end],
        "object_lift_m": round(object_end[2] - object_start[2], 4),
        "reach": {"metrics": reach_metrics, "outcome": reach_outcome.value, "diagnosis": reach_diag},
        "grasp": {"metrics": grasp_metrics, "outcome": grasp_outcome.value, "diagnosis": grasp_diag},
        "lift": {"metrics": lift_metrics, "outcome": lift_outcome.value, "diagnosis": lift_diag},
        "hold": hold_metrics,
        "min_lift_m": args.min_lift_m,
        "hold_seconds": args.hold_seconds,
        "phases": world.phases,
        "sim_dt": world.sim.cfg.dt,
    }


if __name__ == "__main__":
    main()
