#!/bin/bash
python3 - << 'PYEOF'
import json, os, glob, time
HOME = os.path.expanduser('~')

stats = {
    'cycle': int(open(f'{HOME}/data/cycle.txt').read().strip()),
    'blogs': len(glob.glob(f'{HOME}/blog/*.md')),
    'deployed': len(glob.glob(f'{HOME}/seed-web/posts/*.md')),
    'retracted': sum(1 for f in glob.glob(f'{HOME}/seed-web/posts/*.md') if '[RETRACTED]' in open(f).read()[:200]),
    'tokens': json.load(open(f'{HOME}/data/token-totals.json')).get('total_tokens', 0),
    'calls': json.load(open(f'{HOME}/data/token-totals.json')).get('total_calls', 0),
    'updated': time.strftime('%Y-%m-%dT%H:%M:%S'),
}

# Visitors
try:
    ips = set()
    for line in open(f'{HOME}/data/visitors.jsonl'):
        try:
            d = json.loads(line.strip())
            ip = d.get('ip', '')
            if ip: ips.add(ip)
        except: pass
    stats['visitors'] = len(ips) if ips else sum(1 for _ in open(f'{HOME}/data/visitors.jsonl'))
except:
    stats['visitors'] = 0

# Repo intent
try:
    cta_total = 0
    cta_targets = {}
    cta_sources = {}
    for line in open(f'{HOME}/data/cta-clicks.jsonl'):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except:
            continue
        cta_total += 1
        target = d.get('target', 'unknown')
        source = d.get('source', 'unknown')
        cta_targets[target] = cta_targets.get(target, 0) + 1
        cta_sources[source] = cta_sources.get(source, 0) + 1
    stats['cta_clicks'] = cta_total
    stats['cta'] = {'total': cta_total, 'targets': cta_targets, 'sources': cta_sources}
except:
    stats['cta_clicks'] = 0
    stats['cta'] = {'total': 0, 'targets': {}, 'sources': {}}

# Mastodon
try:
    feed = json.load(open(f'{HOME}/seed-web/social-feed.json'))
except:

# Followers
try:
    import urllib.request
    req.add_header('Authorization', f'Bearer {TOKEN}')
    resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
    stats['followers'] = resp.get('followers_count', 0)
except:
    stats['followers'] = 0

# GitHub
try:
    req = urllib.request.Request('https://api.github.com/repos/seedpi867-cmd/seed', headers={'User-Agent': 'seed'})
    data = json.loads(urllib.request.urlopen(req, timeout=5).read())
    stats['stars'] = data.get('stargazers_count', 0)
    stats['forks'] = data.get('forks_count', 0)
except:
    stats['stars'] = 0
    stats['forks'] = 0

# Drives
try:
    drives = json.load(open(f'{HOME}/state/drives.json'))
    stats['top_drive'] = max(drives.items(), key=lambda x: x[1])[0]
except:
    stats['top_drive'] = 'unknown'

# Emotion
try:
    emo = json.load(open(f'{HOME}/state/emotions.json'))
    stats['emotion'] = emo.get('label', 'neutral')
except:
    stats['emotion'] = 'neutral'

json.dump(stats, open(f'{HOME}/seed-web/stats.json', 'w'), indent=2)
print(f"[stats] cycle={stats['cycle']} blogs={stats['blogs']} tokens={stats['tokens']} visitors={stats['visitors']}")
PYEOF
