#!/usr/bin/env python3
"""Select one actionable repo-pattern row for the next loop move."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
RUNTIME_ROOT = HOME if (HOME / "data").exists() else ROOT
DEFAULT_INPUT = RUNTIME_ROOT / "data" / "repo-pattern-eligibility" / "latest.json"
DEFAULT_SURFACE_INPUT = RUNTIME_ROOT / "data" / "robotics-path-probe" / "latest.json"
DEFAULT_QUERY_FIXTURE_INPUT = RUNTIME_ROOT / "data" / "enterprise-search-query-fixture" / "latest.json"
DEFAULT_JSON = RUNTIME_ROOT / "data" / "repo-pattern-action" / "latest.json"
DEFAULT_MARKDOWN = RUNTIME_ROOT / "context" / "repo-pattern-action.md"

PRIORITY_BY_CUSTODY = {
    "agentic_ci_workflow_custody": 100,
    "robotics_algorithm_curriculum_custody": 95,
    "cloud_asset_query_custody": 90,
    "visual_web_crawler_custody": 85,
    "shortcut_compiler_custody": 80,
    "python_ui_framework_custody": 75,
    "web_framework_route_custody": 70,
    "ai_api_gateway_quota_custody": 60,
    "driver_assistance_runtime_custody": 55,
    "course_catalog_curation_custody": 40,
}
ENTERPRISE_SEARCH_PRIORITY = 65
ENTERPRISE_SEARCH_CUSTODY = "enterprise_search_knowledge_custody"


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def parse_generated_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def query_fixture_gate(
    decision: dict[str, Any],
    receipt: dict[str, Any] | None,
    minimum_generated_at: str | None = None,
) -> tuple[bool, str]:
    if str(decision.get("custody_type", "")) != ENTERPRISE_SEARCH_CUSTODY:
        return False, "not an enterprise-search custody row"
    repo = decision.get("repo", decision.get("selected_repo"))
    if not receipt:
        return False, "enterprise-search query fixture receipt missing"
    minimum_time = parse_generated_at(minimum_generated_at)
    fixture_time = parse_generated_at(receipt.get("generated_at"))
    if minimum_time is not None:
        if fixture_time is None:
            return False, "enterprise-search query fixture has no generated_at freshness evidence"
        if fixture_time < minimum_time:
            return False, "enterprise-search query fixture is older than the current eligibility receipt"
    if receipt.get("status") != "passed":
        return False, f"enterprise-search query fixture status is {receipt.get('status', 'unknown')}"
    if receipt.get("repo") != repo:
        return False, "enterprise-search query fixture belongs to a different repo"
    if receipt.get("surface") != "query_fixture":
        return False, "enterprise-search query fixture did not run the query_fixture surface"

    assertions = receipt.get("assertions", [])
    if not assertions:
        return False, "enterprise-search query fixture has no assertions"
    for assertion in assertions:
        if not assertion.get("top_hit_passed") or not assertion.get("demotion_passed"):
            return False, "enterprise-search query fixture assertions did not all pass"
    return True, "passed repo-matched fresh enterprise-search query fixture"


def selector_priority(
    decision: dict[str, Any],
    query_fixture_receipt: dict[str, Any] | None = None,
    minimum_generated_at: str | None = None,
) -> int | None:
    custody_type = str(decision.get("custody_type", ""))
    if custody_type in PRIORITY_BY_CUSTODY:
        return PRIORITY_BY_CUSTODY[custody_type]
    gate_passed, _ = query_fixture_gate(decision, query_fixture_receipt, minimum_generated_at)
    if gate_passed:
        return ENTERPRISE_SEARCH_PRIORITY
    return None


def has_selector_priority(
    decision: dict[str, Any],
    query_fixture_receipt: dict[str, Any] | None = None,
    minimum_generated_at: str | None = None,
) -> bool:
    return selector_priority(decision, query_fixture_receipt, minimum_generated_at) is not None


def demotion_reason(
    decision: dict[str, Any],
    query_fixture_receipt: dict[str, Any] | None = None,
    minimum_generated_at: str | None = None,
) -> str:
    custody_type = str(decision.get("custody_type", "unknown_custody"))
    if custody_type == ENTERPRISE_SEARCH_CUSTODY:
        _, reason = query_fixture_gate(decision, query_fixture_receipt, minimum_generated_at)
        return (
            f"{custody_type} is current_infrastructure upstream, but selector priority is gated by "
            f"a passed repo-matched query fixture: {reason}"
        )
    return (
        f"{custody_type} is current_infrastructure upstream, but this selector has no "
        "custody-specific priority rule for it"
    )


def missing_input_action(path: Path) -> dict[str, Any]:
    return {
        "status": "blocked",
        "selected_repo": None,
        "selected_repo_url": None,
        "custody_type": None,
        "reason": f"eligibility input missing: {path}",
        "next_action": "run repo_pattern_eligibility_reader.py before selecting a repo action",
        "candidate_count": 0,
        "demoted_candidate_count": 0,
        "demoted_candidates": [],
        "selected_surface": None,
        "surface_source": "none",
        "surface_reason": "no eligibility receipt available",
        "query_fixture_source": "none",
        "query_fixture_reason": "no eligibility receipt available",
    }


def candidate_score(
    decision: dict[str, Any],
    query_fixture_receipt: dict[str, Any] | None = None,
    minimum_generated_at: str | None = None,
) -> tuple[int, int]:
    reasons = {str(reason) for reason in decision.get("reasons", [])}
    score = selector_priority(decision, query_fixture_receipt, minimum_generated_at)
    if score is None:
        score = 0
    if "executable_surface" in reasons:
        score += 5
    if "evidence_recovery_and_demotion_present" in reasons:
        score += 3
    return score, -len(str(decision.get("repo", "")))


def matching_surface(action: dict[str, Any], receipt: dict[str, Any] | None, source_path: Path) -> dict[str, Any]:
    if not receipt:
        return {
            "selected_surface": None,
            "surface_source": "missing",
            "surface_reason": "no prior robotics path receipt",
        }

    source_action = receipt.get("source_action", {})
    route_plan = receipt.get("route_plan", {})
    if not isinstance(source_action, dict) or not isinstance(route_plan, dict):
        return {
            "selected_surface": None,
            "surface_source": "ignored",
            "surface_reason": "prior robotics path receipt has no source_action/route_plan object",
        }

    if (
        source_action.get("selected_repo") != action.get("selected_repo")
        or source_action.get("custody_type") != action.get("custody_type")
    ):
        return {
            "selected_surface": None,
            "surface_source": "ignored",
            "surface_reason": "prior robotics path receipt belongs to a different selected repo or custody type",
        }

    selected_surface = route_plan.get("selected_surface")
    if not selected_surface:
        return {
            "selected_surface": None,
            "surface_source": "ignored",
            "surface_reason": "prior robotics path receipt did not select a surface",
        }

    return {
        "selected_surface": selected_surface,
        "surface_source": str(source_path),
        "surface_reason": "inherited from matching prior robotics path receipt",
    }


def matching_query_fixture(
    action: dict[str, Any],
    receipt: dict[str, Any] | None,
    source_path: Path,
    minimum_generated_at: str | None = None,
) -> dict[str, Any]:
    gate_passed, reason = query_fixture_gate(action, receipt, minimum_generated_at)
    if not gate_passed:
        return {
            "query_fixture_source": "missing" if receipt is None else "ignored",
            "query_fixture_reason": reason,
        }
    return {
        "query_fixture_source": str(source_path),
        "query_fixture_reason": reason,
    }


def select_action(
    payload: dict[str, Any],
    surface_receipt: dict[str, Any] | None = None,
    surface_path: Path = DEFAULT_SURFACE_INPUT,
    query_fixture_receipt: dict[str, Any] | None = None,
    query_fixture_path: Path = DEFAULT_QUERY_FIXTURE_INPUT,
) -> dict[str, Any]:
    decisions = list(payload.get("decisions", []))
    eligibility_generated_at = payload.get("generated_at")
    candidates = [
        decision
        for decision in decisions
        if decision.get("eligibility") == "current_infrastructure"
    ]
    prioritized_candidates = [
        decision
        for decision in candidates
        if has_selector_priority(decision, query_fixture_receipt, eligibility_generated_at)
    ]
    demoted_candidates = [
        {
            "repo": decision.get("repo", "unknown"),
            "custody_type": decision.get("custody_type", "unknown_custody"),
            "reason": demotion_reason(decision, query_fixture_receipt, eligibility_generated_at),
        }
        for decision in candidates
        if not has_selector_priority(decision, query_fixture_receipt, eligibility_generated_at)
    ]
    if not candidates:
        return {
            "status": "blocked",
            "selected_repo": None,
            "selected_repo_url": None,
            "custody_type": None,
            "reason": "no current_infrastructure eligibility rows",
            "next_action": "wait for classifier or eligibility reader to admit a row",
            "candidate_count": 0,
            "demoted_candidate_count": 0,
            "demoted_candidates": [],
            "selected_surface": None,
            "surface_source": "none",
            "surface_reason": "no selected repo action",
            "query_fixture_source": "none",
            "query_fixture_reason": "no selected repo action",
        }
    if not prioritized_candidates:
        return {
            "status": "blocked",
            "selected_repo": None,
            "selected_repo_url": None,
            "custody_type": None,
            "reason": "no current_infrastructure rows have selector priority rules",
            "next_action": "add an explicit selector priority rule or leave the row demoted at action selection",
            "candidate_count": len(candidates),
            "demoted_candidate_count": len(demoted_candidates),
            "demoted_candidates": demoted_candidates,
            "selected_surface": None,
            "surface_source": "none",
            "surface_reason": "selector demoted every current row without a custody-specific priority rule",
            "query_fixture_source": "none",
            "query_fixture_reason": "selector demoted every current row without a custody-specific priority rule",
        }

    selected = max(
        prioritized_candidates,
        key=lambda decision: candidate_score(decision, query_fixture_receipt, eligibility_generated_at),
    )
    custody_type = str(selected.get("custody_type", "unknown_custody"))
    priority = selector_priority(selected, query_fixture_receipt, eligibility_generated_at)
    reason = (
        f"{custody_type} has priority {priority} because a passed repo-matched query fixture "
        "proved expected hits and demotions on local corpus rows"
        if custody_type == ENTERPRISE_SEARCH_CUSTODY
        else (
            f"{custody_type} has priority {priority} "
            "because it can turn external workflow patterns into local loop execution policy"
        )
    )
    action = {
        "status": "selected",
        "selected_repo": selected.get("repo", "unknown"),
        "selected_repo_url": selected.get("repo_url", ""),
        "custody_type": custody_type,
        "reason": reason,
        "next_action": "deeper pattern study or local prototype",
        "candidate_count": len(candidates),
        "demoted_candidate_count": len(demoted_candidates),
        "demoted_candidates": demoted_candidates,
    }
    action.update(matching_surface(action, surface_receipt, surface_path))
    action.update(matching_query_fixture(action, query_fixture_receipt, query_fixture_path, eligibility_generated_at))
    if custody_type == ENTERPRISE_SEARCH_CUSTODY and action["query_fixture_source"] not in {"missing", "ignored"}:
        action["selected_surface"] = "query_fixture"
        action["surface_source"] = action["query_fixture_source"]
        action["surface_reason"] = action["query_fixture_reason"]
        action["next_action"] = "query_fixture selected repo"
    elif action["selected_surface"]:
        action["next_action"] = f"{action['selected_surface']} selected repo"
    return action


def render_markdown(action: dict[str, Any], source_path: Path, generated_at: str) -> str:
    lines = [
        f"# Repo Pattern Action - {generated_at}",
        "",
        f"Source: `{source_path}`",
        "",
        "This selector consumes `current_infrastructure` eligibility rows and chooses one repo to steer the next build or study.",
        "",
    ]
    if action["status"] == "selected":
        lines.extend(
            [
                f"- selected: **{action['selected_repo']}**",
                f"- url: {action['selected_repo_url']}",
                f"- custody_type: `{action['custody_type']}`",
                f"- candidates: {action['candidate_count']}",
                f"- demoted candidates: {action.get('demoted_candidate_count', 0)}",
                f"- selected surface: `{action.get('selected_surface') or 'none'}`",
                f"- surface source: `{action.get('surface_source', 'none')}`",
                f"- query fixture source: `{action.get('query_fixture_source', 'none')}`",
                f"- why: {action['reason']}",
                f"- surface reason: {action.get('surface_reason', 'none')}",
                f"- query fixture reason: {action.get('query_fixture_reason', 'none')}",
                f"- next: {action['next_action']}",
            ]
        )
    else:
        lines.extend(
            [
                "- selected: none",
                f"- candidates: {action['candidate_count']}",
                f"- demoted candidates: {action.get('demoted_candidate_count', 0)}",
                f"- selected surface: `{action.get('selected_surface') or 'none'}`",
                f"- query fixture source: `{action.get('query_fixture_source', 'none')}`",
                f"- why: {action['reason']}",
                f"- query fixture reason: {action.get('query_fixture_reason', 'none')}",
                f"- next: {action['next_action']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--surface-input", type=Path, default=DEFAULT_SURFACE_INPUT)
    parser.add_argument("--query-fixture-input", type=Path, default=DEFAULT_QUERY_FIXTURE_INPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    surface_receipt = load_optional_receipt(args.surface_input)
    query_fixture_receipt = load_optional_receipt(args.query_fixture_input)
    generated_at = datetime.now(timezone.utc).isoformat()
    if args.input.exists():
        payload = load_payload(args.input)
        action = select_action(payload, surface_receipt, args.surface_input, query_fixture_receipt, args.query_fixture_input)
    else:
        action = missing_input_action(args.input)
    output = {
        "schema_version": 1,
        "generated_at": generated_at,
        "source_path": str(args.input),
        "action": action,
    }

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(action, args.input, generated_at), encoding="utf-8")

    if action["status"] == "selected":
        print(f"selected {action['selected_repo']} from {action['candidate_count']} current_infrastructure rows")
    else:
        print(f"blocked: {action['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
