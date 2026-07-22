#!/usr/bin/env python3
"""Auto-loop for Stage 2: run, check result, print guidance for next fix.

Usage:
    python scripts/task3/run_stage2_loop.py [--max-attempts N] [--skip-nav]
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE2_SCRIPT = REPO_ROOT / "scripts" / "task3" / "run_stage2_feeding.py"
DEFAULT_OUT = REPO_ROOT / "outputs" / "task3_stage2_feeding"

GUIDANCE: dict[str, str] = {
    "raise_spine": "Spine raise timed out. Try --travel-spine or increase timeout.",
    "navigation": "Navigation to island failed. Verify waypoints or try --skip-navigation.",
    "pregrasp_spoon": "Arm can't reach spoon pregrasp. Adjust --object-grasp-x-offset / y-offset or stance position.",
    "descend_spoon": "Arm can't reach spoon grasp height. The spoon may be too far: try larger x/y offsets or --skip-navigation + --spawn-at-island.",
    "close_spoon": "Gripper didn't catch the spoon. Adjust grasp position/z-offset or try --close-effort-scale 0.8.",
    "lift_spoon": "Lift timed out or spoon dropped. The spoon may not be held securely.",
    "navigate_dining": "Navigation to dining table failed. Check corridor waypoints.",
    "feed_start_pose": "Arm can't reach feed start (20cm from head). Head may be out of workspace; adjust DINING_TARGET or stance pose.",
    "feed_insertion": "Arm can't reach insertion pose (10cm from head). Adjust insertion offsets or try different HEAD_Z_OFFSET.",
    "complete": "Pipeline ran but score < 3. Check: beans_on_spoon count, hold_seconds, smooth_motion in result JSON.",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-attempts", type=int, default=20)
    parser.add_argument("--skip-nav", action="store_true")
    args = parser.parse_args()

    extra_flags = " --skip-navigation" if args.skip_nav else ""
    cmd = (
        f"python -B {STAGE2_SCRIPT} --record-video --fast-exit{extra_flags}"
    )

    for attempt in range(1, args.max_attempts + 1):
        print(f"\n{'='*60}")
        print(f"ATTEMPT {attempt}/{args.max_attempts}")
        print(f"{'='*60}")
        print(f"Running: {cmd}")
        start = time.time()

        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=600
        )
        elapsed = time.time() - start
        print(f"Wall time: {elapsed:.1f}s")

        result_json = DEFAULT_OUT / "result.json"
        if result_json.exists():
            data = json.loads(result_json.read_text())
            passed = data.get("passed", False)
            phase = data.get("failed_phase", "unknown")
            score = data.get("score", "N/A")
            print(f"Result: passed={passed}, score={score}, phase={phase}")
            guidance = GUIDANCE.get(phase, "Unknown failure mode.")
            if not passed:
                print(f"Guidance: {guidance}")
                print(f"Full result: {json.dumps(data, indent=2)}")
                suggestion_specific(data)
            else:
                print("STAGE 2 PASSED!")
                print(f"Full result: {json.dumps(data, indent=2)}")
                return
        else:
            print(f"No result.json found at {result_json}")
            print("STDERR:", result.stderr[-2000:] if result.stderr else "NONE")
            print("STDOUT:", result.stdout[-2000:] if result.stdout else "NONE")

        if attempt < args.max_attempts:
            print("\nWaiting before next attempt...")
            time.sleep(5)


def suggestion_specific(data: dict) -> None:
    phase = data.get("failed_phase", "")
    if phase == "pregrasp_spoon":
        spoon_pos = [
            p for p in data.get("phases", []) if p.get("phase") == "scene_loaded"
        ]
        if spoon_pos:
            s = spoon_pos[0].get("spoon_start", [0, 0, 0])
            print(f"  Spoon at ({s[0]:.3f}, {s[1]:.3f}, {s[2]:.3f})")
            print(f"  Suggested fix: --object-grasp-x-offset 0.06 --object-grasp-y-offset 0.02")
    elif phase == "feed_start_pose" or phase == "feed_insertion":
        head_pos = [
            p for p in data.get("phases", []) if p.get("phase") == "head_found"
        ]
        if head_pos:
            h = head_pos[0].get("head", [0, 0, 0])
            print(f"  Head at ({h[0]:.3f}, {h[1]:.3f}, {h[2]:.3f})")
            print(f"  Suggested fix: adjust DINING_TARGET constant or use full nav instead of skip-nav")


if __name__ == "__main__":
    main()
