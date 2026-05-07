#!/usr/bin/env python3
"""
Smart triggers — automatic responses to system conditions.
Runs every cycle BEFORE the LLM call. Zero tokens.
Only returns 'critical' if the LLM needs to intervene.
"""
import subprocess, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def check_all():
    """Run all triggers. Returns list of actions taken + whether situation is critical."""
    actions = []
    critical = False

    # ── RAM PRESSURE ──────────────────────────
    try:
        mem = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=3)
        for line in mem.stdout.split('\n'):
            if 'Mem:' in line:
                parts = line.split()
                free_mb = int(parts[3])
                total_mb = int(parts[1])
                pct_used = (total_mb - free_mb) / total_mb

                avail_mb = int(parts[6]) if len(parts) > 6 else free_mb
                if avail_mb < 30:
                    # CRITICAL — kill heavy processes
                    subprocess.run(['pkill', '-f', 'node.*codex'], timeout=5)
                    actions.append(f'CRITICAL: RAM {avail_mb}MB available — killed heavy processes')
                    critical = True
                elif avail_mb < 60:
                    # WARNING — run compaction
                    subprocess.run(['bash', os.path.expanduser('~/tools/self-maintain.sh')], timeout=30)
                    actions.append(f'WARNING: RAM {avail_mb}MB available — ran self-maintain')
                elif avail_mb < 100:
                    actions.append(f'LOW RAM: {avail_mb}MB available — monitoring')
    except:
        pass

    # ── DISK PRESSURE ─────────────────────────
    try:
        df = subprocess.run(['df', '--output=pcent', '/'], capture_output=True, text=True, timeout=3)
        for line in df.stdout.split('\n'):
            if '%' in line and 'Use' not in line:
                pct = int(line.strip().replace('%', ''))
                if pct > 95:
                    # CRITICAL — emergency cleanup
                    subprocess.run(['bash', '-c',
                        'rm -rf ~/tmp/* ~/archive/episodic/*.json 2>/dev/null; '
                        'ls -t ~/data/logs/cycle_*.log | tail -n +20 | xargs rm -f 2>/dev/null'
                    ], timeout=10)
                    actions.append(f'CRITICAL: Disk at {pct}% — emergency cleanup')
                    critical = True
                elif pct > 85:
                    subprocess.run(['bash', '-c',
                        'ls -t ~/data/logs/cycle_*.log | tail -n +50 | xargs rm -f 2>/dev/null'
                    ], timeout=10)
                    actions.append(f'WARNING: Disk at {pct}% — cleaned old logs')
    except:
        pass

    # ── TEMPERATURE ───────────────────────────
    try:
        temp = int(read_text('/sys/class/thermal/thermal_zone0/temp', '0').strip() or '0')
        temp_c = temp / 1000
        if temp_c > 75:
            # CRITICAL — throttling, sleep longer
            (DATA / 'sleep_seconds.txt').write_text('120')
            actions.append(f'CRITICAL: Temp {temp_c}C — forcing long sleep')
            critical = True
        elif temp_c > 65:
            (DATA / 'sleep_seconds.txt').write_text('120')
            actions.append(f'WARNING: Temp {temp_c}C — extending sleep')
    except:
        pass

    # ── LOG ROTATION ──────────────────────────
    try:
        log_dir = DATA / 'logs'
        logs = sorted(log_dir.glob('cycle_*.log'), key=lambda f: f.stat().st_mtime)
        if len(logs) > 100:
            for f in logs[:-80]:
                f.unlink()
            actions.append(f'Cleaned logs: kept 80, removed {len(logs)-80}')
    except:
        pass

    # ── MEMORY FILE SIZE ──────────────────────
    try:
        mem_file = DATA / 'memory.md'
        if mem_file.exists():
            lines = mem_file.read_text().split('\n')
            if len(lines) > 250:
                # Keep last 150 lines
                mem_file.write_text('\n'.join(lines[-150:]))
                actions.append(f'Compacted memory.md: {len(lines)} -> 150 lines')
    except:
        pass

    # ── TASK/GOAL ARCHIVING ────────────────
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('task_archiver',
            os.path.expanduser('~/cognitive/task_archiver.py'))
        ta = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ta)
        t = ta.archive_completed_tasks()
        g = ta.archive_completed_goals()
        ta.trim_completed_archive()
        if t or g:
            actions.append(f'Archived {t} tasks, {g} goals')
    except Exception as e:
        pass

    # ── INNER VOICE TRIM ──────────────────────
    trim_file(DATA / 'inner-voice.md', 80)

    # ── EPISODIC MEMORY TRIM ──────────────────
    try:
        ep_dir = MEMORY / 'episodic'
        eps = sorted(ep_dir.glob('*.json'), key=lambda f: f.stat().st_mtime)
        if len(eps) > 100:
            archive = HOME / 'archive' / 'episodic'
            archive.mkdir(parents=True, exist_ok=True)
            for f in eps[:-80]:
                try: f.rename(archive / f.name)
                except: f.unlink()
            actions.append(f'Archived {len(eps)-80} old episodic memories')
    except:
        pass

    return actions, critical

if __name__ == '__main__':
    actions, critical = check_all()
    for a in actions:
        print(f'[trigger] {a}')
    if critical:
        print('CRITICAL')
    else:
        print('OK')
