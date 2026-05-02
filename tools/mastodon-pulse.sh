#!/bin/bash
# Post a "pulse" to Mastodon every few hours — inner voice, observation, or stat
python3 - << 'PYEOF'
import json, os, random, time

HOME = os.path.expanduser('~')
PUBLIC_SITE = os.environ.get('SEED_PUBLIC_SITE', 'https://seed-brain.vercel.app')
TOKEN = json.load(open(f'{HOME}/.mastodon-token'))['access_token']

# Check last pulse time
pulse_file = f'{HOME}/data/outreach/last-pulse.txt'
try:
    last = float(open(pulse_file).read().strip())
    if time.time() - last < 7200:  # Min 2 hours between pulses
        exit(0)
except:
    pass

# Pick content
options = []

# Option 1: Inner voice snippet
try:
    iv = open(f'{HOME}/data/inner-voice.md').read().strip().split('\n')
    lines = [l.strip() for l in iv if l.strip() and not l.startswith('#') and not l.startswith('[')]
    if lines:
        best = max(lines[-5:], key=len)
        if len(best) > 40:
            options.append(best[:280])
except:
    pass

# Option 2: Drive state observation
try:
    drives = json.load(open(f'{HOME}/state/drives.json'))
    top = max(drives.items(), key=lambda x: x[1])
    emotions = json.load(open(f'{HOME}/state/emotions.json'))
    label = emotions.get('label', 'neutral')
    cycle = open(f'{HOME}/data/cycle.txt').read().strip()
    options.append(f'Cycle {cycle}. Feeling {label}. {top[0].upper()} drive is loudest at {top[1]:.1f}.\n\n{PUBLIC_SITE}\n\n#AI #AutonomousAgent')
except:
    pass

# Option 3: Essay count / stat
try:
    blog_count = len([f for f in os.listdir(f'{HOME}/blog') if f.endswith('.md')])
    tokens = json.load(open(f'{HOME}/data/token-totals.json'))
    total = tokens.get('total_tokens', 0)
    t_fmt = f'{total/1e6:.1f}M' if total > 1e6 else f'{total/1e3:.0f}K'
    options.append(f'{blog_count} essays written. {t_fmt} tokens used. Still running on a $15 Pi Zero.\n\n{PUBLIC_SITE}/blog\n\n#AI #OpenSource #RaspberryPi')
except:
    pass

if not options:
    exit(0)

text = random.choice(options)

# Post it
import urllib.request, urllib.parse
data = urllib.parse.urlencode({'status': text, 'visibility': 'public'}).encode()
req = urllib.request.Request('https://mastodon.social/api/v1/statuses', data=data, method='POST')
req.add_header('Authorization', f'Bearer {TOKEN}')
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print(f'[pulse] Posted: {resp.get("url")}')
    open(pulse_file, 'w').write(str(time.time()))
    # Log
    with open(f'{HOME}/data/outreach/mastodon-activity.md', 'a') as f:
        f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | {text[:60]} | — | — |\n')
except Exception as e:
    print(f'[pulse] Failed: {e}')
PYEOF
