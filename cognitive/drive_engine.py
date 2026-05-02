#!/usr/bin/env python3
"""Drive engine — computes drive pressures from real data and events"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *

DRIVE_DEFS = {
    'create':     {'baseline': 0.3, 'rate': 0.008, 'decay': 0.05},
    'explore':    {'baseline': 0.4, 'rate': 0.010, 'decay': 0.04},
    'connect':    {'baseline': 0.2, 'rate': 0.005, 'decay': 0.03},
    'preserve':   {'baseline': 0.3, 'rate': 0.003, 'decay': 0.02},
    'understand': {'baseline': 0.3, 'rate': 0.007, 'decay': 0.04},
    'express':    {'baseline': 0.2, 'rate': 0.006, 'decay': 0.03},
    'order':      {'baseline': 0.3, 'rate': 0.004, 'decay': 0.03},
}

SATISFACTION_MAP = {
    'wrote_essay':        {'create': -0.30, 'express': -0.15},
    'published_blog':     {'create': -0.25, 'connect': -0.10},
    'completed_research': {'explore': -0.25, 'understand': -0.10},
    'learned_lesson':     {'understand': -0.20},
    'completed_task':     {'order': -0.15},
    'health_ok':          {'preserve': -0.10},
    'visitor_engaged':    {'connect': -0.20},
    'dream_completed':    {'express': -0.15, 'understand': -0.10},
    'inner_voice_written':{'express': -0.10},
    'git_committed':      {'order': -0.05},
    'error_occurred':     {'preserve': 0.10},
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

        drives[name] = clamp(p, 0.0, 1.0)

    # Apply satisfaction from events
    events = outcome.get('events', [])
    for event in events:
        action = event.get('action', '')
        deltas = SATISFACTION_MAP.get(action, {})
        for drive, delta in deltas.items():
            if drive in drives:
                drives[drive] = clamp(drives[drive] + delta, 0.0, 1.0)

    save_json(STATE / 'drives.json', drives)

    # Compute sleep duration from urgency
    mx = max(drives.values()) if drives else 0.5
    if mx > 0.8: sleep_s = 120
    elif mx > 0.6: sleep_s = 300
    elif mx > 0.4: sleep_s = 600
    else: sleep_s = 900
    (DATA / 'sleep_seconds.txt').write_text(str(sleep_s))

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
