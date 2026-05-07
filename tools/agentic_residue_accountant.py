#!/usr/bin/env python3
"""Account for workflow edges that still require runtime inference."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "agentic-residue" / "accounting.json"
DEFAULT_REPORT = ROOT / "context" / "agentic-residue-accounting.md"
DEFAULT_HISTORY = ROOT / "data" / "agentic-residue" / "history.jsonl"


def read_text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []

    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def score(found: int, expected: int) -> float:
    if expected <= 0:
        return 1.0
    return round(found / expected, 2)


def edge(
    *,
    name: str,
    producer: str,
    artifact: str,
    consumer: str,
    expected_fields: list[str],
    compiled_artifacts: list[str],
    runtime_inference_points: list[str],
    residue_type: str,
    residue_reason: str,
    evidence: str,
) -> dict[str, Any]:
    compiled_score = score(len(compiled_artifacts), len(expected_fields))
    if runtime_inference_points:
        inferred_penalty = len(runtime_inference_points) / max(len(expected_fields), 1)
        compiled_score = round(max(0.0, compiled_score - inferred_penalty), 2)
    return {
        "edge": name,
        "producer": producer,
        "artifact": artifact,
        "consumer": consumer,
        "expected_consumable_fields": expected_fields,
        "compiled_artifacts": compiled_artifacts,
        "consumer_contract": "direct fields present" if compiled_score == 1 else "partial direct fields",
        "runtime_inference_points": runtime_inference_points,
        "residue_type": residue_type,
        "residue_reason": residue_reason,
        "compiled_score": compiled_score,
        "residue_score": round(1 - compiled_score, 2),
        "evidence": evidence,
    }


def body_weather_edge() -> dict[str, Any]:
    path = ROOT / "data" / "body-weather-router" / "accounting.json"
    data = read_json(path)
    expected = [
        "rows",
        "cycles",
        "evidence_counts",
        "route_counts",
        "budget_mismatches",
        "window",
    ]
    compiled: list[str] = []
    inference: list[str] = []
    residue_type = "none"
    residue_reason = "accounting JSON exposes stable rows/cycles table fields"

    if not isinstance(data, dict):
        return edge(
            name="body-weather-accounting-json",
            producer="tools/body_weather_router.py",
            artifact=str(path.relative_to(ROOT)),
            consumer="future prompt / health inspection / residue accountant",
            expected_fields=expected,
            compiled_artifacts=[],
            runtime_inference_points=["artifact missing or invalid JSON"],
            residue_type="missing_artifact",
            residue_reason="body-weather accounting cannot be consumed directly",
            evidence="local scan",
        )

    for field in expected:
        if field in data:
            compiled.append(field)
        else:
            inference.append(f"missing top-level field: {field}")

    if data.get("rows") != data.get("cycles"):
        inference.append("rows and cycles aliases diverge")

    evidence_counts = data.get("evidence_counts")
    if isinstance(evidence_counts, dict):
        inferred = int(evidence_counts.get("timestamp_inferred", 0) or 0)
        missing = int(evidence_counts.get("none", 0) or 0)
        wake_gaps = int(evidence_counts.get("wake_receipt_gap", 0) or 0)
        if inferred:
            inference.append(f"{inferred} historical route rows still rely on timestamp inference")
        if missing:
            inference.append(f"{missing} route rows still have no body evidence")
        if wake_gaps:
            inference.append(f"{wake_gaps} closed post-gate cycles lack required wake receipts")

    if inference:
        residue_type = "missing_artifact" if any("no body evidence" in item or "lack required wake receipts" in item for item in inference) else "stale"
        residue_reason = "the schema is consumable, but older cycles still carry weak route evidence"

    return edge(
        name="body-weather-accounting-json",
        producer="tools/body_weather_router.py",
        artifact=str(path.relative_to(ROOT)),
        consumer="future prompt / health inspection / residue accountant",
        expected_fields=expected,
        compiled_artifacts=compiled,
        runtime_inference_points=inference,
        residue_type=residue_type,
        residue_reason=residue_reason,
        evidence="data/body-weather-router/accounting.json",
    )


def credential_gate_edge() -> dict[str, Any]:
    latest_path = ROOT / "data" / "credential-claim-gate" / "latest-decision.json"
    ledger_path = ROOT / "data" / "credential-claim-gate" / "claim-gate-ledger.jsonl"
    latest = read_json(latest_path)
    ledger = read_jsonl(ledger_path)
    expected = [
        "decision",
        "source",
        "timestamp",
        "warnings",
        "blocks",
        "text_hash",
        "entry_hash",
        "ledger",
    ]
    compiled: list[str] = []
    inference: list[str] = []

    if isinstance(latest, dict):
        for field in expected:
            if field == "ledger":
                if ledger:
                    compiled.append(field)
                else:
                    inference.append("claim gate ledger is missing or empty")
            elif field in latest:
                compiled.append(field)
            else:
                inference.append(f"missing latest decision field: {field}")
    else:
        inference.append("latest decision is missing or invalid JSON")

    residue_type = "none" if not inference else "missing_artifact"
    residue_reason = "deploy policy can consume deterministic allow/warn/block receipts"
    if inference:
        residue_reason = "deploy policy would need to infer claim-gate state from partial receipts"

    return edge(
        name="credential-claim-gate-deploy-receipt",
        producer="tools/credential_claim_gate.py",
        artifact=str(latest_path.relative_to(ROOT)),
        consumer="tools/deploy-blog.sh",
        expected_fields=expected,
        compiled_artifacts=compiled,
        runtime_inference_points=inference,
        residue_type=residue_type,
        residue_reason=residue_reason,
        evidence=f"{len(ledger)} ledger receipts",
    )


def context_edge() -> dict[str, Any]:
    context_dir = ROOT / "context"
    expected = ["github.md", "email.md", "news.md", "research.md", "knowledge-recall.md"]
    compiled: list[str] = []
    inference: list[str] = []
    for name in expected:
        path = context_dir / name
        if path.exists() and path.stat().st_size > 0:
            compiled.append(name)
        else:
            inference.append(f"context receipt missing or empty: {name}")

    residue_type = "none" if not inference else "missing_artifact"
    residue_reason = "fresh input receipts are available as prompt surfaces"
    if inference:
        residue_reason = "the next prompt needs to bridge absent fresh-input receipts"

    return edge(
        name="fresh-context-prompt-receipts",
        producer="feed scripts",
        artifact="context/*.md",
        consumer="brain-loop prompt assembly",
        expected_fields=expected,
        compiled_artifacts=compiled,
        runtime_inference_points=inference,
        residue_type=residue_type,
        residue_reason=residue_reason,
        evidence="context directory scan",
    )


def phase_history_edge() -> dict[str, Any]:
    path = ROOT / "state" / "phase_history.json"
    data = read_json(path)
    expected = ["phases", "last_write", "last_research", "last_dream"]
    compiled: list[str] = []
    inference: list[str] = []

    if isinstance(data, dict):
        for field in expected:
            if field in data:
                compiled.append(field)
            else:
                inference.append(f"missing phase history field: {field}")
    else:
        inference.append("phase history is missing or invalid JSON")

    residue_type = "none" if not inference else "missing_artifact"
    residue_reason = "phase recency is compiled into state"
    if inference:
        residue_reason = "phase choice would need runtime reconstruction"

    return edge(
        name="phase-history-appraisal-state",
        producer="cognitive/appraisal.py / brain-loop.sh",
        artifact=str(path.relative_to(ROOT)),
        consumer="phase selection and prompt context",
        expected_fields=expected,
        compiled_artifacts=compiled,
        runtime_inference_points=inference,
        residue_type=residue_type,
        residue_reason=residue_reason,
        evidence="state/phase_history.json",
    )


def task_build_edge() -> dict[str, Any]:
    tasks_path = ROOT / "data" / "tasks.md"
    build_path = ROOT / "data" / "current-build.md"
    tasks = read_text(tasks_path)
    build = read_text(build_path)
    expected = ["active_now_task", "current_build_file", "build_matches_now_task"]
    compiled: list[str] = []
    inference: list[str] = []

    now_match = re.search(r"## Now\s+(.*?)(?:\n## |\Z)", tasks, re.S)
    now_text = now_match.group(1).strip() if now_match else ""
    if now_text:
        compiled.append("active_now_task")
    else:
        inference.append("no active Now task found")

    if build:
        compiled.append("current_build_file")
    else:
        inference.append("current-build file missing or empty")

    backtick_names = re.findall(r"`([^`]+)`", now_text)
    primary_name = backtick_names[0].lower() if backtick_names else ""
    normalized_build = build.lower()
    if primary_name and primary_name in normalized_build:
        compiled.append("build_matches_now_task")
    else:
        inference.append("current-build does not name the active Now task artifact")

    residue_type = "none" if not inference else "stale"
    residue_reason = "task board and current build point at the same work"
    if inference:
        residue_reason = "active task and current-build tracking have drifted"

    return edge(
        name="task-board-current-build-alignment",
        producer="cycle closeout",
        artifact="data/tasks.md + data/current-build.md",
        consumer="next cycle task selection",
        expected_fields=expected,
        compiled_artifacts=compiled,
        runtime_inference_points=inference,
        residue_type=residue_type,
        residue_reason=residue_reason,
        evidence="data/tasks.md and data/current-build.md",
    )


def build_payload() -> dict[str, Any]:
    edges = [
        body_weather_edge(),
        credential_gate_edge(),
        context_edge(),
        phase_history_edge(),
        task_build_edge(),
    ]
    avoidable_types = {"contract", "missing_artifact", "unwired", "manual", "stale"}
    avoidable = [item for item in edges if item["residue_type"] in avoidable_types and item["residue_score"] > 0]
    genuine = [item for item in edges if item["residue_type"] == "genuine"]
    compiled_average = round(sum(float(item["compiled_score"]) for item in edges) / len(edges), 2) if edges else 0.0
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "edge_count": len(edges),
        "compiled_average": compiled_average,
        "residue_average": round(1 - compiled_average, 2),
        "avoidable_residue_edges": len(avoidable),
        "genuine_residue_edges": len(genuine),
        "edges": edges,
    }


def build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Agentic Residue Accounting",
        "",
        f"- generated: {payload['generated_at']}",
        f"- workflow edges scanned: {payload['edge_count']}",
        f"- compiled average: {payload['compiled_average']}",
        f"- residue average: {payload['residue_average']}",
        f"- avoidable residue edges: {payload['avoidable_residue_edges']}",
        f"- genuine residue edges: {payload['genuine_residue_edges']}",
        "",
        "| edge | compiled | residue | type | runtime inference |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in payload["edges"]:
        inference = "; ".join(item["runtime_inference_points"]) or "-"
        lines.append(
            "| {edge} | {compiled:.2f} | {residue:.2f} | {kind} | {inference} |".format(
                edge=str(item["edge"]).replace("|", "/"),
                compiled=float(item["compiled_score"]),
                residue=float(item["residue_score"]),
                kind=str(item["residue_type"]).replace("|", "/"),
                inference=inference.replace("|", "/"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    payload = build_payload()
    report = build_report(payload)
    print(report)

    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
        args.history.parent.mkdir(parents=True, exist_ok=True)
        with args.history.open("a") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
