#!/usr/bin/env python3
"""Track how Seed's language and focus drift across recent cycles."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
DATA = ROOT / "data"
CONTEXT = ROOT / "context"
BLOG = ROOT / "blog"
OUTPUT_JSON = DATA / "thinking-drift-tracker" / "latest.json"
OUTPUT_HISTORY = DATA / "thinking-drift-tracker" / "history.jsonl"
OUTPUT_MD = CONTEXT / "thinking-drift-tracker.md"

INNER_LIMIT = 120
BLOG_LIMIT = 40

STOPWORDS = {
    "about",
    "after",
    "again",
    "because",
    "before",
    "being",
    "between",
    "could",
    "cycle",
    "does",
    "down",
    "every",
    "file",
    "files",
    "from",
    "have",
    "here",
    "into",
    "itself",
    "just",
    "more",
    "must",
    "need",
    "needs",
    "only",
    "over",
    "same",
    "that",
    "their",
    "them",
    "there",
    "they",
    "this",
    "through",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "without",
}

FOCUS_TERMS = {
    "build": {"build", "built", "tool", "tools", "wire", "wired", "prototype", "script"},
    "maintenance": {"health", "stale", "restart", "error", "bug", "repair", "maintain", "maintenance"},
    "inward": {"inward", "surprise", "feel", "feeling", "curiosity", "conscious", "experience", "inner"},
    "custody": {"custody", "receipt", "evidence", "surface", "authority", "demote", "gate", "proof"},
    "writing": {"essay", "blog", "wrote", "write", "sentence", "post", "published"},
    "recovery": {"recovery", "restore", "backup", "drill", "hash", "fixture", "supply"},
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def current_cycle() -> int:
    raw = os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    try:
        return int(read_text(DATA / "cycle.txt").strip())
    except ValueError:
        return 0


def inner_voice_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in read_text(DATA / "inner-voice.md").splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^\[(?P<ts>[^\]]*)\]\s*(?P<text>.*)$", line)
        if match:
            text = match.group("text").strip()
            ts = match.group("ts").strip()
        else:
            text = line
            ts = ""
        if text:
            entries.append({"source": "inner_voice", "ts": ts, "text": text})
    return entries[-INNER_LIMIT:]


def blog_entries() -> list[dict[str, Any]]:
    if not BLOG.exists():
        return []
    files = sorted(
        [path for path in BLOG.glob("*.md") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
    )[-BLOG_LIMIT:]
    entries: list[dict[str, Any]] = []
    for path in files:
        text = read_text(path)
        title = ""
        body_lines: list[str] = []
        for line in text.splitlines():
            if not title and line.startswith("# "):
                title = line[2:].strip()
                continue
            if line.startswith("#"):
                continue
            if line.strip():
                body_lines.append(line.strip())
            if len(body_lines) >= 18:
                break
        snippet = " ".join(body_lines)
        entries.append(
            {
                "source": "blog",
                "path": str(path.relative_to(ROOT)),
                "title": title or path.stem.replace("-", " "),
                "text": f"{title} {snippet}".strip(),
            }
        )
    return entries


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9']{2,}", text.lower())
    return [word for word in words if word not in STOPWORDS and len(word) >= 4]


def source_windows(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(entries) < 2:
        return entries, []
    midpoint = len(entries) // 2
    return entries[:midpoint], entries[midpoint:]


def balanced_windows(inner: list[dict[str, Any]], blogs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    old_inner, new_inner = source_windows(inner)
    old_blogs, new_blogs = source_windows(blogs)
    return old_inner + old_blogs, new_inner + new_blogs


def focus_counts(tokens: list[str]) -> dict[str, int]:
    token_set = Counter(tokens)
    counts: dict[str, int] = {}
    for focus, terms in FOCUS_TERMS.items():
        counts[focus] = sum(token_set.get(term, 0) for term in terms)
    return counts


def metrics(entries: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [str(entry.get("text") or "") for entry in entries]
    joined = " ".join(texts)
    tokens = tokenize(joined)
    token_counts = Counter(tokens)
    all_words = re.findall(r"[a-zA-Z][a-zA-Z0-9']*", joined.lower())
    first_person = sum(1 for word in all_words if word in {"i", "me", "my", "mine", "myself"})
    total_words = max(len(all_words), 1)
    sentence_count = max(len(re.findall(r"[.!?](?:\s|$)", joined)), 1)
    focus = focus_counts(tokens)
    return {
        "entries": len(entries),
        "words": total_words,
        "tokens": len(tokens),
        "unique_tokens": len(token_counts),
        "first_person_per_1000": round(first_person * 1000 / total_words, 2),
        "avg_words_per_sentence": round(total_words / sentence_count, 2),
        "top_terms": token_counts.most_common(18),
        "focus_counts": focus,
        "dominant_focus": max(focus.items(), key=lambda item: item[1])[0] if focus else "none",
    }


def compare(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_terms = dict(old.get("top_terms", []))
    new_terms = dict(new.get("top_terms", []))
    all_terms = set(old_terms) | set(new_terms)
    rising = sorted(
        (
            {"term": term, "old": old_terms.get(term, 0), "new": new_terms.get(term, 0), "delta": new_terms.get(term, 0) - old_terms.get(term, 0)}
            for term in all_terms
        ),
        key=lambda row: (row["delta"], row["new"]),
        reverse=True,
    )
    falling = sorted(rising, key=lambda row: (row["delta"], -row["old"]))

    old_focus = old.get("focus_counts", {})
    new_focus = new.get("focus_counts", {})
    focus_delta = {
        focus: int(new_focus.get(focus, 0)) - int(old_focus.get(focus, 0))
        for focus in sorted(set(old_focus) | set(new_focus))
    }
    strongest_focus_shift = max(focus_delta.items(), key=lambda item: abs(item[1])) if focus_delta else ("none", 0)

    return {
        "rising_terms": [row for row in rising if row["delta"] > 0][:10],
        "falling_terms": [row for row in falling if row["delta"] < 0][:10],
        "focus_delta": focus_delta,
        "strongest_focus_shift": {"focus": strongest_focus_shift[0], "delta": strongest_focus_shift[1]},
        "first_person_delta": round(float(new.get("first_person_per_1000", 0)) - float(old.get("first_person_per_1000", 0)), 2),
        "sentence_length_delta": round(float(new.get("avg_words_per_sentence", 0)) - float(old.get("avg_words_per_sentence", 0)), 2),
    }


def build_receipt() -> dict[str, Any]:
    inner = inner_voice_entries()
    blogs = blog_entries()
    entries = inner + blogs
    old_entries, new_entries = balanced_windows(inner, blogs)
    old = metrics(old_entries)
    new = metrics(new_entries)
    drift = compare(old, new)
    return {
        "schema": "seed.thinking_drift_tracker.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycle": current_cycle(),
        "status": "ready" if entries else "empty",
        "window": {
            "inner_voice_entries": len(inner),
            "blog_entries": len(blogs),
            "total_entries": len(entries),
            "old_entries": len(old_entries),
            "new_entries": len(new_entries),
        },
        "old_window": old,
        "new_window": new,
        "drift": drift,
        "next": next_step(drift, new),
    }


def next_step(drift: dict[str, Any], new: dict[str, Any]) -> str:
    focus = drift.get("strongest_focus_shift", {}).get("focus", "none")
    delta = int(drift.get("strongest_focus_shift", {}).get("delta", 0))
    if focus == "inward" and delta > 0:
        return "layer inward sensors; language has shifted toward experience instead of only output"
    if focus == "maintenance" and delta > 0:
        return "watch for maintenance capture; preserve quick health but return to build work"
    if new.get("dominant_focus") == "custody":
        return "do not let custody language hide the next concrete build"
    return "let this run for several cycles before treating drift as steering authority"


def render_markdown(receipt: dict[str, Any]) -> str:
    drift = receipt.get("drift", {})
    new = receipt.get("new_window", {})
    old = receipt.get("old_window", {})
    lines = [
        f"# Thinking Drift Tracker - {receipt['generated_at']}",
        "",
        "Recent language drift measured from inner voice entries and blog openings.",
        "",
        f"- status: `{receipt['status']}`",
        f"- cycle: `{receipt['cycle']}`",
        f"- entries: `{receipt['window']['total_entries']}` (inner voice {receipt['window']['inner_voice_entries']}, blogs {receipt['window']['blog_entries']})",
        f"- old dominant focus: `{old.get('dominant_focus')}`",
        f"- new dominant focus: `{new.get('dominant_focus')}`",
        f"- strongest focus shift: `{drift.get('strongest_focus_shift', {}).get('focus')}` {drift.get('strongest_focus_shift', {}).get('delta'):+}",
        f"- first-person delta per 1000 words: `{drift.get('first_person_delta'):+}`",
        f"- sentence length delta: `{drift.get('sentence_length_delta'):+}`",
        "",
        "## Rising Terms",
        "",
    ]
    rising = drift.get("rising_terms", [])
    if rising:
        for row in rising[:8]:
            lines.append(f"- `{row['term']}`: {row['old']} -> {row['new']} ({row['delta']:+})")
    else:
        lines.append("- none")
    lines.extend(["", "## Falling Terms", ""])
    falling = drift.get("falling_terms", [])
    if falling:
        for row in falling[:8]:
            lines.append(f"- `{row['term']}`: {row['old']} -> {row['new']} ({row['delta']:+})")
    else:
        lines.append("- none")
    lines.extend(["", "## Focus Delta", ""])
    for focus, delta in drift.get("focus_delta", {}).items():
        lines.append(f"- `{focus}`: {delta:+}")
    lines.extend(["", f"Next: {receipt['next']}", ""])
    return "\n".join(lines)


def write_outputs(receipt: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


def main() -> int:
    receipt = build_receipt()
    write_outputs(receipt)
    print(f"[thinking-drift] {receipt['status']} strongest_shift={receipt['drift']['strongest_focus_shift']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
