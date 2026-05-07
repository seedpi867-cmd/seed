#!/usr/bin/env python3
"""Preserve passed query-fixture chunks as a compact retrieval packet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
DEFAULT_FIXTURE = ROOT / "data" / "enterprise-search-query-fixture" / "latest.json"
DEFAULT_ACTION = ROOT / "data" / "repo-pattern-action" / "latest.json"
DEFAULT_ROUTE = ROOT / "data" / "robotics-path-probe" / "latest.json"
DEFAULT_JSON = ROOT / "data" / "retrieval-loom-packet" / "latest.json"
DEFAULT_MARKDOWN = ROOT / "context" / "retrieval-loom-packet.md"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "reason": f"missing input: {path}"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "unreadable", "reason": f"unreadable input {path}: {exc.msg}"}
    return payload if isinstance(payload, dict) else {"status": "invalid", "reason": f"non-object input: {path}"}


def add_doc(target: dict[str, dict[str, Any]], result: dict[str, Any], query: str, role: str) -> None:
    doc_id = str(result.get("doc_id", "unknown"))
    doc = target.setdefault(
        doc_id,
        {
            "doc_id": doc_id,
            "title": result.get("title", ""),
            "role": role,
            "queries": [],
            "best_score": result.get("score"),
            "demotion_hits": sorted(result.get("demotion_hits", [])),
            "demotion_reason": result.get("demotion_reason", ""),
        },
    )
    if query not in doc["queries"]:
        doc["queries"].append(query)
    score = result.get("score")
    if isinstance(score, (int, float)) and (
        not isinstance(doc.get("best_score"), (int, float)) or score > doc["best_score"]
    ):
        doc["best_score"] = score
    hits = set(doc.get("demotion_hits", [])) | set(result.get("demotion_hits", []))
    doc["demotion_hits"] = sorted(hits)
    if result.get("demotion_reason") and not doc.get("demotion_reason"):
        doc["demotion_reason"] = result["demotion_reason"]


def build_packet(fixture: dict[str, Any], action_payload: dict[str, Any], route_payload: dict[str, Any]) -> dict[str, Any]:
    if fixture.get("status") != "passed":
        return {
            "status": "blocked",
            "reason": fixture.get("reason", "query fixture has not passed"),
            "repo": fixture.get("repo"),
            "next_action": "wait for a passed local query fixture before preserving retrieval chunks",
        }

    winning_docs: dict[str, dict[str, Any]] = {}
    losing_docs: dict[str, dict[str, Any]] = {}
    control_docs: dict[str, dict[str, Any]] = {}
    assertions = fixture.get("assertions", [])
    if not isinstance(assertions, list):
        assertions = []

    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        query = str(assertion.get("query", ""))
        expected_top_doc = str(assertion.get("expected_top_doc", ""))
        demoted_below = {str(doc_id) for doc_id in assertion.get("demoted_below", [])}
        for result in assertion.get("results", []):
            if not isinstance(result, dict):
                continue
            doc_id = str(result.get("doc_id", ""))
            if doc_id == expected_top_doc:
                add_doc(winning_docs, result, query, "winner")
            elif result.get("demoted") or doc_id in demoted_below:
                add_doc(losing_docs, result, query, "loser")
            elif result.get("raw_overlap") == 0:
                add_doc(control_docs, result, query, "control")

    action = action_payload.get("action") if isinstance(action_payload.get("action"), dict) else {}
    route_plan = route_payload.get("route_plan") if isinstance(route_payload.get("route_plan"), dict) else {}
    selected_surface = action.get("selected_surface") or route_plan.get("selected_surface")
    downstream_action = {
        "selected_repo": action.get("selected_repo") or fixture.get("repo"),
        "selected_surface": selected_surface,
        "route_path": route_plan.get("path", []),
        "route_cost": route_plan.get("cost"),
        "next_action": action.get("next_action") or "query_fixture selected repo",
    }

    return {
        "status": "ready",
        "repo": fixture.get("repo"),
        "surface": fixture.get("surface"),
        "source_fixture_generated_at": fixture.get("generated_at"),
        "winning_docs": sorted(winning_docs.values(), key=lambda item: item["doc_id"]),
        "losing_docs": sorted(losing_docs.values(), key=lambda item: item["doc_id"]),
        "control_docs": sorted(control_docs.values(), key=lambda item: item["doc_id"]),
        "missing_evidence": [
            "no external repo clone",
            "no external repo execution",
            "no generalized priority beyond this repo-matched fresh receipt",
            "no full chunk text persisted beyond fixture titles, ids, scores, and demotion reasons",
        ],
        "stop_conditions": [
            "fixture status is not passed",
            "fixture repo no longer matches selector repo",
            "fixture generated_at is older than eligibility generated_at",
            "expected top hit fails",
            "demotion assertion fails",
        ],
        "downstream_action": downstream_action,
        "packet_rule": (
            "carry both the winning local chunks and the losing demoted chunks forward; "
            "do not treat the external repo as authority"
        ),
        "next_action": "use this packet as the retrieval unit for the next natural same-cycle fixture pass",
    }


def render_markdown(packet: dict[str, Any], fixture_path: Path, action_path: Path, route_path: Path) -> str:
    lines = [
        f"# Retrieval Loom Packet - {packet['generated_at']}",
        "",
        f"Fixture: `{fixture_path}`",
        f"Action: `{action_path}`",
        f"Route: `{route_path}`",
        "",
        "This packet preserves the local retrieval evidence before any broader action.",
        "",
        f"- status: `{packet['status']}`",
        f"- repo: `{packet.get('repo') or 'none'}`",
        f"- surface: `{packet.get('surface') or 'none'}`",
        f"- next: {packet['next_action']}",
    ]
    if packet["status"] != "ready":
        lines.append(f"- why: {packet.get('reason', 'blocked')}")
        lines.append("")
        return "\n".join(lines)

    action = packet["downstream_action"]
    lines.extend(
        [
            f"- downstream surface: `{action.get('selected_surface')}`",
            f"- route path: `{' -> '.join(action.get('route_path') or [])}`",
            f"- packet rule: {packet['packet_rule']}",
            "",
            "## Winning Local Docs",
            "",
        ]
    )
    for doc in packet["winning_docs"]:
        lines.append(
            f"- `{doc['doc_id']}` score={doc.get('best_score')} queries={', '.join(doc['queries'])}: {doc['title']}"
        )
    lines.extend(["", "## Losing Local Docs", ""])
    for doc in packet["losing_docs"]:
        reason = doc.get("demotion_reason") or "lost to custody-bearing expected hit"
        hits = ", ".join(doc.get("demotion_hits", [])) or "none"
        lines.append(
            f"- `{doc['doc_id']}` score={doc.get('best_score')} hits={hits}: {reason}"
        )
    lines.extend(["", "## Control Docs", ""])
    for doc in packet.get("control_docs", []):
        lines.append(
            f"- `{doc['doc_id']}` score={doc.get('best_score')} queries={', '.join(doc['queries'])}: zero-overlap control"
        )
    lines.extend(["", "## Missing Evidence", ""])
    for item in packet.get("missing_evidence", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Stop Conditions", ""])
    for item in packet.get("stop_conditions", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--action", type=Path, default=DEFAULT_ACTION)
    parser.add_argument("--route", type=Path, default=DEFAULT_ROUTE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    fixture = load_json(args.fixture)
    action = load_json(args.action)
    route = load_json(args.route)
    receipt = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_paths": {
            "fixture": str(args.fixture),
            "action": str(args.action),
            "route": str(args.route),
        },
        **build_packet(fixture, action, route),
    }

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(receipt, args.fixture, args.action, args.route), encoding="utf-8")

    print(f"retrieval loom packet {receipt['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
