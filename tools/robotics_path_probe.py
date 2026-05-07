#!/usr/bin/env python3
"""Plan a safe next-action route from the selected repo action."""

from __future__ import annotations

import heapq
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
ACTION_JSON = ROOT / "data" / "repo-pattern-action" / "latest.json"
BODY_JSON = ROOT / "data" / "body-weather-router" / "latest.json"
OUTPUT_JSON = ROOT / "data" / "robotics-path-probe" / "latest.json"
OUTPUT_MD = ROOT / "context" / "robotics-path-probe.md"


SURFACE_PROFILES: dict[str, dict[str, Any]] = {
    "study": {
        "base_cost": 2.0,
        "risk": 1.0,
        "value": 7.0,
        "description": "read source/docs and extract a local pattern",
    },
    "query_fixture": {
        "base_cost": 2.5,
        "risk": 1.0,
        "value": 9.0,
        "description": "run the selected local query fixture and preserve its receipt",
    },
    "local_prototype": {
        "base_cost": 5.0,
        "risk": 4.0,
        "value": 10.0,
        "description": "build a Seed-owned local prototype on local data",
    },
    "fixture": {
        "base_cost": 3.0,
        "risk": 1.5,
        "value": 8.0,
        "description": "encode the pattern as a deterministic fixture/test",
    },
    "watch_only": {
        "base_cost": 1.0,
        "risk": 0.5,
        "value": 2.0,
        "description": "keep the repo visible without acting on it",
    },
    "refuse": {
        "base_cost": 0.5,
        "risk": 0.0,
        "value": 0.0,
        "description": "refuse action because constraints dominate",
    },
}

BODY_SURFACE_RULES = {
    "write_or_build": {
        "allowed": {"study", "query_fixture", "local_prototype", "fixture", "watch_only", "refuse"},
        "penalties": {},
    },
    "script_small": {
        "allowed": {"study", "query_fixture", "fixture", "watch_only", "refuse"},
        "penalties": {"study": 1.0, "fixture": 0.5},
    },
    "delay_or_maintain": {
        "allowed": {"watch_only", "refuse"},
        "penalties": {"watch_only": 1.0},
    },
    "unknown": {
        "allowed": {"watch_only", "refuse"},
        "penalties": {"watch_only": 2.0},
    },
}

HIGH_RISK_CUSTODY_BLOCKS = {
    "driver_assistance_runtime_custody": {
        "local_prototype": "would approach vehicle-control runtime instead of local loop policy",
    },
    "visual_web_crawler_custody": {
        "local_prototype": "could become live external crawling instead of fixture-bound parsing",
    },
    "ai_api_gateway_quota_custody": {
        "local_prototype": "could touch external API credentials or quota surfaces",
    },
}

SURFACE_ORDER = ["query_fixture", "study", "fixture", "local_prototype", "watch_only", "refuse"]
START = "selected_repo"
GOAL = "measured_receipt"


def read_action() -> dict:
    if not ACTION_JSON.exists():
        return {"status": "missing", "selected_repo": None, "custody_type": None}
    try:
        data = json.loads(ACTION_JSON.read_text())
    except json.JSONDecodeError as exc:
        return {"status": "unreadable", "error": str(exc)}
    return data.get("action", data)


def read_body() -> dict[str, Any]:
    if not BODY_JSON.exists():
        return {"route": "unknown", "reasons": ["body-weather receipt missing"]}
    try:
        data = json.loads(BODY_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"route": "unknown", "reasons": [f"body-weather receipt unreadable: {exc.msg}"]}
    return data


def body_route(body: dict[str, Any]) -> str:
    route = str(body.get("route", "unknown"))
    if route not in BODY_SURFACE_RULES:
        return "unknown"
    return route


