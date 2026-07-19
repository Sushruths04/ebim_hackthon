#!/usr/bin/env python3
# Copyright (c) 2026 The EBiM Benchmark Contributors
# SPDX-License-Identifier: Apache-2.0

"""Freeze a Task 3 proof bundle from already-exported evidence.

The command is intentionally conservative: it copies evidence, refuses to
overwrite an existing bundle unless ``--force`` is supplied, and appends the
ledger only after all requested files exist.  It never starts Isaac Sim or
changes scene/physics state.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "slug",
        help="proof directory name, e.g. phase3-stage1",
    )
    parser.add_argument("--task", required=True, help="ledger task name")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--repro", type=Path)
    parser.add_argument("--command", help="exact reproduction command")
    parser.add_argument("--result-note", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-ledger", action="store_true")
    return parser.parse_args()


def _commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _copy(source: Path, destination: Path) -> None:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _write_repro(args: argparse.Namespace, path: Path) -> None:
    if args.repro is not None:
        _copy(args.repro, path)
        return
    if not args.command:
        raise ValueError("provide --repro or --command")
    path.write_text(args.command.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    bundle = REPO_ROOT / "proofs" / args.slug
    if bundle.exists() and not args.force:
        raise SystemExit(
            f"Refusing to overwrite {bundle}; use --force only for an "
            "intentional re-freeze."
        )
    bundle.mkdir(parents=True, exist_ok=True)

    result_path = bundle / "result.json"
    _copy(args.result, result_path)
    video_destination = bundle / f"proof{args.video.suffix.lower()}"
    _copy(args.video, video_destination)
    repro_path = bundle / "repro.txt"
    _write_repro(args, repro_path)

    manifest = {
        "task": args.task,
        "slug": args.slug,
        "commit": _commit(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": result_path.name,
        "video": video_destination.name,
        "video_format": args.video.suffix.lower().lstrip("."),
        "repro": repro_path.name,
        "note": args.result_note,
    }
    (bundle / "bundle.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not args.no_ledger:
        ledger = REPO_ROOT / "docs" / "eval_results.md"
        line = (
            f"| {manifest['created_at'][:10]} | {args.task} | "
            f"{manifest['commit']} | "
            f"{args.result_note or 'see result.json'} | "
            f"`proofs/{args.slug}/` |\n"
        )
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(line)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
