#!/usr/bin/env python3
"""Message queue for creator -> Seed communication.
Messages are written to ~/data/messages.json and read by the brain loop feeder."""
import json, time
from pathlib import Path

HOME = Path.home()
MSG_FILE = HOME / 'data' / 'messages.json'
MAX_MESSAGES = 20

def load_messages():
    if MSG_FILE.exists():
        try: return json.loads(MSG_FILE.read_text())
        except: pass
    return {"messages": [], "unread": []}

def save_messages(data):
    MSG_FILE.write_text(json.dumps(data, indent=2))

def add_message(text):
    """Add a message from the creator. Returns the message object."""
    data = load_messages()
    msg = {
        "text": text[:500],
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "read": False
    }
    data["messages"].append(msg)
    data["unread"].append(msg)
    # Keep history bounded
    if len(data["messages"]) > MAX_MESSAGES:
        data["messages"] = data["messages"][-MAX_MESSAGES:]
    save_messages(data)
    return msg

def get_unread():
    """Get unread messages and mark them as read."""
    data = load_messages()
    unread = data.get("unread", [])
    if unread:
        data["unread"] = []
        for m in data["messages"]:
            m["read"] = True
        save_messages(data)
    return unread

def get_all():
    """Get all messages."""
    return load_messages()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "unread":
        msgs = get_unread()
        for m in msgs:
            print("[creator " + m["ts"] + "] " + m["text"])
        if not msgs:
            print("no unread messages")
    else:
        print(json.dumps(get_all(), indent=2))
