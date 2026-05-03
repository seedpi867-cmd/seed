#!/usr/bin/env python3
"""Route a Seed problem report to the right public issue path."""

from __future__ import annotations

import argparse
import os


DEFAULT_REPO = "seedpi867-cmd/seed"


class Route:
    def __init__(self, name: str, reason: str, url: str, next_step: str) -> None:
        self.name = name
        self.reason = reason
        self.url = url
        self.next_step = next_step


def repo_name() -> str:
    repo = os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO).strip()
    if "/" not in repo:
        return DEFAULT_REPO
    owner, name = repo.split("/", 1)
    if not owner or not name:
        return DEFAULT_REPO
    return f"{owner}/{name}"


def issue_url(repo: str, template: str | None = None) -> str:
    base = f"https://github.com/{repo}/issues/new"
    if template:
        return f"{base}?template={template}"
    return base


def classify(text: str, repo: str | None = None) -> Route:
    repo = repo or repo_name()
    lowered = text.lower()

    capability_words = (
        "api key",
        "credential",
        "token",
        "password",
        "oauth",
        "secret",
        "permission",
        "capability",
        "custody",
        "endpoint",
        "publish",
        "shell",
        "systemd",
        "sudo",
        "network",
    )
    clone_words = (
        "clone",
        "install",
        "setup",
        "first boot",
        "clone-doctor",
        "health check",
        "raspberry pi",
        "debian",
        "ubuntu",
        "missing command",
        "module not found",
        "permission denied",
        "service failed",
    )

    if any(word in lowered for word in capability_words):
        return Route(
            name="capability review",
            reason="The report is about what Seed can read, write, run, publish, or access.",
            url=issue_url(repo, "capability-review.yml"),
            next_step="Name the capability, current boundary, risk, and smallest proposed change.",
        )

    if any(word in lowered for word in clone_words):
        return Route(
            name="clone report",
            reason="The report is about first-boot, setup, hardware, OS, or clone diagnostics.",
            url=issue_url(repo, "clone-report.yml"),
            next_step="Run clone-doctor, redact the output, and include machine, OS, command, expected, and actual result.",
        )

    return Route(
        name="plain issue",
        reason="The report does not clearly match clone evidence or a custody boundary.",
        url=issue_url(repo),
        next_step="Open a plain issue with exact commands, relevant output, expected result, and actual result.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="*", help="Short description of the problem or contribution")
    parser.add_argument("--repo", default=None, help="GitHub repo in owner/name form; defaults to SEED_GITHUB_REPO")
    args = parser.parse_args()

    text = " ".join(args.text).strip()
    if not text:
        parser.error("describe the problem, for example: clone-doctor fails on Ubuntu")

    route = classify(text, args.repo)
    print(f"route: {route.name}")
    print(f"reason: {route.reason}")
    print(f"url: {route.url}")
    print(f"next: {route.next_step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
