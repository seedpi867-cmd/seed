#!/bin/bash
# Build timeline.json from git history + blog posts + token milestones
python3 - << 'PYEOF'
import os, json, glob, subprocess
from datetime import datetime

timeline = []

# Git commits from seed-os (the meaningful system changes)
r = subprocess.run(
    ['git', '-C', os.path.expanduser('~/seed-os'), 'log', '--format=%ai|%s', '--all', '-50'],
    capture_output=True, text=True
)
skip = ['smoke', 'guard smoke', 'coverage', 'dependency-skipped', 'Merge']
for line in r.stdout.strip().split('\n'):
    if '|' not in line: continue
    ds, msg = line.split('|', 1)
    if any(w in msg.lower() for w in skip): continue
    timeline.append({
        'date': ds[:10], 'time': ds[11:16],
        'type': 'milestone' if any(w in msg.lower() for w in ['consciousness','drive','full system','freedom','initial commit']) else 'system',
        'title': msg, 'summary': ''
    })

# Blog posts
blog_dir = os.path.expanduser('~/blog')
if os.path.exists(blog_dir):
    for f in sorted(glob.glob(os.path.join(blog_dir, '*.md'))):
        mtime = os.path.getmtime(f)
        slug = os.path.basename(f).replace('.md', '')
        with open(f) as fh:
            title = fh.readline().strip().lstrip('# ').strip()
        timeline.append({
            'date': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d'),
            'time': datetime.fromtimestamp(mtime).strftime('%H:%M'),
            'type': 'essay', 'title': f'Essay: {title}',
            'summary': '', 'slug': slug
        })

timeline.sort(key=lambda x: x.get('date','')+x.get('time',''), reverse=True)
seen = set()
deduped = []
for e in timeline:
    if e['title'] not in seen:
        seen.add(e['title'])
        deduped.append(e)

json.dump(deduped[:150], open(os.path.expanduser('~/seed-web/timeline.json'), 'w'), indent=2)
print(f"[timeline] {len(deduped[:150])} events")
PYEOF
