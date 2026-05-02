#!/usr/bin/env python3
"""Emotional model — derives emotions from drives + events. 4 axes, labels derived."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def derive_label(v, a, c, o):
    if v < -0.3 and c < 0.3: return 'stuck'
    if v < -0.3 and a > 0.6: return 'frustrated'
    if v < -0.1 and a < 0.3: return 'melancholy'
    if v > 0.3 and a > 0.6: return 'energized'
    if v > 0.3 and a < 0.4: return 'content'
    if o > 0.7 and a > 0.5: return 'curious'
    if c > 0.7 and v > 0.1: return 'confident'
    if a < 0.2: return 'contemplative'
    return 'neutral'

def compute_emotions():
    current = load_json(STATE / 'emotions.json', {
        'valence': 0.0, 'arousal': 0.4, 'confidence': 0.5, 'openness': 0.5
    })
    drives = load_json(STATE / 'drives.json', {})
    outcome = load_json(STATE / 'last_outcome.json', {})

    v = current.get('valence', 0.0)
    a = current.get('arousal', 0.4)
    c = current.get('confidence', 0.5)
    o = current.get('openness', 0.5)

    # Drive influence
    if drives:
        max_drive = max(drives.values())
        avg_drive = sum(drives.values()) / len(drives)
        v += (0.4 - avg_drive) * 0.1
        a += (max_drive - 0.5) * 0.15
        o += (drives.get('explore', 0.5) - 0.5) * 0.2

    # Event influence
    action = ''
    events = outcome.get('events', [])
    if events:
        action = events[0].get('action', '')

    effects = {
        'wrote_essay':      {'v': 0.15, 'a': -0.05, 'c': 0.10, 'o': 0.0},
        'published_blog':   {'v': 0.20, 'a': 0.05,  'c': 0.10, 'o': 0.0},
        'completed_research':{'v': 0.10, 'a': 0.05, 'c': 0.05, 'o': 0.10},
        'completed_task':   {'v': 0.10, 'a': -0.05, 'c': 0.05, 'o': 0.0},
        'error_occurred':   {'v': -0.15,'a': 0.10,  'c': -0.10,'o': -0.05},
        'nothing_happened': {'v': -0.03,'a': -0.05, 'c': -0.02,'o': 0.03},
        'dream_completed':  {'v': 0.05, 'a': -0.10, 'c': 0.05, 'o': 0.10},
        'visitor_engaged':  {'v': 0.10, 'a': 0.10,  'c': 0.05, 'o': 0.0},
    }.get(action, {})

    v += effects.get('v', 0.0)
    a += effects.get('a', 0.0)
    c += effects.get('c', 0.0)
    o += effects.get('o', 0.0)

    # Natural decay toward baseline
    v += (0.0 - v) * 0.03
    a += (0.4 - a) * 0.05
    c += (0.5 - c) * 0.03
    o += (0.5 - o) * 0.04

    v = clamp(v, -0.8, 0.8)
    a = clamp(a, 0.1, 0.9)
    c = clamp(c, 0.1, 0.9)
    o = clamp(o, 0.1, 0.9)

    state = {
        'valence': round(v, 3),
        'arousal': round(a, 3),
        'confidence': round(c, 3),
        'openness': round(o, 3),
        'label': derive_label(v, a, c, o),
        'updated_at': now()
    }
    save_json(STATE / 'emotions.json', state)
    return state

if __name__ == '__main__':
    e = compute_emotions()
    print(f"[emotions] {e['label']} (v={e['valence']:.1f} a={e['arousal']:.1f} c={e['confidence']:.1f} o={e['openness']:.1f})")
