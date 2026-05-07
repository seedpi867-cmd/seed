#!/usr/bin/env python3
"""Name and test the first enterprise-search downstream action surface."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
ELIGIBILITY_JSON = ROOT / "data" / "repo-pattern-eligibility" / "latest.json"
OUTPUT_JSON = ROOT / "data" / "enterprise-search-surface-probe" / "latest.json"
OUTPUT_MD = ROOT / "context" / "enterprise-search-surface-probe.md"

TARGET_CUSTODY = "enterprise_search_knowledge_custody"
SURFACE = "query_fixture"


def load_eligibility(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"decisions": [], "missing_input": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"decisions": [], "unreadable_input": f"{path}: {exc.msg}"}


def enterprise_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        decision
        for decision in payload.get("decisions", [])
        if decision.get("eligibility") == "current_infrastructure"
        and decision.get("custody_type") == TARGET_CUSTODY
    ]


def build_fixture(row: dict[str, Any]) -> dict[str, Any]:
    repo = str(row.get("repo", "unknown/repo"))
    repo_tail = repo.split("/")[-1].lower()
    return {
        "surface": SURFACE,
        "repo": repo,
        "purpose": "test whether enterprise-search custody can be reduced to local query, corpus, expected-hit, and demotion fixtures",
        "queries": [
            {
                "query": f"{repo_tail} evidence recovery",
                "expected_signal": "retrieval returns a custody-bearing document, not only a marketing summary",
            },
            {
                "query": f"{repo_tail} demotion rule",
                "expected_signal": "retrieval exposes when stale or unsupported results must be demoted",
            },
        ],
        "pass_condition": "a local fixture can express expected hits and demotions without cloning, executing, or trusting the external repo",
    }


def probe(payload: dict[str, Any]) -> dict[str, Any]:
    rows = enterprise_rows(payload)
    if not rows:
        return {
            "status": "blocked",
            "selected_surface": None,
            "reason": "no current enterprise_search_knowledge_custody eligibility row",
            "rows": [],
            "next_action": "wait for a recurring enterprise-search row before naming selector priority",
        }

    row = rows[0]
    reasons = {str(reason) for reason in row.get("reasons", [])}
    allowed = "evidence_recovery_and_demotion_present" in reasons and "executable_surface" in reasons
    fixture = build_fixture(row)
    return {
        "status": "ready" if allowed else "blocked",
        "selected_surface": SURFACE if allowed else None,
        "reason": (
            "enterprise-search row has evidence recovery, demotion evidence, and an executable surface"
            if allowed
            else "enterprise-search row lacks the evidence needed for a query fixture"
        ),
        "rows": rows,
        "fixture": fixture if allowed else None,
        "next_action": (
            "build a local query_fixture before adding selector priority"
            if allowed
            else "keep enterprise_search_knowledge_custody demoted at action selection"
        ),
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Enterprise Search Surface Probe - {receipt['generated_at']}",
        "",
        "This probe names the first downstream surface for `enterprise_search_knowledge_custody` without granting selector priority.",
        "",
        f"- status: `{receipt['status']}`",
        f"- selected surface: `{receipt.get('selected_surface') or 'none'}`",
        f"- rows: {len(receipt.get('rows', []))}",
        f"- why: {receipt['reason']}",
        f"- next: {receipt['next_action']}",
    ]
    fixture = receipt.get("fixture")
    if fixture:
        lines.extend(
            [
                "",
                "## Query Fixture",
                "",
                f"- repo: **{fixture['repo']}**",
                f"- pass condition: {fixture['pass_condition']}",
                "",
                "## Fixture Queries",
                "",
            ]
        )
        for query in fixture["queries"]:
            lines.append(f"- `{query['query']}` -> {query['expected_signal']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    payload = load_eligibility(ELIGIBILITY_JSON)
    generated_at = datetime.now(timezone.utc).isoformat()
    result = probe(payload)
    receipt = {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_path": str(ELIGIBILITY_JSON),
        **result,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


if __name__ == "__main__":
    main()
