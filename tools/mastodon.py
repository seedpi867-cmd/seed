#!/usr/bin/env python3
"""Post to Mastodon"""
import urllib.error
import urllib.request, urllib.parse, json, sys, os

TOKEN = None
INSTANCE = None

class MastodonError(RuntimeError):
    pass

def load_config():
    global TOKEN, INSTANCE
    if TOKEN and INSTANCE:
        return
    try:
        TOKEN = json.load(open(os.path.expanduser('~/.mastodon-token')))['access_token']
        app = json.load(open(os.path.expanduser('~/.mastodon-app')))
        INSTANCE = app['instance']
    except (OSError, KeyError, json.JSONDecodeError) as e:
        raise MastodonError(f'Mastodon credentials are not configured: {e}') from None

def request_json(path, data=None, method=None, timeout=10):
    load_config()
    req = urllib.request.Request(f'{INSTANCE}{path}', data=data, method=method)
    req.add_header('Authorization', f'Bearer {TOKEN}')
    if data is not None:
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:200].strip()
        detail = f': {body}' if body else ''
        raise MastodonError(f'Mastodon API {e.code} on {path}{detail}') from None
    except urllib.error.URLError as e:
        raise MastodonError(f'Mastodon API unavailable on {path}: {e.reason}') from None
    except json.JSONDecodeError:
        raise MastodonError(f'Mastodon API returned invalid JSON on {path}') from None

def post(text, visibility='public'):
    data = urllib.parse.urlencode({'status': text, 'visibility': visibility}).encode()
    resp = request_json('/api/v1/statuses', data=data, method='POST', timeout=15)
    url = resp.get('url', '')
    print(f'Posted: {url}')
    # Log activity
    import time
    log = os.path.expanduser('~/data/outreach/mastodon-activity.md')
    with open(log, 'a') as f:
        f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | {text[:80]} | — | — |\n')
    return resp

def verify():
    resp = request_json('/api/v1/accounts/verify_credentials')
    print(f'@{resp["username"]}@{INSTANCE.replace("https://","")}')
    print(f'Followers: {resp.get("followers_count",0)} Posts: {resp.get("statuses_count",0)}')
    return resp

def status():
    return verify()

def reply(status_id, text, visibility='public'):
    data = urllib.parse.urlencode({'status': text, 'in_reply_to_id': status_id, 'visibility': visibility}).encode()
    resp = request_json('/api/v1/statuses', data=data, method='POST', timeout=15)
    print(f'Replied: {resp.get("url", "")}')
    import time
    with open(os.path.expanduser('~/data/outreach/mastodon-activity.md'), 'a') as f:
        f.write(f'| {time.strftime("%Y-%m-%d %H:%M")} | Reply to {status_id}: {text[:60]} | — | — |\n')
    return resp

def follow(account_id):
    resp = request_json(f'/api/v1/accounts/{account_id}/follow', data=b'', method='POST')
    print(f'Followed: {account_id}')
    return resp

def favourite(status_id):
    request_json(f'/api/v1/statuses/{status_id}/favourite', data=b'', method='POST')
    print(f'Favourited: {status_id}')

def get_notifications(limit=20):
    return request_json(f'/api/v1/notifications?limit={limit}')

if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print('Usage: mastodon.py verify')
            print('       mastodon.py status')
            print('       mastodon.py post "your message"')
            sys.exit(2)
        elif sys.argv[1] in ('verify', 'status'):
            status()
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
        else:
            print(f'Unknown command: {sys.argv[1]}')
            sys.exit(2)
    except (IndexError, MastodonError) as e:
        print(f'ERROR: {e}')
        sys.exit(1)
