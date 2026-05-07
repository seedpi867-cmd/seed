#!/usr/bin/env python3
"""Detect when recent cycles repeat work without new residue."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
DATA = ROOT / "data"
CONTEXT = ROOT / "context"
FEEDBACK_LEDGER = DATA / "feedback_ledger.jsonl"
EXPERIMENTS = DATA / "experiments.jsonl"
CYCLE_WEIGHT = DATA / "cycle-weight" / "latest.json"
OUTPUT_JSON = DATA / "diminishing-return-detector" / "latest.json"
OUTPUT_HISTORY = DATA / "diminishing-return-detector" / "history.jsonl"
OUTPUT_MD = CONTEXT / "diminishing-return-detector.md"
WINDOW = 10

IGNORED_ACTIONS = {"health_ok", "inner_voice_written"}
BUILD_MARKERS = ("build", "built", "wired", "tool", "script", "reader")
ROUTINE_MARKERS = ("health", "stale", "closure", "closed", "maintenance", "maintain")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def current_cycle() -> int | None:
    raw = os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    try:
        return int((DATA / "cycle.txt").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def grouped_cycles(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        cycle = row.get("cycle")
        if not isinstance(cycle, int):
            continue
        record = grouped.setdefault(
            cycle,
            {"cycle": cycle, "actions": [], "failed_actions": [], "intended_phase": None, "phases": Counter()},
        )
        action = str(row.get("action") or "")
        phase = str(row.get("phase") or "unknown")
        record["phases"][phase] += 1
        if action.startswith("intention_"):
            record["intended_phase"] = action.removeprefix("intention_")
            continue
        if action:
            record["actions"].append(action)
            if not bool(row.get("success", False)):
                record["failed_actions"].append(action)
    return grouped


def phase_for(record: dict[str, Any]) -> str:
    if record.get("intended_phase"):
        return str(record["intended_phase"])
    phases = record.get("phases", Counter())
    if phases:
        return phases.most_common(1)[0][0]
    return "unknown"


def signature(record: dict[str, Any]) -> str:
    actions = sorted({str(action) for action in record.get("actions", []) if action not in IGNORED_ACTIONS})
    return f"{phase_for(record)}|" + ",".join(actions)


def classify_experiment(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    kind = str(row.get("type") or "").lower()
    name = str(row.get("name") or row.get("topic") or row.get("experiment") or "").lower()
    result = str(row.get("result") or row.get("output") or "").lower()
    if "build" in kind:
        return "build_residue"
    if "write" in kind:
        return "write_residue"
    if "repair" in kind or "maintain" in kind or any(marker in name for marker in ROUTINE_MARKERS):
        return "routine_closure"
    text = " ".join([name, result])
    if "wrote" in result or "essay" in result or "blog/" in result:
        return "write_residue"
    if any(marker in text for marker in BUILD_MARKERS):
        return "build_residue"
    if any(marker in text for marker in ROUTINE_MARKERS):
        return "routine_closure"
    return "unknown_residue"


def experiment_by_cycle(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        cycle = row.get("cycle")
        if isinstance(cycle, int):
            indexed[cycle] = row
    return indexed


def build_receipt() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    feedback_rows = read_jsonl(FEEDBACK_LEDGER)
    grouped = grouped_cycles(feedback_rows)
    now = current_cycle()
    completed = [
        cycle
        for cycle, record in grouped.items()
        if record.get("actions") and (now is None or cycle < now)
    ]
    if not completed:
        return {
            "schema": "seed.diminishing_return_detector.v1",
            "generated_at": generated_at,
            "status": "empty",
            "target_cycle": None,
            "level": "none",
            "score": 0,
            "next": "wait for completed feedback rows",
        }

    recent_cycles = sorted(completed)[-WINDOW:]
    experiments = experiment_by_cycle(read_jsonl(EXPERIMENTS))
    cycle_rows = []
    signatures: Counter[str] = Counter()
    for cycle in recent_cycles:
        record = grouped[cycle]
        sig = signature(record)
        signatures[sig] += 1
        exp = experiments.get(cycle)
        cycle_rows.append(
            {
                "cycle": cycle,
                "phase": phase_for(record),
                "signature": sig,
                "actions": record.get("actions", []),
                "residue": classify_experiment(exp),
                "experiment": exp.get("name") or exp.get("topic") or exp.get("experiment") if exp else None,
            }
        )

    target_cycle = recent_cycles[-1]
    target_signature = signature(grouped[target_cycle])
    matching = [row for row in cycle_rows if row["signature"] == target_signature]
    target_exp = experiments.get(target_cycle)
    target_residue = classify_experiment(target_exp)
    repeated_count = len(matching)
    routine_count = sum(1 for row in matching if row["residue"] in {"routine_closure", "none", "unknown_residue"})
    build_count = sum(1 for row in matching if row["residue"] == "build_residue")

    score = min(100, repeated_count * 12 + routine_count * 8 - build_count * 10)
    if repeated_count < 3:
        level = "none"
    elif score >= 55:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    if level == "high":
        next_step = "force a branch or terminate the repeated action pattern"
    elif level == "medium":
        next_step = "treat the repeated signature as build pressure unless the next cycle adds new residue"
    elif level == "low":
        next_step = "watch the repeat; build residue is still interrupting full sameness"
    else:
        next_step = "no diminishing-return pressure yet"

    cycle_weight = read_json(CYCLE_WEIGHT, {})
    return {
        "schema": "seed.diminishing_return_detector.v1",
        "generated_at": generated_at,
        "status": "ready",
        "window": WINDOW,
        "target_cycle": target_cycle,
        "target_signature": target_signature,
        "target_residue": target_residue,
        "repeated_signature_count": repeated_count,
        "routine_repeat_count": routine_count,
        "build_repeat_count": build_count,
        "score": score,
        "level": level,
        "matching_cycles": [row["cycle"] for row in matching],
        "recent_cycles": cycle_rows,
        "signature_counts": dict(signatures),
        "source_receipts": {
            "feedback_ledger": str(FEEDBACK_LEDGER),
            "experiments": str(EXPERIMENTS),
            "cycle_weight": str(CYCLE_WEIGHT) if cycle_weight else None,
        },
        "next": next_step,
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Diminishing Return Detector - {receipt['generated_at']}",
        "",
        "Repeated cycle signatures measured against visible residue.",
        "",
        f"- status: `{receipt['status']}`",
        f"- target cycle: `{receipt.get('target_cycle')}`",
        f"- target signature: `{receipt.get('target_signature', 'none')}`",
        f"- score: `{receipt.get('score', 0)}`",
        f"- level: `{receipt.get('level', 'none')}`",
        f"- repeated signature count: `{receipt.get('repeated_signature_count', 0)}`",
        f"- target residue: `{receipt.get('target_residue', 'none')}`",
        "",
        "## Matching Cycles",
        "",
    ]
    matches = receipt.get("matching_cycles", [])
    if matches:
        lines.append(", ".join(f"`{cycle}`" for cycle in matches))
    else:
        lines.append("- none")
    lines.extend(["", "## Recent Window", ""])
    for row in receipt.get("recent_cycles", [])[-10:]:
        lines.append(
            f"- cycle `{row.get('cycle')}`: `{row.get('signature')}` -> `{row.get('residue')}`"
        )
    lines.extend(["", f"Next: {receipt.get('next')}", ""])
    return "\n".join(lines)


def main() -> int:
    receipt = build_receipt()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")
    print(f"[diminishing-return-detector] {receipt['status']} {receipt.get('level')} score={receipt.get('score')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
