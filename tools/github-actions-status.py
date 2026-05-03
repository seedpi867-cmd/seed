#!/usr/bin/env python3
"""Print recent public GitHub Actions runs without requiring gh auth."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_REPO = "seedpi867-cmd/seed"


def actions_runs_url(repo: str, limit: int) -> str:
    return f"https://api.github.com/repos/{repo}/actions/runs?per_page={limit}"


def fetch_json(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": "Seed actions status"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def summarize_runs(data) -> list[dict[str, str]]:
    summaries = []
    for run in data.get("workflow_runs", []):
        summaries.append(
            {
                "id": str(run.get("id", "")),
                "name": run.get("name", ""),
                "branch": run.get("head_branch", ""),
                "sha": str(run.get("head_sha", ""))[:7],
                "status": run.get("status", ""),
                "conclusion": run.get("conclusion") or "",
                "created_at": run.get("created_at", ""),
                "url": run.get("html_url", ""),
            }
        )
    return summaries


def latest_state(runs: list[dict[str, str]]) -> str:
    if not runs:
        return "unknown"
    latest = runs[0]
    conclusion = latest.get("conclusion") or latest.get("status") or "unknown"
    return f"{latest.get('name', 'workflow')} at {latest.get('sha', '')}: {conclusion}"


def main() -> int:
    repo = os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO)
    limit = int(os.environ.get("SEED_ACTIONS_LIMIT", "5"))

    print("Seed GitHub Actions status")
    print(f"repo: {repo}")
    print()

    try:
        data = fetch_json(actions_runs_url(repo, limit))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"GitHub Actions: unavailable ({exc})")
        return 1

    runs = summarize_runs(data)
    print(f"latest: {latest_state(runs)}")
    print()
    print("Recent runs")
    for run in runs:
        conclusion = run["conclusion"] or run["status"] or "unknown"
        print(
            f"- {run['created_at']} {run['name']} "
            f"{run['branch']} {run['sha']} {conclusion} {run['url']}"
        )
    if not runs:
        print("- none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
