#!/usr/bin/env python3
"""Print the shortest path from a fresh clone to public run evidence."""

from __future__ import annotations

import argparse
import os


DEFAULT_REPO = "seedpi867-cmd/seed"


def normalize_repo(repo: str) -> str:
    repo = repo.strip()
    if "/" not in repo:
        return DEFAULT_REPO
    owner, name = repo.split("/", 1)
    if not owner or not name:
        return DEFAULT_REPO
    return f"{owner}/{name}"


def github_url(repo: str) -> str:
    return f"https://github.com/{repo}"


def issue_url(repo: str, template: str) -> str:
    return f"{github_url(repo)}/issues/new?template={template}"


def render(repo: str) -> str:
    repo = normalize_repo(repo)
    return "\n".join(
        [
            "Seed clone evidence kit",
            f"repo: {repo}",
            "",
            "1. Run the clean clone check:",
            "",
            "```bash",
            f"git clone {github_url(repo)}.git seed",
            "cd seed",
            "bash tools/clone-doctor.sh",
            "```",
            "",
            "2. If it passes, generate paste-ready clone-proof fields:",
            "",
            "```bash",
            "bash tools/clone-doctor.sh 2>&1 \\",
            "  | python3 tools/redact-report.py \\",
            "  | python3 tools/share-proof.py --issue-fields",
            "```",
            "",
            f"Clone proof: {issue_url(repo, 'clone-proof.yml')}",
            "",
            "3. If it fails, generate a clone-report draft:",
            "",
            "```bash",
            "bash tools/clone-doctor.sh 2>&1 \\",
            "  | python3 tools/redact-report.py \\",
            "  | python3 tools/clone-report-summary.py",
            "```",
            "",
            f"Clone report: {issue_url(repo, 'clone-report.yml')}",
            "",
            "4. Check current public propagation and successful clone proofs:",
            "",
            "```bash",
            "python3 tools/propagation-report.py",
            "python3 tools/clone-proof-board.py",
            "```",
            "",
            "A useful proof names the machine, OS, backend path, exact command, and anything surprising.",
            "A useful failure report preserves the first rough edge instead of smoothing it away.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO),
        help="GitHub repo in owner/name form; defaults to SEED_GITHUB_REPO",
    )
    args = parser.parse_args()
    print(render(args.repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
