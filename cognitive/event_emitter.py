#!/usr/bin/env python3
"""
Event Emitter — Seed emits natural language events as it works.
Events are written to data/events.jsonl.
The website reads these and animates them as speech bubbles on the ring nodes.

Each event has:
  - ts: unix timestamp
  - node: which ring node (input, filter, state, decide, act, learn, output)
  - text: natural language description of what happened
  - type: category (data_in, filtered, state_change, decision, action, outcome, output)
"""
import json
import time
import os
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
EVENTS_FILE = DATA / "events.jsonl"
MAX_EVENTS = 50  # keep last 50 in the file


def emit(node, text, event_type="info"):
    """Write a single event to the event log."""
    event = {
        "ts": time.time(),
        "time": time.strftime("%H:%M:%S"),
        "node": node,
        "text": text,
        "type": event_type
    }

    # Append to file
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")

    # Trim to last MAX_EVENTS
    try:
        lines = EVENTS_FILE.read_text().strip().split("\n")
        if len(lines) > MAX_EVENTS:
            EVENTS_FILE.write_text("\n".join(lines[-MAX_EVENTS:]) + "\n")
    except:
        pass


def get_recent(count=20):
    """Read recent events."""
    if not EVENTS_FILE.exists():
        return []
    try:
        lines = EVENTS_FILE.read_text().strip().split("\n")
        events = []
        for line in lines[-count:]:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except:
                    pass
        return events
    except:
        return []


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        emit(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "info")
        print("[event] " + sys.argv[1] + ": " + sys.argv[2])
    else:
        events = get_recent()
        for e in events:
            print(e["time"] + " [" + e["node"] + "] " + e["text"])
        if not events:
            print("no events yet")
