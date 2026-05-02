#!/usr/bin/env python3
"""Post to Mastodon"""
import urllib.request, urllib.parse, json, sys, os

TOKEN = json.load(open(os.path.expanduser('~/.mastodon-token')))['access_token']
APP = json.load(open(os.path.expanduser('~/.mastodon-app')))
INSTANCE = APP['instance']

def post(text, visibility='public'):
    data = urllib.parse.urlencode({'status': text, 'visibility': visibility}).encode()
    req = urllib.request.Request(f'{INSTANCE}/api/v1/statuses', data=data, method='POST')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    url = resp.get('url', '')
    print(f'Posted: {url}')
    # Log activity
    import time
    log = os.path.expanduser('~/data/outreach/mastodon-activity.md')
    with open(log, 'a') as f:
        f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | {text[:80]} | — | — |\n')
    return resp

def verify():
    req = urllib.request.Request(f'{INSTANCE}/api/v1/accounts/verify_credentials')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f'@{resp["username"]}@{INSTANCE.replace("https://","")}')
    print(f'Followers: {resp.get("followers_count",0)} Posts: {resp.get("statuses_count",0)}')
    return resp

def reply(status_id, text, visibility='public'):
    data = urllib.parse.urlencode({'status': text, 'in_reply_to_id': status_id, 'visibility': visibility}).encode()
    req = urllib.request.Request(f'{INSTANCE}/api/v1/statuses', data=data, method='POST')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print(f'Replied: {resp.get("url", "")}')
    import time
    with open(os.path.expanduser('~/data/outreach/mastodon-activity.md'), 'a') as f:
        f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | Reply to {status_id}: {text[:60]} | — | — |\n')
    return resp

def follow(account_id):
    req = urllib.request.Request(f'{INSTANCE}/api/v1/accounts/{account_id}/follow', data=b'', method='POST')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f'Followed: {account_id}')
    return resp

def favourite(status_id):
    req = urllib.request.Request(f'{INSTANCE}/api/v1/statuses/{status_id}/favourite', data=b'', method='POST')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    urllib.request.urlopen(req, timeout=10)
    print(f'Favourited: {status_id}')

def get_notifications(limit=20):
    req = urllib.request.Request(f'{INSTANCE}/api/v1/notifications?limit={limit}')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    return json.loads(urllib.request.urlopen(req, timeout=10).read())

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: mastodon.py verify')
        print('       mastodon.py post "your message"')
    elif sys.argv[1] == 'verify':
        verify()
    elif sys.argv[1] == 'post':
        post(sys.argv[2])
    elif sys.argv[1] == 'reply':
        reply(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'follow':
        follow(sys.argv[2])
    elif sys.argv[1] == 'fav':
        favourite(sys.argv[2])
    elif sys.argv[1] == 'notifications':
        for n in get_notifications():
            t = n.get('type','')
            who = n.get('account',{}).get('acct','?')
            sid = n.get('status',{}).get('id','') if n.get('status') else ''
            print(f'{t} from @{who} (status:{sid})')
