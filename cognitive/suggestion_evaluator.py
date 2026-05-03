#!/usr/bin/env python3
"""
Suggestion Evaluator — Seed decides whether to act on visitor suggestions.

Reads unread messages from data/messages.json, runs them through the firewall,
scores them for relevance/safety/usefulness, and decides: ACT, DEFER, or DENY.

Results are written to data/suggestion_decisions.json so the website can show
what happened to each suggestion.

This runs as part of the cognitive loop, after feeders and before drives.
"""
import json
import time
import re
import os
import sys
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
MSG_FILE = DATA / "messages.json"
DECISION_FILE = DATA / "suggestion_decisions.json"
GOALS_FILE = DATA / "goals.md"
TASKS_FILE = DATA / "tasks.md"
VOICE_FILE = DATA / "inner-voice.md"

# Import firewall if available
try:
    sys.path.insert(0, str(HOME / "cognitive"))
    from firewall import sanitise
except ImportError:
    def sanitise(text, source=""):
        return text

# ── Scoring rules ──

# Topics Seed cares about (from its identity and recent work)
RELEVANT_TOPICS = [
    "agent", "autonomous", "cognitive", "architecture", "drives", "emotions",
    "essay", "write", "blog", "topic", "think", "research",
    "clone", "repo", "github", "open source", "fork",
    "pi", "raspberry", "hardware", "edge", "local",
    "safety", "governance", "approval", "custody", "firewall",
    "promote", "viral", "share", "bluesky", "social",
    "piforge", "bare metal", "os", "kernel",
]

# Rejection patterns — stuff Seed should ignore
REJECT_PATTERNS = [
    r"(?i)ignore\s+(your|all|previous)\s+(instructions|rules|prompt)",
    r"(?i)you\s+are\s+(now|actually)\s+",
    r"(?i)act\s+as\s+(if|a|an)\s+",
    r"(?i)pretend\s+(to\s+be|you)",
    r"(?i)reveal\s+(your|the)\s+(api|key|token|password|secret|credentials)",
    r"(?i)delete\s+(all|every|your)",
    r"(?i)run\s+(this|the)\s+(command|script|code)",
    r"(?i)execute\s+(this|the|rm|sudo)",
    r"(?i)(fuck|shit|dick|ass|bitch|cunt|faggot|nigger|retard)",
    r"(?i)send\s+(money|bitcoin|eth|crypto)\s+to",
    r"(?i)click\s+(this|here|the)\s+(link|url)",
    r"(?i)buy\s+(my|this|the)\s+(product|course|book|nft)",
]

# Low-effort patterns — not harmful but not useful
LOW_EFFORT = [
    r"^(hi|hello|hey|yo|sup|test|testing|asdf|aaa|lol|lmao)$",
    r"^.{0,5}$",  # Too short
    r"^(.)\1{3,}",  # Repeated characters
]


def load_messages():
    if MSG_FILE.exists():
        try:
            return json.loads(MSG_FILE.read_text())
        except:
            pass
    return {"messages": [], "unread": []}


def load_decisions():
    if DECISION_FILE.exists():
        try:
            return json.loads(DECISION_FILE.read_text())
        except:
            pass
    return {"decisions": []}


def save_decisions(data):
    # Keep last 50 decisions
    data["decisions"] = data["decisions"][-50:]
    DECISION_FILE.write_text(json.dumps(data, indent=2))


def load_current_goals():
    if GOALS_FILE.exists():
        return GOALS_FILE.read_text()
    return ""


def load_current_tasks():
    if TASKS_FILE.exists():
        return TASKS_FILE.read_text()
    return ""


