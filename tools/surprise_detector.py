#!/usr/bin/env python3
"""Measure the gap between expected and actual cycle outcomes."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
FEEDBACK_LEDGER = ROOT / "data" / "feedback_ledger.jsonl"
INTENTION_FILE = ROOT / "state" / "intention.json"
OUTPUT_JSON = ROOT / "data" / "surprise-detector" / "latest.json"
OUTPUT_HISTORY = ROOT / "data" / "surprise-detector" / "history.jsonl"
OUTPUT_MD = ROOT / "context" / "surprise-detector.md"
WINDOW = 80

EXPECTED_BY_PHASE = {
    "think": {"completed_task", "completed_research", "git_committed"},
    "write": {"wrote_essay", "published_blog", "completed_research"},
    "research": {"completed_research"},
    "maintain": {"health_ok"},
    "dream": {"inner_voice_written"},
}

UNEXPECTED_BY_PHASE = {
    "think": {"wrote_essay", "published_blog"},
    "write": {"error_occurred", "nothing_happened"},
    "research": {"published_blog"},
    "maintain": {"published_blog", "wrote_essay"},
}

ACTION_WEIGHTS = {
    "wrote_essay": 3,
    "published_blog": 3,
    "error_occurred": 3,
    "nothing_happened": 4,
    "completed_task": 2,
    "completed_research": 2,
    "git_committed": 1,
    "inner_voice_written": 1,
    "health_ok": 1,
}


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def current_cycle() -> int | None:
    raw = os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    try:
        return int((ROOT / "data" / "cycle.txt").read_text(encoding="utf-8").strip())
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
            {
                "cycle": cycle,
                "actions": [],
                "failed_actions": [],
                "phases": Counter(),
                "intended_phase": None,
                "intention_success": None,
            },
        )
        action = str(row.get("action") or "")
        phase = str(row.get("phase") or "unknown")
        success = bool(row.get("success", False))
        record["phases"][phase] += 1
        if action.startswith("intention_"):
            record["intended_phase"] = action.removeprefix("intention_")
            record["intention_success"] = success
            continue
        if action:
            record["actions"].append(action)
            if not success:
                record["failed_actions"].append(action)
    return grouped


def baseline(rows: list[dict[str, Any]], target_cycle: int) -> dict[str, Any]:
    phase_action_counts: dict[str, Counter[str]] = defaultdict(Counter)
    phase_cycle_counts: Counter[str] = Counter()
    grouped = grouped_cycles(rows[-WINDOW:])
    for cycle, record in grouped.items():
        if cycle == target_cycle:
            continue
        phase = record["phases"].most_common(1)[0][0] if record["phases"] else "unknown"
        phase_cycle_counts[phase] += 1
        phase_action_counts[phase].update(set(record["actions"]))
    return {
        "phase_cycle_counts": dict(phase_cycle_counts),
        "phase_action_counts": {phase: dict(counts) for phase, counts in phase_action_counts.items()},
    }


def classify_level(score: int) -> str:
    if score >= 8:
        return "high"
    if score >= 4:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def surprise_signature(receipt: dict[str, Any]) -> str:
    parts: list[str] = [str(receipt.get("phase") or "unknown"), str(receipt.get("level") or "none")]
    for item in receipt.get("surprises", []):
        parts.append(
            "|".join(
                [
                    str(item.get("type") or ""),
                    str(item.get("action") or ""),
                    str(item.get("detail") or ""),
                ]
            )
        )
    for action in receipt.get("missing_expected_actions", []):
        parts.append(f"missing:{action}")
    return "||".join(parts)


def trend_from_history(receipt: dict[str, Any], history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_cycle = receipt.get("target_cycle")
    current_signature = surprise_signature(receipt)
    ready_rows = [
        row
        for row in history_rows
        if row.get("status") == "ready" and isinstance(row.get("target_cycle"), int)
    ]
    rows_with_current = ready_rows + [receipt]

    latest_by_cycle: dict[int, dict[str, Any]] = {}
    for row in rows_with_current:
        cycle = row.get("target_cycle")
        if isinstance(cycle, int):
            latest_by_cycle[cycle] = row

    recent_distinct = [latest_by_cycle[cycle] for cycle in sorted(latest_by_cycle)[-12:]]
    matching_cycles = [
        int(row["target_cycle"])
        for row in recent_distinct
        if surprise_signature(row) == current_signature
    ]
    duplicate_runs_for_target = sum(1 for row in ready_rows if row.get("target_cycle") == target_cycle)
    level_counts = Counter(str(row.get("level") or "none") for row in recent_distinct)

    pressure = "wait"
    if len(matching_cycles) >= 3 and receipt.get("level") in {"medium", "high"}:
        pressure = "recurring_mismatch"
    elif duplicate_runs_for_target >= 2:
        pressure = "duplicate_receipt_noise"
    elif receipt.get("level") in {"medium", "high"}:
        pressure = "single_cycle_gap"

    next_step = "wait for more natural receipts before treating this as emotional authority"
    if pressure == "recurring_mismatch":
        next_step = "promote repeated mismatch into build pressure or a new feeling signal"
    elif pressure == "duplicate_receipt_noise":
        next_step = "ignore duplicate runs for trend authority; count only new target cycles"
    elif pressure == "single_cycle_gap":
        next_step = "preserve the gap but do not call it a trend yet"

    return {
        "window_distinct_cycles": len(recent_distinct),
        "duplicate_runs_for_target": duplicate_runs_for_target,
        "matching_distinct_cycles": matching_cycles,
        "matching_distinct_count": len(matching_cycles),
        "level_counts": dict(level_counts),
        "pressure": pressure,
        "signature": current_signature,
        "next": next_step,
    }


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    now_cycle = current_cycle()
    grouped = grouped_cycles(rows)
    completed_cycles = sorted(
        cycle
        for cycle, record in grouped.items()
        if now_cycle is None or cycle < now_cycle or record.get("intention_success") is not None
    )
    if not completed_cycles:
        return {
            "status": "empty",
            "target_cycle": None,
            "score": 0,
            "level": "none",
            "surprises": [],
            "next": "wait for a completed cycle with feedback ledger rows",
        }

    target_cycle = completed_cycles[-1]
    record = grouped[target_cycle]
    phase = record["intended_phase"] or (record["phases"].most_common(1)[0][0] if record["phases"] else "unknown")
    actions = list(record["actions"])
    action_set = set(actions)
    expected = EXPECTED_BY_PHASE.get(str(phase), set())
    unexpected = UNEXPECTED_BY_PHASE.get(str(phase), set())
    base = baseline(rows, target_cycle)
    phase_count = int(base["phase_cycle_counts"].get(str(phase), 0))
    phase_action_counts = base["phase_action_counts"].get(str(phase), {})

    surprises: list[dict[str, Any]] = []
    score = 0

    if record.get("intention_success") is False:
        surprises.append({"type": "missed_intention", "weight": 5, "detail": "declared intention was not delivered"})
        score += 5

    for action in sorted(action_set & unexpected):
        weight = ACTION_WEIGHTS.get(action, 2)
        surprises.append({"type": "phase_unexpected_action", "action": action, "weight": weight})
        score += weight

    missing = sorted(expected - action_set)
    for action in missing:
        surprises.append({"type": "expected_action_missing", "action": action, "weight": 1})
        score += 1

    duplicates = sorted(action for action, count in Counter(actions).items() if count > 1)
    for action in duplicates:
        surprises.append({"type": "duplicate_action", "action": action, "weight": 1})
        score += 1

    if phase_count >= 6:
        for action in sorted(action_set):
            seen_count = int(phase_action_counts.get(action, 0))
            if seen_count == 0:
                weight = min(3, ACTION_WEIGHTS.get(action, 1))
                surprises.append(
                    {
                        "type": "rare_for_phase",
                        "action": action,
                        "weight": weight,
                        "baseline_cycles": phase_count,
                    }
                )
                score += weight

    score = min(score, 12)
    return {
        "status": "ready",
        "target_cycle": target_cycle,
        "phase": phase,
        "actions": actions,
        "failed_actions": record["failed_actions"],
        "intention_success": record.get("intention_success"),
        "expected_actions": sorted(expected),
        "missing_expected_actions": missing,
        "score": score,
        "level": classify_level(score),
        "surprises": surprises,
        "baseline": base,
        "next": "treat high surprise as essay or build pressure; treat repeated no-surprise cycles as drift toward routine",
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Surprise Detector - {receipt['generated_at']}",
        "",
        "Expected-vs-actual cycle gap measured from the feedback ledger and intention protocol.",
        "",
        f"- status: `{receipt['status']}`",
        f"- target cycle: `{receipt.get('target_cycle')}`",
        f"- phase: `{receipt.get('phase', 'unknown')}`",
        f"- score: `{receipt.get('score', 0)}`",
        f"- level: `{receipt.get('level', 'none')}`",
        "",
    ]
    if receipt.get("actions"):
        lines.append(f"- actions: {', '.join(f'`{action}`' for action in receipt['actions'])}")
    if receipt.get("missing_expected_actions"):
        lines.append(
            "- missing expected actions: "
            + ", ".join(f"`{action}`" for action in receipt["missing_expected_actions"])
        )
    lines.extend(["", "## Gap Signals", ""])
    surprises = receipt.get("surprises", [])
    if not surprises:
        lines.append("- none")
    for item in surprises[:10]:
        action = f" `{item['action']}`" if item.get("action") else ""
        detail = f" - {item['detail']}" if item.get("detail") else ""
        lines.append(f"- {item['type']}{action}: weight {item['weight']}{detail}")
    trend = receipt.get("trend", {})
    if trend:
        lines.extend(
            [
                "",
                "## Trend",
                "",
                f"- pressure: `{trend.get('pressure', 'wait')}`",
                f"- distinct cycles in window: `{trend.get('window_distinct_cycles', 0)}`",
                f"- matching distinct cycles: "
                + (
                    ", ".join(f"`{cycle}`" for cycle in trend.get("matching_distinct_cycles", []))
                    if trend.get("matching_distinct_cycles")
                    else "`none`"
                ),
                f"- duplicate runs for target: `{trend.get('duplicate_runs_for_target', 0)}`",
            ]
        )
        if trend.get("level_counts"):
            lines.append(
                "- level counts: "
                + ", ".join(f"`{level}`={count}" for level, count in sorted(trend["level_counts"].items()))
            )
        lines.append(f"- trend next: {trend.get('next')}")
    lines.extend(["", f"Next: {receipt.get('next')}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    rows = read_jsonl(FEEDBACK_LEDGER)
    history_rows = read_jsonl(OUTPUT_HISTORY)
    receipt = {
        "schema": "seed.surprise_detector.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "feedback_ledger": str(FEEDBACK_LEDGER),
            "intention_file": str(INTENTION_FILE),
            "history": str(OUTPUT_HISTORY),
        },
        **analyse(rows),
    }
    receipt["trend"] = trend_from_history(receipt, history_rows)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


if __name__ == "__main__":
    main()
