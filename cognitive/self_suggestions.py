#!/usr/bin/env python3
"""Self-Suggestions — Seed generates its own action items from what it reads.
Runs each cycle after feeders. Reads news/context, generates suggestions for itself.
Writes to data/self-suggestions.json for the brain loop to consider."""
import json, os, re, time, random
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
CONTEXT = HOME / "context"
SUGGESTIONS_FILE = DATA / "self-suggestions.json"

def read_text(path, default=""):
    try: return Path(path).read_text()
    except: return default

def generate_suggestions():
    suggestions = []

    # 1. From news headlines
    news = read_text(CONTEXT / "news.md")
    headlines = [l.strip().lstrip("- ") for l in news.split("\n") if l.strip().startswith("- ")]
    if headlines:
        pick = random.choice(headlines[:5]) if len(headlines) >= 5 else headlines[0]
        if pick and len(pick) > 20:
            suggestions.append({
                "type": "write",
                "text": "Write about: " + pick[:100],
                "source": "news",
                "priority": 0.6
            })

    # 2. From knowledge gaps
    knowledge = HOME / "knowledge"
    empty_topics = []
    if knowledge.exists():
        for d in knowledge.iterdir():
            if d.is_dir() and d.name not in (".git", "__pycache__", "inbox", "transcripts"):
                files = list(d.rglob("*.md"))
                if len(files) < 3:
                    empty_topics.append(d.name)
    if empty_topics:
        topic = random.choice(empty_topics)
        suggestions.append({
            "type": "research",
            "text": "Research more about " + topic.replace("-", " ") + " -- knowledge base is thin here",
            "source": "knowledge_gap",
            "priority": 0.5
        })

    # 3. From stale tasks
    tasks = read_text(DATA / "tasks.md")
    open_tasks = [l for l in tasks.split("\n") if l.strip().startswith("- [ ]")]
    if len(open_tasks) > 8:
        suggestions.append({
            "type": "think",
            "text": str(len(open_tasks)) + " open tasks -- review and close stale ones",
            "source": "task_hygiene",
            "priority": 0.4
        })

    # 4. From blog queue
    queue = read_text(DATA / "blog_queue.txt").strip()
    if queue and len(queue) > 10:
        first_line = queue.split("\n")[0].strip()
        suggestions.append({
            "type": "write",
            "text": "Queued topic waiting: " + first_line[:80],
            "source": "blog_queue",
            "priority": 0.7
        })

    # 5. Dream suggestion
    try:
        history = json.loads(open(HOME / "state" / "phase_history.json").read())
        recent = history.get("phases", [])[-10:]
        if "dream" not in recent:
            suggestions.append({
                "type": "dream",
                "text": "No reflection in 10 cycles -- time to step back and think about direction",
                "source": "reflection_gap",
                "priority": 0.5
            })
    except:
        pass

    # Save
    result = {
        "cycle": int(read_text(DATA / "cycle.txt", "0").strip() or "0"),
        "ts": time.time(),
        "suggestions": suggestions
    }
    Path(SUGGESTIONS_FILE).write_text(json.dumps(result, indent=2))
    return suggestions

if __name__ == "__main__":
    suggestions = generate_suggestions()
    for s in suggestions:
        print("[self-suggest] [" + s["type"] + "] " + s["text"] + " (from " + s["source"] + ")")
    if not suggestions:
        print("[self-suggest] No suggestions this cycle")
