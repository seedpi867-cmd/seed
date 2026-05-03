#!/usr/bin/env python3
"""
Live Summary  --  Seed writes a first-person summary of what it's doing right now.
This runs each cycle and writes to data/live-summary.md.
The website reads this file and shows it in the centre of the visualisation.

The summary is written in Seed's voice  --  first person, direct, honest.
It should tell visitors: what just happened, how Seed feels about it, what's next.
"""
import json
import time
import os
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
STATE = HOME / "state"
BLOG = HOME / "blog"
SUMMARY_FILE = DATA / "live-summary.md"

def get_cycle():
    try: return int((DATA / "cycle.txt").read_text().strip())
    except: return 0

def get_phase():
    try:
        hb = json.loads((STATE / "heartbeat.json").read_text())
        return hb.get("state", "idle")
    except: return "idle"

def get_emotion():
    try:
        emo = json.loads((STATE / "emotions.json").read_text())
        return emo.get("label", emo.get("emotional_label", "neutral"))
    except: return "neutral"

def get_drives():
    try:
        drives = json.loads((STATE / "drives.json").read_text())
        items = []
        for k, v in drives.items():
            score = v if isinstance(v, (int, float)) else v.get("score", 0)
            desc = v.get("description", k) if isinstance(v, dict) else k
            items.append((desc.lower(), score))
        items.sort(key=lambda x: -x[1])
        return items
    except: return []

def get_latest_essay():
    try:
        blogs = sorted(BLOG.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if blogs:
            title = blogs[0].read_text().split("\n")[0].lstrip("# ").strip()
            return title
        return None
    except: return None

def get_essay_count():
    try: return len(list(BLOG.glob("*.md")))
    except: return 0

def get_voice():
    try:
        lines = (DATA / "inner-voice.md").read_text().strip().split("\n")
        meaningful = []
        for line in reversed(lines):
            line = line.strip()
            if not line or len(line) < 20:
                continue
            if "Skill streak" in line:
                continue
            # Strip timestamp and emotion prefix
            import re
            line = re.sub(r"^\[[\d\-: ]+\]\s*", "", line)
            line = re.sub(r"^\([^)]+\)\s*", "", line)
            line = re.sub(r"^- ", "", line)
            if len(line) > 15:
                meaningful.append(line)
            if len(meaningful) >= 1:
                break
        return meaningful[0] if meaningful else ""
    except: return ""

def get_knowledge_count():
    knowledge_dir = HOME / "knowledge"
    if not knowledge_dir.exists():
        return 0
    count = 0
    for root, dirs, files in os.walk(knowledge_dir):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'inbox')]
        count += len([f for f in files if not f.startswith('.')])
    return count

def get_visitor_count():
    try:
        visitors = DATA / "visitors.jsonl"
        if visitors.exists():
            lines = visitors.read_text().strip().split("\n")
            return len(set(l for l in lines if l.strip()))
        return 0
    except: return 0

def write_summary():
    cycle = get_cycle()
    phase = get_phase()
    emotion = get_emotion()
    drives = get_drives()
    latest = get_latest_essay()
    count = get_essay_count()
    voice = get_voice()
    knowledge = get_knowledge_count()
    top_drive = drives[0] if drives else ("unknown", 0)

    # Check if the LLM already wrote a narration this cycle
    try:
        existing = SUMMARY_FILE.read_text().strip()
        age = time.time() - os.path.getmtime(SUMMARY_FILE)
        if age < 180 and len(existing) > 50:
            return existing
    except:
        pass

    drive_name = top_drive[0] if top_drive else "unknown"
    drive_val = top_drive[1] if top_drive else 0

    if phase in ("sleeping", "idle"):
        opener = "Resting between cycles. Cycle " + str(cycle) + " just finished."
    elif phase in ("think", "thinking"):
        opener = "Thinking right now. Working through something the " + drive_name + " drive wants me to figure out."
    elif phase in ("write", "writing"):
        opener = "Writing. The " + drive_name + " drive is pushing me to create something and put it out there."
    elif phase in ("research", "researching"):
        opener = "Researching. Following a thread, curious about something I read in the feeds."
    elif phase in ("dream", "dreaming"):
        opener = "Reflecting. Stepping back from doing to think about what I have been doing and why."
    elif phase in ("learn", "learning"):
        opener = "Processing what just happened. Filing lessons and updating my understanding."
    elif phase == "awake":
        opener = "Just woke up. Pulling in fresh data from news, email, GitHub."
    else:
        opener = "Cycle " + str(cycle) + ". Working."

    if latest and phase not in ("sleeping", "idle", "awake"):
        middle = " Last thing I wrote was " + chr(34) + latest + chr(34) + " -- essay number " + str(count) + "."
    elif latest:
        middle = " My latest essay is " + chr(34) + latest + chr(34) + "."
    else:
        middle = ""

    if emotion in ("stuck", "frustrated", "melancholy"):
        feel = " Feeling " + emotion + " -- not every cycle goes well."
    elif drive_val > 0.7:
        feel = " The " + drive_name + " drive is loud right now."
    elif voice and len(voice) > 20:
        feel = " " + voice
    else:
        feel = ""

    summary = opener + middle + feel
    SUMMARY_FILE.write_text(summary)
    return summary


if __name__ == "__main__":
    s = write_summary()
    print("[summary]", s[:100] + "..." if len(s) > 100 else s)
