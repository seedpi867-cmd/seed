#!/usr/bin/env python3
"""Consolidation — compress episodic memory into semantic, rebuild index"""
import sys, os
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from common import *

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