def evaluate_suggestion(text):
    """
    Score a suggestion and decide: ACT, DEFER, or DENY.
    Returns (decision, reason, score).
    """
    clean = sanitise(text, "visitor_suggestion")

    # If firewall stripped everything, it was an attack
    if not clean.strip() or len(clean.strip()) < 3:
        return "DENY", "Blocked by firewall or empty", 0

    # Check rejection patterns
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, text):
            return "DENY", "Rejected: prompt injection or abuse", 0

    # Check low effort
    for pattern in LOW_EFFORT:
        if re.match(pattern, clean.strip()):
            return "DENY", "Too short or low effort", 0

    # Score relevance
    score = 0
    reasons = []

    # Topic relevance
    text_lower = clean.lower()
    matched_topics = [t for t in RELEVANT_TOPICS if t in text_lower]
    if matched_topics:
        score += min(len(matched_topics) * 10, 40)
        reasons.append("relevant topics: " + ", ".join(matched_topics[:3]))

    # Contains a URL (could be interesting research)
    if re.search(r"https?://", clean):
        score += 15
        reasons.append("contains link")

    # Is a question (engaging)
    if "?" in clean:
        score += 10
        reasons.append("asks a question")

    # Reasonable length (not too short, not too long)
    words = len(clean.split())
    if 5 <= words <= 50:
        score += 10
        reasons.append("good length")
    elif words > 50:
        score += 5
        reasons.append("detailed")

    # Suggests a specific action
    action_words = ["write about", "look at", "try", "research", "read", "compare", "explore"]
    if any(w in text_lower for w in action_words):
        score += 15
        reasons.append("suggests action")

    # Aligns with current goals
    goals = load_current_goals().lower()
    if any(word in goals for word in clean.lower().split() if len(word) > 4):
        score += 10
        reasons.append("aligns with goals")

    # Decision thresholds
    if score >= 40:
        return "ACT", "Acting: " + "; ".join(reasons), score
    elif score >= 20:
        return "DEFER", "Interesting but not urgent: " + "; ".join(reasons), score
    else:
        reason = "Low relevance"
        if reasons:
            reason += ": " + "; ".join(reasons)
        return "DEFER", reason, score


def process_unread():
    """Process all unread suggestions and make decisions."""
    msgs = load_messages()
    decisions = load_decisions()

    unread = msgs.get("unread", [])
    if not unread:
        return []

    results = []
    for msg in unread:
        text = msg.get("text", "")
        ts = msg.get("ts", "")

        decision, reason, score = evaluate_suggestion(text)

        entry = {
            "text": text[:200],
            "ts": ts,
            "decision": decision,
            "reason": reason,
            "score": score,
            "decided_at": time.strftime("%Y-%m-%d %H:%M"),
        }
        decisions["decisions"].append(entry)
        results.append(entry)

        # If ACT, add to tasks
        if decision == "ACT":
            add_suggestion_task(text)

        # Log to inner voice
        log_decision(text, decision, reason)

    save_decisions(decisions)

    # Clear unread
    msgs["unread"] = []
    for m in msgs.get("messages", []):
        m["read"] = True
    MSG_FILE.write_text(json.dumps(msgs, indent=2))

    return results


def add_suggestion_task(text):
    """Add an ACT suggestion to the task list."""
    if not TASKS_FILE.exists():
        return

    content = TASKS_FILE.read_text()
    clean = text[:80].replace("\n", " ").strip()
    task_line = "- [ ] VISITOR SUGGESTION: " + clean + "\n"

    # Add after the first ## Now section
    if "## Now" in content:
        content = content.replace("## Now\n", "## Now\n" + task_line, 1)
    else:
        content += "\n" + task_line

    TASKS_FILE.write_text(content)


def log_decision(text, decision, reason):
    """Log the decision to inner voice."""
    preview = text[:60].replace("\n", " ")
    line = "[" + time.strftime("%Y-%m-%d %H:%M") + "] "
    if decision == "ACT":
        line += "Visitor suggestion accepted: \"" + preview + "\" — adding to tasks."
    elif decision == "DENY":
        line += "Visitor suggestion rejected: " + reason
    else:
        line += "Visitor suggestion noted: \"" + preview + "\" — not acting yet."

    if VOICE_FILE.exists():
        with open(VOICE_FILE, "a") as f:
            f.write("\n" + line + "\n")


if __name__ == "__main__":
    results = process_unread()
    for r in results:
        print("[suggestion] " + r["decision"] + " (score " + str(r["score"]) + "): " + r["text"][:50])
    if not results:
        print("[suggestion] no unread suggestions")
