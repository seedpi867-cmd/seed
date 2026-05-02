#!/usr/bin/env python3
"""Turn clone-doctor output into a compact GitHub clone report."""

from __future__ import annotations

import argparse
import re
import sys


FIELD_PATTERNS = {
    "root": re.compile(r"^root:\s*(.+)$", re.M),
    "host": re.compile(r"^host:\s*(.+)$", re.M),
    "kernel": re.compile(r"^kernel:\s*(.+)$", re.M),
    "os": re.compile(r"^os:\s*(.+)$", re.M),
    "proof": re.compile(r"^I cloned .+$", re.M),
}


def find_field(text: str, name: str, fallback: str = "unknown") -> str:
    match = FIELD_PATTERNS[name].search(text)
    if match is None:
        return fallback
    return match.group(1).strip() if match.lastindex else match.group(0).strip()


def find_failures(text: str) -> list[str]:
    failures = []
    for line in text.splitlines():
        if line.startswith("fail ") or line.startswith("fail: "):
            failures.append(line.strip())
    return failures


def find_dirty_state(text: str) -> str:
    marker = "== git state after checks =="
    if marker not in text:
        return "unknown"
    after = text.split(marker, 1)[1].lstrip("\r\n").splitlines()
    interesting = []
    for line in after:
        if line.startswith("clone doctor passed") or line.startswith("If this ran"):
            break
        if line.strip():
            interesting.append(line.rstrip())
    return "\n".join(interesting) if interesting else "unknown"


def summarize(text: str, command: str) -> str:
    failures = find_failures(text)
    status = "failed" if failures else "passed"
    failure_text = "\n".join(f"- {line}" for line in failures) if failures else "- none"
    proof = find_field(text, "proof", "")
    proof_block = f"\nShareable proof:\n\n> {proof}\n" if proof else ""

    return "\n".join(
        [
            "## Clone Report Draft",
            "",
            f"Machine: {find_field(text, 'host')} / {find_field(text, 'kernel')}",
            f"OS: {find_field(text, 'os')}",
            f"Install path: {find_field(text, 'root')}",
            "",
            "Commands run:",
            "",
            "```bash",
            command,
            "```",
            "",
            f"Result: clone doctor {status}",
            "",
            "Failures:",
            failure_text,
            "",
            "Git state after checks:",
            "",
            "```text",
            find_dirty_state(text),
            "```",
            proof_block.rstrip(),
            "",
            "Expected vs actual:",
            "",
            "- Expected: clone doctor completes without private assumptions beyond documented fork-readiness warnings.",
            f"- Actual: clone doctor {status}.",
            "",
            "What I tried:",
            "",
            "- Generated this draft with `tools/clone-report-summary.py`.",
            "",
            "Relevant output:",
            "",
            "```text",
            text.strip(),
            "```",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--command",
        default="bash tools/clone-doctor.sh 2>&1 | python3 tools/redact-report.py",
        help="command to show in the report draft",
    )
    args = parser.parse_args()
    sys.stdout.write(summarize(sys.stdin.read(), args.command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
