#!/usr/bin/env python3
"""Extract a short public proof note from clone-doctor output."""
import argparse
import os
import re
import sys


DEFAULT_REPO = "seedpi867-cmd/seed"


def github_web_url(repo):
    return f"https://github.com/{repo}"


def clone_report_url(repo):
    return f"{github_web_url(repo)}/issues/new?template=clone-report.yml"


def extract_proof(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("I cloned https://github.com/") and "clone-doctor.sh passed" in line:
            return line
    return ""


def compact_proof(proof, repo):
    if not proof:
        return ""
    proof = re.sub(r"^I cloned https://github.com/[^ ]+ on ", "", proof)
    proof = proof.replace("; tools/clone-doctor.sh passed ", "; passed ")
    proof = proof.replace(", and left the git tree clean.", "; git tree clean.")
    return f"Cloned {github_web_url(repo)} on {proof}"


def build_note(text, repo, max_length):
    proof = extract_proof(text)
    if not proof:
        return ""
    note = compact_proof(proof, repo)
    report = clone_report_url(repo)
    full = f"{note}\nClone report: {report}"
    if len(full) <= max_length:
        return full

    shorter = f"{note}\nReport: {report}"
    if len(shorter) <= max_length:
        return shorter

    suffix = f"\nReport: {report}"
    budget = max_length - len(suffix) - 4
    if budget < 40:
        return f"Clone report: {report}"
    return f"{note[:budget].rstrip()}...{suffix}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO))
    parser.add_argument("--max-length", type=int, default=500)
    args = parser.parse_args()

    text = sys.stdin.read()
    note = build_note(text, args.repo, args.max_length)
    if not note:
        print("No clone-doctor shareable proof found in input.", file=sys.stderr)
        return 1
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
