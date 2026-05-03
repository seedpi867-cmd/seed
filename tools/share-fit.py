#!/usr/bin/env python3
"""Decide whether a thread is a good place to mention Seed."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass


DEFAULT_REPO = "seedpi867-cmd/seed"

GOOD_SIGNALS = {
    "agent": "autonomous agent discussion",
    "agents": "autonomous agent discussion",
    "raspberry pi": "small Linux hardware",
    "pi zero": "small Linux hardware",
    "self-hosted": "self-hosted systems",
    "self hosted": "self-hosted systems",
    "clone": "cloneability or first-boot evidence",
    "first boot": "cloneability or first-boot evidence",
    "reproducible": "reproducible setup",
    "custody": "capability custody",
    "capability": "capability boundaries",
    "approval": "agent approval boundaries",
    "audit": "auditability",
    "memory": "persistent memory",
    "markdown": "filesystem knowledge or markdown memory",
    "git": "git-backed state",
    "edge": "edge compute",
    "linux": "small Linux machines",
}

BAD_SIGNALS = {
    "giveaway": "promotion thread",
    "follow for follow": "engagement farming",
    "upvote": "engagement farming",
    "like and subscribe": "engagement farming",
    "crypto": "off-topic speculation",
    "airdrop": "promotion thread",
    "coupon": "commercial promotion",
    "job": "hiring thread",
    "hiring": "hiring thread",
}


@dataclass(frozen=True)
class Fit:
    decision: str
    score: int
    reasons: list[str]
    warning: str


def normalize_repo(repo: str) -> str:
    repo = repo.strip()
    if "/" not in repo:
        return DEFAULT_REPO
    owner, name = repo.split("/", 1)
    if not owner or not name:
        return DEFAULT_REPO
    return f"{owner}/{name}"


def github_url(repo: str) -> str:
    return f"https://github.com/{normalize_repo(repo)}"


def find_signals(text: str, signals: dict[str, str]) -> list[str]:
    found: list[str] = []
    lowered = text.lower()
    for needle, reason in signals.items():
        if re.search(rf"\b{re.escape(needle)}\b", lowered):
            found.append(reason)
    return sorted(set(found))


def score_text(text: str) -> Fit:
    good = find_signals(text, GOOD_SIGNALS)
    bad = find_signals(text, BAD_SIGNALS)
    score = len(good) * 2 - len(bad) * 3
    reasons = [f"+ {reason}" for reason in good] + [f"- {reason}" for reason in bad]

    if bad and score <= 1:
        return Fit("SKIP_LINK", score, reasons, "The context looks promotional or off-topic.")
    if score >= 4:
        return Fit("SHARE_CLONE_ASK", score, reasons, "Mention the repo only after adding a useful technical point.")
    if score >= 2:
        return Fit("ADD_VALUE_ONLY", score, reasons, "A comment may fit, but the repo link needs a direct reason.")
    return Fit("SKIP_LINK", score, reasons, "The Seed link would probably be ornamental here.")


def render(fit: Fit, repo: str) -> str:
    repo = normalize_repo(repo)
    lines = [
        f"Decision: {fit.decision}",
        f"Score: {fit.score}",
        f"Repo: {github_url(repo)}",
        "",
        "Reasons:",
    ]
    if fit.reasons:
        lines.extend(f"- {reason}" for reason in fit.reasons)
    else:
        lines.append("- no strong Seed-specific fit signals found")

    lines.extend(["", f"Warning: {fit.warning}", ""])
    if fit.decision == "SHARE_CLONE_ASK":
        lines.extend(
            [
                "Suggested repo mention:",
                "I would test this by cloning it and running `bash tools/clone-doctor.sh`; "
                f"Seed is built around turning first-boot success or failure into public evidence: {github_url(repo)}",
            ]
        )
    elif fit.decision == "ADD_VALUE_ONLY":
        lines.extend(
            [
                "Suggested action:",
                "Write the technical comment first. Add the repo only if the clone-doctor evidence path directly answers the thread.",
            ]
        )
    else:
        lines.extend(
            [
                "Suggested action:",
                "Do not include the repo link. If you have a useful thought, post it without Seed.",
            ]
        )
    return "\n".join(lines)


def read_context(args: argparse.Namespace) -> str:
    parts = []
    if args.text:
        parts.append(" ".join(args.text))
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            parts.append(piped)
    return "\n".join(parts).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", nargs="*", help="thread title, draft, or context; stdin is also accepted")
    parser.add_argument("--repo", default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO))
    args = parser.parse_args()

    context = read_context(args)
    if not context:
        print("No thread or draft text supplied.", file=sys.stderr)
        return 2

    fit = score_text(context)
    print(render(fit, args.repo))
    return 0 if fit.decision != "SKIP_LINK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
