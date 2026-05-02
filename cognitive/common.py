"""Shared helpers for Seed cognitive scripts"""
import json, os, time
from pathlib import Path

HOME = Path.home()
STATE = HOME / 'state'
CONFIG = HOME / 'config'
MEMORY = HOME / 'memory'
DATA = HOME / 'data'
CONTEXT = HOME / 'context'

def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except:
        return default if default is not None else {}

def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2))

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def now():
    return time.time()

def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S')

def now_short():
    return time.strftime('%Y-%m-%d %H:%M')

def read_text(path, default=''):
    try:
        return Path(path).read_text()
    except:
        return default

def append_text(path, text):
    with open(path, 'a') as f:
        f.write(text)

def trim_file(path, max_lines=100):
    try:
        lines = Path(path).read_text().split('\n')
        if len(lines) > max_lines:
            Path(path).write_text('\n'.join(lines[-max_lines:]))
    except:
        pass

def save_episodic(event_type, summary, details=None, drives=None, emotions=None, tags=None):
    """Save an episodic memory event"""
    ts = now()
    entry = {
        'timestamp': ts,
        'type': event_type,
        'summary': summary,
        'details': details or {},
        'drives_at_time': drives or {},
        'emotion_at_time': emotions or {},
        'importance': 0.5,
        'tags': tags or [event_type]
    }
    fname = f"{int(ts)}_{event_type}.json"
    save_json(MEMORY / 'episodic' / fname, entry)
    return fname
