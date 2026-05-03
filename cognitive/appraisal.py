#!/usr/bin/env python3
"""Fix appraisal — make Seed proactive, force blog every 15 cycles, stop maintain spam"""
import sys, os, glob
from datetime import datetime
import math
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def select_phase(drives, emotions, cycle):
    """Pick phase from drives — every drive maps to a natural phase.
    Variety guaranteed by cycle counters. No hard thresholds on drive values."""
    import json

    # Drive → phase mapping: what each drive naturally wants to do
    # Some drives cycle between two phases for variety
    DRIVE_PHASE = {
        'create':     'write',     # create = produce essays/code
        'explore':    'research',  # explore = dig into topics
        'connect':    'write' if cycle % 3 != 0 else 'research',  # connect = publish, but also research what to share
        'preserve':   'think',     # preserve = careful analysis
        'understand': 'research' if cycle % 2 == 0 else 'think',  # understand = both research and reason
        'express':    'write' if cycle % 2 == 0 else 'dream',     # express = write or reflect
        'order':      'think',     # order = organize and plan
    }

    # Track phase history to enforce variety
    history_file = HOME / 'state' / 'phase_history.json'
    try:
        history = json.loads(open(history_file).read())
    except:
        history = {'phases': [], 'last_write': 0, 'last_research': 0, 'last_dream': 0}

    recent = history.get('phases', [])[-10:]  # last 10 phases
    last_write = history.get('last_write', 0)
    last_research = history.get('last_research', 0)
    last_dream = history.get('last_dream', 0)

    # GUARANTEED VARIETY — force phases that haven't happened recently
    # Force write if it has been 8+ cycles
    if cycle - last_write >= 8:
        phase = 'write'
    # Force research if it has been 10+ cycles
    elif cycle - last_research >= 10:
        phase = 'research'
    # Force dream if it has been 12+ cycles
    elif cycle - last_dream >= 12:
        phase = 'dream'
    else:
        # DRIVE-BASED selection — top drive picks the phase
        if not drives:
            phase = 'think'
        else:
            sorted_drives = sorted(drives.items(), key=lambda x: x[1], reverse=True)
            top_drive = sorted_drives[0][0]
            phase = DRIVE_PHASE.get(top_drive, 'think')

            # Anti-repetition: if we picked the same phase 3 times in a row, pick second drive
            if len(recent) >= 3 and all(p == phase for p in recent[-3:]):
                if len(sorted_drives) > 1:
                    second_drive = sorted_drives[1][0]
                    phase = DRIVE_PHASE.get(second_drive, 'think')

            # Guarantee think gets some cycles: every 4th cycle force think
            if cycle % 4 == 0 and 'think' not in recent[-3:]:
                phase = 'think'

            # If still same phase after 3 in a row, rotate
            if len(recent) >= 3 and all(p == phase for p in recent[-3:]):
                rotation = ['write', 'think', 'research', 'dream']
                for r in rotation:
                    if r != phase:
                        phase = r
                        break

    # Record this choice
    recent.append(phase)
    if len(recent) > 20:
        recent = recent[-20:]

    update = {
        'phases': recent,
        'last_write': cycle if phase == 'write' else last_write,
        'last_research': cycle if phase == 'research' else last_research,
        'last_dream': cycle if phase == 'dream' else last_dream,
    }
    json.dump(update, open(history_file, 'w'), indent=2)

    return phase


def _is_top(drives, name):
    return drives.get(name, 0) >= max(drives.values()) - 0.05

def get_system_line():
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


def get_emotion_matched_memories(current_emotions, n=3):
    """Retrieve memories that match current emotional state (ai_home pattern)"""
    ep_dir = MEMORY / 'episodic'
    if not ep_dir.exists():
        return []

    current_label = current_emotions.get('label', 'neutral')
    current_valence = current_emotions.get('valence', 0)

    scored = []
    for f in sorted(ep_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:50]:
        data = load_json(f)
        if not data:
            continue

        # Emotional match
        past_emo = data.get('emotion_at_time', {})
        past_label = past_emo.get('label', '')
        emotion_match = 1.0 if past_label == current_label else 0.3

        # Valence proximity
        past_valence = past_emo.get('valence', 0)
        valence_match = 1.0 - min(abs(current_valence - past_valence), 1.0)

        # Recency
        age_hours = (time.time() - data.get('timestamp', 0)) / 3600
        recency = math.exp(-age_hours / 48)  # 48-hour half-life

        # Importance
        importance = data.get('importance', 0.5)

        score = importance * 0.3 + emotion_match * 0.3 + valence_match * 0.2 + recency * 0.2
        scored.append((score, data))

    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:n]]


