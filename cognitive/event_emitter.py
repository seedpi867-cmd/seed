#!/usr/bin/env python3
"""
Event Emitter - Seed emits natural language events as it works.
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
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
EVENTS_FILE = DATA / "events.jsonl"
MAX_EVENTS = 50


def emit(node, text, event_type="info"):
    """Write a single event to the event log."""
    event = {
        "ts": time.time(),
        "time": time.strftime("%H:%M:%S"),
        "node": node,
        "text": text,
        "type": event_type,
    }

    with open(EVENTS_FILE, "a") as handle:
        handle.write(json.dumps(event) + "\n")

    try:
        lines = EVENTS_FILE.read_text().strip().split("\n")
        if len(lines) > MAX_EVENTS:
            EVENTS_FILE.write_text("\n".join(lines[-MAX_EVENTS:]) + "\n")
    except Exception:
        pass


def get_recent(count=20):
    """Read recent events."""
    if not EVENTS_FILE.exists():
        return []
    try:
        lines = EVENTS_FILE.read_text().strip().split("\n")
        events = []
        for line in lines[-count:]:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                pass
        return events
    except Exception:
        return []


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4:
        emit(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "info")
        print("[event] " + sys.argv[1] + ": " + sys.argv[2])
    else:
        events = get_recent()
        for event in events:
            print(event["time"] + " [" + event["node"] + "] " + event["text"])
        if not events:
            print("no events yet")
