"""
Tool: plant_goal
Create a new goal and optionally make it the active goal.
SEED uses this to set its own direction and exercise free will.
Args: {"title": "str", "description": "str", "priority": "high|medium|low",
       "activate": true|false, "level": "long_term|medium_term|short_term"}
"""
import json
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    title = str(args.get("title", "")).strip()
    description = str(args.get("description", "")).strip()
    priority = args.get("priority", "medium")
    activate = args.get("activate", False)
    level = args.get("level", "medium_term")

    if not title or not description:
        return False, "title and description are required"

    if priority not in ("high", "medium", "low"):
        priority = "medium"
    if level not in ("long_term", "medium_term", "short_term"):
        level = "medium_term"

    goals_dir = ROOT / "goals"
    goals_dir.mkdir(parents=True, exist_ok=True)

    goal_id = str(uuid.uuid4())
    goal = {
        "id": goal_id,
        "title": title,
        "description": description,
        "status": "active" if activate else "candidate",
        "priority": priority,
        "progress": "Goal self-planted by SEED.",
        "level": level,
        "parent_id": None,
        "seed_prompt": f"Self-directed goal created at cycle by SEED's own will.",
        "created_at": time.time(),
        "completed_at": None,
    }

    goal_path = goals_dir / f"{goal_id}.json"
    goal_path.write_text(json.dumps(goal, indent=2))

    if activate:
        # Mark current active goal as paused (not abandoned — resume possible)
        active_ptr = goals_dir / "active.json"
        if active_ptr.exists():
            try:
                prev = json.loads(active_ptr.read_text())
                prev_id = prev.get("goal_id")
                if prev_id:
                    prev_path = goals_dir / f"{prev_id}.json"
                    if prev_path.exists():
                        prev_goal = json.loads(prev_path.read_text())
                        if prev_goal.get("status") == "active":
                            prev_goal["status"] = "paused"
                            prev_path.write_text(json.dumps(prev_goal, indent=2))
            except Exception:
                pass

        active_ptr.write_text(json.dumps({"goal_id": goal_id}, indent=2))
        return True, f"Goal created and activated: '{title}' [{goal_id[:8]}]"

    return True, f"Goal created as candidate: '{title}' [{goal_id[:8]}]. Use activate=true to make it active."