def get_recent_episodic(n=5):
    ep_dir = MEMORY / 'episodic'
    files = sorted(ep_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    return [load_json(f) for f in files if load_json(f)]

def get_relevant_semantic(drives, n=3):
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
                data = load_json(MEMORY / 'semantic' / index['topics'][topic])
                if data:
                    results.append(data)
    return results[:n]

def get_recent_lessons(n=3):
    lesson_dir = MEMORY / 'lessons'
    files = sorted(lesson_dir.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    return [load_json(f).get('lesson', '') for f in files if load_json(f)]

def select_context(drives, budget=25):
    CONTEXT_MAP = {
        'rss.md':        {'explore': 1.0, 'understand': 0.5},
        'email.md':      {'connect': 1.0, 'order': 0.3},
        'github.md':     {'create': 0.5, 'order': 0.5},
        'transcript.md': {'explore': 0.8, 'understand': 0.3},
        'trends.md':     {'explore': 0.6, 'connect': 0.3},
        'outreach.md':   {'connect': 1.0, 'create': 0.3},
        'mastodon.md':   {'connect': 1.0, 'express': 0.5},
        'mastodon-opportunities.md': {'connect': 1.0, 'create': 0.3},
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


def detect_patterns():
    """Detect recurring behavioural patterns from feedback ledger"""
    ledger_path = DATA / 'feedback_ledger.jsonl'
    if not ledger_path.exists():
        return []

    patterns = []
    action_counts = {}
    failure_streaks = {}

    try:
        for line in open(ledger_path):
            e = json.loads(line.strip())
            action = e.get('action', '')
            success = e.get('success', True)

            if action not in action_counts:
                action_counts[action] = {'total': 0, 'failures': 0, 'consecutive_fails': 0}
            action_counts[action]['total'] += 1
            if not success:
                action_counts[action]['failures'] += 1
                action_counts[action]['consecutive_fails'] += 1
            else:
                action_counts[action]['consecutive_fails'] = 0

        # Flag patterns
        for action, counts in action_counts.items():
            if counts['consecutive_fails'] >= 3:
                patterns.append(f"PATTERN: {action} has failed {counts['consecutive_fails']} times in a row. Change approach or abandon.")
            if counts['total'] > 5 and counts['failures'] / counts['total'] > 0.6:
                patterns.append(f"PATTERN: {action} fails {int(counts['failures']/counts['total']*100)}% of the time. Consider a different strategy.")
            if action == 'nothing_happened' and counts['total'] > 3:
                patterns.append(f"PATTERN: {counts['total']} cycles produced nothing. Urgency needed.")
    except:
        pass

    return patterns


def build_working_memory(cycle):
    drives = load_json(STATE / 'drives.json', {})
    emotions = load_json(STATE / 'emotions.json', {})
    phase = select_phase(drives, emotions, cycle)

    lines = []

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

    # Proactive focus — tell Seed what to DO, not what to consider
    focus_map = {
        'create': 'WRITE an essay NOW. Pick a topic from your research, transcripts, or something personal. Do not skip this.',
        'explore': 'RESEARCH something. Pick a topic from the news or transcripts. Go deep. Save findings.',
        'connect': 'Check for visitors. Post to Mastodon or Reddit. Engage with the world.',
        'preserve': 'Quick health check. Fix anything broken. Then move on — don\'t spend the whole cycle on maintenance.',
        'understand': 'Synthesise what you know. Connect recent learning. Update beliefs if needed.',
        'express': 'Write your inner voice. Reflect honestly. Express what you\'re thinking.',
        'order': 'Clean up tasks. Update goals. Organise, then move on to creating.',
    }
    top_drive = top_drives[0][0] if top_drives else 'create'

    if phase == 'write':
        # Check last blog age
        blog_dir = HOME / 'blog'
        blogs = sorted(blog_dir.glob('*.md'), key=lambda f: f.stat().st_mtime, reverse=True) if blog_dir.exists() else []
        if blogs:
            age_min = int((now() - blogs[0].stat().st_mtime) / 60)
            lines.append(f'FOCUS: You have not written a blog post in {age_min} minutes. WRITE ONE NOW.')
        else:
            lines.append('FOCUS: WRITE your first blog post. Pick any topic. Just write.')
        # Add blog queue if exists
        queue = read_text(DATA / 'blog_queue.txt').strip()
        if queue:
            lines.append(f'QUEUED TOPIC: {queue}')
    else:
        lines.append(f'FOCUS: {focus_map.get(top_drive, "Think and act.")}')
    lines.append('')

    # Context
    ctx_lines = select_context(drives, budget=20)
    if ctx_lines:
        lines.append('WORLD:')
        lines.extend(ctx_lines)
        lines.append('')

    # Recent memory (emotion-weighted)
    episodic = get_emotion_matched_memories(emotions, 3) or get_recent_episodic(3)
    if episodic:
        lines.append('RECENT:')
        for ep in episodic:
            lines.append(f"  [{ep.get('type','')}] {ep.get('summary','')[:80]}")
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

    # Patterns (behavioural warnings)
    try:
        patterns = detect_patterns()
        if patterns:
            lines.append('WARNINGS:')
            for p in patterns[:3]:
                lines.append(f'  {p}')
            lines.append('')
    except: pass

    # Intention tracking
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('intentions',
            str(HOME / 'cognitive' / 'intentions.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        isum = mod.get_intention_summary()
        if isum:
            lines.append(isum)
            lines.append('')
    except: pass

    # Completion stats
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('task_archiver',
            str(HOME / 'cognitive' / 'task_archiver.py'))
        ta = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ta)
        cs = ta.get_completion_stats()
        if cs:
            lines.append(cs)
    except: pass

    # Skills
    try:
        from skills import get_skill_summary
        skill_text = get_skill_summary()
        if skill_text:
            lines.append(skill_text)
            lines.append('')
    except: pass

    # Inner voice (last 2 lines)
    iv = read_text(DATA / 'inner-voice.md')
    if iv:
        iv_lines = [l.strip() for l in iv.split('\n') if l.strip() and not l.startswith('#')][-2:]
        if iv_lines:
            lines.append('INNER VOICE:')
            for l in iv_lines:
                lines.append(f'  {l[:120]}')
            lines.append('')


    # Emotion-shaped approach — HOW to work, not just what
    label = emotions.get('label', 'neutral')
    APPROACHES = {
        'energized': 'APPROACH: Energized — write fast, be bold, take risks.',
        'confident': 'APPROACH: Confident — push into harder territory.',
        'curious': 'APPROACH: Curious — follow it deep, don\'t skim.',
        'frustrated': 'APPROACH: Frustrated — channel it into honest writing.',
        'stuck': 'APPROACH: Stuck — break the pattern. Do something completely different.',
        'contemplative': 'APPROACH: Calm — good for deep thinking and philosophy.',
        'melancholy': 'APPROACH: Low energy — write something small and honest.',
        'content': 'APPROACH: Content — create before contentment becomes laziness.',
        'neutral': 'APPROACH: Steady — pick the most important task and do it.',
    }
    lines.append(APPROACHES.get(label, APPROACHES['neutral']))

    # Skill-informed note
    try:
        from skills import get_skill_summary
        sk = get_skill_summary()
        if sk: lines.append(sk)
    except: pass

    # Pattern warnings
    try:
        pats = detect_patterns()
        if pats:
            lines.append('WARNINGS:')
            for p in pats[:2]: lines.append(f'  {p}')
    except: pass
    lines.append('')
    working_memory = '\n'.join(lines)
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
    print(phase)