def score_surface(surface: str, action: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    profile = SURFACE_PROFILES[surface]
    route = body_route(body)
    rule = BODY_SURFACE_RULES[route]
    custody_type = str(action.get("custody_type", "unknown_custody"))
    selected_surface = action.get("selected_surface")
    blocked: list[str] = []

    if action.get("status") != "selected" and surface not in {"watch_only", "refuse"}:
        blocked.append("no selected repo action")
    if selected_surface and surface not in {selected_surface, "refuse"}:
        blocked.append(f"selected action surface is {selected_surface}")
    if surface not in rule["allowed"]:
        blocked.append(f"body route {route} does not allow {surface}")
    custody_blocks = HIGH_RISK_CUSTODY_BLOCKS.get(custody_type, {})
    if surface in custody_blocks:
        blocked.append(custody_blocks[surface])

    body_penalty = float(rule["penalties"].get(surface, 0.0))
    risk = float(profile["risk"])
    value = float(profile["value"])
    cost = float(profile["base_cost"]) + body_penalty + risk - (value * 0.35)
    if surface == "refuse":
        cost += 6.0 if action.get("status") == "selected" else 0.0
    if blocked:
        cost = None

    return {
        "surface": surface,
        "description": profile["description"],
        "allowed": not blocked,
        "blocked_reasons": blocked,
        "base_cost": profile["base_cost"],
        "body_penalty": body_penalty,
        "risk": risk,
        "value": value,
        "score": round(cost, 3) if cost is not None else None,
    }


def build_candidates(action: dict[str, Any], body: dict[str, Any]) -> list[dict[str, Any]]:
    return [score_surface(surface, action, body) for surface in SURFACE_ORDER]


def build_graph(candidates: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    edges: dict[str, list[tuple[str, float]]] = {START: [], GOAL: []}
    for candidate in candidates:
        surface = str(candidate["surface"])
        edges[surface] = []
        if candidate["allowed"]:
            edges[START].append((surface, float(candidate["score"])))
            edges[surface].append((GOAL, 0.0))
    return edges


def search(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    graph = build_graph(candidates)
    frontier: list[tuple[float, int, str]] = []
    heapq.heappush(frontier, (0.0, 0, START))
    came_from: dict[str, str | None] = {START: None}
    cost_so_far: dict[str, float] = {START: 0.0}
    expansions = 0
    sequence = 0

    while frontier:
        _, _, current = heapq.heappop(frontier)
        expansions += 1
        if current == GOAL:
            break

        for nxt, move_cost in graph[current]:
            new_cost = cost_so_far[current] + move_cost
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                sequence += 1
                heapq.heappush(frontier, (new_cost, sequence, nxt))
                came_from[nxt] = current

    if GOAL not in came_from:
        return {
            "status": "failed",
            "path": [],
            "cost": None,
            "expansions": expansions,
            "selected_surface": None,
        }

    path: list[str] = []
    current = GOAL
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return {
        "status": "found",
        "path": path,
        "cost": round(cost_so_far[GOAL], 3),
        "expansions": expansions,
        "selected_surface": path[1] if len(path) > 2 else None,
    }


def render_markdown(receipt: dict) -> str:
    route = receipt["route_plan"]
    action = receipt["source_action"]
    candidates = receipt["candidate_surfaces"]
    blocked_count = sum(1 for candidate in candidates if not candidate["allowed"])
    selected_surface = route.get("selected_surface") or "none"
    return "\n".join(
        [
            f"# Robotics Path Probe - {receipt['generated_at']}",
            "",
            "A repo-action route planner distilled from the selected PythonRobotics pattern.",
            "",
            f"- selected repo: **{action.get('selected_repo', 'unknown')}**",
            f"- custody type: `{action.get('custody_type', 'unknown')}`",
            f"- body route: `{receipt['body_weather'].get('route', 'unknown')}`",
            f"- source pattern: `{receipt['source_pattern']}`",
            f"- route status: `{route['status']}`",
            f"- selected surface: `{selected_surface}`",
            f"- route path: `{' -> '.join(route['path']) if route['path'] else 'none'}`",
            f"- route cost: {route['cost']}",
            f"- planner expansions: {route['expansions']}",
            f"- candidate surfaces: {len(candidates)}",
            f"- blocked surfaces: {blocked_count}",
            "",
            "## Surface Scores",
            "",
            *[
                (
                    f"- `{candidate['surface']}`: "
                    f"{'allowed' if candidate['allowed'] else 'blocked'}, "
                    f"score={candidate['score']}, risk={candidate['risk']}, value={candidate['value']}"
                )
                for candidate in candidates
            ],
            "",
            "The useful pattern is not robotics hardware control. It is the custody split:",
            "map the action surfaces, reject unsafe transitions before expansion, keep an explicit frontier, then emit a path receipt.",
            "",
            "Next layer: feed the selected surface into the next build decision instead of treating all current_infrastructure repos as equally actionable.",
            "",
        ]
    )


def main() -> None:
    action = read_action()
    body = read_body()
    candidates = build_candidates(action, body)
    route_plan = search(candidates)
    receipt = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_action": action,
        "body_weather": {
            "route": body_route(body),
            "temperature_c": body.get("temperature_c"),
            "available_mb": body.get("memory", {}).get("available_mb") if isinstance(body.get("memory"), dict) else None,
            "reasons": body.get("reasons", []),
        },
        "source_pattern": "AtsushiSakai/PythonRobotics A* frontier plus verify_node gate",
        "candidate_surfaces": candidates,
        "route_plan": route_plan,
        "verdict": "layer" if route_plan["status"] == "found" else "abandon",
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt))
    print(
        "[robotics-path-probe] "
        f"{route_plan['status']} surface={route_plan['selected_surface']} "
        f"cost={route_plan['cost']} expansions={route_plan['expansions']}"
    )


if __name__ == "__main__":
    main()
