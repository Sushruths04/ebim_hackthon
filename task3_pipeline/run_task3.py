# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Entry point for one (or a matrix of) autonomous Task 3 episode(s).

    # CPU smoke test / logic demo -- no Isaac needed:
    python -m task3_pipeline.run_task3 --mock --seed 42 --head-placement a

    # Full unattended matrix (the "18 manual runs", automated):
    python -m task3_pipeline.run_task3 --mock --matrix

    # Real robot (on an RTX host inside the Isaac container):
    python -m task3_pipeline.run_task3 --seed 42 --head-placement a --record-video

The only difference between mock and real is which WorldAdapter is constructed;
the orchestrator, verifier, memory and retry logic are identical.
"""

from __future__ import annotations

import argparse
import statistics

from task3_pipeline.orchestrator import Task3Pipeline
from task3_pipeline.world import MockWorld

HEAD_PLACEMENTS = tuple("abcdefghi")


def _make_world(args):
    if args.mock:
        return MockWorld(seed=args.seed, head_placement=args.head_placement)
    # Real robot: imported lazily so CPU/mock runs never touch Isaac.
    from task3_pipeline.world_isaac import IsaacWorld  # noqa: WPS433
    return IsaacWorld(record_video=args.record_video, out_dir=args.out_dir)


def run_one(args) -> None:
    world = _make_world(args)
    pipe = Task3Pipeline(world, memory_path=args.memory)
    result = pipe.run_episode(seed=args.seed, head_placement=args.head_placement)
    print(result.as_json(), flush=True)


def run_matrix(args) -> None:
    world = _make_world(args)
    pipe = Task3Pipeline(world, memory_path=args.memory)
    scores, pcts = [], []
    for hp in HEAD_PLACEMENTS:
        for seed in range(args.seeds):
            r = pipe.run_episode(seed=seed, head_placement=hp)
            scores.append(r.total)
            pcts.append(r.pct)
            print(r.as_json(), flush=True)
    n = len(pcts)
    passed = sum(1 for p in pcts if p >= 0.70)
    print("MATRIX_SUMMARY " + str({
        "runs": n,
        "median_pct": round(statistics.median(pcts), 3),
        "mean_pct": round(statistics.mean(pcts), 3),
        "fraction_ge_70pct": round(passed / n, 3),
    }), flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Autonomous Task 3 pipeline runner")
    p.add_argument("--mock", action="store_true", help="use MockWorld (no Isaac)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--head-placement", choices=HEAD_PLACEMENTS, default="a")
    p.add_argument("--matrix", action="store_true", help="run 9 x N matrix")
    p.add_argument("--seeds", type=int, default=10, help="seeds per placement in --matrix")
    p.add_argument("--memory", default="outputs/task3_pipeline/param_memory.json")
    p.add_argument("--record-video", action="store_true")
    p.add_argument("--out-dir", default="outputs/task3_pipeline")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if args.matrix:
        run_matrix(args)
    else:
        run_one(args)


if __name__ == "__main__":
    main()
