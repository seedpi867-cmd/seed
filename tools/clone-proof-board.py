#!/usr/bin/env python3
"""Build a hardware compatibility table from public clone-proof issues."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request


DEFAULT_REPO = "seedpi867-cmd/seed"
FIELD_RE = re.compile(r"^###\s+(.+?)\s*$", re.M)


def issues_url(repo: str, state: str, limit: int) -> str:
    label = urllib.parse.quote("clone-proof")
    return (
        f"https://api.github.com/repos/{repo}/issues"
        f"?state={state}&labels={label}&per_page={limit}"
    )


def fetch_json(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": "Seed clone proof board"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def issue_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    matches = list(FIELD_RE.finditer(body or ""))
    for index, match in enumerate(matches):
        label = match.group(1).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        value = body[start:end].strip()
        value = re.sub(r"^```[a-zA-Z0-9_-]*\n|\n```$", "", value).strip()
        if value and value != "_No response_":
            fields[label] = " ".join(value.split())
    return fields


def one_line(value: str, fallback: str = "unknown") -> str:
    value = " ".join((value or "").split())
    return value if value else fallback


def markdown_cell(value: str) -> str:
    return one_line(value).replace("|", "\\|")


def summarize_issue(issue: dict) -> dict[str, str]:
    fields = issue_fields(issue.get("body") or "")
    return {
        "number": str(issue.get("number", "")),
        "state": issue.get("state", ""),
        "title": issue.get("title", ""),
        "url": issue.get("html_url", ""),
        "created_at": issue.get("created_at", ""),
        "machine": fields.get("machine", ""),
        "os": fields.get("os", ""),
        "backend": fields.get("backend tested", ""),
        "proof": fields.get("shareable proof", ""),
    }


def proof_rows(issues: list[dict]) -> list[dict[str, str]]:
    rows = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        rows.append(summarize_issue(issue))
    return rows


def build_table(issues: list[dict], repo: str, limit: int) -> str:
    rows = proof_rows(issues)[:limit]
    lines = [
        f"# Clone Proof Board: {repo}",
        "",
        "Successful clone-doctor runs reported through public clone-proof issues.",
        "",
    ]
    if not rows:
        lines.extend([
            "No clone proofs found yet.",
            "",
            f"Open one: https://github.com/{repo}/issues/new?template=clone-proof.yml",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "| Issue | Machine | OS | Backend | State | Created |",
        "|---|---|---|---|---|---|",
    ])
    for row in rows:
        issue_label = f"#{row['number']}" if row["number"] else "issue"
        issue_link = f"[{issue_label}]({row['url']})" if row["url"] else issue_label
        created = row["created_at"][:10] if row["created_at"] else "unknown"
        lines.append(
            "| "
            + " | ".join(
                [
                    issue_link,
                    markdown_cell(row["machine"]),
                    markdown_cell(row["os"]),
                    markdown_cell(row["backend"],),
                    markdown_cell(row["state"]),
                    markdown_cell(created),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO))
    parser.add_argument("--state", default="all", choices=("open", "closed", "all"))
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    issues = fetch_json(issues_url(args.repo, args.state, max(args.limit, 1)))
    sys.stdout.write(build_table(issues, args.repo, args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
