#!/usr/bin/env python3
"""Surface knowledge files that complicate the current cycle plan."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "context" / "contradiction-query.md"
DEFAULT_JSON = ROOT / "data" / "contradiction-query" / "latest.json"
KDIR = ROOT / "knowledge"

STOPWORDS = {
    "about",
    "after",
    "again",
    "agent",
    "because",
    "before",
    "build",
    "called",
    "could",
    "current",
    "cycle",
    "data",
    "does",
    "done",
    "each",
    "emit",
    "every",
    "file",
    "files",
    "from",
    "given",
    "have",
    "into",
    "just",
    "knowledge",
    "loop",
    "make",
    "more",
    "over",
    "plan",
    "query",
    "read",
    "rows",
    "seed",
    "should",
    "surface",
    "that",
    "then",
    "they",
    "this",
    "tool",
    "what",
    "when",
    "which",
    "with",
    "would",
    "another",
    "assembly",
    "closed",
    "doing",
    "feeder",
    "feeling",
    "testing",
    "usable",
}

NEGATIVE_RE = re.compile(
    r"\b("
    r"against|abandon|blocked|but|cannot|decay|demot\w*|"
    r"disagree\w*|diverge\w*|fail\w*|false|friction|however|instead|"
    r"missing|never|not|risk|stale|unless|wrong"
    r")\b",
    re.I,
)
WORD_RE = re.compile(r"[a-z][a-z0-9_-]{3,}", re.I)


@dataclass(frozen=True)
class Candidate:
    score: float
    path: str
    title: str
    snippet: str
    plan_terms: list[str]
    negative_markers: list[str]


def read_plan() -> str:
    parts: list[str] = []
    tasks_path = ROOT / "data" / "tasks.md"
    if tasks_path.exists():
        tasks_text = tasks_path.read_text(encoding="utf-8", errors="ignore")
        for line in tasks_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                parts.append(stripped[6:].strip())
                break

    for path in (ROOT / "data" / "what-im-doing.txt",):
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="ignore")[:2500])
    return "\n".join(parts)


def keywords(text: str, limit: int = 24) -> list[str]:
    counts: dict[str, int] = {}
    for match in WORD_RE.finditer(text.lower()):
        token = match.group(0).strip("_-")
        if len(token) < 4 or token in STOPWORDS:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def title_for(text: str, fallback: str) -> str:
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:120] or fallback
    return fallback


def sentence_windows(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text[:16000]).strip()
    if not compact:
        return []
    pieces = re.split(r"(?<=[.!?])\s+| (?=- )", compact)
    return [piece.strip(" -") for piece in pieces if len(piece.strip()) >= 40]


def score_file(path: Path, plan_terms: list[str]) -> Candidate | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    relpath = str(path.relative_to(KDIR))
    best: tuple[float, str, list[str], list[str]] | None = None
    path_terms = {term for term in plan_terms if term in relpath.lower()}

    for sentence in sentence_windows(text):
        lower = sentence.lower()
        if "contradiction query" in lower and "second access path" in lower:
            continue
        matched_terms = [term for term in plan_terms if term in lower]
        markers = sorted({m.group(1).lower() for m in NEGATIVE_RE.finditer(sentence)})
        if not markers:
            continue
        if not matched_terms and not path_terms:
            continue
        score = (len(set(matched_terms)) * 3.0) + (len(markers) * 1.5) + (len(path_terms) * 1.0)
        if re.search(r"\b(do not|should not|cannot|unless|instead|demote|stale)\b", lower):
            score += 2.0
        if "contradict" in lower or "disagree" in lower:
            score += 1.0
        if best is None or score > best[0]:
            best = (score, sentence, sorted(set(matched_terms) | path_terms), markers)

    if best is None:
        return None

    snippet = best[1]
    if len(snippet) > 280:
        snippet = snippet[:277].rstrip() + "..."
    return Candidate(
        score=best[0],
        path=relpath,
        title=title_for(text, relpath),
        snippet=snippet,
        plan_terms=best[2],
        negative_markers=best[3],
    )


def find_candidates(plan: str, limit: int) -> list[Candidate]:
    plan_terms = keywords(plan)
    candidates: list[Candidate] = []
    current_cycle = current_cycle_id()
    for path in KDIR.rglob("*.md"):
        rel = str(path.relative_to(KDIR))
        if "/inbox" in rel or rel.endswith("/starting-points.md"):
            continue
        if current_cycle and f"cycle-{current_cycle}" in rel:
            continue
        candidate = score_file(path, plan_terms)
        if candidate:
            candidates.append(candidate)
    candidates.sort(key=lambda item: (-item.score, item.path))
    return candidates[:limit]


def current_cycle_id() -> int | None:
    env_cycle = os.environ.get("SEED_CYCLE", "").strip()
    if env_cycle.isdigit():
        return int(env_cycle)
    cycle_path = ROOT / "state" / "cycle.json"
    try:
        value = json.loads(cycle_path.read_text(encoding="utf-8")).get("cycle")
    except (OSError, json.JSONDecodeError):
        return None
    return int(value) if isinstance(value, int) else None


def write_outputs(candidates: list[Candidate], plan: str, output: Path, json_output: Path) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    plan_terms = keywords(plan)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Contradiction Query - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "These knowledge files may complicate the current cycle plan. Treat them as friction to inspect, not as final verdicts.",
        "",
        "## Plan Terms",
        "",
        ", ".join(plan_terms[:12]) or "none",
        "",
    ]
    if not candidates:
        lines.extend(["## No Candidates", "", "No disagreement candidates matched the current plan terms."])
    for index, candidate in enumerate(candidates, 1):
        lines.extend(
            [
                f"## {index}. {candidate.path} (score: {candidate.score:.1f})",
                "",
                f"Title: {candidate.title}",
                "",
                f"Plan overlap: {', '.join(candidate.plan_terms) or 'none'}",
                "",
                f"Friction markers: {', '.join(candidate.negative_markers) or 'none'}",
                "",
                f"Snippet: {candidate.snippet}",
                "",
                "---",
                "",
            ]
        )
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    payload = {
        "generated_at": ts,
        "source": "tools/knowledge_contradiction_query.py",
        "plan_terms": plan_terms,
        "candidate_count": len(candidates),
        "candidates": [
            {
                "score": candidate.score,
                "path": candidate.path,
                "title": candidate.title,
                "snippet": candidate.snippet,
                "plan_terms": candidate.plan_terms,
                "negative_markers": candidate.negative_markers,
            }
            for candidate in candidates
        ],
    }
    json_output.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", help="explicit plan text; defaults to live Seed state")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    plan = args.plan if args.plan is not None else read_plan()
    candidates = find_candidates(plan, args.limit)
    write_outputs(candidates, plan, args.output, args.json_output)
    print(f"wrote {len(candidates)} contradiction candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
