#!/usr/bin/env python3
"""Smart memory compaction — keeps what matters, drops what doesn't."""
import os, time, json, re
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'

def compact_memory():
    """Compact memory.md — keep recent + important, drop filler."""
    mem = DATA / 'memory.md'
    if not mem.exists():
        return
    lines = mem.read_text().split('\n')
    if len(lines) <= 150:
        return

    # Keep: last 100 lines (recent), any line with MILESTONE/bug/error/published
    important_words = ['milestone', 'published', 'deployed', 'error', 'bug', 'fix',
                       'wrote', 'posted', 'github',
                       'star', 'fork', 'follower', 'visitor']

    kept = []
    for line in lines[:-100]:
        lower = line.lower()
        if any(w in lower for w in important_words):
            kept.append(line)
    # Always keep last 100
    kept.extend(lines[-100:])

    mem.write_text('\n'.join(kept))
    print(f'[compact] memory: {len(lines)} -> {len(kept)} lines')

def compact_inner_voice():
    """Keep inner voice focused — recent + insightful."""
    iv = DATA / 'inner-voice.md'
    if not iv.exists():
        return
    lines = iv.read_text().split('\n')
    if len(lines) <= 50:
        return
    iv.write_text('\n'.join(lines[-40:]))
    print(f'[compact] inner voice: {len(lines)} -> 40 lines')

def compact_tasks():
    """Archive completed, remove stale."""
    tasks_file = DATA / 'tasks.md'
    if not tasks_file.exists():
        return
    content = tasks_file.read_text()
    lines = content.split('\n')
    kept = [l for l in lines if not l.strip().startswith('- [x]')]
    if len(kept) < len(lines):
        # Run the archiver
        os.system('python3 ' + str(HOME / 'cognitive' / 'task_archiver.py') + ' 2>/dev/null')
        print(f'[compact] tasks: archived {len(lines)-len(kept)} completed')

def compact_goals():
    """Move achieved milestones up, trim old handoff notes."""
    goals = DATA / 'goals.md'
    if not goals.exists():
        return
    content = goals.read_text()
    # Remove old cycle handoff notes (Cycle NNN order pass: ...)
    content = re.sub(r'- Cycle \d+ (?:order|think|write|research) (?:pass|handoff):.*\n?', '', content)
    while '\n\n\n' in content:
        content = content.replace('\n\n\n', '\n\n')
    goals.write_text(content)

def compact_event_log():
    """Keep event log under 300 lines."""
    log = DATA / 'event_log.jsonl'
    if log.exists():
        lines = log.read_text().split('\n')
        if len(lines) > 300:
            log.write_text('\n'.join(lines[-200:]))

def run_compaction():
    compact_memory()
    compact_inner_voice()
    compact_tasks()
    compact_goals()
    compact_event_log()

if __name__ == '__main__':
    run_compaction()
