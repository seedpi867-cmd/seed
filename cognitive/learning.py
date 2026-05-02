#!/usr/bin/env python3
"""Learning — detects outcomes, updates drives, writes inner voice, logs episodic memory"""
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def detect_outcomes(log_path, cycle):
    """Parse cycle log to detect what the LLM actually did"""
    log = read_text(log_path)
    events = []

    patterns = [
        (r'blog/.*\.md', 'wrote_essay'),
        (r'deploy.*blog|blog.*deploy|Pushed to Vercel', 'published_blog'),
        (r'Research|Researching', 'completed_research'),
        (r'git commit|committed', 'git_committed'),
        (r'[Ee]rror|ERROR|[Ff]ailed|FATAL', 'error_occurred'),
        (r'[Dd]ream|reflecting on', 'dream_completed'),
        (r'inner.voice|inner-voice', 'inner_voice_written'),
        (r'health.*ok|health.*safe|health.*passed', 'health_ok'),
    ]

    for pattern, action in patterns:
        if re.search(pattern, log):
            events.append({'action': action, 'source': 'log'})

    # Check file modifications (last 10 minutes)
    cutoff = now() - 600
    for fpath in glob.glob(str(HOME / 'blog' / '*.md')):
        if os.path.getmtime(fpath) > cutoff:
            events.append({'action': 'wrote_essay', 'source': 'file', 'file': os.path.basename(fpath)})
    for fpath in [DATA / 'tasks.md']:
        if fpath.exists() and os.path.getmtime(fpath) > cutoff:
            events.append({'action': 'completed_task', 'source': 'file'})

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
                drives[drive] = clamp(drives[drive] + delta, 0.0, 1.0)

    save_json(STATE / 'drives.json', drives)
    save_json(STATE / 'last_outcome.json', {'events': events, 'timestamp': now()})
    return drives

def write_inner_voice(events, drives, emotions):
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
            error_lines = [l for l in log.split('\n') if 'error' in l.lower() or 'Error' in l][:3]
            if error_lines:
                lesson = f"Error in this cycle: {error_lines[0][:100]}"
                save_json(MEMORY / 'lessons' / f'{int(now())}_error.json', {
                    'lesson': lesson, 'type': 'error', 'timestamp': now()
                })

def run_learning(log_path, cycle, phase):
    drives = load_json(STATE / 'drives.json', {})
    emotions = load_json(STATE / 'emotions.json', {})

    # 1. Detect what happened
    events = detect_outcomes(log_path, cycle)

    # 2. Update drives from outcomes
    drives = update_from_outcomes(events)

    # 3. Write inner voice
    write_inner_voice(events, drives, emotions)

    # 4. Save episodic memory
    save_episodic_memory(events, drives, emotions, cycle, phase)

    # 5. Detect lessons
    detect_lessons(events, log_path)

    # 6. Update mood.json for backward compat with webserver/homepage
    _update_mood_compat(drives, emotions, cycle)

    return events

def _update_mood_compat(drives, emotions, cycle):
    """Update data/mood.json for backward compatibility with webserver"""
    mood = load_json(DATA / 'mood.json', {})
    mood['cycle'] = cycle
    mood['valence'] = emotions.get('valence', 0)
    mood['arousal'] = emotions.get('arousal', 0.4)
    mood['confidence'] = emotions.get('confidence', 0.5)
    mood['openness'] = emotions.get('openness', 0.5)
    mood['emotional_label'] = emotions.get('label', 'neutral')
    # Map drives to the old format for dashboard
    old_drives = mood.get('drives', {})
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
