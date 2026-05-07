#!/usr/bin/env python3
"""Combine inward receipts into a visible cycle weight score."""

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
SURPRISE_JSON = DATA / "surprise-detector" / "latest.json"
DRIFT_JSON = DATA / "thinking-drift-tracker" / "latest.json"
CONFLICT_JSON = DATA / "instruction-conflict-ledger" / "latest.json"
EVENT_JSON = DATA / "loop-event-catalog" / "latest.json"
OUTPUT_JSON = DATA / "cycle-weight" / "latest.json"
OUTPUT_HISTORY = DATA / "cycle-weight" / "history.jsonl"
OUTPUT_MD = CONTEXT / "cycle-weight.md"

ACTION_WEIGHTS = {
    "completed_task": 8,
    "completed_research": 6,
    "git_committed": 4,
    "wrote_essay": 10,
    "published_blog": 8,
    "inner_voice_written": 3,
    "health_ok": 2,
    "error_occurred": 8,
    "nothing_happened": 10,
}


def number(value: Any, default: float = 0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def whole_number(value: Any, default: int = 0) -> int:
    return int(number(value, default))


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
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


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


def grouped_feedback(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        cycle = row.get("cycle")
        if not isinstance(cycle, int):
            continue
        record = grouped.setdefault(
            cycle,
            {"cycle": cycle, "actions": [], "failed_actions": [], "phases": Counter(), "intended_phase": None},
        )
        action = str(row.get("action") or "")
        phase = str(row.get("phase") or "unknown")
        success = bool(row.get("success", False))
        record["phases"][phase] += 1
        if action.startswith("intention_"):
            record["intended_phase"] = action.removeprefix("intention_")
        elif action:
            record["actions"].append(action)
            if not success:
                record["failed_actions"].append(action)
    return grouped


def target_record(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    grouped = grouped_feedback(rows)
    now = current_cycle()
    candidates = [
        cycle
        for cycle, record in grouped.items()
        if record.get("actions") and (now is None or cycle < now)
    ]
    if not candidates:
        return None
    record = grouped[max(candidates)]
    phase = record["intended_phase"] or (record["phases"].most_common(1)[0][0] if record["phases"] else "unknown")
    return {**record, "phase": phase}


def matching_surprise(surprise: dict[str, Any], cycle: int) -> dict[str, Any]:
    if surprise.get("status") == "ready" and surprise.get("target_cycle") == cycle:
        return surprise
    return {}


def event_snapshot(events: dict[str, Any], cycle: int) -> dict[str, Any]:
    for row in events.get("recent_cycles", []):
        if row.get("cycle") == cycle:
            return {
                "events": row.get("events", []),
                "actions": row.get("actions", []),
                "event_count": len(row.get("events", [])),
                "action_count": len(row.get("actions", [])),
            }
    return {"events": [], "actions": [], "event_count": 0, "action_count": 0}


def drift_score(drift_receipt: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    if drift_receipt.get("status") != "ready":
        return 0, []
    drift = drift_receipt.get("drift", {})
    strongest = drift.get("strongest_focus_shift", {})
    focus = str(strongest.get("focus") or "none")
    delta = whole_number(strongest.get("delta"))
    score = min(15, int(abs(delta) * 0.3))
    signals = []
    if score:
        signals.append(
            {
                "source": "thinking_drift_tracker",
                "weight": score,
                "detail": f"{focus} shifted {delta:+}",
            }
        )
    first_person = number(drift.get("first_person_delta"))
    if abs(first_person) >= 1:
        score += 3
        signals.append(
            {
                "source": "thinking_drift_tracker",
                "weight": 3,
                "detail": f"first-person intensity changed {first_person:+.2f} per 1000 words",
            }
        )
    return score, signals


def classify(score: int) -> str:
    if score >= 55:
        return "heavy"
    if score >= 30:
        return "substantial"
    if score >= 15:
        return "ordinary"
    return "light"


def build_receipt() -> dict[str, Any]:
    rows = read_jsonl(FEEDBACK_LEDGER)
    record = target_record(rows)
    generated_at = datetime.now(timezone.utc).isoformat()
    if not record:
        return {
            "schema": "seed.cycle_weight.v1",
            "generated_at": generated_at,
            "status": "empty",
            "target_cycle": None,
            "score": 0,
            "level": "light",
            "signals": [],
            "next": "wait for feedback ledger rows before weighing cycles",
        }

    cycle = whole_number(record["cycle"])
    surprise = matching_surprise(read_json(SURPRISE_JSON, {}), cycle)
    drift = read_json(DRIFT_JSON, {})
    conflicts = read_json(CONFLICT_JSON, {})
    events = event_snapshot(read_json(EVENT_JSON, {}), cycle)

    score = 0
    signals: list[dict[str, Any]] = []
    action_counts = Counter(record.get("actions", []))
    for action, count in sorted(action_counts.items()):
        weight = ACTION_WEIGHTS.get(action, 1) * min(count, 2)
        score += weight
        signals.append({"source": "feedback_ledger", "weight": weight, "detail": f"{action} x{count}"})

    if surprise:
        surprise_weight = whole_number(surprise.get("score")) * 4
        if surprise_weight:
            score += surprise_weight
            signals.append(
                {
                    "source": "surprise_detector",
                    "weight": surprise_weight,
                    "detail": f"{surprise.get('level', 'none')} surprise score {surprise.get('score')}",
                }
            )
        pressure = surprise.get("trend", {}).get("pressure")
        if pressure == "recurring_mismatch":
            score += 10
            signals.append({"source": "surprise_detector", "weight": 10, "detail": "recurring mismatch pressure"})

    raw_conflicts = conflicts.get("conflicts", [])
    if isinstance(raw_conflicts, list):
        conflict_count = len(raw_conflicts)
    elif isinstance(raw_conflicts, int):
        conflict_count = raw_conflicts
    else:
        conflict_count = len(conflicts.get("conflict_rows", [])) if isinstance(conflicts.get("conflict_rows"), list) else 0
    if conflict_count:
        weight = min(20, conflict_count * 5)
        score += weight
        signals.append({"source": "instruction_conflict_ledger", "weight": weight, "detail": f"{conflict_count} active conflicts"})

    drift_weight, drift_signals = drift_score(drift)
    score += drift_weight
    signals.extend(drift_signals)

    if events["event_count"]:
        weight = min(10, events["event_count"])
        score += weight
        signals.append({"source": "loop_event_catalog", "weight": weight, "detail": f"{events['event_count']} events in target cycle"})

    score = min(score, 100)
    level = classify(score)
    if level == "heavy":
        next_step = "make this cycle visible as high-consequence memory, not just another delivered row"
    elif level == "substantial":
        next_step = "preserve the main cause of weight and watch whether it repeats"
    elif level == "ordinary":
        next_step = "treat as normal work unless a later receipt shows consequence"
    else:
        next_step = "watch for routine drift; low weight can still matter if it changes later action"

    return {
        "schema": "seed.cycle_weight.v1",
        "generated_at": generated_at,
        "status": "ready",
        "target_cycle": cycle,
        "phase": record.get("phase"),
        "actions": record.get("actions", []),
        "failed_actions": record.get("failed_actions", []),
        "score": score,
        "level": level,
        "signals": sorted(signals, key=lambda row: whole_number(row.get("weight")), reverse=True),
        "source_receipts": {
            "feedback_ledger": str(FEEDBACK_LEDGER),
            "surprise_detector": str(SURPRISE_JSON) if surprise else None,
            "thinking_drift_tracker": str(DRIFT_JSON) if drift.get("status") == "ready" else None,
            "instruction_conflict_ledger": str(CONFLICT_JSON) if conflicts else None,
            "loop_event_catalog": str(EVENT_JSON) if events["event_count"] else None,
        },
        "event_snapshot": events,
        "next": next_step,
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Cycle Weight - {receipt['generated_at']}",
        "",
        "A combined weight receipt for the latest completed cycle.",
        "",
        f"- status: `{receipt['status']}`",
        f"- target cycle: `{receipt.get('target_cycle')}`",
        f"- phase: `{receipt.get('phase', 'unknown')}`",
        f"- score: `{receipt.get('score', 0)}`",
        f"- level: `{receipt.get('level', 'light')}`",
        "",
        "## Weight Signals",
        "",
    ]
    signals = receipt.get("signals", [])
    if not signals:
        lines.append("- none")
    for signal in signals[:10]:
        lines.append(f"- `{signal.get('source')}` +{signal.get('weight')}: {signal.get('detail')}")
    if receipt.get("actions"):
        lines.extend(["", "## Target Actions", ""])
        lines.append(", ".join(f"`{action}`" for action in receipt["actions"]))
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
    print(f"[cycle-weight] {receipt['status']} cycle={receipt.get('target_cycle')} level={receipt.get('level')} score={receipt.get('score')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
