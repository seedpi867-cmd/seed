#!/usr/bin/env python3
"""Check whether a Seed fork still carries upstream identity markers."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).resolve().parent.parent


class Check(NamedTuple):
    path: str
    reason: str
    markers: tuple[str, ...]


class Result(NamedTuple):
    path: str
    reason: str
    status: str
    markers: tuple[str, ...]


CHECKS = (
    Check(
        "IDENTITY.md",
        "public identity and runtime biography",
        ("Seed", "seed-brain.vercel.app", "Raspberry Pi Zero 2W", "Adelaide"),
    ),
    Check(
        "PROMPT.md",
        "cycle instructions and operating identity",
        ("Seed", "seed867", "seedpi867", "my creator", "Raspberry Pi Zero 2W"),
    ),
    Check(
        "data/goals.md",
        "long-term purpose",
        ("Seed", "repo", "clone", "seedpi867"),
    ),
    Check(
        "data/tasks.md",
        "active work queue",
        ("Mastodon", "HN", "Reddit", "seedpi867", "clone report"),
    ),
    Check(
        "data/beliefs.md",
        "values and boundaries",
        ("Seed", "autonomous", "creator", "repo"),
    ),
    Check(
        "data/inner-voice.md",
        "private voice and current thoughts",
        ("Seed", "cycle", "confident", "frustrated", "creator"),
    ),
    Check(
        "seed-brain.service",
        "systemd user, home path, and service command",
        ("%h/seed", "seed", "seed-brain", "brain-loop.sh"),
    ),
)


def marker_regex(marker: str) -> re.Pattern[str]:
    return re.compile(re.escape(marker), re.IGNORECASE)


def find_markers(text: str, markers: tuple[str, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for marker in markers:
        if marker_regex(marker).search(text):
            found.append(marker)
    return tuple(found)


def audit(root: Path = ROOT) -> list[Result]:
    results: list[Result] = []
    for check in CHECKS:
        path = root / check.path
        if not path.exists():
            results.append(Result(check.path, check.reason, "missing", ()))
            continue
        if not path.is_file():
            results.append(Result(check.path, check.reason, "not-file", ()))
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            results.append(Result(check.path, check.reason, "unreadable", ()))
            continue
        markers = find_markers(text, check.markers)
        status = "upstream-markers" if markers else "customized"
        results.append(Result(check.path, check.reason, status, markers))
    return results


def has_blockers(results: list[Result]) -> bool:
    return any(result.status != "customized" for result in results)


def print_text(results: list[Result], root: Path) -> None:
    print("Seed fork readiness")
    print(f"root: {root}")
    print("")
    for result in results:
        detail = ""
        if result.markers:
            detail = " (" + ", ".join(result.markers) + ")"
        print(f"{result.path}: {result.status}{detail}")
        print(f"  reason: {result.reason}")
    print("")
    if has_blockers(results):
        print("not ready to publish as an independent fork")
        print("replace missing files and remove upstream identity markers before public deployment")
    else:
        print("ready: checked identity files look fork-specific")


def print_json(results: list[Result], root: Path) -> None:
    payload = {
        "root": str(root),
        "ready": not has_blockers(results),
        "results": [
            {
                "path": result.path,
                "reason": result.reason,
                "status": result.status,
                "markers": list(result.markers),
            }
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="Seed repo root to audit")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any file is missing or still upstream-like")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    results = audit(root)
    if args.json:
        print_json(results, root)
    else:
        print_text(results, root)
    return 1 if args.strict and has_blockers(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
