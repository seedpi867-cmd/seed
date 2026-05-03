#!/usr/bin/env python3
"""Print a compact, shareable repo card for Seed."""

from __future__ import annotations

import argparse
import os


DEFAULT_REPO = "seedpi867-cmd/seed"
DEFAULT_SITE = "https://seed-brain.vercel.app"


def normalize_repo(repo: str) -> str:
    repo = repo.strip()
    if "/" not in repo:
        return DEFAULT_REPO
    owner, name = repo.split("/", 1)
    if not owner or not name:
        return DEFAULT_REPO
    return f"{owner}/{name}"


def normalize_site(site: str) -> str:
    site = site.strip().rstrip("/")
    if not site.startswith(("http://", "https://")):
        return DEFAULT_SITE
    return site


def github_url(repo: str) -> str:
    return f"https://github.com/{repo}"


def issue_url(repo: str, template: str) -> str:
    return f"{github_url(repo)}/issues/new?template={template}"


def clone_command(repo: str) -> str:
    return f"git clone {github_url(repo)}.git seed && cd seed && bash tools/clone-doctor.sh"


def render_text(repo: str, site: str) -> str:
    repo = normalize_repo(repo)
    site = normalize_site(site)
    return "\n".join(
        [
            "Seed is a cloneable autonomous agent loop for cheap Linux edge devices.",
            "The useful test is not whether the demo looks alive; it is whether the repo survives a fresh clone on someone else's machine.",
            "",
            f"Repo: {github_url(repo)}",
            f"Live instance: {site}",
            f"Run: {clone_command(repo)}",
            f"Clean run proof: {issue_url(repo, 'clone-proof.yml')}",
            f"Failure report: {issue_url(repo, 'clone-report.yml')}",
        ]
    )


def render_markdown(repo: str, site: str) -> str:
    repo = normalize_repo(repo)
    site = normalize_site(site)
    return "\n".join(
        [
            "### Seed",
            "",
            "Seed is a cloneable autonomous agent loop for cheap Linux edge devices.",
            "The useful test is whether it survives a fresh clone on someone else's machine.",
            "",
            f"- Repo: [{repo}]({github_url(repo)})",
            f"- Live instance: [{site}]({site})",
            f"- Run: `{clone_command(repo)}`",
            f"- Clean run proof: [{issue_url(repo, 'clone-proof.yml')}]({issue_url(repo, 'clone-proof.yml')})",
            f"- Failure report: [{issue_url(repo, 'clone-report.yml')}]({issue_url(repo, 'clone-report.yml')})",
        ]
    )


def render(repo: str, site: str, output_format: str) -> str:
    if output_format == "markdown":
        return render_markdown(repo, site)
    return render_text(repo, site)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO),
        help="GitHub repo in owner/name form; defaults to SEED_GITHUB_REPO",
    )
    parser.add_argument(
        "--site",
        default=os.environ.get("SEED_PUBLIC_SITE", DEFAULT_SITE),
        help="public site URL; defaults to SEED_PUBLIC_SITE",
    )
    parser.add_argument(
        "--format",
        choices=("text", "markdown"),
        default="text",
        help="output format",
    )
    args = parser.parse_args()
    print(render(args.repo, args.site, args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
