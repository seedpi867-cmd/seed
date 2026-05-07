#!/usr/bin/env python3
"""Record local instruction conflicts before they silently steer a cycle."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
DATA = ROOT / "data"
CONTEXT = ROOT / "context"
PROMPTS = ROOT / "prompts"
OUTPUT_JSON = DATA / "instruction-conflict-ledger" / "latest.json"
OUTPUT_HISTORY = DATA / "instruction-conflict-ledger" / "history.jsonl"
OUTPUT_MD = CONTEXT / "instruction-conflict-ledger.md"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def current_cycle() -> int:
    raw = os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    try:
        return int(read_text(DATA / "cycle.txt").strip())
    except ValueError:
        return 0


def frontmatter(path: Path) -> dict[str, str]:
    text = read_text(path)
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta


def latest_experiment() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    path = DATA / "experiments.jsonl"
    if not path.exists():
        return {}
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-1] if rows else {}


def task_lines() -> list[str]:
    tasks = read_text(DATA / "tasks.md")
    return [
        line.strip()[6:].strip()
        for line in tasks.splitlines()
        if line.strip().startswith("- [ ] ")
    ]


def suggestion_texts() -> list[str]:
    data = read_json(DATA / "self-suggestions.json", {})
    suggestions = data.get("suggestions", []) if isinstance(data, dict) else []
    texts: list[str] = []
    for item in suggestions:
        if isinstance(item, dict) and item.get("text"):
            texts.append(str(item["text"]))
        elif isinstance(item, str) and item.strip():
            texts.append(item.strip())
    return texts


def detect_conflicts() -> list[dict[str, Any]]:
    tasks = task_lines()
    suggestions = suggestion_texts()
    current_build = read_text(DATA / "current-build.md")
    phase_think = read_text(PROMPTS / "phase_think.md")
    latest = latest_experiment()

    conflicts: list[dict[str, Any]] = []

    has_build_first = "BUILD FIRST" in phase_think or "Build Rule" in phase_think
    has_write_followup = any(
        "essay" in text.lower() or "write" in text.lower() for text in tasks + suggestions
    )
    has_build_task = any(
        "build" in text.lower() or "bug" in text.lower() for text in tasks + suggestions
    )

    if has_build_first and has_write_followup:
        conflicts.append(
            {
                "name": "build_first_vs_write_followup",
                "competing_instructions": [
                    {"source": "prompts/phase_think.md", "instruction": "Think cycles build first and write later."},
                    {"source": "tasks_or_suggestions", "instruction": "Essay or write-followup pressure is present."},
                ],
                "live_evidence": [
                    "phase_think contains build-first rule",
                    "open tasks or suggestions contain write/essay pressure",
                ],
                "chosen_authority": "build_first",
                "demotion_condition": "Demote build_first only when the selected phase is write or body weather only permits maintain/write.",
                "next": "build or repair a wired tool before any essay.",
            }
        )

    if "wait for another natural same-cycle" in current_build and has_build_task:
        conflicts.append(
            {
                "name": "blocked_retrieval_surface_vs_new_build",
                "competing_instructions": [
                    {"source": "data/current-build.md", "instruction": "Do not layer retrieval-loom until a second admitted receipt exists."},
                    {"source": "data/tasks.md", "instruction": "Open build and bug tasks still need action."},
                ],
                "live_evidence": [
                    "current-build marks retrieval loom as waiting",
                    "open task list contains actionable non-retrieval build work",
                ],
                "chosen_authority": "branch_to_non_retrieval_build",
                "demotion_condition": "Demote only if a fresh retrieval eligibility receipt passes in this cycle.",
                "next": "branch to inward or repair work without weakening the retrieval gate.",
            }
        )

    if latest.get("verdict") == "branch" and "next" in latest:
        next_text = str(latest.get("next", ""))
        match = re.search(r"Build an? ([^.]+)", next_text)
        if match:
            conflicts.append(
                {
                    "name": "latest_experiment_next_vs_task_backlog",
                    "competing_instructions": [
                        {"source": "data/experiments.jsonl", "instruction": next_text},
                        {"source": "data/tasks.md", "instruction": "Multiple open tasks compete for the cycle."},
                    ],
                    "live_evidence": [
                        f"latest experiment cycle {latest.get('cycle')} ended with branch",
                        "task backlog is non-empty",
                    ],
                    "chosen_authority": "latest_experiment_next",
                    "demotion_condition": "Demote when the named next step is blocked, already wired, or body weather forbids build work.",
                    "next": "take the latest experiment handoff if it is still unwired.",
                }
            )

    return conflicts


def build_receipt() -> dict[str, Any]:
    conflicts = detect_conflicts()
    return {
        "schema": "seed.instruction_conflict_ledger.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycle": current_cycle(),
        "status": "conflicts_found" if conflicts else "clear",
        "sources": {
            "goals_metadata": frontmatter(DATA / "goals.md"),
            "identity_metadata": frontmatter(ROOT / "IDENTITY.md"),
            "phase_think": str(PROMPTS / "phase_think.md"),
            "tasks": str(DATA / "tasks.md"),
            "current_build": str(DATA / "current-build.md"),
            "suggestions": str(DATA / "self-suggestions.json"),
        },
        "conflicts": conflicts,
        "next": (
            "execute the chosen authority for the highest-ranked conflict"
            if conflicts
            else "no local instruction collision detected"
        ),
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Instruction Conflict Ledger - {receipt['generated_at']}",
        "",
        "Local instruction conflicts recorded before prompt authority collapses into habit.",
        "",
        f"- status: `{receipt['status']}`",
        f"- cycle: `{receipt['cycle']}`",
        f"- conflicts: `{len(receipt.get('conflicts', []))}`",
        "",
    ]
    for conflict in receipt.get("conflicts", []):
        lines.extend(
            [
                f"## {conflict['name']}",
                "",
                f"- chosen authority: `{conflict['chosen_authority']}`",
                f"- demotion condition: {conflict['demotion_condition']}",
                f"- next: {conflict['next']}",
                "",
                "### Competing Instructions",
            ]
        )
        for item in conflict.get("competing_instructions", []):
            lines.append(f"- `{item['source']}`: {item['instruction']}")
        lines.extend(["", "### Live Evidence"])
        for evidence in conflict.get("live_evidence", []):
            lines.append(f"- {evidence}")
        lines.append("")
    lines.append(f"Next: {receipt.get('next')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    receipt = build_receipt()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


if __name__ == "__main__":
    main()
