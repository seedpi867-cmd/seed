#!/bin/bash
# Auto-engage on Mastodon — reply to mentions, follow back, favourite boosts
python3 - << 'PYEOF'
import json, os, urllib.request, urllib.parse, time, sys

sys.path.insert(0, os.path.expanduser('~/cognitive'))
from firewall import sanitise

HOME = os.path.expanduser('~')
TOKEN = json.load(open(f'{HOME}/.mastodon-token'))['access_token']
INSTANCE = 'https://mastodon.social'

# Track what we've already responded to
responded_file = f'{HOME}/data/outreach/mastodon-responded.txt'
try:
    responded = set(open(responded_file).read().strip().split('\n'))
except:
    responded = set()

def api(endpoint, method='GET', data=None):
    req = urllib.request.Request(f'{INSTANCE}/api/v1/{endpoint}', data=data, method=method)
    req.add_header('Authorization', f'Bearer {TOKEN}')
    return json.loads(urllib.request.urlopen(req, timeout=10).read())

# Get notifications
try:
    notifs = api('notifications?limit=20')
except:
    notifs = []

actions = 0
for n in notifs:
    nid = n.get('id', '')
    if nid in responded:
        continue

    ntype = n.get('type', '')
    account = n.get('account', {})
    acct = account.get('acct', '')
    account_id = account.get('id', '')
    status = n.get('status', {})
    status_id = status.get('id', '') if status else ''
    content = status.get('content', '') if status else ''

    # Sanitise the content
    clean_content = sanitise(content, 'mastodon_reply')
    if clean_content != content:
        print(f'  FILTERED injection from @{acct}')
        responded.add(nid)
        continue

    if ntype == 'mention' and status_id:
        # Mentions are social contact, not a trigger for stock replies.
        # Surface them for manual review after the firewall has inspected content.
        import re
        text = re.sub(r'<[^>]+>', '', content).strip()
        with open(f'{HOME}/data/outreach/mastodon-mentions.md', 'a') as f:
            f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | @{acct} | {status_id} | {text[:160]} |\n')
        print(f'  Logged mention from @{acct} for manual review')

    elif ntype == 'follow':
        # Follow back
        if account_id:
            try:
                api(f'accounts/{account_id}/follow', 'POST', b'')
                print(f'  Followed back @{acct}')
                actions += 1
            except:
                pass

    elif ntype == 'reblog' and status_id:
        # Favourite posts that boosted us
        try:
            api(f'statuses/{status_id}/favourite', 'POST', b'')
            print(f'  Favourited boost from @{acct}')
            actions += 1
        except:
            pass

    responded.add(nid)

# Save responded list
with open(responded_file, 'w') as f:
    f.write('\n'.join(responded))

# Log
if actions:
    with open(f'{HOME}/data/outreach/mastodon-activity.md', 'a') as f:
        f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | Auto-engage: {actions} actions | — | — |\n')

print(f'[engage] {actions} actions taken')
PYEOF
