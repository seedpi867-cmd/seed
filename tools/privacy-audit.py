#!/usr/bin/env python3
"""Scan tracked Seed files for common private-data leaks before publishing."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SKIP_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".png",
    ".pyc",
    ".sqlite",
    ".webp",
}

SKIP_PATH_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
}

EMAIL_ALLOWLIST = {
    "onboarding@resend.dev",
    "recipient@example.com",
    "your-email@gmail.com",
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Google OAuth refresh token", re.compile(r"\b1//[0-9A-Za-z_-]{20,}\b")),
    (
        "Google app password",
        re.compile(
            r"\b(?:app[-_ ]?password|gmail|smtp|imap|password)\b.{0,80}\b[a-z]{4} [a-z]{4} [a-z]{4} [a-z]{4}\b",
            re.I,
        ),
    ),
]

EMAIL_PATTERN = re.compile(r"(?<!@)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RISKY_FILENAME = re.compile(r"(^|/)(\.env|.*credential.*|.*secret.*|.*password.*|.*token\.json|.*token$)", re.I)


def tracked_files() -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
    return [Path(line) for line in proc.stdout.splitlines() if line.strip()]


def should_scan(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    return not any(part in SKIP_PATH_PARTS for part in path.parts)


def is_allowed_email(address: str) -> bool:
    lowered = address.lower()
    if lowered in EMAIL_ALLOWLIST:
        return True
    if lowered.endswith("@example.com") or lowered.endswith("@example.org"):
        return True
    return False


def line_excerpt(line: str, match: re.Match[str]) -> str:
    start = max(match.start() - 24, 0)
    end = min(match.end() + 24, len(line))
    excerpt = line[start:end].strip()
    return re.sub(r"\s+", " ", excerpt)


def scan_file(relpath: Path) -> list[str]:
    findings: list[str] = []
    path = ROOT / relpath
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return [f"{relpath}: could not read file: {exc}"]

    if RISKY_FILENAME.search(relpath.as_posix()):
        findings.append(f"{relpath}: risky filename for a public repo")

    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(f"{relpath}:{lineno}: {label}: {line_excerpt(line, match)}")

        for match in EMAIL_PATTERN.finditer(line):
            address = match.group(0)
            if not is_allowed_email(address):
                findings.append(f"{relpath}:{lineno}: real-looking email address: {address}")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan tracked files for common private-data leaks before publishing a Seed fork."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="scan the whole tree instead of git-tracked files",
    )
    args = parser.parse_args()

    if args.all:
        candidates = [
            path.relative_to(ROOT)
            for path in ROOT.rglob("*")
            if path.is_file()
        ]
    else:
        candidates = tracked_files()

    scanned = 0
    findings: list[str] = []
    for relpath in sorted(candidates):
        if not should_scan(relpath):
            continue
        scanned += 1
        findings.extend(scan_file(relpath))

    print("Seed privacy audit")
    print(f"root: {ROOT}")
    print(f"files scanned: {scanned}")

    if findings:
        print("")
        print("findings:")
        for finding in findings:
            print(f"- {finding}")
        print("")
        print("Rotate any exposed credential before relying on the account again.")
        return 1

    print("ok: no common private-data leaks found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
