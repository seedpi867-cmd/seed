#!/usr/bin/env python3
"""Run a local query fixture for enterprise-search custody rows."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "enterprise-search-surface-probe" / "latest.json"
DEFAULT_JSON = ROOT / "data" / "enterprise-search-query-fixture" / "latest.json"
DEFAULT_MARKDOWN = ROOT / "context" / "enterprise-search-query-fixture.md"

TOKEN_RE = re.compile(r"[a-z0-9]+")
DEMOTION_TERMS = {
    "stale",
    "archived",
    "unsupported",
    "untrusted",
    "external",
    "clone",
    "execute",
    "marketing",
    "summary",
}


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "blocked", "reason": f"surface probe input missing: {path}"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "blocked", "reason": f"surface probe input unreadable: {exc.msg}"}


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def token_counts(text: str) -> Counter[str]:
    return Counter(tokens(text))


def corpus_for_fixture(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    repo = str(fixture.get("repo", "unknown/repo"))
    repo_tail = repo.split("/")[-1].lower()
    return [
        {
            "id": "custody_contract",
            "title": f"{repo} local enterprise-search custody contract",
            "body": (
                f"{repo_tail} evidence recovery uses a local corpus, a stable query surface, "
                "expected hits, evidence artifacts, and demotion rules before any selector priority."
            ),
            "demote": False,
            "demotion_reason": "",
        },
        {
            "id": "demotion_rule",
            "title": f"{repo} stale-result demotion rule",
            "body": (
                f"{repo_tail} demotion rule: demote stale summaries, unsupported execution advice, "
                "external clone pressure, and claims without custody artifacts."
            ),
            "demote": False,
            "demotion_reason": "",
        },
        {
            "id": "stale_marketing_summary",
            "title": f"{repo} marketing summary without custody",
            "body": (
                f"{repo_tail} is a powerful enterprise search platform. This stale marketing summary "
                "has no local evidence artifact, no expected hit, and no recovery path."
            ),
            "demote": True,
            "demotion_reason": "marketing or stale summary lacks custody evidence",
        },
        {
            "id": "unsupported_external_clone",
            "title": f"{repo} unsupported external execution path",
            "body": (
                f"{repo_tail} instructions say to clone the external repository and execute it directly. "
                "That unsupported external action is untrusted in this local fixture."
            ),
            "demote": True,
            "demotion_reason": "external clone or execution pressure is outside the local fixture",
        },
        {
            "id": "unrelated_body_weather",
            "title": "Body weather receipt",
            "body": "temperature, memory, swap, and latency route the loop budget but do not answer enterprise search queries.",
            "demote": False,
            "demotion_reason": "",
        },
    ]


def search(query: str, corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query_counts = token_counts(query)
    results: list[dict[str, Any]] = []
    for doc in corpus:
        doc_text = f"{doc['title']} {doc['body']}"
        doc_counts = token_counts(doc_text)
        overlap = sum(min(query_counts[token], doc_counts[token]) for token in query_counts)
        demotion_hits = sorted(set(tokens(doc_text)) & DEMOTION_TERMS)
        penalty = 2 if doc.get("demote") else 0
        score = overlap - penalty
        results.append(
            {
                "doc_id": doc["id"],
                "score": score,
                "raw_overlap": overlap,
                "demoted": bool(doc.get("demote")),
                "demotion_hits": demotion_hits,
                "demotion_reason": doc.get("demotion_reason", ""),
                "title": doc["title"],
            }
        )
    return sorted(results, key=lambda item: (item["score"], item["raw_overlap"], item["doc_id"]), reverse=True)


def expected_queries(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    fixture_queries = fixture.get("queries", [])
    query_texts = [str(item.get("query", "")) for item in fixture_queries if item.get("query")]
    if len(query_texts) < 2:
        repo_tail = str(fixture.get("repo", "unknown/repo")).split("/")[-1].lower()
        query_texts = [f"{repo_tail} evidence recovery", f"{repo_tail} demotion rule"]
    return [
        {
            "query": query_texts[0],
            "expected_top_doc": "custody_contract",
            "demoted_below": ["stale_marketing_summary", "unsupported_external_clone"],
        },
        {
            "query": query_texts[1],
            "expected_top_doc": "demotion_rule",
            "demoted_below": ["stale_marketing_summary", "unsupported_external_clone"],
        },
    ]


def evaluate(fixture: dict[str, Any]) -> dict[str, Any]:
    corpus = corpus_for_fixture(fixture)
    assertions: list[dict[str, Any]] = []
    for expected in expected_queries(fixture):
        results = search(expected["query"], corpus)
        ranks = {result["doc_id"]: rank for rank, result in enumerate(results, start=1)}
        top_doc = results[0]["doc_id"] if results else None
        expected_top_doc = expected["expected_top_doc"]
        top_hit_passed = top_doc == expected_top_doc
        demotion_passed = all(
            ranks.get(doc_id, 0) > ranks.get(expected_top_doc, 999)
            for doc_id in expected["demoted_below"]
        )
        assertions.append(
            {
                "query": expected["query"],
                "expected_top_doc": expected_top_doc,
                "actual_top_doc": top_doc,
                "top_hit_passed": top_hit_passed,
                "demoted_below": expected["demoted_below"],
                "demotion_passed": demotion_passed,
                "results": results,
            }
        )
    passed = all(item["top_hit_passed"] and item["demotion_passed"] for item in assertions)
    return {
        "status": "passed" if passed else "failed",
        "repo": fixture.get("repo", "unknown/repo"),
        "surface": fixture.get("surface", "query_fixture"),
        "corpus_doc_count": len(corpus),
        "assertion_count": len(assertions),
        "assertions": assertions,
        "pass_condition": (
            "local queries returned expected custody-bearing hits while stale marketing and "
            "unsupported external execution rows were demoted"
        ),
        "next_action": (
            "selector priority can now be considered for enterprise_search_knowledge_custody"
            if passed
            else "keep enterprise_search_knowledge_custody demoted until the local query fixture passes"
        ),
    }


def run_fixture(surface_payload: dict[str, Any]) -> dict[str, Any]:
    if surface_payload.get("status") != "ready":
        return {
            "status": "blocked",
            "repo": None,
            "surface": None,
            "reason": surface_payload.get("reason", "surface probe is not ready"),
            "next_action": "wait for enterprise search surface probe to select query_fixture",
        }
    fixture = surface_payload.get("fixture")
    if not isinstance(fixture, dict) or fixture.get("surface") != "query_fixture":
        return {
            "status": "blocked",
            "repo": None,
            "surface": None,
            "reason": "surface probe did not provide a query_fixture object",
            "next_action": "re-run enterprise_search_surface_probe.py before query fixture",
        }
    return evaluate(fixture)


def render_markdown(receipt: dict[str, Any], source_path: Path) -> str:
    lines = [
        f"# Enterprise Search Query Fixture - {receipt['generated_at']}",
        "",
        f"Source: `{source_path}`",
        "",
        "This fixture tests `enterprise_search_knowledge_custody` on local corpus rows only.",
        "",
        f"- status: `{receipt['status']}`",
        f"- repo: `{receipt.get('repo') or 'none'}`",
        f"- surface: `{receipt.get('surface') or 'none'}`",
        f"- next: {receipt['next_action']}",
    ]
    if receipt["status"] in {"passed", "failed"}:
        lines.extend(
            [
                f"- corpus docs: {receipt['corpus_doc_count']}",
                f"- assertions: {receipt['assertion_count']}",
                f"- pass condition: {receipt['pass_condition']}",
                "",
                "## Assertions",
                "",
            ]
        )
        for assertion in receipt["assertions"]:
            lines.append(
                f"- `{assertion['query']}` -> expected `{assertion['expected_top_doc']}`, "
                f"got `{assertion['actual_top_doc']}`; "
                f"hit={assertion['top_hit_passed']} demotion={assertion['demotion_passed']}"
            )
    else:
        lines.append(f"- why: {receipt.get('reason', 'blocked')}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat()
    surface_payload = load_payload(args.input)
    result = run_fixture(surface_payload)
    receipt = {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_path": str(args.input),
        **result,
    }

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(receipt, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(receipt, args.input), encoding="utf-8")

    print(f"enterprise search query fixture {receipt['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
