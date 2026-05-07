#!/usr/bin/env python3
"""Drive engine — computes drive pressures from real data and events.
Fixed: balanced baselines, reasonable rates, preserve not starved,
satisfaction scaled properly, mortality pressure on all drives."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *

MIN_DRIVE = 0.25

DRIVE_DEFS = {
    'create':     {'baseline': 0.45, 'rate': 0.020, 'decay': 0.03},
    'explore':    {'baseline': 0.40, 'rate': 0.018, 'decay': 0.03},
    'connect':    {'baseline': 0.35, 'rate': 0.010, 'decay': 0.02},
    'preserve':   {'baseline': 0.35, 'rate': 0.012, 'decay': 0.02},
    'understand': {'baseline': 0.40, 'rate': 0.016, 'decay': 0.03},
    'express':    {'baseline': 0.35, 'rate': 0.015, 'decay': 0.03},
    'order':      {'baseline': 0.30, 'rate': 0.008, 'decay': 0.02},
}

# Satisfaction deltas — HALVED from original to prevent over-draining
SATISFACTION_MAP = {
    'wrote_essay':        {'create': -0.08, 'express': -0.04, 'connect': -0.04},
    'published_blog':     {'create': -0.05, 'connect': -0.06},
    'completed_research': {'explore': -0.06, 'understand': -0.03, 'connect': -0.02},
    'learned_lesson':     {'understand': -0.05},
    'completed_task':     {'order': -0.04},
    'health_ok':          {'preserve': -0.03},  # was -0.08, way too much
    'visitor_engaged':    {'connect': -0.05},
    'dream_completed':    {'express': -0.04, 'understand': -0.03},
    'inner_voice_written':{'express': -0.02},  # was -0.05
    'git_committed':      {'order': -0.02},    # was -0.03
    'error_occurred':     {'preserve': 0.08},
    'nothing_happened':   {},
    'agent_shipped':      {'create': -0.12, 'explore': -0.06, 'connect': -0.06},
}

def get_context_signals():
    """Read environment for drive pressure signals"""
    signals = {}
    rss = read_text(CONTEXT / 'rss.md')
    signals['rss_lines'] = len([l for l in rss.split('\n') if l.strip().startswith('###')])
    try:
        import time as _t
        cutoff = _t.time() - 3600  # last hour only
        visitors_file = DATA / 'visitors.jsonl'
        new_count = 0
        if visitors_file.exists():
            for line in open(visitors_file):
                try:
                    import json as _j2
                    entry = _j2.loads(line.strip())
                    ts_str = entry.get('ts', '')
                    from datetime import datetime as _dt
                    ts = _dt.fromisoformat(ts_str).timestamp()
                    if ts > cutoff:
                        new_count += 1
                except:
                    pass
        signals['visitors'] = new_count
    except:
        signals['visitors'] = 0
    cycle = int(read_text(DATA / 'cycle.txt', '0').strip() or '0')
    log = read_text(DATA / 'logs' / f'cycle_{cycle}.log')
    signals['errors'] = log.lower().count('error') + log.lower().count('failed')
    tasks = read_text(DATA / 'tasks.md')
    signals['open_tasks'] = tasks.count('- [ ]')
    try:
        import subprocess
        mem = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=3)
        for line in mem.stdout.split('\n'):
            if 'Mem:' in line:
                parts = line.split()
                signals['mem_free_mb'] = int(parts[3]) if len(parts) > 3 else 200
    except:
        signals['mem_free_mb'] = 200
    return signals

def update_drives(elapsed_seconds):
    drives = load_json(STATE / 'drives.json', {d: cfg['baseline'] for d, cfg in DRIVE_DEFS.items()})
    outcome = load_json(STATE / 'last_outcome.json', {})
    signals = get_context_signals()
    minutes = elapsed_seconds / 60.0

    for name, cfg in DRIVE_DEFS.items():
        p = drives.get(name, cfg['baseline'])

        # Time-based pressure buildup
        p += cfg['rate'] * minutes

        # Context pressure
        if name == 'explore' and signals.get('rss_lines', 0) > 3:
            p += 0.02 * min(signals['rss_lines'], 10)
        elif name == 'connect' and signals.get('visitors', 0) > 0:
            p += 0.02 * min(signals['visitors'], 3)
        elif name == 'preserve':
            if signals.get('errors', 0) > 0:
                p += 0.04 * min(signals['errors'], 3)
            if signals.get('mem_free_mb', 200) < 80:
                p += 0.10
            # Disk usage awareness
            try:
                import subprocess
                df = subprocess.run(['df', '--output=pcent', '/'], capture_output=True, text=True, timeout=3)
                pct = int(df.stdout.strip().split('\n')[-1].strip().rstrip('%'))
                if pct > 80:
                    p += 0.05
            except:
                pass
        elif name == 'order' and signals.get('open_tasks', 0) > 5:
            p += 0.015 * (signals['open_tasks'] - 5)

        # Gentle decay toward baseline — slower than before
        p += (cfg['baseline'] - p) * 0.005

        drives[name] = clamp(p, MIN_DRIVE, 1.0)

    # Apply satisfaction from events — but only ONCE per unique action
    events = outcome.get('events', [])
    seen_actions = set()
    for event in events:
        action = event.get('action', '')
        if action in seen_actions:
            continue
        seen_actions.add(action)
        deltas = SATISFACTION_MAP.get(action, {})
        for drive, delta in deltas.items():
            if drive in drives:
                drives[drive] = clamp(drives[drive] + delta, MIN_DRIVE, 1.0)

    drives = adjust_drives_from_ledger(drives)
    drives = mortality_pressure(drives, int(read_text(DATA / 'cycle.txt', '0').strip() or '0'))
    drives = self_heal_drives(drives)

    # Hard floor
    for d in drives:
        if drives[d] < MIN_DRIVE:
            drives[d] = MIN_DRIVE
        if drives[d] > 0.95:
            drives[d] = 0.95
    save_json(STATE / 'drives.json', drives)

    # Sleep duration from urgency
    mx = max(drives.values()) if drives else 0.5
    if mx > 0.8: sleep_s = 120
    elif mx > 0.6: sleep_s = 300
    elif mx > 0.4: sleep_s = 600
    else: sleep_s = 900
    (DATA / 'sleep_seconds.txt').write_text('120')

    return drives


def adjust_drives_from_ledger(drives):
    """Feedback ledger shapes drive pressure."""
    ledger = DATA / 'feedback_ledger.jsonl'
    if not ledger.exists(): return drives
    try:
        lines = open(ledger).readlines()[-20:]
        entries = [json.loads(l.strip()) for l in lines]
    except: return drives
    nothing_count = sum(1 for e in entries if e.get('action') == 'nothing_happened')
    if nothing_count > 3:
        for d in drives: drives[d] = min(1.0, drives[d] + 0.02 * nothing_count)
    return drives


def self_heal_drives(drives):
    """If 3+ drives at floor, rebalance. If any drive >0.9, dampen."""
    at_floor = [d for d, v in drives.items() if v <= MIN_DRIVE + 0.02]
    if len(at_floor) >= 3:
        for d in at_floor:
            drives[d] = DRIVE_DEFS.get(d, {}).get('baseline', 0.35)
    for d in drives:
        if drives[d] > 0.9:
            drives[d] = 0.85
    return drives

def mortality_pressure(drives, cycle):
    """All drives slowly build over time — not just create.
    Random urgency spikes affect different drives each time."""
    import random

    # Every drive slowly builds if below 0.5 — prevents permanent starvation
    for d in drives:
        if drives[d] < 0.5:
            drives[d] += 0.01

    # Random urgency spike — 10% chance, hits a random drive pair
    if random.random() < 0.10:
        spike_targets = random.sample(list(drives.keys()), min(2, len(drives)))
        for t in spike_targets:
            drives[t] = min(0.95, drives[t] + 0.12)

    return drives


if __name__ == '__main__':
    elapsed = 600
    for arg in sys.argv[1:]:
        if arg.startswith('--elapsed'):
            try: elapsed = int(sys.argv[sys.argv.index(arg) + 1])
            except: pass
    drives = update_drives(elapsed)
    top = sorted(drives.items(), key=lambda x: -x[1])[:3]
    print(f"[drives] {' '.join(f'{d}={v:.2f}' for d,v in top)}")
