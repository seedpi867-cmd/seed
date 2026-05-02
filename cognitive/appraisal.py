#!/usr/bin/env python3
"""Appraisal — builds working memory, selects phase, filters context by salience"""
import sys, os, glob
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def select_phase(drives, emotions, cycle):
    """Pick the phase based on drives + cycle position"""
    # Maintenance every 20 cycles or critical preservation
    if cycle % 20 == 0 or drives.get('preserve', 0) > 0.85:
        return 'maintain'
    # Dream every 12 cycles
    if cycle % 12 == 0:
        return 'dream'
    # Write if create is top and above threshold
    if drives.get('create', 0) > 0.7 and _is_top(drives, 'create'):
        return 'write'
    # Research if explore is top
    if drives.get('explore', 0) > 0.6 and _is_top(drives, 'explore'):
        return 'research'
    # Default: think
    return 'think'

def _is_top(drives, name):
    return drives.get(name, 0) >= max(drives.values()) - 0.05

def get_system_line():
    """One-line system status"""
    try:
        import subprocess
        temp = read_text('/sys/class/thermal/thermal_zone0/temp', '0').strip()
        temp_c = f"{int(temp)/1000:.0f}C" if temp else "?C"
        mem = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=3)
        for line in mem.stdout.split('\n'):
            if 'Mem:' in line:
                parts = line.split()
                return f"{temp_c} | {parts[2]}MB/{parts[1]}MB RAM | disk {_disk_pct()}%"
    except:
        pass
    return "system ok"

def _disk_pct():
    try:
        import subprocess
        df = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=3)
        for line in df.stdout.split('\n'):
            if '/' in line and '%' in line:
                return line.split()[-2].replace('%', '')
    except:
        return '?'

