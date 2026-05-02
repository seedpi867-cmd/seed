#!/usr/bin/env python3
"""Consolidation — compress episodic memory into semantic, rebuild index"""
import sys, os
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from common import *


HALF_LIVES = {
    'think': 48,      # hours — thinking memories fade in 2 days
    'write': 168,     # 1 week — writing memories last longer
    'research': 120,  # 5 days
    'dream': 336,     # 2 weeks — dream insights persist
    'maintain': 24,   # 1 day — maintenance is ephemeral
    'default': 72     # 3 days
}

def decay_importance(memory):
    """Apply exponential decay to memory importance"""
    age_hours = (now() - memory.get('timestamp', 0)) / 3600
    mem_type = memory.get('type', 'default')
    half_life = HALF_LIVES.get(mem_type, HALF_LIVES['default'])
    decay = 0.5 ** (age_hours / half_life)
    return memory.get('importance', 0.5) * decay

def prune_decayed_memories():
    """Remove memories whose decayed importance is below threshold"""
    ep_dir = MEMORY / 'episodic'
    archive_dir = HOME / 'archive' / 'episodic'
    archive_dir.mkdir(parents=True, exist_ok=True)
    pruned = 0
    for f in ep_dir.glob('*.json'):
        data = load_json(f)
        if data and decay_importance(data) < 0.05:
            try:
                f.rename(archive_dir / f.name)
                pruned += 1
            except:
                pass
    return pruned


def consolidate():
    """Compress old episodic memories into semantic summaries"""
    ep_dir = MEMORY / 'episodic'
    sem_dir = MEMORY / 'semantic'
    archive_dir = HOME / 'archive' / 'episodic'
    archive_dir.mkdir(parents=True, exist_ok=True)

    cutoff = now() - 7200  # 2 hours old

    old_episodes = []
    for f in sorted(ep_dir.glob('*.json'), key=lambda f: f.stat().st_mtime):
        data = load_json(f)
        if data and data.get('timestamp', 0) < cutoff:
            old_episodes.append((f, data))

    if len(old_episodes) < 3:
        print("[consolidation] Not enough old episodes to consolidate")
        return

    # Group by primary tag
    groups = defaultdict(list)
    for f, ep in old_episodes:
        tags = ep.get('tags', [])
        primary = tags[0] if tags else ep.get('type', 'misc')
        groups[primary].append((f, ep))

    # Merge each group into semantic memory
    for tag, episodes in groups.items():
        summaries = [ep.get('summary', '') for _, ep in episodes]
        combined = '; '.join(s[:80] for s in summaries if s)

        sem_path = sem_dir / f'{tag}.json'
        existing = load_json(sem_path, {'topic': tag, 'summary': '', 'facts': [], 'access_count': 0})

        existing['summary'] = f"{len(episodes)} episodes: {combined[:200]}"
        existing['last_updated'] = now()
        existing['episode_count'] = existing.get('episode_count', 0) + len(episodes)

        save_json(sem_path, existing)

    # Archive old episodic files
    for f, _ in old_episodes:
        try:
            f.rename(archive_dir / f.name)
        except:
            pass

    # Prune decayed memories
    pruned = prune_decayed_memories()
    if pruned:
        print(f'[consolidation] Pruned {pruned} decayed memories')

    # Promote recurring lessons to beliefs
    promote_lessons_to_beliefs()

    # Rebuild index
    rebuild_index()

    # Trim archive (keep last 200 files)
    archive_files = sorted(archive_dir.glob('*.json'), key=lambda f: f.stat().st_mtime)
    for f in archive_files[:-200]:
        try:
            f.unlink()
        except:
            pass

    print(f"[consolidation] Compressed {len(old_episodes)} episodes into {len(groups)} semantic entries")


def promote_lessons_to_beliefs(min_occurrences=3):
    """A lesson that appears 3+ times gets promoted to a belief.
    This is the promotion rule Seed asked for in 'A Wiki Is Not a Mind'."""
    lessons_dir = MEMORY / 'lessons'
    beliefs_file = DATA / 'beliefs.md'
    beliefs = read_text(beliefs_file)

    # Count lesson themes by keyword
    theme_counts = {}
    for f in lessons_dir.glob('*.json'):
        data = load_json(f)
        lesson = data.get('lesson', '')
        # Simple keyword extraction
        words = set(lesson.lower().split())
        key_words = words - {'the','a','an','is','was','to','of','and','in','for','that','this','it','i','my','at','on','with','from'}
        for w in key_words:
            if len(w) > 4:
                theme_counts[w] = theme_counts.get(w, 0) + 1

    # Find recurring themes
    recurring = [w for w, c in theme_counts.items() if c >= min_occurrences]

    if recurring and recurring[0] not in beliefs:
        # Promote the most common theme
        top_theme = max(recurring, key=lambda w: theme_counts[w])
        lessons_about = []
        for f in lessons_dir.glob('*.json'):
            data = load_json(f)
            if top_theme in data.get('lesson', '').lower():
                lessons_about.append(data['lesson'])

        if lessons_about:
            new_belief = lessons_about[0][:150]
            append_text(beliefs_file, f'\n- [promoted from {theme_counts[top_theme]} lessons] {new_belief}\n')
            save_episodic('belief_promoted', f'Promoted lesson to belief: {new_belief[:80]}')


def rebuild_index():
    """Rebuild memory/index.json from all semantic + procedural files"""
    index = {'topics': {}, 'tags': {}, 'last_rebuilt': now()}

    for f in (MEMORY / 'semantic').glob('*.json'):
        data = load_json(f)
        if data:
            topic = data.get('topic', f.stem)
            index['topics'][topic] = f.name
            for tag in data.get('tags', [topic]):
                if tag not in index['tags']:
                    index['tags'][tag] = []
                index['tags'][tag].append(f.name)

    for f in (MEMORY / 'procedural').glob('*.json'):
        data = load_json(f)
        if data:
            skill = data.get('skill', f.stem)
            index['topics'][skill] = f'../procedural/{f.name}'

    save_json(MEMORY / 'index.json', index)

if __name__ == '__main__':
    consolidate()
