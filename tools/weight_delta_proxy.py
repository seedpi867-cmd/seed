#!/usr/bin/env python3
"""Compare cycle action-signature changes against file-change receipts."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
DATA = ROOT / "data"
CONTEXT = ROOT / "context"
FEEDBACK_LEDGER = DATA / "feedback_ledger.jsonl"
CHANGELOG = DATA / "changelog.jsonl"
OUTPUT_JSON = DATA / "weight-delta-proxy" / "latest.json"
OUTPUT_HISTORY = DATA / "weight-delta-proxy" / "history.jsonl"
OUTPUT_MD = CONTEXT / "weight-delta-proxy.md"
WINDOW = 12

IGNORED_ACTIONS = {"health_ok", "inner_voice_written"}
SURFACE_WEIGHTS = {
    "loop_runtime": 12,
    "cognitive_runtime": 10,
    "tool_runtime": 9,
    "steering_state": 7,
    "memory_state": 5,
    "public_expression": 3,
    "supporting_state": 2,
}


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
        record = grouped.setdefault(cycle, {"cycle": cycle, "actions": [], "intended_phase": None, "phases": Counter()})
        action = str(row.get("action") or "")
        phase = str(row.get("phase") or "unknown")
        record["phases"][phase] += 1
        if action.startswith("intention_"):
            record["intended_phase"] = action.removeprefix("intention_")
        elif action:
            record["actions"].append(action)
    return grouped


def phase_for(record: dict[str, Any]) -> str:
    if record.get("intended_phase"):
        return str(record["intended_phase"])
    phases = record.get("phases", Counter())
    if phases:
        return phases.most_common(1)[0][0]
    return "unknown"


def action_set(record: dict[str, Any]) -> set[str]:
    return {str(action) for action in record.get("actions", []) if action not in IGNORED_ACTIONS}


def signature(record: dict[str, Any]) -> str:
    return f"{phase_for(record)}|" + ",".join(sorted(action_set(record)))


def surface_for(path: str) -> str:
    if path == "brain-loop.sh" or path.startswith("brain-loop/"):
        return "loop_runtime"
    if path.startswith("cognitive/"):
        return "cognitive_runtime"
    if path.startswith("tools/"):
        return "tool_runtime"
    if path in {"tasks.md", "goals.md", "current-build.md"} or path.startswith("data/tasks") or path.startswith("data/current-build"):
        return "steering_state"
    if path.startswith("data/") or path.startswith("state/"):
        return "memory_state"
    if path.startswith("blog/") or path.startswith("knowledge/"):
        return "public_expression"
    return "supporting_state"


def grouped_changes(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cycle = row.get("cycle")
        filename = row.get("file")
        if not isinstance(cycle, int) or not isinstance(filename, str):
            continue
        path = filename
        if not path.startswith(("data/", "state/", "tools/", "cognitive/", "blog/", "knowledge/", "brain-loop")):
            path = f"data/{path}" if path in {"tasks.md", "goals.md", "current-build.md", "mood.json"} else path
        grouped[cycle].append(
            {
                "file": path,
                "surface": surface_for(path),
                "hash": row.get("hash"),
                "size": row.get("size"),
            }
        )
    return grouped


def file_weight(changes: list[dict[str, Any]]) -> int:
    surfaces = {str(item.get("surface")) for item in changes}
    return sum(SURFACE_WEIGHTS.get(surface, 1) for surface in surfaces)


def transition_row(previous: dict[str, Any], current: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    previous_actions = action_set(previous)
    current_actions = action_set(current)
    added = sorted(current_actions - previous_actions)
    removed = sorted(previous_actions - current_actions)
    sig_before = signature(previous)
    sig_after = signature(current)
    changed = sig_before != sig_after
    surfaces = Counter(str(item["surface"]) for item in changes)
    behavior_delta = len(added) + len(removed) + (1 if phase_for(previous) != phase_for(current) else 0)
    residue_weight = file_weight(changes)
    proxy_score = residue_weight + behavior_delta * 4

    if residue_weight and not changed:
        class_name = "file_change_without_behavior_delta"
    elif changed and not residue_weight:
        class_name = "behavior_delta_without_file_receipt"
    elif residue_weight and changed:
        class_name = "coupled_delta"
    else:
        class_name = "flat"

    return {
        "cycle": current["cycle"],
        "previous_cycle": previous["cycle"],
        "previous_signature": sig_before,
        "signature": sig_after,
        "signature_changed": changed,
        "phase_changed": phase_for(previous) != phase_for(current),
        "actions_added": added,
        "actions_removed": removed,
        "behavior_delta": behavior_delta,
        "file_change_count": len(changes),
        "file_surfaces": dict(sorted(surfaces.items())),
        "file_weight": residue_weight,
        "proxy_score": proxy_score,
        "class": class_name,
    }


def build_receipt() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    feedback = grouped_feedback(read_jsonl(FEEDBACK_LEDGER))
    changes = grouped_changes(read_jsonl(CHANGELOG))
    now = current_cycle()
    completed = sorted(cycle for cycle, record in feedback.items() if record.get("actions") and (now is None or cycle < now))
    if len(completed) < 2:
        return {
            "schema": "seed.weight_delta_proxy.v1",
            "generated_at": generated_at,
            "status": "empty",
            "target_cycle": None,
            "next": "wait for at least two completed cycles with feedback rows",
        }

    window_cycles = completed[-WINDOW:]
    rows = []
    for previous_cycle, cycle in zip(window_cycles, window_cycles[1:]):
        rows.append(transition_row(feedback[previous_cycle], feedback[cycle], changes.get(cycle, [])))

    target = rows[-1]
    classes = Counter(row["class"] for row in rows)
    file_only = [row for row in rows if row["class"] == "file_change_without_behavior_delta"]
    behavior_only = [row for row in rows if row["class"] == "behavior_delta_without_file_receipt"]
    average_proxy = round(sum(int(row["proxy_score"]) for row in rows) / len(rows), 2)

    if target["class"] == "file_change_without_behavior_delta":
        next_step = "inspect whether the changed files ever steer later actions before adding more memory"
    elif target["class"] == "behavior_delta_without_file_receipt":
        next_step = "preserve a receipt for the behavior change or treat it as volatile execution"
    elif target["class"] == "coupled_delta":
        next_step = "watch whether this coupled file/action delta repeats or decays next cycle"
    else:
        next_step = "no visible weight delta; branch if flatness repeats"

    return {
        "schema": "seed.weight_delta_proxy.v1",
        "generated_at": generated_at,
        "status": "ready",
        "window": len(window_cycles),
        "target_cycle": target["cycle"],
        "target_transition": target,
        "class_counts": dict(classes),
        "average_proxy_score": average_proxy,
        "file_only_cycles": [row["cycle"] for row in file_only],
        "behavior_only_cycles": [row["cycle"] for row in behavior_only],
        "transitions": rows,
        "next": next_step,
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Weight Delta Proxy",
        "",
        "Cycle action signatures compared against file-change receipts from the changelog.",
        "",
        f"- status: `{receipt.get('status')}`",
        f"- generated: {receipt.get('generated_at')}",
        f"- target cycle: `{receipt.get('target_cycle')}`",
    ]
    if receipt.get("status") != "ready":
        lines.append(f"- next: {receipt.get('next')}")
        lines.append("")
        return "\n".join(lines)

    target = receipt["target_transition"]
    lines.extend(
        [
            f"- target class: `{target['class']}`",
            f"- target proxy score: `{target['proxy_score']}`",
            f"- average proxy score: `{receipt['average_proxy_score']}`",
            f"- class counts: `{', '.join(f'{key}={value}' for key, value in sorted(receipt['class_counts'].items()))}`",
            f"- next: {receipt['next']}",
            "",
            "## Target Transition",
            "",
            f"- previous signature: `{target['previous_signature']}`",
            f"- current signature: `{target['signature']}`",
            f"- actions added: `{', '.join(target['actions_added']) or '-'}`",
            f"- actions removed: `{', '.join(target['actions_removed']) or '-'}`",
            f"- file surfaces: `{', '.join(f'{key}={value}' for key, value in target['file_surfaces'].items()) or '-'}`",
            "",
            "## Recent Transitions",
            "",
            "| cycle | class | behavior delta | file weight | proxy |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in receipt["transitions"]:
        lines.append(
            f"| {row['cycle']} | `{row['class']}` | {row['behavior_delta']} | {row['file_weight']} | {row['proxy_score']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    receipt = build_receipt()
    report = render_markdown(receipt)
    print(report)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(report)
    OUTPUT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
