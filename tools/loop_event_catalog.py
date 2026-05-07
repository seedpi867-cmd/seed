#!/usr/bin/env python3
"""Build a small EventCatalog-style map of Seed's own loop events."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
EVENT_LOG = ROOT / "data" / "event_log.jsonl"
OUTPUT_JSON = ROOT / "data" / "loop-event-catalog" / "latest.json"
OUTPUT_HISTORY = ROOT / "data" / "loop-event-catalog" / "history.jsonl"
OUTPUT_MD = ROOT / "context" / "loop-event-catalog.md"
WINDOW = 60


def load_rows(path: Path, limit: int = WINDOW) -> list[dict[str, Any]]:
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
    return rows[-limit:]


def catalog(rows: list[dict[str, Any]]) -> dict[str, Any]:
    event_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    event_actions: dict[str, Counter[str]] = defaultdict(Counter)
    cycle_events: list[dict[str, Any]] = []

    for row in rows:
        cycle = row.get("cycle")
        events = [str(event) for event in row.get("events", [])]
        actions = [str(action) for action in row.get("actions", [])]
        event_counts.update(events)
        action_counts.update(actions)
        for event in events:
            for action in actions:
                event_actions[event][action] += 1
        cycle_events.append({"cycle": cycle, "events": events, "actions": actions})

    contracts = []
    for event, count in event_counts.most_common():
        common_actions = [
            {"action": action, "count": action_count}
            for action, action_count in event_actions[event].most_common(5)
        ]
        contracts.append(
            {
                "event": event,
                "count": count,
                "common_downstream_actions": common_actions,
                "consumer_contract": "event should imply at least one explicit downstream action or be demoted to observation",
                "demotion_rule": "demote if the event recurs without changing action, route, memory, publication, or maintenance state",
            }
        )

    return {
        "cycles_read": len(rows),
        "first_cycle": rows[0].get("cycle") if rows else None,
        "last_cycle": rows[-1].get("cycle") if rows else None,
        "event_counts": dict(event_counts.most_common()),
        "action_counts": dict(action_counts.most_common(20)),
        "contracts": contracts,
        "recent_cycles": cycle_events[-10:],
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Loop Event Catalog - {receipt['generated_at']}",
        "",
        "EventCatalog-style map of Seed's own loop events, consumers, and demotion rules.",
        "",
        f"- source: `{receipt['source_path']}`",
        f"- cycles read: {receipt['cycles_read']}",
        f"- first cycle: `{receipt.get('first_cycle')}`",
        f"- last cycle: `{receipt.get('last_cycle')}`",
        "",
        "## Event Contracts",
        "",
    ]
    for contract in receipt["contracts"][:12]:
        lines.append(f"### {contract['event']}")
        lines.append(f"- count: {contract['count']}")
        if contract["common_downstream_actions"]:
            actions = "; ".join(
                f"{item['action']} ({item['count']})" for item in contract["common_downstream_actions"][:3]
            )
            lines.append(f"- common downstream actions: {actions}")
        else:
            lines.append("- common downstream actions: none")
        lines.append(f"- consumer contract: {contract['consumer_contract']}")
        lines.append(f"- demotion rule: {contract['demotion_rule']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    rows = load_rows(EVENT_LOG)
    generated_at = datetime.now(timezone.utc).isoformat()
    body = catalog(rows)
    receipt = {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_path": str(EVENT_LOG),
        "status": "ready" if body["cycles_read"] else "empty",
        **body,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


if __name__ == "__main__":
    main()
