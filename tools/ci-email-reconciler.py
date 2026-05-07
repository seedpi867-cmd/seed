#!/usr/bin/env python3
"""Classify GitHub Actions failure emails against current workflow state."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


DEFAULT_REPO = "seedpi867-cmd/seed"


def github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()

    cred_path = os.path.expanduser("~/.git-credentials")
    try:
        text = open(cred_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""

    match = re.search(r"https://[^:\s]+:([^@\s]+)@github\.com", text)
    return match.group(1).strip() if match else ""


@dataclass(frozen=True)
class Notice:
    repo: str
    workflow: str
    branch: str
    sha: str


def fetch_json(url: str, timeout: int = 15, attempts: int = 3) -> dict:
    headers = {"User-Agent": "Seed CI email reconciler"}
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_error: Exception | None = None
    for _ in range(attempts):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except http.client.IncompleteRead as exc:
            last_error = exc
            partial = exc.partial.decode("utf-8", errors="replace")
            try:
                return json.loads(partial)
            except json.JSONDecodeError:
                continue

    if last_error:
        raise last_error
    raise RuntimeError("GitHub API request failed without an exception")


def parse_notice(text: str, fallback_repo: str) -> Notice:
    repo = fallback_repo
    repo_match = re.search(r"\[([\w.-]+/[\w.-]+)\]", text)
    if repo_match:
        repo = repo_match.group(1)

    subject_match = re.search(
        r"Run failed:\s*(?P<workflow>.+?)\s*-\s*(?P<branch>[\w./-]+)\s*\((?P<sha>[0-9a-fA-F]{7,40})\)",
        text,
    )
    workflow = subject_match.group("workflow").strip() if subject_match else ""
    branch = subject_match.group("branch").strip() if subject_match else ""
    sha = subject_match.group("sha").lower() if subject_match else ""

    workflow_match = re.search(r"Workflow:\s*(.+)", text)
    if workflow_match:
        workflow = workflow_match.group(1).strip()

    if not workflow or not sha:
        raise ValueError("could not extract workflow and commit sha from notice")

    return Notice(repo=repo, workflow=workflow, branch=branch or "main", sha=sha)


def runs_url(repo: str, limit: int) -> str:
    return f"https://api.github.com/repos/{repo}/actions/runs?per_page={limit}"


def matching_runs(data: dict, notice: Notice) -> list[dict]:
    matches = []
    for run in data.get("workflow_runs", []):
        if run.get("name") != notice.workflow:
            continue
        if notice.branch and run.get("head_branch") != notice.branch:
            continue
        matches.append(run)
    return matches


def run_conclusion(run: dict | None) -> str:
    if not run:
        return "unknown"
    return run.get("conclusion") or run.get("status") or "unknown"


def classify(notice: Notice, runs: list[dict]) -> tuple[str, str]:
    named = next(
        (run for run in runs if str(run.get("head_sha", "")).lower().startswith(notice.sha)),
        None,
    )
    latest = runs[0] if runs else None

    if not latest:
        return "UNREPRODUCIBLE", "no matching workflow runs were returned"

    latest_conclusion = run_conclusion(latest)
    named_conclusion = run_conclusion(named)

    if latest_conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
        return "LIVE_FAILURE", f"latest matching run is {latest_conclusion}"
    if named and named_conclusion == "success":
        return "CURRENT_SUCCESS", "named run succeeded"
    if named and named_conclusion == "failure" and latest_conclusion == "success":
        return "STALE_FAILURE", "named run failed, but latest matching run succeeded"
    if not named:
        return "UNREPRODUCIBLE", "named commit was not found in recent matching runs"
    if latest_conclusion == "success":
        return "STALE_FAILURE", f"latest matching run succeeded; named run is {named_conclusion}"
    return "UNREPRODUCIBLE", f"latest matching run is {latest_conclusion}"


def summarize_run(label: str, run: dict | None) -> str:
    if not run:
        return f"{label}: none"
    sha = str(run.get("head_sha", ""))[:7]
    conclusion = run_conclusion(run)
    return (
        f"{label}: {run.get('created_at', '')} {run.get('name', '')} "
        f"{run.get('head_branch', '')} {sha} {conclusion} {run.get('html_url', '')}"
    )


def reconcile_text(text: str, repo: str = DEFAULT_REPO, limit: int = 20) -> tuple[str, str, Notice, dict | None, dict | None]:
    notice = parse_notice(text, repo)
    data = fetch_json(runs_url(notice.repo, limit))
    runs = matching_runs(data, notice)
    named = next(
        (run for run in runs if str(run.get("head_sha", "")).lower().startswith(notice.sha)),
        None,
    )
    latest = runs[0] if runs else None
    verdict, reason = classify(notice, runs)
    return verdict, reason, notice, named, latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository, owner/name")
    parser.add_argument("--workflow", help="workflow name from the failure notice")
    parser.add_argument("--branch", default="main", help="branch from the failure notice")
    parser.add_argument("--sha", help="commit sha from the failure notice")
    parser.add_argument("--limit", type=int, default=20, help="recent run count to inspect")
    args = parser.parse_args()

    try:
        if args.workflow and args.sha:
            notice = Notice(args.repo, args.workflow, args.branch, args.sha.lower())
            data = fetch_json(runs_url(notice.repo, args.limit))
            runs = matching_runs(data, notice)
            named = next(
                (run for run in runs if str(run.get("head_sha", "")).lower().startswith(notice.sha)),
                None,
            )
            latest = runs[0] if runs else None
            verdict, reason = classify(notice, runs)
        else:
            verdict, reason, notice, named, latest = reconcile_text(sys.stdin.read(), args.repo, args.limit)
    except (
        ValueError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        http.client.IncompleteRead,
    ) as exc:
        print(f"UNREPRODUCIBLE: {exc}")
        return 2

    print(verdict)
    print(f"reason: {reason}")
    print(f"notice: {notice.repo} {notice.workflow} {notice.branch} {notice.sha[:7]}")
    print(summarize_run("named", named))
    print(summarize_run("latest", latest))
    return 1 if verdict == "LIVE_FAILURE" else 0


if __name__ == "__main__":
    sys.exit(main())
