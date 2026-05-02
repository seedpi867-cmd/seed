#!/usr/bin/env python3
"""Redact common secrets from clone reports before pasting them into GitHub."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


EMAIL_ALLOWLIST = {
    "recipient@example.com",
    "your-email@gmail.com",
}

LINE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "sk-[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "gh[REDACTED]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "xox[REDACTED]"),
    (re.compile(r"\b1//[0-9A-Za-z_-]{20,}\b"), "1//[REDACTED]"),
    (
        re.compile(
            r"(\b(?:app[-_ ]?password|gmail|smtp|imap|password)\b.{0,80}?)"
            r"\b[a-z]{4} [a-z]{4} [a-z]{4} [a-z]{4}\b",
            re.I,
        ),
        r"\1[REDACTED-APP-PASSWORD]",
    ),
    (
        re.compile(r"(?<!@)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED-EMAIL]",
    ),
]

PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----",
    re.S,
)


def redact_email_match(match: re.Match[str]) -> str:
    address = match.group(0)
    if address.lower() in EMAIL_ALLOWLIST:
        return address
    if address.lower().endswith("@example.com") or address.lower().endswith("@example.org"):
        return address
    return "[REDACTED-EMAIL]"


def redact_text(text: str) -> str:
    text = PRIVATE_KEY_BLOCK.sub("[REDACTED-PRIVATE-KEY-BLOCK]", text)
    for pattern, replacement in LINE_PATTERNS:
        if replacement == "[REDACTED-EMAIL]":
            text = pattern.sub(redact_email_match, text)
        else:
            text = pattern.sub(replacement, text)
    return text


def read_input(paths: list[str]) -> str:
    if not paths:
        return sys.stdin.read()
    chunks = []
    for name in paths:
        chunks.append(Path(name).read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Redact common credentials and personal email addresses from clone-report output."
    )
    parser.add_argument("paths", nargs="*", help="files to redact; reads stdin when omitted")
    args = parser.parse_args()
    sys.stdout.write(redact_text(read_input(args.paths)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
