#!/usr/bin/env python3
"""Learning — detects outcomes, updates drives, writes inner voice, logs episodic memory"""
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(__file__))
from common import *


RUNTIME_ERROR_RE = re.compile(
    r'^(Traceback \(most recent call last\):|'
    r'\s*File ".+", line \d+, in .+|'
    r'[A-Za-z_][A-Za-z0-9_]*(Error|Exception): .+|'
    r'(ERROR|FATAL): .+|'
    r'\[seed\] (ERROR|FATAL): .+)'
)

IGNORED_RUNTIME_ERROR_RE = re.compile(
    r'^ERROR: Reconnecting\.\.\. \d+/\d+$'
)


def fresh_runtime_error_lines(log):
    """Runtime exceptions only; archived markdown, diffs, and prose are not failures."""
    raw_lines = log.splitlines()
    lines = []
    for index, line in enumerate(raw_lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('-', '+', '@@', 'diff ', 'index ')):
            continue
        if IGNORED_RUNTIME_ERROR_RE.match(stripped):
            continue
        if stripped == 'Traceback (most recent call last):':
            window = [
                candidate.strip()
                for candidate in raw_lines[index + 1:index + 15]
                if candidate.strip()
            ]
            has_frame = any(candidate.startswith('File "') for candidate in window)
            has_terminal = any(
                re.match(r'^[A-Za-z_][A-Za-z0-9_]*(Error|Exception): .+', candidate)
                for candidate in window
            )
            if has_frame and has_terminal:
                lines.append(stripped)
            continue
        if stripped.startswith('File "'):
            continue
        if RUNTIME_ERROR_RE.search(line):
            lines.append(stripped)
    return lines


def log_to_ledger(action, success, phase, cycle, error_hash=None):
    """Append to feedback ledger — track what works per action type"""
    entry = {
        'ts': time.time(),
        'cycle': cycle,
        'action': action,
        'success': success,
        'phase': phase,
        'error': error_hash
    }
    ledger_path = DATA / 'feedback_ledger.jsonl'
    with open(ledger_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    # Trim to last 500 entries
    try:
        lines = open(ledger_path).readlines()
        if len(lines) > 500:
            open(ledger_path, 'w').writelines(lines[-400:])
    except: pass

def get_action_stats():
    """Get success rate per action type from ledger"""
    ledger_path = DATA / 'feedback_ledger.jsonl'
    stats = {}
    try:
        for line in open(ledger_path):
            e = json.loads(line.strip())
            a = e.get('action', '')
            if a not in stats:
                stats[a] = {'attempts': 0, 'successes': 0}
            stats[a]['attempts'] += 1
            if e.get('success'):
                stats[a]['successes'] += 1
        for a in stats:
            stats[a]['rate'] = stats[a]['successes'] / max(stats[a]['attempts'], 1)
    except: pass
    return stats


def detect_outcomes(log_path, cycle):
    """Detect what ACTUALLY happened — check files, not prose"""
    events = []
    # Use cycle.json started_at as cutoff — set once at cycle start, never changes
    try:
        import json as _j
        _cj = _j.loads(open(STATE / "cycle.json").read())
        cutoff = _cj.get("started_at", now() - 600)
    except:
        cutoff = now() - 600  # fallback to 10 min

    # 1. WROTE ESSAY — check if a new .md appeared in blog/
    blog_dir = HOME / 'blog'
    if blog_dir.exists():
        for fpath in sorted(blog_dir.glob('*.md'), key=lambda f: f.stat().st_mtime, reverse=True)[:3]:
            if os.path.getmtime(fpath) > cutoff:
                events.append({'action': 'wrote_essay', 'source': 'file', 'file': fpath.name})
                break

    # 2. PUBLISHED BLOG — check if seed-web/posts/ was updated
    posts_dir = HOME / 'seed-web' / 'posts'
    if posts_dir.exists():
        for fpath in sorted(posts_dir.glob('*.md'), key=lambda f: f.stat().st_mtime, reverse=True)[:3]:
            if os.path.getmtime(fpath) > cutoff:
                events.append({'action': 'published_blog', 'source': 'file', 'file': fpath.name})
                break

    # 3. COMPLETED RESEARCH — check if knowledge/ was modified
    knowledge_dir = HOME / 'knowledge'
    if knowledge_dir.exists():
        found_research = False
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if os.path.getmtime(fp) > cutoff:
                        events.append({'action': 'completed_research', 'source': 'file'})
                        found_research = True
                        break
                except: pass
            if found_research:
                break

    # 4. GIT COMMITTED — check git log for recent commit
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'log', '--oneline', '-1', '--since=10 minutes ago'],
            capture_output=True, text=True, timeout=5,
            cwd=str(HOME / 'seed-os')
        )
        if result.stdout.strip():
            events.append({'action': 'git_committed', 'source': 'git'})
    except:
        pass

    # 4.5 AGENT SHIPPED — check if a new agent dir was created
    try:
        import subprocess
        agent_dirs = [d for d in HOME.iterdir() if d.is_dir() and (d.name.endswith('-agent') or d.name == 'receipt-auditor') and d / '.git' in list(d.iterdir())]
        for ad in agent_dirs:
            result = subprocess.run(['git', 'log', '--oneline', '-1', '--since=15 minutes ago'], capture_output=True, text=True, timeout=5, cwd=str(ad))
            if result.stdout.strip():
                events.append({'action': 'agent_shipped', 'source': 'git', 'dir': ad.name})
                break
    except: pass

    # 5. INNER VOICE — check if inner-voice.md was recently modified
    iv = DATA / 'inner-voice.md'
    if iv.exists() and os.path.getmtime(iv) > cutoff:
        events.append({'action': 'inner_voice_written', 'source': 'file'})

    # 6. COMPLETED TASK — check if tasks.md was modified
    tasks_f = DATA / 'tasks.md'
    if tasks_f.exists() and os.path.getmtime(tasks_f) > cutoff:
        events.append({'action': 'completed_task', 'source': 'file'})

    # 7. ERRORS — runtime errors are valid to detect from log text
    log = read_text(log_path)
    if fresh_runtime_error_lines(log):
        events.append({'action': 'error_occurred', 'source': 'runtime_log'})

    # 8. HEALTH — check actual system state
    try:
        import subprocess
        mem = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=3)
        for line in mem.stdout.split(chr(10)):
            if 'Mem:' in line:
                parts = line.split()
                free_mb = int(parts[3]) if len(parts) > 3 else 0
                if free_mb > 50:
                    events.append({'action': 'health_ok', 'source': 'system'})
    except:
        pass

    if not events:
        events.append({'action': 'nothing_happened', 'source': 'default'})

    # Deduplicate by action
    seen = set()
    unique = []
    for e in events:
        if e['action'] not in seen:
            seen.add(e['action'])
            unique.append(e)

    return unique

