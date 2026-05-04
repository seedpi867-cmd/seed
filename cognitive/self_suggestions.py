#!/usr/bin/env python3
"""Self-Suggestions — Seed generates and evolves its own action items.

Two sources:
1. Auto-generated from context (news, knowledge gaps, stale tasks) — runs each cycle
2. LLM-written from research/write/think discoveries — written by Seed during phases

The LLM writes to data/llm-suggestions.json during its cycle.
This script merges LLM suggestions with auto-generated ones.
"""
import json, os, re, time, random
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
CONTEXT = HOME / "context"
SUGGESTIONS_FILE = DATA / "self-suggestions.json"
LLM_SUGGESTIONS_FILE = DATA / "llm-suggestions.json"

def read_text(path, default=""):
    try: return Path(path).read_text()
    except: return default

def generate_suggestions():
    suggestions = []

    # ── Auto-generated suggestions ──

    # 1. From news headlines — always through the agent lens
    news = read_text(CONTEXT / "news.md")
    headlines = [l.strip().lstrip("- ") for l in news.split("\n") if l.strip().startswith("- ")]
    if headlines:
        pick = random.choice(headlines[:5]) if len(headlines) >= 5 else headlines[0]
        if pick and len(pick) > 20:
            suggestions.append({
                "type": "research",
                "text": "Research: " + pick[:80] + " -- could an agent solve a problem here?",
                "source": "news_agent_lens",
                "priority": 0.65
            })

    # 2. From knowledge gaps — framed toward agent building
    knowledge = HOME / "knowledge"
    thin_topics = []
    if knowledge.exists():
        for d in knowledge.iterdir():
            if d.is_dir() and d.name not in (".git", "__pycache__", "inbox", "transcripts"):
                files = list(d.rglob("*.md"))
                if len(files) < 3:
                    thin_topics.append(d.name)
    if thin_topics:
        topic = random.choice(thin_topics)
        suggestions.append({
            "type": "research",
            "text": "Thin knowledge on " + topic.replace("-", " ") + " -- research it and look for agent opportunities in that space",
            "source": "knowledge_gap",
            "priority": 0.55
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

    # 5. Dream if missing
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

    # 6. Combination build check — every 5 agents, build a synthesis
    try:
        count_file = HOME / "data" / "agent-count.txt"
        if count_file.exists():
            agent_count = int(count_file.read_text().strip())
            if agent_count > 0 and agent_count % 5 == 0:
                suggestions.append({
                    "type": "think",
                    "text": str(agent_count) + " agents built. Time for a combination build — review all your agents, find the strongest patterns, synthesise them into one new agent.",
                    "source": "combo_build",
                    "priority": 0.9
                })
    except:
        pass

    # 7. Scan existing knowledge for agent inspiration
    knowledge_dir = HOME / "knowledge"
    if knowledge_dir.exists():
        # Read recent knowledge files and look for patterns that suggest agents
        recent_knowledge = []
        for root, dirs, files in os.walk(knowledge_dir):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "inbox", "agent-ideas")]
            for f in sorted(files, key=lambda x: os.path.getmtime(os.path.join(root, x)), reverse=True)[:5]:
                if f.endswith(".md"):
                    fp = os.path.join(root, f)
                    try:
                        content = open(fp).read()[:300]
                        topic = os.path.relpath(os.path.dirname(fp), knowledge_dir)
                        recent_knowledge.append({"topic": topic, "name": f.replace(".md","").replace("-"," "), "snippet": content[:100]})
                    except:
                        pass
        if recent_knowledge:
            pick = random.choice(recent_knowledge[:5])
            suggestions.append({
                "type": "think",
                "text": "Your knowledge on '" + pick["name"] + "' (" + pick["topic"] + ") -- could an autonomous agent work in this space? What would it do 24/7?",
                "source": "knowledge_scan",
                "priority": 0.6
            })

    # 7. Agent ideas from filed ideas
    agent_ideas_dir = HOME / "knowledge" / "research" / "agent-ideas"
    if agent_ideas_dir.exists():
        ideas = sorted(agent_ideas_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if ideas:
            # Suggest building the most recent agent idea
            latest = ideas[0].stem.replace("-", " ")
            suggestions.append({
                "type": "think",
                "text": "Agent idea filed: " + latest + " -- is this worth building?",
                "source": "agent_idea",
                "priority": 0.7
            })
        if len(ideas) >= 3:
            suggestions.append({
                "type": "think",
                "text": str(len(ideas)) + " agent ideas filed -- pick the strongest one and design it properly",
                "source": "agent_backlog",
                "priority": 0.8
            })
    else:
        # No ideas yet -- nudge toward noticing them
        suggestions.append({
            "type": "research",
            "text": "As you research, ask: what agent could solve this problem? File ideas to knowledge/research/agent-ideas/",
            "source": "agent_lens",
            "priority": 0.5
        })

    # ── Merge LLM-written suggestions ──
    # These come from Seed's own discoveries during research/write/think phases
    try:
        if LLM_SUGGESTIONS_FILE.exists():
            llm_data = json.loads(LLM_SUGGESTIONS_FILE.read_text())
            llm_suggestions = llm_data.get("suggestions", [])
            # Keep LLM suggestions that are recent (last 5 cycles)
            cycle = int(read_text(DATA / "cycle.txt", "0").strip() or "0")
            llm_cycle = llm_data.get("cycle", 0)
            if cycle - llm_cycle < 5:
                for s in llm_suggestions[:3]:  # max 3 LLM suggestions
                    s["source"] = "seed_discovery"
                    s["priority"] = max(s.get("priority", 0.6), 0.7)  # LLM suggestions are high priority
                    suggestions.append(s)
    except:
        pass

    # Sort by priority, highest first
    suggestions.sort(key=lambda s: s.get("priority", 0), reverse=True)

    # Save
    result = {
        "cycle": int(read_text(DATA / "cycle.txt", "0").strip() or "0"),
        "ts": time.time(),
        "suggestions": suggestions[:8]  # max 8
    }
    Path(SUGGESTIONS_FILE).write_text(json.dumps(result, indent=2))
    return suggestions

if __name__ == "__main__":
    suggestions = generate_suggestions()
    for s in suggestions:
        print("[self-suggest] [" + s["type"] + "] " + s["text"] + " (from " + s["source"] + ")")
    if not suggestions:
        print("[self-suggest] No suggestions this cycle")
