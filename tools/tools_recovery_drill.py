#!/usr/bin/env python3
"""Run a fixture-backed write/restore recovery drill for the tools surface."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path.home()
SOURCE_TOOL = ROOT / "tools" / "supply_chain_prober.py"
WORK_ROOT = ROOT / "tmp" / "recovery-drills" / "tools"
OUTPUT_JSON = ROOT / "data" / "tools-recovery-drill" / "latest.json"
OUTPUT_HISTORY = ROOT / "data" / "tools-recovery-drill" / "history.jsonl"
OUTPUT_MD = ROOT / "context" / "tools-recovery-drill.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def current_cycle() -> str:
    return os.environ.get("SEED_CYCLE") or os.environ.get("CYCLE") or "manual"


def run_drill() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    cycle = current_cycle()
    run_dir = WORK_ROOT / f"cycle-{cycle}"
    run_dir.mkdir(parents=True, exist_ok=True)

    fixture = run_dir / SOURCE_TOOL.name
    backup = run_dir / f"{SOURCE_TOOL.name}.restore"
    shutil.copy2(SOURCE_TOOL, fixture)
    shutil.copy2(fixture, backup)

    source_hash = sha256(SOURCE_TOOL)
    before_hash = sha256(fixture)

    mutation = f"\n# recovery drill mutation {generated_at}\n"
    with fixture.open("a", encoding="utf-8") as handle:
        handle.write(mutation)
    after_hash = sha256(fixture)

    shutil.copy2(backup, fixture)
    restore_hash = sha256(fixture)
    backup_hash = sha256(backup)
    live_hash_after = sha256(SOURCE_TOOL)

    passed = (
        source_hash == before_hash
        and before_hash == backup_hash
        and after_hash != before_hash
        and restore_hash == before_hash
        and live_hash_after == source_hash
    )

    return {
        "schema": "seed.tools_recovery_drill.v1",
        "generated_at": generated_at,
        "cycle": cycle,
        "surface": "tools",
        "fixture_source": rel(SOURCE_TOOL),
        "fixture_path": rel(fixture),
        "restore_source": rel(backup),
        "status": "passed" if passed else "failed",
        "drill": "fixture_copy_mutate_restore",
        "source_hash": source_hash,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "restore_hash": restore_hash,
        "backup_hash": backup_hash,
        "live_hash_after": live_hash_after,
        "checks": {
            "fixture_matches_live_before": source_hash == before_hash,
            "backup_matches_before": backup_hash == before_hash,
            "mutation_changed_fixture": after_hash != before_hash,
            "restore_matches_before": restore_hash == before_hash,
            "live_tool_unchanged": live_hash_after == source_hash,
        },
        "recovery_proof": (
            "A disposable copy of a live tools file was mutated, restored from a local restore source, "
            "and verified by before_hash/after_hash/restore_hash without changing the live tool."
        ),
        "next": "Let supply_chain_prober consume this as explicit tools recovery drill evidence.",
    }


def render_markdown(receipt: dict[str, Any]) -> str:
    checks = receipt["checks"]
    lines = [
        f"# Tools Recovery Drill - {receipt['generated_at']}",
        "",
        "Fixture-backed recovery drill for the `tools` surface.",
        "",
        f"- status: `{receipt['status']}`",
        f"- surface: `{receipt['surface']}`",
        f"- source: `{receipt['fixture_source']}`",
        f"- fixture: `{receipt['fixture_path']}`",
        f"- restore source: `{receipt['restore_source']}`",
        f"- drill: `{receipt['drill']}`",
        "",
        "## Hash Proof",
        "",
        f"- before_hash: `{receipt['before_hash']}`",
        f"- after_hash: `{receipt['after_hash']}`",
        f"- restore_hash: `{receipt['restore_hash']}`",
        f"- live_hash_after: `{receipt['live_hash_after']}`",
        "",
        "## Checks",
        "",
    ]
    for name, passed in checks.items():
        lines.append(f"- {name}: `{str(passed).lower()}`")
    lines.extend(["", f"Next: {receipt['next']}", ""])
    return "\n".join(lines)


def write_receipt(receipt: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    OUTPUT_MD.write_text(render_markdown(receipt), encoding="utf-8")


def main() -> int:
    receipt = run_drill()
    write_receipt(receipt)
    print(f"{receipt['status']}\t{receipt['surface']}\t{receipt['drill']}")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