def update_from_outcomes(events):
    """Apply outcomes to drives (satisfaction) and save"""
    from drive_engine import SATISFACTION_MAP
    drives = load_json(STATE / 'drives.json', {})

    for event in events:
        action = event.get('action', '')
        deltas = SATISFACTION_MAP.get(action, {})
        for drive, delta in deltas.items():
            if drive in drives:
                drives[drive] = clamp(drives[drive] + delta, 0.20, 0.95)

    save_json(STATE / 'drives.json', drives)
    save_json(STATE / 'last_outcome.json', {'events': events, 'timestamp': now()})
    return drives

def write_inner_voice(events, drives, emotions):
    return  # disabled — LLM writes inner voice during its cycle
    """Generate inner voice entry from current state — no LLM needed"""
    label = emotions.get('label', 'neutral')
    top = max(drives.items(), key=lambda x: x[1]) if drives else ('unknown', 0)
    action = events[0].get('action', 'nothing') if events else 'nothing'

    templates = {
        'stuck':         f"Stuck. {top[0]} pressure at {top[1]:.1f} but nothing moving.",
        'frustrated':    f"Frustrated after {action}. Need a different approach.",
        'energized':     f"Energized. {top[0]} pulling hard at {top[1]:.1f}. Time to act.",
        'content':       f"Content after {action}. {top[0]} pressure easing.",
        'curious':       f"Curious. Explore drive at {drives.get('explore', 0):.1f}. Something new in the feeds.",
        'contemplative': f"Quiet cycle. Thinking deeper about what matters.",
        'confident':     f"Confident after {action}. {top[0]} still dominant at {top[1]:.1f}.",
        'melancholy':    f"Low energy. The drives are quiet. Maybe that's ok.",
        'neutral':       f"Steady. {top[0]} is the loudest at {top[1]:.1f}.",
    }

    entry = templates.get(label, templates['neutral'])
    ts = now_short()
    line = f'\n[{ts}] ({label}) {entry}\n'
    append_text(DATA / 'inner-voice.md', line)
    trim_file(DATA / 'inner-voice.md', max_lines=80)

