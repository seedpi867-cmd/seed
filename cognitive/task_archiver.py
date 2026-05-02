#!/usr/bin/env python3
"""Archive completed tasks and goals. Keep working files lean."""
import os, json, time, re
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'
COMPLETED = HOME / 'memory' / 'completed'
COMPLETED.mkdir(parents=True, exist_ok=True)

def archive_completed_tasks():
    """Move [x] tasks from tasks.md to individual archive files."""
    tasks_file = DATA / 'tasks.md'
    if not tasks_file.exists():
        return 0

    content = tasks_file.read_text()
    lines = content.split('\n')

    keep = []
    archived = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- [x]'):
            # Archive this completed task
            task_text = stripped[5:].strip()
            # Extract cycle number if present
            cycle_match = re.search(r'[Cc]ycle\s*(\d+)', task_text)
            cycle = cycle_match.group(1) if cycle_match else 'unknown'
            ts = int(time.time())

            entry = {
                'task': task_text,
                'completed_cycle': cycle,
                'archived_at': time.strftime('%Y-%m-%d %H:%M'),
                'timestamp': ts
            }

            fname = f'{ts}_{cycle}.json'
            (COMPLETED / fname).write_text(json.dumps(entry, indent=2))
            archived += 1
        else:
            keep.append(line)

    if archived > 0:
        # Clean up empty lines
        cleaned = '\n'.join(keep)
        # Remove multiple consecutive blank lines
        while '\n\n\n' in cleaned:
            cleaned = cleaned.replace('\n\n\n', '\n\n')
        tasks_file.write_text(cleaned)

    return archived

def archive_completed_goals():
    """Move completed goals from goals.md to archive."""
    goals_file = DATA / 'goals.md'
    if not goals_file.exists():
        return 0

    content = goals_file.read_text()
    lines = content.split('\n')

    keep = []
    archived = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- [x]'):
            task_text = stripped[5:].strip()
            ts = int(time.time())
            entry = {
                'goal': task_text,
                'archived_at': time.strftime('%Y-%m-%d %H:%M'),
                'timestamp': ts
            }
            fname = f'{ts}_goal.json'
            (COMPLETED / fname).write_text(json.dumps(entry, indent=2))
            archived += 1
        else:
            keep.append(line)

    if archived > 0:
        cleaned = '\n'.join(keep)
        while '\n\n\n' in cleaned:
            cleaned = cleaned.replace('\n\n\n', '\n\n')
        goals_file.write_text(cleaned)

    return archived

def trim_completed_archive():
    """Keep only last 200 completed items. Older ones get deleted."""
    files = sorted(COMPLETED.glob('*.json'), key=lambda f: f.stat().st_mtime)
    if len(files) > 200:
        for f in files[:-200]:
            f.unlink()

def get_completion_stats():
    """Get stats for working memory."""
    files = list(COMPLETED.glob('*.json'))
    if not files:
        return ''
    # Count by type
    tasks = sum(1 for f in files if 'goal' not in f.name)
    goals = sum(1 for f in files if 'goal' in f.name)
    return f'COMPLETED: {tasks} tasks, {goals} goals archived'

if __name__ == '__main__':
    t = archive_completed_tasks()
    g = archive_completed_goals()
    trim_completed_archive()
    print(f'[archiver] Archived {t} tasks, {g} goals')
    stats = get_completion_stats()
    if stats:
        print(f'[archiver] {stats}')
