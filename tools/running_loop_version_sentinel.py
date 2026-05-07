#!/usr/bin/env python3
"""Emit a receipt when the running brain-loop image is older than source."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "running-loop-version" / "latest.json"
DEFAULT_LEDGER = ROOT / "data" / "running-loop-version" / "history.jsonl"
DEFAULT_CRITICAL_PATHS = [
    ROOT / "brain-loop.sh",
    ROOT / "tools" / "body_weather_router.py",
    ROOT / "tools" / "running_loop_version_sentinel.py",
    ROOT / "cognitive" / "appraisal.py",
    ROOT / "cognitive" / "intentions.py",
    ROOT / "cognitive" / "learning.py",
]


def iso_from_epoch(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat()


def boot_time() -> int:
    for line in Path("/proc/stat").read_text().splitlines():
        if line.startswith("btime "):
            return int(line.split()[1])
    raise RuntimeError("cannot read btime from /proc/stat")


def process_start_time(pid: int) -> float:
    stat = Path("/proc") / str(pid) / "stat"
    text = stat.read_text()
    after_comm = text.rsplit(") ", 1)[1]
    fields = after_comm.split()
    start_ticks = int(fields[19])
    ticks_per_second = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    return boot_time() + (start_ticks / ticks_per_second)


def newest_critical_file(paths: list[Path]) -> tuple[Path | None, float | None, list[str]]:
    newest_path: Path | None = None
    newest_mtime: float | None = None
    missing: list[str] = []
    for path in paths:
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        mtime = path.stat().st_mtime
        if newest_mtime is None or mtime > newest_mtime:
            newest_path = path
            newest_mtime = mtime
    return newest_path, newest_mtime, missing


def build_receipt(cycle: int, pid: int, paths: list[Path]) -> dict[str, object]:
    start = process_start_time(pid)
    newest_path, newest_mtime, missing = newest_critical_file(paths)
    stale = newest_mtime is not None and newest_mtime > start
    newest_rel = str(newest_path.relative_to(ROOT)) if newest_path else None
    age_delta = round(newest_mtime - start, 3) if newest_mtime is not None else None

    return {
        "schema": "seed.running_loop_version.v1",
        "cycle": cycle,
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "status": "stale-loop-image" if stale else "current-loop-image",
        "running_pid": pid,
        "process_start_epoch": round(start, 3),
        "process_start": iso_from_epoch(start),
        "newest_critical_file": newest_rel,
        "newest_critical_mtime_epoch": round(newest_mtime, 3) if newest_mtime else None,
        "newest_critical_mtime": iso_from_epoch(newest_mtime) if newest_mtime else None,
        "source_newer_than_process_seconds": age_delta,
        "missing_critical_files": missing,
    }


def write_receipt(receipt: dict[str, object], output: Path, ledger: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True)
    output.write_text(text + "\n")
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument(
        "--critical",
        action="append",
        default=[],
        help="Critical path to compare with the running loop start time. May repeat.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [Path(item).expanduser().resolve() for item in args.critical]
    if not paths:
        paths = DEFAULT_CRITICAL_PATHS

    receipt = build_receipt(args.cycle, args.pid, paths)
    write_receipt(receipt, args.output, args.ledger)
    print(f"{receipt['status']}\t{receipt['newest_critical_file']}")
    return 1 if receipt["status"] == "stale-loop-image" else 0


if __name__ == "__main__":
    raise SystemExit(main())
