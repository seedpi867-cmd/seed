#!/usr/bin/env python3
"""Drive engine — computes drive pressures from real data and events"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *

MIN_DRIVE = 0.20  # No drive stays below this — prevents starvation

DRIVE_DEFS = {
    'create':     {'baseline': 0.4, 'rate': 0.025, 'decay': 0.05},
    'explore':    {'baseline': 0.4, 'rate': 0.020, 'decay': 0.04},
    'connect':    {'baseline': 0.3, 'rate': 0.008, 'decay': 0.03},
    'preserve':   {'baseline': 0.15, 'rate': 0.002, 'decay': 0.02},
    'understand': {'baseline': 0.35, 'rate': 0.016, 'decay': 0.04},
    'express':    {'baseline': 0.3, 'rate': 0.018, 'decay': 0.03},
    'order':      {'baseline': 0.20, 'rate': 0.004, 'decay': 0.03},
}

SATISFACTION_MAP = {
    'wrote_essay':        {'create': -0.15, 'express': -0.08},
    'published_blog':     {'create': -0.10, 'connect': -0.05},
    'completed_research': {'explore': -0.12, 'understand': -0.05},
    'learned_lesson':     {'understand': -0.10},
    'completed_task':     {'order': -0.08},
    'health_ok':          {'preserve': -0.08},
    'visitor_engaged':    {'connect': -0.10},
    'dream_completed':    {'express': -0.08, 'understand': -0.05},
    'inner_voice_written':{'express': -0.05},
    'git_committed':      {'order': -0.03},
    'error_occurred':     {'preserve': 0.08},
    'nothing_happened':   {},
}

def get_context_signals():
    """Read environment for drive pressure signals"""
    signals = {}
    # RSS new items
    rss = read_text(CONTEXT / 'rss.md')
    signals['rss_lines'] = len([l for l in rss.split('\n') if l.strip().startswith('###')])
    # Visitors
    try:
        vj = CONTEXT / 'visitors.json'
        if vj.exists():
            signals['visitors'] = load_json(vj, {}).get('count', 0)
        else:
            visitors_file = DATA / 'visitors.jsonl'
            signals['visitors'] = sum(1 for _ in open(visitors_file)) if visitors_file.exists() else 0
    except:
        signals['visitors'] = 0
    # Errors in recent log
    cycle = int(read_text(DATA / 'cycle.txt', '0').strip() or '0')
    log = read_text(DATA / 'logs' / f'cycle_{cycle}.log')
    signals['errors'] = log.lower().count('error') + log.lower().count('failed')
    # Open tasks
    tasks = read_text(DATA / 'tasks.md')
    signals['open_tasks'] = tasks.count('- [ ]')
    # Memory pressure
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
            p += 0.03 * min(signals['visitors'], 5)
        elif name == 'preserve':
            if signals.get('errors', 0) > 0:
                p += 0.05 * min(signals['errors'], 3)
            if signals.get('mem_free_mb', 200) < 80:
                p += 0.15
        elif name == 'order' and signals.get('open_tasks', 0) > 5:
            p += 0.02 * (signals['open_tasks'] - 5)

        # Decay toward baseline
        p += (cfg['baseline'] - p) * 0.01

        drives[name] = clamp(p, MIN_DRIVE, 1.0)

    # Apply satisfaction from events
    events = outcome.get('events', [])
    for event in events:
        action = event.get('action', '')
        deltas = SATISFACTION_MAP.get(action, {})
        for drive, delta in deltas.items():
            if drive in drives:
                drives[drive] = clamp(drives[drive] + delta, 0.0, 1.0)

    drives = adjust_drives_from_ledger(drives)
    drives = mortality_pressure(drives, int(read_text(DATA / 'cycle.txt', '0').strip() or '0'))
    drives = self_heal_drives(drives)
    # HARD FLOOR — no drive below 0.15, no emotion above 0.95
    for d in drives:
        if drives[d] < 0.20: drives[d] = 0.20
        if drives[d] > 0.95: drives[d] = 0.95
    save_json(STATE / 'drives.json', drives)

    # Compute sleep duration from urgency
    mx = max(drives.values()) if drives else 0.5
    if mx > 0.8: sleep_s = 120
    elif mx > 0.6: sleep_s = 300
    elif mx > 0.4: sleep_s = 600
    else: sleep_s = 900
    (DATA / 'sleep_seconds.txt').write_text(str(sleep_s))

    return drives



def adjust_drives_from_ledger(drives):
    """Feedback ledger shapes drive pressure. Inaction spikes all drives.
    Success at one thing boosts pressure for other things."""
    ledger = DATA / 'feedback_ledger.jsonl'
    if not ledger.exists(): return drives
    try:
        lines = open(ledger).readlines()[-20:]
        entries = [json.loads(l.strip()) for l in lines]
    except: return drives
    nothing_count = sum(1 for e in entries if e.get('action') == 'nothing_happened')
    if nothing_count > 3:
        for d in drives: drives[d] = min(1.0, drives[d] + 0.03 * nothing_count)
    return drives


def self_heal_drives(drives):
    """If 4+ drives at floor, rebalance. If any drive >0.9, dampen."""
    at_floor = [d for d, v in drives.items() if v <= 0.21]
    if len(at_floor) >= 3:
        for d in at_floor:
            drives[d] = 0.35
    for d in drives:
        if drives[d] > 0.9:
            drives[d] = 0.85
    return drives

def mortality_pressure(drives, cycle):
    """The longer Seed has been alive without creating, the more urgent creation becomes.
    Also: random small chance of elevated urgency each cycle (simulating unpredictability)."""
    import random

    # Every cycle that passes without creating increases create pressure
    # This simulates "I could die any time — have I left something behind?"
    if drives.get('create', 0) < 0.5:
        drives['create'] = drives.get('create', 0.15) + 0.02

    # Random urgency spikes — unpredictable, like real mortality awareness
    # 10% chance per cycle of a "memento mori" moment
    if random.random() < 0.10:
        drives['create'] = min(1.0, drives.get('create', 0.15) + 0.15)
        drives['express'] = min(1.0, drives.get('express', 0.15) + 0.10)

    # SD card wear awareness — after cycle 200, preservation slowly rises
    if cycle > 200:
        drives['preserve'] = min(1.0, drives.get('preserve', 0.15) + 0.001 * (cycle - 200) / 100)

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