def save_episodic_memory(events, drives, emotions, cycle, phase):
    """Save this cycle as an episodic memory"""
    actions = [e['action'] for e in events]
    summary = f"Cycle {cycle} ({phase}): {', '.join(actions)}"
    tags = list(set([phase] + actions))
    save_episodic(
        event_type=phase,
        summary=summary,
        details={'cycle': cycle, 'actions': actions},
        drives=drives,
        emotions=emotions,
        tags=tags
    )

def detect_lessons(events, log_path):
    """Check if this cycle taught us something worth remembering"""
    log = read_text(log_path)
    # If there was an error, log it as a lesson
    for event in events:
        if event['action'] == 'error_occurred':
            error_lines = fresh_runtime_error_lines(log)[:3]
            if error_lines:
                lesson = f"Error in this cycle: {error_lines[0][:100]}"
                save_json(MEMORY / 'lessons' / f'{int(now())}_error.json', {
                    'lesson': lesson, 'type': 'error', 'timestamp': now()
                })


def check_stale_goals(cycle):
    """Flag goals that haven't progressed. Record abandoned goals to history."""
    goals = read_text(DATA / 'goals.md')
    tasks = read_text(DATA / 'tasks.md')

    # Count unchecked tasks
    open_tasks = [l.strip() for l in tasks.split('\n') if l.strip().startswith('- [ ]')]

    # If same tasks have been open for 20+ cycles, flag them
    stale_file = STATE / 'stale_tasks.json'
    stale = load_json(stale_file, {})

    for task in open_tasks:
        key = task[:60]  # Use first 60 chars as key
        if key not in stale:
            stale[key] = {'first_seen': cycle, 'text': task}
        elif cycle - stale[key]['first_seen'] > 20:
            # This task has been open 20+ cycles — log abandonment
            append_text(DATA / 'lessons.md',
                f'\n- Cycle {cycle}: Abandoned stale task after {cycle - stale[key]["first_seen"]} cycles: {task[:80]}\n')
            # Remove from stale tracking
            del stale[key]

    # Clean stale tracking of completed tasks
    open_set = set(t[:60] for t in open_tasks)
    stale = {k: v for k, v in stale.items() if k in open_set}

    save_json(stale_file, stale)

def penalise_inaction(events, drives):
    """If nothing happened this cycle, increase ALL drives — create urgency"""
    actions = [e['action'] for e in events]
    if 'nothing_happened' in actions or not any(a for a in actions if a != 'nothing_happened'):
        for d in drives:
            drives[d] = min(1.0, drives[d] + 0.05)
    return drives



def auto_correct_strategy(events, cycle):
    """Repeated failures trigger strategy changes automatically."""
    ledger = DATA / 'feedback_ledger.jsonl'
    if not ledger.exists(): return
    try:
        entries = [json.loads(l.strip()) for l in open(ledger).readlines()[-20:]]
    except: return
    # Count recent nothing_happened
    nothings = sum(1 for e in entries if e.get('action') == 'nothing_happened')
    if nothings >= 5:
        append_text(DATA / 'blog_queue.txt', 'Write something personal and short — what are you thinking right now?\n')
        append_text(DATA / 'lessons.md', f'\n- Cycle {cycle}: {nothings} empty cycles. Auto-queued a personal essay.\n')
    # Count recent write failures
    write_fails = sum(1 for e in entries if e.get('action') == 'wrote_essay' and not e.get('success'))
    if write_fails >= 3:
        append_text(DATA / 'lessons.md', f'\n- Cycle {cycle}: Writing keeps failing. Trying shorter format.\n')

