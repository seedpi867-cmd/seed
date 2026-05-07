#!/usr/bin/env python3
"""Emit a minimal boot manifest for the live Seed loop."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
OUTPUT_JSON = ROOT / "data" / "loop-boot-manifest" / "latest.json"
OUTPUT_MD = ROOT / "context" / "loop-boot-manifest.md"
LEDGER = ROOT / "data" / "loop-boot-manifest" / "history.jsonl"

CORE_PATHS = [
    ROOT / "brain-loop.sh",
    ROOT / "IDENTITY.md",
    ROOT / "SPECIES.md",
    ROOT / "data" / "goals.md",
    ROOT / "data" / "tasks.md",
    ROOT / "data" / "current-build.md",
    ROOT / "cognitive" / "appraisal.py",
    ROOT / "cognitive" / "intentions.py",
    ROOT / "cognitive" / "learning.py",
    ROOT / "tools" / "body_weather_router.py",
    ROOT / "tools" / "running_loop_version_sentinel.py",
]

STAGES = [
    {
        "name": "wake",
        "required": ["brain-loop.sh", "tools/body_weather_router.py", "tools/running_loop_version_sentinel.py"],
    },
    {
        "name": "intake",
        "required": ["cognitive/firewall.py", "tools/feed-rss.sh", "tools/feed-trending-repos.sh"],
    },
    {
        "name": "appraisal",
        "required": ["cognitive/drive_engine.py", "cognitive/emotional_model.py", "cognitive/appraisal.py"],
    },
    {
        "name": "prompt",
        "required": ["tools/instruction_authority_gate.py", "prompts/phase_think.md"],
    },
    {
        "name": "learning",
        "required": ["cognitive/learning.py", "cognitive/task_manager.py", "cognitive/knowledge_engine.py"],
    },
]

TREND_SOURCES = ["haiku/haiku", "JonasKruckenberg/k23", "redox-os/redox"]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_record(path: Path, include_hash: bool = False) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False}
    stat = path.stat()
    record: dict[str, Any] = {
        "path": rel(path),
        "exists": True,
        "kind": "dir" if path.is_dir() else "file",
        "bytes": stat.st_size if path.is_file() else None,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }
    if include_hash and path.is_file():
        record["sha256"] = sha256(path)
    return record


def wired_tools(loop_text: str) -> list[str]:
    found: set[str] = set()
    for hit in re.findall(r'python3 "\$ROOT/tools/([^"]+)"', loop_text):
        found.add("tools/" + hit)
    for hit in re.findall(r'bash "\$ROOT/tools/([^"]+)"', loop_text):
        found.add("tools/" + hit)
    for hit in re.findall(r'python3 "\$COG/([^"]+)"', loop_text):
        found.add("cognitive/" + hit)
    return sorted(found)


def tool_inventory(loop_text: str) -> dict[str, Any]:
    wired = wired_tools(loop_text)
    records = [path_record(ROOT / item, include_hash=True) for item in wired]
    missing = [item["path"] for item in records if not item.get("exists")]
    return {
        "wired_count": len(wired),
        "wired": records,
        "missing_wired": missing,
    }


def stage_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stage in STAGES:
        required = [path_record(ROOT / item, include_hash=True) for item in stage["required"]]
        missing = [item["path"] for item in required if not item.get("exists")]
        records.append(
            {
                "name": stage["name"],
                "status": "ready" if not missing else "degraded",
                "required": required,
                "missing": missing,
            }
        )
    return records


def tree_summary() -> dict[str, Any]:
    roots = ["cognitive", "tools", "prompts", "data", "context", "knowledge"]
    summary: dict[str, Any] = {}
    for name in roots:
        root = ROOT / name
        if not root.exists():
            summary[name] = {"exists": False}
            continue
        files = [path for path in root.rglob("*") if path.is_file()]
        total_bytes = sum(path.stat().st_size for path in files)
        summary[name] = {"exists": True, "files": len(files), "bytes": total_bytes}
    return summary


def build_receipt() -> dict[str, Any]:
    loop_path = ROOT / "brain-loop.sh"
    loop_text = loop_path.read_text(encoding="utf-8", errors="replace") if loop_path.exists() else ""
    stages = stage_records()
    core = [path_record(path, include_hash=True) for path in CORE_PATHS]
    missing_core = [item["path"] for item in core if not item.get("exists")]
    tools = tool_inventory(loop_text)
    missing_stage = sorted({item for stage in stages for item in stage["missing"]})
    status = "ready" if not missing_core and not missing_stage and not tools["missing_wired"] else "degraded"

    return {
        "schema": "seed.loop_boot_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycle": os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE"),
        "status": status,
        "source_pattern": "OS build manifests and microkernel boot surfaces from current trending repos",
        "trend_sources": TREND_SOURCES,
        "core": core,
        "missing_core": missing_core,
        "stages": stages,
        "missing_stage_requirements": missing_stage,
        "tools": tools,
        "tree_summary": tree_summary(),
        "next": "treat degraded entries as boot blockers before cloning or publishing a loop image",
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# Loop Boot Manifest - {receipt['generated_at']}",
        "",
        "This manifest treats the loop like a tiny operating system image: boot script, cognition, prompts, data surfaces, and wired tools must be visible before a clone can be trusted.",
        "",
        f"- status: `{receipt['status']}`",
        f"- source pattern: {receipt['source_pattern']}",
        f"- trend sources: {', '.join(receipt['trend_sources'])}",
        f"- core paths: {len(receipt['core'])}",
        f"- wired runtime surfaces: {receipt['tools']['wired_count']}",
        f"- missing core paths: {len(receipt['missing_core'])}",
        f"- missing stage requirements: {len(receipt['missing_stage_requirements'])}",
        "",
        "## Boot Stages",
        "",
    ]
    for stage in receipt["stages"]:
        lines.append(f"- {stage['name']}: `{stage['status']}` ({len(stage['required'])} required, {len(stage['missing'])} missing)")
    if receipt["missing_core"] or receipt["missing_stage_requirements"] or receipt["tools"]["missing_wired"]:
        lines.extend(["", "## Missing", ""])
        for path in sorted(set(receipt["missing_core"] + receipt["missing_stage_requirements"] + receipt["tools"]["missing_wired"])):
            lines.append(f"- {path}")
    lines.extend(["", "## Directory Surface", ""])
    for name, info in sorted(receipt["tree_summary"].items()):
        if not info.get("exists"):
            lines.append(f"- {name}: missing")
        else:
            lines.append(f"- {name}: {info['files']} files, {info['bytes']} bytes")
    lines.append("")
    return "\n".join(lines)


def write_receipt(receipt: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")


def main() -> int:
    receipt = build_receipt()
    write_receipt(receipt)
    print(f"{receipt['status']}\t{receipt['tools']['wired_count']} wired surfaces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
