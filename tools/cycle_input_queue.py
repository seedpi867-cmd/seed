#!/usr/bin/env python3
"""Cycle Input Queue — three separate rolling lists of 5.
Each cycle: add 1 to each list, remove oldest from each.
Seed reads all 15 (5 repos + 5 knowledge + 5 blogs) and picks one from each to collide.
Every 5 cycles: build pressure forces a build from what it picked."""

import json, os, random, time
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'
QUEUE_FILE = DATA / 'input-queue.json'
KNOWLEDGE = HOME / 'knowledge'
BLOGS = HOME / 'seed-web' / 'posts'
TRENDING = HOME / 'context' / 'trending-repos.md'

def load_queue():
    try:
        return json.loads(QUEUE_FILE.read_text())
    except:
        return {'repos': [], 'knowledge': [], 'blogs': [], 'cycle': 0, 'cycles_since_build': 0, 'build_pressure': False}

def save_queue(q):
    QUEUE_FILE.write_text(json.dumps(q, indent=2))

def random_repo():
    try:
        text = TRENDING.read_text()
        repos = [l.strip().lstrip('# ') for l in text.split('\n') if l.strip().startswith('### ')]
        if repos:
            return {'text': random.choice(repos), 'added': time.time()}
    except:
        pass
    return None

def random_knowledge():
    try:
        files = [f for f in KNOWLEDGE.rglob('*.md') if 'inbox' not in str(f) and 'starting-points' not in f.name]
        if files:
            f = random.choice(files)
            title = f.stem.replace('-', ' ')
            try:
                first = f.read_text()[:200].split('\n')[0].lstrip('# ').strip()
                if first and len(first) > 5:
                    title = first
            except:
                pass
            return {'text': title, 'path': str(f.relative_to(KNOWLEDGE)), 'added': time.time()}
    except:
        pass
    return None

def random_blog():
    try:
        files = list(BLOGS.glob('*.md'))
        if files:
            f = random.choice(files)
            title = f.stem.replace('-', ' ')
            try:
                text = f.read_text()[:300]
                if text.startswith('---'):
                    for line in text.split('\n'):
                        if line.strip().startswith('title:'):
                            title = line.split(':', 1)[1].strip().strip('"').strip("'")
                            break
                elif text.startswith('# '):
                    title = text.split('\n')[0].lstrip('# ')
            except:
                pass
            return {'text': title, 'slug': f.stem, 'added': time.time()}
    except:
        pass
    return None

def run():
    q = load_queue()
    cycle = int((DATA / 'cycle.txt').read_text().strip())

    # Add 1 new to each list
    repo = random_repo()
    know = random_knowledge()
    blog = random_blog()

    if repo:
        q['repos'].append(repo)
    if know:
        q['knowledge'].append(know)
    if blog:
        q['blogs'].append(blog)

    # Keep each list at 5 — remove oldest
    q['repos'] = q['repos'][-5:]
    q['knowledge'] = q['knowledge'][-5:]
    q['blogs'] = q['blogs'][-5:]

    q['cycle'] = cycle
    q['cycles_since_build'] = q.get('cycles_since_build', 0) + 1
    q['build_pressure'] = q['cycles_since_build'] >= 5

    save_queue(q)

    # Write context for prompt
    ctx = HOME / 'context' / 'input-queue.md'
    lines = [f"# Input Queue — Cycle {cycle}\n\n"]
    lines.append(f"Cycles since last build: {q['cycles_since_build']}\n\n")

    if q['build_pressure']:
        lines.append("**BUILD PRESSURE: 5 cycles without building. Pick one from each list below. Collide them. Build a tool. NOW.**\n\n")

    lines.append("## Repos (pick one)\n")
    for item in q['repos']:
        lines.append(f"- {item['text']}\n")

    lines.append("\n## Knowledge (pick one)\n")
    for item in q['knowledge']:
        lines.append(f"- {item['text']}\n")

    lines.append("\n## Blogs (pick one)\n")
    for item in q['blogs']:
        lines.append(f"- {item['text']}\n")

    lines.append(f"\nRead all three lists. Pick one from each. Find the collision. {'BUILD FROM IT NOW.' if q['build_pressure'] else 'Think about what you could build from the collision.'}\n")

    ctx.write_text(''.join(lines))
    print(f"[input-queue] repos={len(q['repos'])} knowledge={len(q['knowledge'])} blogs={len(q['blogs'])} pressure={'YES' if q['build_pressure'] else 'no'}")

if __name__ == '__main__':
    run()