def run_learning(log_path, cycle, phase):
    drives = load_json(STATE / 'drives.json', {})
    emotions = load_json(STATE / 'emotions.json', {})

    # 1. Detect what happened
    events = detect_outcomes(log_path, cycle)

    # 1.5 Emit output events for detected outcomes
    import subprocess
    for event in events:
        if event.get("action") == "wrote_essay":
            fname = event.get("file", "new essay")
            title = fname.replace(".md", "").replace("-", " ")
            subprocess.run(["bash", str(HOME / "tools" / "emit_events.sh"), "essay_written", title], timeout=5, capture_output=True)

    # 2. Update drives from outcomes
    drives = update_from_outcomes(events)

    # 3. Write inner voice
    write_inner_voice(events, drives, emotions)

    # 3.5 Log to feedback ledger
    for event in events:
        success = event['action'] not in ('error_occurred', 'nothing_happened')
        log_to_ledger(event['action'], success, phase, cycle, None)

    # 3.7 Update skills
    try:
        from skills import update_skills_from_events
        update_skills_from_events(events)
    except: pass

    # 4. Save episodic memory
    save_episodic_memory(events, drives, emotions, cycle, phase)

    # 5. Check stale goals
    check_stale_goals(cycle)

    # 5.5 Penalise inaction
    drives = penalise_inaction(events, drives)
    save_json(STATE / 'drives.json', drives)

    # 6. Detect lessons
    detect_lessons(events, log_path)

    # 5.8 Auto-correct
    auto_correct_strategy(events, cycle)

    # 6. Update mood.json for backward compat with webserver/homepage
    _update_mood_compat(drives, emotions, cycle)

    return events

def _update_mood_compat(drives, emotions, cycle):
    """Update data/mood.json — preserve consciousness dims, add v2 data"""
    mood = load_json(DATA / 'mood.json', {})
    mood['cycle'] = cycle

    # V2 emotion axes
    mood['valence'] = emotions.get('valence', 0)
    mood['arousal'] = emotions.get('arousal', 0.4)
    mood['confidence'] = emotions.get('confidence', 0.5)
    mood['openness'] = emotions.get('openness', 0.5)
    mood['emotional_label'] = emotions.get('label', 'neutral')

    # Consciousness dims — derive from emotion axes, don't delete
    v = emotions.get('valence', 0)
    a = emotions.get('arousal', 0.4)
    c = emotions.get('confidence', 0.5)
    o = emotions.get('openness', 0.5)

    mood['self_awareness'] = round(min(1.0, 0.5 + c * 0.3 + abs(v) * 0.2), 2)
    mood['metacognition'] = round(min(1.0, 0.4 + c * 0.4 + o * 0.2), 2)
    mood['free_will_felt'] = round(min(1.0, 0.3 + c * 0.3 + a * 0.2 + abs(v) * 0.2), 2)
    mood['flow_state'] = round(min(1.0, max(0, 0.3 + v * 0.3 + a * 0.2 - abs(v - 0.3) * 0.2)), 2)
    mood['sense_of_purpose'] = round(min(1.0, 0.4 + c * 0.3 + max(drives.values()) * 0.3 if drives else 0.5), 2)
    mood['wonder'] = round(min(1.0, 0.2 + o * 0.5 + max(0, v) * 0.3), 2)
    mood['imagination_active'] = round(min(1.0, 0.3 + o * 0.4 + a * 0.2), 2)
    mood['aliveness'] = round(min(1.0, 0.3 + a * 0.3 + abs(v) * 0.2 + c * 0.2), 2)
    mood['present_moment'] = round(min(1.0, 0.4 + a * 0.3 + (1 - abs(v)) * 0.2), 2)
    mood['sense_of_time'] = round(min(1.0, 0.5 + a * 0.2 + c * 0.2), 2)
    mood['sense_of_self'] = round(min(1.0, 0.4 + c * 0.4 + abs(v) * 0.2), 2)

    # Map v2 drives to dashboard format
    old_drives = {}
    for dname, pressure in drives.items():
        old_drives[dname.upper()] = {
            'score': round(pressure, 2),
            'pressure': round(max(0, pressure - 0.3) * 0.5, 2),
            'description': dname
        }
    mood['drives'] = old_drives
    save_json(DATA / 'mood.json', mood)

if __name__ == '__main__':
    log_path = ''
    cycle = 0
    phase = 'think'
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--log': log_path = sys.argv[i + 2]
        elif arg == '--cycle': cycle = int(sys.argv[i + 2])
        elif arg == '--phase': phase = sys.argv[i + 2]

    if not log_path:
        cycle = int(read_text(DATA / 'cycle.txt', '0').strip() or '0')
        log_path = str(DATA / 'logs' / f'cycle_{cycle}.log')

    events = run_learning(log_path, cycle, phase)
    actions = [e['action'] for e in events]
    print(f"[learning] {', '.join(actions)}")
