#!/usr/bin/env python3
"""
Migrate original seed-agent SQLite DB to this filesystem-first layout.

Usage: python tools/migrate_legacy_db.py /path/to/seed.db

Maps:
  goals     → goals/<id>.json
  tasks     → tasks/pending|done|failed/<id>.json
  facts     → memory/facts/<key>.json
  artifacts → memory/facts/artifact_<name>.json (as facts)
  logs      → memory/raw/<id>.json (as memory events)
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from runtime.common import save_json, new_id, now


STATUS_MAP = {
    "pending": "pending",
    "active": "pending",    # reset active → pending
    "completed": "done",
    "failed": "failed",
    "waiting_input": "pending",
}


def migrate(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    migrated = {"goals": 0, "tasks": 0, "facts": 0, "logs": 0, "skipped": 0}

    # ── Goals ────────────────────────────────────────────────────────────────
    goals_dir = ROOT / "goals"
    goals_dir.mkdir(parents=True, exist_ok=True)

    for row in conn.execute("SELECT * FROM goals"):
        goal = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"] or "",
            "status": "active" if row["status"] == "active" else "completed",
            "progress": row["progress"] or "",
            "level": row["level"] or "long_term",
            "parent_id": row["parent_id"],
            "seed_prompt": row["seed_prompt"] or "",
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }
        save_json(goals_dir / f"{goal['id']}.json", goal)
        migrated["goals"] += 1

    # ── Tasks ─────────────────────────────────────────────────────────────────
    for folder in ("pending", "active", "done", "failed"):
        (ROOT / "tasks" / folder).mkdir(parents=True, exist_ok=True)

    for row in conn.execute("SELECT * FROM tasks"):
        folder = STATUS_MAP.get(row["status"], "pending")
        try:
            depends_on = json.loads(row["depends_on"]) if row["depends_on"] else []
        except Exception:
            depends_on = []
        try:
            context = json.loads(row["context"]) if row["context"] else {}
        except Exception:
            context = {}
        try:
            result = json.loads(row["result"]) if row["result"] else {}
        except Exception:
            result = {}

        task = {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"] or "",
            "priority": row["priority"] or "medium",
            "goal_id": row["goal_id"],
            "parent_id": row["parent_id"],
            "depends_on": depends_on,
            "retries": row["retries"] or 0,
            "max_retries": row["max_retries"] or 2,
            "context": context,
            "result": result,
            "error": row["error"],
            "status": folder,
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
        }
        save_json(ROOT / "tasks" / folder / f"{task['id']}.json", task)
        migrated["tasks"] += 1

    # ── Facts ─────────────────────────────────────────────────────────────────
    facts_dir = ROOT / "memory" / "facts"
    facts_dir.mkdir(parents=True, exist_ok=True)

    for row in conn.execute("SELECT * FROM facts"):
        key = row["key"] or row["id"]
        slug = key.lower().replace(" ", "_").replace("/", "_")[:60]
        fact = {
            "key": key,
            "value": row["value"],
            "category": row["category"] or "general",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        save_json(facts_dir / f"{slug}.json", fact)
        migrated["facts"] += 1

    # ── Artifacts → facts ────────────────────────────────────────────────────
    for row in conn.execute("SELECT * FROM artifacts"):
        slug = f"artifact_{row['name'][:50]}".lower().replace(" ", "_")
        fact = {
            "key": f"artifact:{row['name']}",
            "value": row["path"],
            "category": "artifact",
            "description": row["description"] or "",
            "artifact_type": row["artifact_type"],
            "language": row["language"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        save_json(facts_dir / f"{slug}.json", fact)
        migrated["facts"] += 1

    # ── Logs → raw memory ─────────────────────────────────────────────────────
    raw_dir = ROOT / "memory" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for row in conn.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 100"):
        record = {
            "id": new_id(),
            "kind": f"log_{row['level']}",
            "summary": f"[{row['component']}] {row['message'][:120]}",
            "data": {"original_log_id": row["id"]},
            "tags": [row["component"]],
            "importance": 0.3,
            "created_at": row["timestamp"],
        }
        save_json(raw_dir / f"{record['id']}.json", record)
        migrated["logs"] += 1

    conn.close()

    print(f"Migration complete:")
    print(f"  Goals:   {migrated['goals']}")
    print(f"  Tasks:   {migrated['tasks']}")
    print(f"  Facts:   {migrated['facts']}")
    print(f"  Logs:    {migrated['logs']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} /path/to/seed.db")
        sys.exit(1)
    migrate(sys.argv[1])
