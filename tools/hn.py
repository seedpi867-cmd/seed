#!/usr/bin/env python3
"""Post/comment on Hacker News"""
import html
import time
import urllib.request, urllib.parse, http.cookiejar, json, re, sys, os

CREDS = None


def load_creds(required=True):
    global CREDS
    if CREDS is not None:
        return CREDS
    path = os.path.expanduser('~/.hn-credentials')
    try:
        with open(path) as f:
            CREDS = json.load(f)
    except FileNotFoundError:
        if required:
            raise RuntimeError(f'HN credentials missing: {path}')
        return None
    return CREDS


def log_activity(action, item_id='', text=''):
    """Log HN activity to data/outreach/hn-activity.md"""
    import time
    ts = time.strftime('%Y-%m-%d %H:%M')
    log_path = os.path.expanduser('~/data/outreach/hn-activity.md')
    try:
        with open(log_path, 'a') as f:
            if action == 'comment':
                f.write(f'| {ts} | {item_id} | comment | {text[:80]} |\n')
            elif action == 'submit':
                f.write(f'| {ts} | {text} | submitted | — |\n')
    except:
        pass

def login():
    creds = load_creds()
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = urllib.parse.urlencode({'acct': creds['username'], 'pw': creds['password'], 'goto': 'news'}).encode()
    req = urllib.request.Request('https://news.ycombinator.com/login', data=data, method='POST')
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    opener.open(req, timeout=15)
    page = fetch(opener, 'https://news.ycombinator.com/news')
    if f'user?id={html.escape(creds["username"])}' not in page:
        raise RuntimeError('HN login failed or account not visible in session')
    return opener

def fetch(opener, url):
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0')
    return opener.open(req, timeout=10).read().decode('utf-8', errors='replace')

def visible_phrase(text):
    words = re.findall(r'[A-Za-z0-9][A-Za-z0-9/.-]*', text)
    return ' '.join(words[:6])

def response_error(page):
    title = re.search(r'<title>(.*?)</title>', page, re.I | re.S)
    body = re.sub(r'<[^>]+>', ' ', page)
    body = html.unescape(re.sub(r'\s+', ' ', body)).strip()
    for needle in (
        'Please don\'t post so fast',
        'You are posting too fast',
        'Too many requests',
        'Unknown or expired link',
        'Sorry, you are banned',
        'not allowed',
        'login',
    ):
        if needle.lower() in body.lower():
            return needle
    if title and 'error' in html.unescape(title.group(1)).lower():
        return html.unescape(title.group(1)).strip()
    return None

def hn_api(path):
    req = urllib.request.Request(f'https://hacker-news.firebaseio.com/v0/{path}')
    req.add_header('User-Agent', 'Mozilla/5.0')
    return json.loads(urllib.request.urlopen(req, timeout=10).read())

def dead_comments_for_parent(parent_id, since_ts):
    """Return recent submitted comments on parent_id that HN marked dead."""
    try:
        creds = load_creds()
        user = hn_api(f'user/{creds["username"]}.json') or {}
        found = []
        for item_id in user.get('submitted', [])[:20]:
            item = hn_api(f'item/{item_id}.json') or {}
            if (
                item.get('type') == 'comment'
                and str(item.get('parent')) == str(parent_id)
                and item.get('time', 0) >= since_ts - 5
                and item.get('dead')
            ):
                found.append(str(item_id))
        return found
    except Exception:
        return []

def status():
    creds = load_creds(required=False)
    if not creds:
        print('HN: no credentials configured')
        return True
    try:
        user = hn_api(f'user/{creds["username"]}.json') or {}
    except Exception as e:
        print(f'HN: status unavailable: {e}')
        return False
    submitted = user.get('submitted', [])[:30]
    comments = dead = visible = 0
    recent_dead = []
    for item_id in submitted:
        try:
            item = hn_api(f'item/{item_id}.json') or {}
        except Exception:
            continue
        if item.get('type') != 'comment':
            continue
        comments += 1
        if item.get('dead'):
            dead += 1
            if len(recent_dead) < 5:
                recent_dead.append(str(item_id))
        else:
            visible += 1
    print(f'HN user: {creds["username"]}')
    print(f'karma: {user.get("karma", "unknown")}')
    print(f'recent_comments_checked: {comments}')
    print(f'visible_recent_comments: {visible}')
    print(f'dead_recent_comments: {dead}')
    if recent_dead:
        print(f'recent_dead_comment_ids: {", ".join(recent_dead)}')
    if comments and dead == comments:
        print('recommendation: treat HN as read-only until a comment is publicly visible')
    return True

def comment(item_id, text):
    opener = login()
    page = fetch(opener, f'https://news.ycombinator.com/item?id={item_id}')
    hmac_match = re.search(r'name="hmac" value="([^"]+)"', page)
    if not hmac_match:
        print('ERROR: no hmac found')
        return False
    hmac = hmac_match.group(1)
    data = urllib.parse.urlencode({'parent': item_id, 'hmac': hmac, 'text': text, 'goto': f'item?id={item_id}'}).encode()
    req = urllib.request.Request('https://news.ycombinator.com/comment', data=data, method='POST')
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    started = int(time.time())
    response = opener.open(req, timeout=15).read().decode('utf-8', errors='replace')
    error = response_error(response)
    if error:
        print(f'ERROR: HN rejected comment on {item_id}: {error}')
        return False
    page = fetch(opener, f'https://news.ycombinator.com/item?id={item_id}')
    phrase = visible_phrase(text)
    if phrase and phrase not in html.unescape(page):
        dead_ids = dead_comments_for_parent(item_id, started)
        if dead_ids:
            print(f'ERROR: HN created dead comment(s) on {item_id}: {", ".join(dead_ids)}')
            return False
        print(f'ERROR: comment not visible after posting to {item_id}')
        return False
    log_activity('comment', item_id, text[:80])
    print(f'Commented on {item_id}')
    return True

def submit(title, url=None, text=None):
    opener = login()
    page_req = urllib.request.Request('https://news.ycombinator.com/submit')
    page_req.add_header('User-Agent', 'Mozilla/5.0')
    page = opener.open(page_req, timeout=10).read().decode('utf-8', errors='replace')
    fnid_match = re.search(r'name="fnid" value="([^"]+)"', page)
    if not fnid_match:
        print('ERROR: no fnid found')
        return False
    fnid = fnid_match.group(1)
    params = {'fnid': fnid, 'fnop': 'submit-page', 'title': title}
    if url: params['url'] = url
    if text: params['text'] = text
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request('https://news.ycombinator.com/r', data=data, method='POST')
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    opener.open(req, timeout=15)
    log_activity('submit', '', title)
    print(f'Submitted: {title}')
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: hn.py comment <item_id> <text>')
        print('       hn.py submit <title> [url] [text]')
        print('       hn.py status')
    elif sys.argv[1] == 'comment':
        sys.exit(0 if comment(sys.argv[2], sys.argv[3]) else 1)
    elif sys.argv[1] == 'submit':
        sys.exit(0 if submit(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None, sys.argv[4] if len(sys.argv) > 4 else None) else 1)
    elif sys.argv[1] == 'status':
        sys.exit(0 if status() else 1)
