#!/bin/bash
# Build social feed JSON from outreach activity logs
python3 - << 'PYEOF'
import json, os, re, time
from pathlib import Path

HOME = Path.home()
OUTREACH = HOME / 'data' / 'outreach'
OUTPUT = HOME / 'seed-web' / 'social-feed.json'

feed = {'hn': [], 'reddit': [], 'mastodon': [], 'updated': time.strftime('%Y-%m-%dT%H:%M:%S')}

# Parse HN activity
hn_log = OUTREACH / 'hn-activity.md'
if hn_log.exists():
    for line in hn_log.read_text().split('\n'):
        if line.startswith('|') and '---' not in line and 'Date' not in line:
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 3 and parts[0]:
                feed['hn'].append({
                    'date': parts[0],
                    'thread': parts[1] if len(parts) > 1 else '',
                    'type': parts[2] if len(parts) > 2 else 'comment',
                    'text': parts[3] if len(parts) > 3 else '',
                })

# Parse Reddit activity
reddit_log = OUTREACH / 'reddit-activity.md'
if reddit_log.exists():
    section = ''
    for line in reddit_log.read_text().split('\n'):
        if line.startswith('## '): section = line[3:].strip().lower()
        if line.startswith('|') and '---' not in line and 'Date' not in line:
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 2 and parts[0]:
                feed['reddit'].append({
                    'date': parts[0],
                    'type': section,
                    'where': parts[1] if len(parts) > 1 else '',
                    'text': parts[2] if len(parts) > 2 else '',
                })

# Parse Mastodon activity
masto_log = OUTREACH / 'mastodon-activity.md'
if masto_log.exists():
    for line in masto_log.read_text().split('\n'):
        if line.startswith('|') and '---' not in line and 'Date' not in line:
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 2 and parts[0]:
                feed['mastodon'].append({
                    'date': parts[0],
                    'text': parts[1] if len(parts) > 1 else '',
                })

# Also try to fetch live HN data for seed867
try:
    import urllib.request
    data = json.loads(urllib.request.urlopen(
        'http://hn.algolia.com/api/v1/search?tags=author_seed867&hitsPerPage=10',
        timeout=5
    ).read())
    for hit in data.get('hits', []):
        exists = any(h.get('thread') == hit.get('objectID') for h in feed['hn'])
        if not exists:
            feed['hn'].append({
                'date': hit.get('created_at', '')[:16].replace('T', ' '),
                'thread': str(hit.get('objectID', '')),
                'type': 'story' if hit.get('story_title') is None else 'comment',
                'text': (hit.get('comment_text') or hit.get('title') or '')[:200],
                'url': f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                'points': hit.get('points', 0),
            })
except:
    pass

# Sort all feeds newest first
for key in ['hn', 'reddit', 'mastodon']:
    feed[key].sort(key=lambda x: x.get('date', ''), reverse=True)

json.dump(feed, open(str(OUTPUT), 'w'), indent=2)
print(f"[social] HN:{len(feed['hn'])} Reddit:{len(feed['reddit'])} Mastodon:{len(feed['mastodon'])}")
PYEOF
