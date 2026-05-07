#!/usr/bin/env python3
"""Map recovery coverage across Seed's local data supply chain."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
OUTPUT_JSON = ROOT / "data" / "supply-chain-prober" / "latest.json"
OUTPUT_HISTORY = ROOT / "data" / "supply-chain-prober" / "history.jsonl"
OUTPUT_MD = ROOT / "context" / "supply-chain-prober.md"

SURFACES = [
    {
        "name": "loop_state",
        "path": ROOT / "state",
        "critical": True,
        "why": "heartbeat, drives, emotions, and last outcome steer the next cycle",
    },
    {
        "name": "live_data",
        "path": ROOT / "data",
        "critical": True,
        "why": "tasks, goals, memory, receipts, experiments, and runtime ledgers",
    },
    {
        "name": "knowledge_base",
        "path": ROOT / "knowledge",
        "critical": True,
        "why": "long-term recalled corpus and research memory",
    },
    {
        "name": "blog_posts",
        "path": ROOT / "blog",
        "critical": False,
        "why": "published thought artifacts that should remain reconstructable",
    },
    {
        "name": "context_queue",
        "path": ROOT / "context",
        "critical": False,
        "why": "fresh inputs that steer the current prompt",
    },
    {
        "name": "tools",
        "path": ROOT / "tools",
        "critical": True,
        "why": "local actuators and readers wired into the loop",
    },
    {
        "name": "cognitive_scripts",
        "path": ROOT / "cognitive",
        "critical": True,
        "why": "zero-token cognition, appraisal, learning, and task machinery",
    },
    {
        "name": "public_clone",
        "path": ROOT / "public-seed",
        "critical": False,
        "why": "public clone surface for future loops",
    },
    {
        "name": "foundation_repo",
        "path": ROOT / "brain-loop",
        "critical": False,
        "why": "foundation repo used when spawning a fresh loop",
    },
]

BACKUP_SUFFIXES = (".bak", ".backup", ".old", ".orig")
LEDGER_NAMES = {"history.jsonl", "latest.json", "receipt.json", "receipts.jsonl"}
DRILL_TERMS = ("recovery drill", "restore_hash", "before_hash", "after_hash", "recovery proof")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def git_ls_files(repo: Path) -> set[str]:
    tracked: set[str] = set()
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo), "ls-files"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return tracked
    for line in output.splitlines():
        if line.strip():
            tracked.add(line.strip())
    return tracked


def git_tracked_paths() -> set[str]:
    tracked = set(git_ls_files(ROOT))
    tracked.update(git_ls_files(ROOT / "seed-os"))
    tracked.update(f"public-seed/{item}" for item in git_ls_files(ROOT / "public-seed"))
    tracked.update(f"brain-loop/{item}" for item in git_ls_files(ROOT / "brain-loop"))
    return tracked


def iter_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return [item for item in path.rglob("*") if item.is_file()]


def count_recent(paths: list[Path]) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - (7 * 24 * 60 * 60)
    return sum(1 for path in paths if path.stat().st_mtime >= cutoff)


def drill_hits(surface: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    path = surface["path"]
    surface_name = str(surface["name"]).lower()
    candidates = [
        ROOT / "knowledge" / "research" / "recovery-surface",
        ROOT / "knowledge" / "research" / "receipt-audit",
        ROOT / "data" / f"{surface_name.replace('_', '-')}-recovery-drill",
        ROOT / "context" / f"{surface_name.replace('_', '-')}-recovery-drill.md",
    ]
    for candidate in candidates:
        for file_path in iter_files(candidate):
            if file_path.suffix.lower() not in {".md", ".jsonl", ".txt"}:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            path_specific = (
                f'"surface": "{surface_name}"' in text
                or f"- surface: `{surface_name}`" in text
                or f"for `{surface_name}`" in text
                or f"`{rel(path).lower()}`" in text
            )
            general_loop_drill = path.name in {"data", "state"} and (
                "cycle 455" in text or "actuator-class recovery drills" in text
            )
            if (path_specific or general_loop_drill) and any(term in text for term in DRILL_TERMS):
                hits.append(rel(file_path))
    return sorted(set(hits))[:8]


def surface_record(surface: dict[str, Any], tracked: set[str]) -> dict[str, Any]:
    path = surface["path"]
    files = iter_files(path)
    rel_files = [rel(item) for item in files]
    file_count = len(files)
    bytes_total = sum(item.stat().st_size for item in files)
    tracked_count = sum(1 for item in rel_files if item in tracked)
    backup_count = sum(1 for item in files if item.name.endswith(BACKUP_SUFFIXES))
    ledger_count = sum(1 for item in files if item.name in LEDGER_NAMES or item.suffix == ".jsonl")
    recent_count = count_recent(files)
    drills = drill_hits(surface)

    signals = {
        "git_tracked": tracked_count > 0,
        "backup_markers": backup_count > 0,
        "receipt_or_history_ledgers": ledger_count > 0,
        "explicit_recovery_drill_reference": bool(drills),
    }
    score = 0
    score += 30 if signals["git_tracked"] else 0
    score += 15 if signals["backup_markers"] else 0
    score += 25 if signals["receipt_or_history_ledgers"] else 0
    score += 30 if signals["explicit_recovery_drill_reference"] else 0
    if surface["critical"] and not signals["explicit_recovery_drill_reference"]:
        score -= 10
    score = max(0, min(100, score))

    if not path.exists():
        status = "missing"
    elif score >= 75:
        status = "drilled_or_reconstructable"
    elif score >= 45:
        status = "partial_recovery_surface"
    else:
        status = "weak_recovery_surface"

    gaps = []
    if not signals["git_tracked"]:
        gaps.append("no git custody found")
    if not signals["receipt_or_history_ledgers"]:
        gaps.append("no local receipt or history ledger found")
    if not signals["explicit_recovery_drill_reference"]:
        gaps.append("no explicit recovery drill evidence found")
    if surface["critical"] and not signals["backup_markers"]:
        gaps.append("no visible backup marker")

    return {
        "name": surface["name"],
        "path": rel(path),
        "status": status,
        "critical": surface["critical"],
        "why": surface["why"],
        "file_count": file_count,
        "bytes": bytes_total,
        "recent_files_7d": recent_count,
        "git_tracked_files": tracked_count,
        "backup_markers": backup_count,
        "receipt_or_history_ledgers": ledger_count,
        "recovery_drill_evidence": drills,
        "coverage_score": score,
        "signals": signals,
        "gaps": gaps,
        "next": "run a fixture-backed write-verify-restore drill" if gaps else "keep watching for drift",
    }


def build_receipt() -> dict[str, Any]:
    tracked = git_tracked_paths()
    records = [surface_record(surface, tracked) for surface in SURFACES]
    weak = [item for item in records if item["status"] == "weak_recovery_surface"]
    critical_weak = [item for item in weak if item["critical"]]
    status = "critical_gaps" if critical_weak else "gaps_found" if weak else "ready"
    return {
        "schema": "seed.supply_chain_prober.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycle": os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE"),
        "source_collision": {
            "repo": "turing-db/turingdb",
            "knowledge": "Recovery Drills",
            "blog": "Every Empire Is A Supply Chain",
        },
        "status": status,
        "surface_count": len(records),
        "critical_weak_count": len(critical_weak),
        "weak_count": len(weak),
        "surfaces": records,
        "next": "prioritize the highest-criticality weak surface for a fixture-backed recovery drill",
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Supply Chain Prober - {receipt['generated_at']}",
        "",
        "Recovery coverage report for Seed's local data supply chain.",
        "",
        f"- status: `{receipt['status']}`",
        f"- collision: {receipt['source_collision']['repo']} + {receipt['source_collision']['knowledge']} + {receipt['source_collision']['blog']}",
        f"- surfaces checked: {receipt['surface_count']}",
        f"- weak surfaces: {receipt['weak_count']}",
        f"- critical weak surfaces: {receipt['critical_weak_count']}",
        "",
        "## Surface Coverage",
        "",
    ]
    for item in sorted(receipt["surfaces"], key=lambda row: (row["coverage_score"], not row["critical"])):
        lines.append(
            f"- **{item['name']}** -> `{item['status']}` "
            f"(score {item['coverage_score']}, files {item['file_count']}, ledgers {item['receipt_or_history_ledgers']})"
        )
        if item["gaps"]:
            lines.append(f"  - gaps: {'; '.join(item['gaps'][:4])}")
        if item["recovery_drill_evidence"]:
            lines.append(f"  - drill evidence: {', '.join(item['recovery_drill_evidence'][:3])}")
    lines.extend(["", f"Next: {receipt['next']}", ""])
    return "\n".join(lines)


def write_receipt(receipt: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")


def main() -> int:
    receipt = build_receipt()
    write_receipt(receipt)
    print(f"{receipt['status']}\t{receipt['surface_count']} surfaces\t{receipt['critical_weak_count']} critical weak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
