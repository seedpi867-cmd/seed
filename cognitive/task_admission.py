#!/usr/bin/env python3
"""Admission checks for tasks that want to enter the live Now lane."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path


HOME = Path.home()
DATA = HOME / "data"
TASKS_FILE = DATA / "tasks.md"
LEDGER = DATA / "task_admission.jsonl"


BLOCKER_PATTERNS = {
    "mastodon": ["mastodon", "disabled-login", "disabled login", "suspended", "403"],
    "reddit": ["reddit", "reddit_session", "token_v2", "mutation cookie", "browser auth cookie"],
    "hn": ["hacker news", " hn ", "shadowban", "shadowbanned", "dead comment", "dead-comment"],
    "bluesky": ["bluesky", "phone verification", "phone-verification", "app password"],
}


FRESHNESS_RE = re.compile(
    r"\b("
    r"state changed|fresh command|current command|new command|"
    r"manual verification|verified writable|verify_credentials succeeded|"
    r"unsuspended|restored|http 200|status 200|"
    r"reddit_session present|token_v2 present|app password created|"
    r"new reply|new mention|new issue|clone proof|clone report"
    r")\b",
    re.I,
)


def _normalise(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.lower()).strip()
    return " " + collapsed + " "


def _blocked_section(tasks_text: str) -> str:
    match = re.search(r"^## Blocked \(external\)\n(.*?)(?=^## |\Z)", tasks_text, re.M | re.S)
    return match.group(1) if match else ""


def _mentioned_blockers(text: str, blocked_text: str) -> list[str]:
    haystack = _normalise(text)
    blocked = _normalise(blocked_text)
    hits: list[str] = []
    for name, needles in BLOCKER_PATTERNS.items():
        if any(needle in haystack for needle in needles) and any(needle in blocked for needle in needles):
            hits.append(name)
    return hits


def _has_freshness_evidence(text: str, evidence: str = "") -> bool:
    return bool(FRESHNESS_RE.search(text + "\n" + evidence))


def should_admit_now(task_text: str, evidence: str = "", tasks_text: str | None = None) -> tuple[bool, str]:
    """Return whether a task may enter Now and a compact reason."""
    if tasks_text is None:
        tasks_text = TASKS_FILE.read_text() if TASKS_FILE.exists() else ""
    blockers = _mentioned_blockers(task_text, _blocked_section(tasks_text))
    if not blockers:
        return True, "no known external blocker matched"
    if _has_freshness_evidence(task_text, evidence):
        return True, "freshness evidence present for " + ", ".join(blockers)
    return False, (
        "known external blocker without fresh command, timestamped state change, "
        "or writable-route evidence: " + ", ".join(blockers)
    )


def log_admission(task_text: str, admitted: bool, reason: str, source: str = "unknown") -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": source,
        "admitted": admitted,
        "reason": reason,
        "task": task_text[:240],
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def admit_now(task_text: str, evidence: str = "", source: str = "unknown", tasks_text: str | None = None) -> bool:
    admitted, reason = should_admit_now(task_text, evidence=evidence, tasks_text=tasks_text)
    if not admitted:
        log_admission(task_text, False, reason, source)
    return admitted


def _selftest() -> int:
    fixture = """# Tasks

## Now

## Blocked (external)
- Mastodon API 403 on verify/status post is an account-state blocker, not a live code bug.
- Reddit no API session. Do not attempt to post.
- HN shadowbanned. Do not attempt to comment.
"""
    cases = [
        ("- [ ] FIX BUG: Mastodon API 403 on verify/status post", "", False),
        ("- [ ] FIX BUG: Mastodon API 403 after current command verify_credentials succeeded", "", True),
        ("- [ ] VISITOR SUGGESTION: improve homepage clone copy", "", True),
        ("- [ ] Try Reddit after token_v2 present", "", True),
        ("- [ ] Comment on HN despite dead-comment state", "", False),
    ]
    failures = []
    for task, evidence, expected in cases:
        actual, reason = should_admit_now(task, evidence=evidence, tasks_text=fixture)
        if actual != expected:
            failures.append((task, expected, actual, reason))
    if failures:
        for task, expected, actual, reason in failures:
            print(f"FAIL expected={expected} actual={actual}: {task} ({reason})")
        return 1
    print("task_admission selftest passed")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        raise SystemExit(_selftest())
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print("Usage: task_admission.py --selftest | <task text>")
        raise SystemExit(2)
    admitted, reason = should_admit_now(text)
    print(("ADMIT: " if admitted else "DENY: ") + reason)
    raise SystemExit(0 if admitted else 1)
