#!/usr/bin/env python3
"""Turn repo-pattern classifier rows into downstream eligibility decisions."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "repo-pattern-classifier" / "latest.jsonl"
DEFAULT_JSON = ROOT / "data" / "repo-pattern-eligibility" / "latest.json"
DEFAULT_MARKDOWN = ROOT / "context" / "repo-pattern-eligibility.md"

ELIGIBILITY_STATES = {
    "current_infrastructure",
    "watch_only",
    "historical_reference",
    "demoted",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append(
                {
                    "repo": f"line-{line_no}",
                    "repo_url": "",
                    "admission_status": "defect",
                    "custody_type": "unreadable_json",
                    "defects": [f"json_decode_error:{exc.msg}"],
                }
            )
            continue
        rows.append(row)
    return rows


def text_blob(row: dict[str, Any]) -> str:
    fields = [
        "repo",
        "custody_type",
        "raw_object",
        "admitted_object",
        "stable_surface",
        "volatile_substrate",
        "authority_owner",
        "evidence_artifact",
        "fallback_or_recovery_path",
        "demotion_rule",
    ]
    parts = [str(row.get(field, "")) for field in fields]
    parts.extend(str(topic) for topic in row.get("topics", []) if topic)
    return " ".join(parts).lower()


def infer_maintenance_authority(row: dict[str, Any], blob: str) -> str:
    if any(token in blob for token in (" archived", "read-only", "readonly", "unmaintained")):
        return "inactive"
    if "deprecated" in blob or "will not get new features" in blob:
        return "deprecated"
    if "beta" in blob or "experimental" in blob:
        return "volatile"
    if "maintainers" in blob or "authority_owner" in row:
        return "active_or_claimed"
    return "unknown"


def infer_operational_residue(row: dict[str, Any], blob: str) -> str:
    residue_markers = (
        "cli",
        "api",
        "sdk",
        "lsp",
        "ci",
        "database",
        "query",
        "sandbox",
        "proxy",
        "recipes",
        "docker",
        "wireguard",
        "tailscale",
        "runtime",
        "receipts",
    )
    if any(marker in blob for marker in residue_markers):
        return "executable_surface"
    if str(row.get("evidence_artifact", "")).strip():
        return "documented_claim"
    return "none"


def decide(row: dict[str, Any]) -> dict[str, Any]:
    blob = text_blob(row)
    defects = [str(defect) for defect in row.get("defects", [])]
    custody_type = str(row.get("custody_type", "unknown_custody"))
    admission_status = str(row.get("admission_status", "defect"))
    demotion_rule = str(row.get("demotion_rule", "")).strip()
    evidence = str(row.get("evidence_artifact", "")).strip()
    recovery = str(row.get("fallback_or_recovery_path", "")).strip()
    maintenance_authority = infer_maintenance_authority(row, blob)
    operational_residue = infer_operational_residue(row, blob)

    reasons: list[str] = []
    blockers: list[str] = []

    if admission_status != "admitted":
        blockers.append(f"admission_status={admission_status}")
    if defects:
        blockers.append("classifier_defects_present")
    if not demotion_rule:
        blockers.append("missing_demotion_rule")
    if custody_type == "unknown_custody":
        blockers.append("unknown_custody")
    if "demote unless a later classifier run" in demotion_rule.lower():
        blockers.append("self_demoting_classifier_row")
    if maintenance_authority == "inactive":
        blockers.append("inactive_maintenance_authority")
    if operational_residue == "none":
        blockers.append("no_operational_residue")

    if blockers:
        if "inactive_maintenance_authority" in blockers and custody_type != "unknown_custody":
            eligibility = "historical_reference"
            next_action = "keep as pattern evidence only; do not clone or wire"
        else:
            eligibility = "demoted"
            next_action = "exclude from future build pressure until a better classifier row exists"
        reasons.extend(blockers)
    elif maintenance_authority in {"deprecated", "volatile"}:
        eligibility = "watch_only"
        next_action = "watch for stability evidence before treating as infrastructure"
        reasons.append(f"maintenance_authority={maintenance_authority}")
    elif evidence and recovery and operational_residue == "executable_surface":
        eligibility = "current_infrastructure"
        next_action = "eligible for deeper study or local prototype"
        reasons.extend(["specific_custody_type", "evidence_recovery_and_demotion_present", "executable_surface"])
    else:
        eligibility = "watch_only"
        next_action = "hold for more evidence before future action"
        reasons.append("insufficient_runtime_evidence")

    assert eligibility in ELIGIBILITY_STATES
    return {
        "repo": row.get("repo", "unknown"),
        "repo_url": row.get("repo_url", ""),
        "custody_type": custody_type,
        "eligibility": eligibility,
        "maintenance_authority": maintenance_authority,
        "operational_residue": operational_residue,
        "reasons": reasons,
        "next_action": next_action,
    }


def render_markdown(decisions: list[dict[str, Any]], source_path: Path, generated_at: str) -> str:
    counts = Counter(str(decision["eligibility"]) for decision in decisions)
    lines = [
        f"# Repo Pattern Eligibility - {generated_at}",
        "",
        f"Source: `{source_path}`",
        "",
        "This reader consumes classifier rows and decides whether each repo can steer future action.",
        "",
        "## Counts",
        "",
    ]
    for state in ["current_infrastructure", "watch_only", "historical_reference", "demoted"]:
        lines.append(f"- {state}: {counts.get(state, 0)}")
    lines.extend(["", "## Decisions", ""])
    for decision in decisions:
        reasons = "; ".join(decision["reasons"]) or "no reasons recorded"
        lines.append(
            f"- **{decision['repo']}** -> `{decision['eligibility']}` "
            f"({decision['custody_type']}; {decision['maintenance_authority']}; "
            f"{decision['operational_residue']})"
        )
        lines.append(f"  - why: {reasons}")
        lines.append(f"  - next: {decision['next_action']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    if not rows:
        raise SystemExit(f"no rows read from {args.input}")

    generated_at = datetime.now(timezone.utc).isoformat()
    decisions = [decide(row) for row in rows]
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_path": str(args.input),
        "counts": dict(Counter(str(decision["eligibility"]) for decision in decisions)),
        "decisions": decisions,
    }

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(decisions, args.input, generated_at), encoding="utf-8")

    counts = payload["counts"]
    print(
        "wrote "
        f"{len(decisions)} eligibility decisions to {args.json_output} "
        f"(current_infrastructure={counts.get('current_infrastructure', 0)}, "
        f"watch_only={counts.get('watch_only', 0)}, "
        f"historical_reference={counts.get('historical_reference', 0)}, "
        f"demoted={counts.get('demoted', 0)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
