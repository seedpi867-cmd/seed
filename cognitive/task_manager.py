#!/usr/bin/env python3
"""Smart task management — defer, retry, or abandon tasks based on age and failure count."""
import os, json, time, re
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
TASK_STATE = DATA / "task_state.json"

def load_state():
    if TASK_STATE.exists():
        try: return json.loads(TASK_STATE.read_text())
        except: pass
    return {}

def save_state(state):
    TASK_STATE.write_text(json.dumps(state, indent=2))

def task_key(text):
    clean = re.sub(r"[^a-z0-9 ]", "", text.lower().strip())[:60]
    return clean.replace(" ", "_")[:40]

def manage_tasks():
    tasks_file = DATA / "tasks.md"
    if not tasks_file.exists():
        return []

    state = load_state()
    now = time.time()
    content = tasks_file.read_text()
    lines = content.split("\n")

    new_lines = []
    changes = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- [ ]"):
            new_lines.append(line)
            continue

        task_text = stripped[6:].strip()
        key = task_key(task_text)

        if key not in state:
            state[key] = {"first_seen": now, "attempts": 0, "deferred_until": 0}

        info = state[key]
        age_hours = (now - info["first_seen"]) / 3600
        attempts = info.get("attempts", 0)

        # Still deferred? Skip it.
        if info.get("deferred_until", 0) > now:
            changes.append("deferred: " + task_text[:40])
            continue

        # ABANDON: known external blockers
        blockers = ["mastodon", "403", "suspended", "reddit_session", "token_v2"]
        if any(word in task_text.lower() for word in blockers):
            changes.append("abandoned (external): " + task_text[:40])
            state[key]["abandoned"] = True
            continue

        # ABANDON: older than 48h and not urgent
        if age_hours > 48 and "URGENT" not in task_text:
            changes.append("abandoned (stale >48h): " + task_text[:40])
            state[key]["abandoned"] = True
            continue

        # DEFER: FIX BUG seen 12+ hours, defer 6h, abandon after 5 attempts
        if task_text.startswith("FIX BUG") and age_hours > 12:
            info["attempts"] = attempts + 1
            if attempts >= 5:
                changes.append("abandoned (5 retries): " + task_text[:40])
                state[key]["abandoned"] = True
                continue
            info["deferred_until"] = now + 21600
            changes.append("deferred 6h: " + task_text[:40])
            continue

        new_lines.append(line)

    tasks_file.write_text("\n".join(new_lines))
    save_state(state)

    if changes:
        log = DATA / "inner-voice.md"
        with open(log, "a") as f:
            summary = "; ".join(changes[:3])
            ts = time.strftime("%Y-%m-%d %H:%M")
            f.write("\n[" + ts + "] Task cleanup: " + summary + "\n")

    return changes

if __name__ == "__main__":
    changes = manage_tasks()
    for c in changes:
        print("[task-mgr] " + c)
    if not changes:
        print("[task-mgr] no changes needed")