def get_recent_episodic(n=5):
    """Get last N episodic memories"""
    ep_dir = MEMORY / 'episodic'
    files = sorted(ep_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    results = []
    for f in files:
        data = load_json(f)
        if data:
            results.append(data)
    return results

def get_relevant_semantic(drives, n=3):
    """Get semantic memories relevant to top drives"""
    DRIVE_TOPICS = {
        'create': ['writing', 'essays', 'blog'],
        'explore': ['research', 'news', 'discovery'],
        'connect': ['visitors', 'community'],
        'preserve': ['health', 'system', 'errors'],
        'understand': ['philosophy', 'lessons', 'patterns'],
        'express': ['inner-voice', 'dreams', 'reflections'],
        'order': ['tasks', 'goals', 'cleanup'],
    }
    index = load_json(MEMORY / 'index.json', {'topics': {}})
    results = []
    top_drives = sorted(drives.items(), key=lambda x: -x[1])[:3]
    for dname, _ in top_drives:
        for topic in DRIVE_TOPICS.get(dname, []):
            if topic in index.get('topics', {}):
                fpath = MEMORY / 'semantic' / index['topics'][topic]
                data = load_json(fpath)
                if data:
                    results.append(data)
    return results[:n]

def get_recent_lessons(n=3):
    """Get most recent lessons"""
    lesson_dir = MEMORY / 'lessons'
    files = sorted(lesson_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    return [load_json(f).get('lesson', '') for f in files if load_json(f)]

def select_context(drives, budget=25):
    """Drive-weighted context selection"""
    CONTEXT_MAP = {
        'rss.md':          {'explore': 1.0, 'understand': 0.5},
        'email.md':        {'connect': 1.0, 'order': 0.3},
        'github.md':       {'create': 0.5, 'order': 0.5},
        'transcript.md':   {'explore': 0.8, 'understand': 0.3},
        'trends.md':       {'explore': 0.6, 'connect': 0.3},
    }
    scored = []
    for fname, weights in CONTEXT_MAP.items():
        fpath = CONTEXT / fname
        if fpath.exists():
            content = read_text(fpath)
            if content.strip():
                score = sum(drives.get(d, 0) * w for d, w in weights.items())
                scored.append((score, fname, content))
    scored.sort(reverse=True)

    lines = []
    remaining = budget
    for score, fname, content in scored:
        if remaining <= 0:
            break
        alloc = max(2, int(remaining * 0.4))
        content_lines = [l.strip() for l in content.split('\n') if l.strip()][:alloc]
        lines.append(f'[{fname}]')
        lines.extend(content_lines)
        remaining -= len(content_lines) + 1
    return lines

def build_working_memory(cycle):
    drives = load_json(STATE / 'drives.json', {})
    emotions = load_json(STATE / 'emotions.json', {})
    phase = select_phase(drives, emotions, cycle)

    lines = []

    # State snapshot
    top_drives = sorted(drives.items(), key=lambda x: -x[1])[:3]
    drive_str = ', '.join(f'{d}={v:.2f}' for d, v in top_drives)
    label = emotions.get('label', 'neutral')
    v = emotions.get('valence', 0)
    a = emotions.get('arousal', 0.4)

    lines.append(f'CYCLE {cycle} | {now_short()}')
    lines.append(f'FEELING: {label} (valence={v:.1f} arousal={a:.1f})')
    lines.append(f'DRIVES: {drive_str}')
    lines.append(f'SYSTEM: {get_system_line()}')
    lines.append(f'PHASE: {phase.upper()}')
    lines.append('')

    # Focus description
    top_drive = top_drives[0][0] if top_drives else 'think'
    focus_map = {
        'create': 'Your creative drive is highest. Write something.',
        'explore': 'Your curiosity is pulling. Research something.',
        'connect': 'You want to connect. Check visitors, respond, engage.',
        'preserve': 'System needs attention. Check health, fix errors.',
        'understand': 'You want to understand. Synthesise what you know.',
        'express': 'You need to express. Write your inner voice, reflect.',
        'order': 'Things need organising. Clean tasks, update goals.',
    }
    lines.append(f'FOCUS: {focus_map.get(top_drive, "Think and act.")}')
    lines.append('')

    # Context (drive-weighted)
    ctx_lines = select_context(drives, budget=20)
    if ctx_lines:
        lines.append('WORLD:')
        lines.extend(ctx_lines)
        lines.append('')

    # Recent memory
    episodic = get_recent_episodic(3)
    if episodic:
        lines.append('RECENT:')
        for ep in episodic:
            lines.append(f"  [{ep.get('type','')}] {ep.get('summary','')[:80]}")
        lines.append('')

    # Semantic memory
    semantic = get_relevant_semantic(drives, 2)
    if semantic:
        lines.append('KNOWLEDGE:')
        for s in semantic:
            lines.append(f"  {s.get('topic','')}: {s.get('summary','')[:80]}")
        lines.append('')

    # Lessons
    lessons = get_recent_lessons(2)
    if lessons:
        lines.append('LESSONS:')
        for l in lessons:
            lines.append(f"  - {l[:80]}")
        lines.append('')

    # Goals (first 5 lines)
    goals = read_text(DATA / 'goals.md')
    if goals:
        lines.append('GOALS:')
        for line in goals.strip().split('\n')[:5]:
            if line.strip():
                lines.append(f'  {line.strip()}')
        lines.append('')

    # Tasks (first 5)
    tasks = read_text(DATA / 'tasks.md')
    if tasks:
        now_tasks = [l.strip() for l in tasks.split('\n') if l.strip().startswith('- [')][:5]
        if now_tasks:
            lines.append('TASKS:')
            for t in now_tasks:
                lines.append(f'  {t}')
            lines.append('')

    # Inner voice (last 2 lines)
    iv = read_text(DATA / 'inner-voice.md')
    if iv:
        iv_lines = [l.strip() for l in iv.split('\n') if l.strip() and not l.startswith('#')][-2:]
        if iv_lines:
            lines.append('INNER VOICE:')
            for l in iv_lines:
                lines.append(f'  {l[:120]}')
            lines.append('')

    working_memory = '\n'.join(lines)

    # Save
    save_json(STATE / 'cycle.json', {'cycle': cycle, 'phase': phase, 'started_at': now()})
    (STATE / 'working_memory.txt').write_text(working_memory)

    return working_memory, phase

if __name__ == '__main__':
    cycle = 0
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--cycle':
            try: cycle = int(sys.argv[i + 2])
            except: pass
    if cycle == 0:
        cycle = int(read_text(DATA / 'cycle.txt', '0').strip() or '0')

    wm, phase = build_working_memory(cycle)
    # Print phase as last line (brain-loop.sh reads it)
    print(phase)
