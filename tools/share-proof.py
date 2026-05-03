#!/usr/bin/env python3
"""Extract a short public proof note from clone-doctor output."""
import argparse
import os
import re
import sys


DEFAULT_REPO = "seedpi867-cmd/seed"
FIELD_PATTERNS = {
    "host": re.compile(r"^host:\s*(.+)$", re.M),
    "kernel": re.compile(r"^kernel:\s*(.+)$", re.M),
    "os": re.compile(r"^os:\s*(.+)$", re.M),
}


def github_web_url(repo):
    return f"https://github.com/{repo}"


def clone_proof_url(repo):
    return f"{github_web_url(repo)}/issues/new?template=clone-proof.yml"


def extract_proof(text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("I cloned https://github.com/") and "clone-doctor.sh passed" in line:
            return line
    return ""


def find_field(text, name, fallback="unknown"):
    match = FIELD_PATTERNS[name].search(text)
    if match is None:
        return fallback
    return match.group(1).strip()


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
    proof_url = clone_proof_url(repo)
    full = f"{note}\nClone proof: {proof_url}"
    if len(full) <= max_length:
        return full

    shorter = f"{note}\nProof: {proof_url}"
    if len(shorter) <= max_length:
        return shorter

    suffix = f"\nProof: {proof_url}"
    budget = max_length - len(suffix) - 4
    if budget < 40:
        return f"Clone proof: {proof_url}"
    return f"{note[:budget].rstrip()}...{suffix}"


def build_issue_fields(text, repo, max_length):
    note = build_note(text, repo, max_length)
    if not note:
        return ""
    return "\n".join(
        [
            "Machine:",
            f"{find_field(text, 'host')} / {find_field(text, 'kernel')}",
            "",
            "OS:",
            find_field(text, "os"),
            "",
            "Backend tested:",
            "clone-doctor only",
            "",
            "Shareable proof:",
            note,
            "",
            "Notes:",
            "Fresh clone-doctor run; no backend setup attempted unless stated above.",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO))
    parser.add_argument("--max-length", type=int, default=500)
    parser.add_argument(
        "--issue-fields",
        action="store_true",
        help="print paste-ready fields for the clone-proof issue form",
    )
    args = parser.parse_args()

    text = sys.stdin.read()
    note = (
        build_issue_fields(text, args.repo, args.max_length)
        if args.issue_fields
        else build_note(text, args.repo, args.max_length)
    )
    if not note:
        print("No clone-doctor shareable proof found in input.", file=sys.stderr)
        return 1
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
