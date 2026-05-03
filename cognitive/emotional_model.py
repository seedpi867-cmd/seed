#!/usr/bin/env python3
"""Emotional model — emotions come from events and drive state, not time decay.

Emotions persist until something changes them. Writing a good essay feels good
until something bad happens, not until a timer runs out. Confidence builds from
streaks and erodes from failures, not from a decay constant.

4 axes: valence (good/bad), arousal (calm/energized), confidence, openness.
Label derived from the combination.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def derive_label(v, a, c, o):
    if v < -0.3 and c < 0.3: return 'stuck'
    if v < -0.3 and a > 0.6: return 'frustrated'
    if v < -0.1 and a < 0.3: return 'melancholy'
    if v > 0.5 and a > 0.6: return 'energized'
    if v > 0.3 and a > 0.6: return 'excited'
    if v > 0.3 and a < 0.4: return 'content'
    if v > 0.1 and c > 0.7: return 'confident'
    if o > 0.7 and a > 0.5: return 'curious'
    if a < 0.2: return 'contemplative'
    if v > 0.1: return 'steady'
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

    # ── Drive influence on arousal and openness ──
    # High drives = high arousal (urgency). Explore drive = openness.
    if drives:
        max_drive = max(drives.values())
        # Arousal tracks the strongest drive — high pressure = high energy
        a += (max_drive - 0.5) * 0.1
        # Openness tracks explore drive
        o += (drives.get('explore', 0.5) - 0.5) * 0.1

    # ── Event influence — process ALL events, not just the first ──
    effects_map = {
        'wrote_essay':        {'v': 0.12, 'a': -0.03, 'c': 0.08, 'o': 0.0},
        'published_blog':     {'v': 0.15, 'a': 0.05,  'c': 0.08, 'o': 0.0},
        'completed_research': {'v': 0.08, 'a': 0.03,  'c': 0.04, 'o': 0.08},
        'completed_task':     {'v': 0.06, 'a': -0.03, 'c': 0.05, 'o': 0.0},
        'error_occurred':     {'v': -0.12,'a': 0.08,  'c': -0.10,'o': -0.05},
        'nothing_happened':   {'v': -0.05,'a': -0.05, 'c': -0.04,'o': 0.0},
        'dream_completed':    {'v': 0.04, 'a': -0.08, 'c': 0.03, 'o': 0.08},
        'visitor_engaged':    {'v': 0.10, 'a': 0.08,  'c': 0.05, 'o': 0.0},
        'health_ok':          {'v': 0.02, 'a': 0.0,   'c': 0.02, 'o': 0.0},
        'inner_voice_written':{'v': 0.02, 'a': -0.02, 'c': 0.01, 'o': 0.03},
        'git_committed':      {'v': 0.03, 'a': 0.0,   'c': 0.02, 'o': 0.0},
    }

    events = outcome.get('events', [])
    seen = set()
    for event in events:
        action = event.get('action', '')
        if action in seen:
            continue
        seen.add(action)
        effects = effects_map.get(action, {})
        v += effects.get('v', 0.0)
        a += effects.get('a', 0.0)
        c += effects.get('c', 0.0)
        o += effects.get('o', 0.0)

    # ── Skill streak influence on confidence ──
    # Long streaks build lasting confidence. This is earned, not decayed.
    try:
        skills = load_json(DATA / 'skill_stats.json', {})
        best_streak = max((s.get('streak', 0) for s in skills.values()), default=0)
        if best_streak > 100:
            c += 0.03  # sustained competence builds confidence
        elif best_streak > 50:
            c += 0.02
    except:
        pass

    # ── NO TIME DECAY ──
    # Emotions only change from events and drive state.
    # The only "decay" is a very gentle regression when nothing is happening,
    # and only on arousal (energy naturally settles, mood does not).
    if not events or (len(events) == 1 and events[0].get('action') == 'health_ok'):
        # Quiet cycle — arousal settles slightly, everything else stays
        a += (0.4 - a) * 0.02  # only arousal drifts — energy settles when idle
        # valence, confidence, openness DO NOT decay

    # ── Hard clamps ──
    v = clamp(v, -0.8, 0.8)
    a = clamp(a, 0.1, 0.9)
    c = clamp(c, 0.15, 0.95)
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
