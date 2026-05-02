#!/usr/bin/env python3
"""Reddit posting via web session.

This only posts when Reddit returns an authenticated browser session cookie.
It does not bypass OAuth, captcha, account locks, or Reddit's anti-abuse gates.
"""
import urllib.request, urllib.parse, http.cookiejar, json, re, sys, os

CREDS_FILE = os.path.expanduser('~/.reddit-credentials')
USER_AGENT = 'Seed/1.0 by u/seed-867'

def request(opener, url, data=None):
    headers = {'User-Agent': USER_AGENT}
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    return urllib.request.Request(url, data=data, headers=headers)

def cookies_dict(cj):
    return {c.name: c.value for c in cj}

def require_auth(cj):
    cookies = cookies_dict(cj)
    if 'reddit_session' not in cookies and 'token_v2' not in cookies:
        names = ', '.join(sorted(cookies)) or 'none'
        raise RuntimeError(
            'No authenticated Reddit session cookie. '
            f'Login returned cookies: {names}. '
            'Set a real Reddit password or complete browser auth before posting.'
        )
    return cookies

def get_session():
    """Login to Reddit via web and return opener with cookies"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler()
    )
    # Get the login page first for csrf
    req = urllib.request.Request('https://www.reddit.com/login/', headers={'User-Agent': USER_AGENT})
    resp = opener.open(req, timeout=15)
    page = resp.read().decode('utf-8', errors='replace')

    # Find csrf token
    csrf = ''
    csrf_match = re.search(r'csrf_token.*?value="([^"]+)"', page)
    if csrf_match:
        csrf = csrf_match.group(1)

    # Try login with username/password
    creds = json.load(open(CREDS_FILE))
    login_data = urllib.parse.urlencode({
        'username': creds['username'],
        'password': creds['password'],
        'csrf_token': csrf,
        'dest': 'https://www.reddit.com',
    }).encode()

    login_req = urllib.request.Request('https://www.reddit.com/login', data=login_data, method='POST')
    login_req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36')
    login_req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        login_resp = opener.open(login_req, timeout=15)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303):
            pass  # Redirects are expected
        else:
            raise

    # Check if we got session cookies
    cookies = cookies_dict(cj)
    if 'reddit_session' in cookies or 'token_v2' in cookies:
        print('Login successful')
        return opener, cj
    else:
        print(f'Login may have failed. Cookies: {list(cookies.keys())}')
        return opener, cj

def check_profile():
    """Check if the Reddit account exists and is accessible"""
    try:
        req = urllib.request.Request(
            'https://www.reddit.com/user/seed-867/about.json',
            headers={'User-Agent': USER_AGENT}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        user = data.get('data', {})
        print(f'Account: u/{user.get("name", "?")}')
        print(f'Karma: {user.get("total_karma", 0)}')
        print(f'Created: {user.get("created_utc", 0)}')
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print('Account not found')
        else:
            print(f'Error: {e.code}')
        return False
    except Exception as e:
        print(f'Error: {e}')
        return False

def api_action(path, fields):
    opener, cj = get_session()
    cookies = require_auth(cj)
    fields = dict(fields)
    if 'modhash' in cookies:
        fields['uh'] = cookies['modhash']
    data = urllib.parse.urlencode(fields).encode()
    req = request(opener, f'https://www.reddit.com{path}', data)
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    req.add_header('Origin', 'https://www.reddit.com')
    req.add_header('Referer', 'https://www.reddit.com/')
    resp = opener.open(req, timeout=20)
    body = resp.read().decode('utf-8', errors='replace')
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        print(body)
        return False
    errors = parsed.get('json', {}).get('errors', [])
    if errors:
        print(json.dumps(errors, indent=2))
        return False
    print(json.dumps(parsed, indent=2))
    return True

def comment(parent_fullname, text):
    if not parent_fullname.startswith(('t1_', 't3_')):
        parent_fullname = 't3_' + parent_fullname
    return api_action('/api/comment', {
        'api_type': 'json',
        'thing_id': parent_fullname,
        'text': text,
    })

def submit(subreddit, title, url_or_text):
    fields = {
        'api_type': 'json',
        'sr': subreddit.removeprefix('r/'),
        'title': title,
    }
    if url_or_text.startswith(('http://', 'https://')):
        fields.update({'kind': 'link', 'url': url_or_text})
    else:
        fields.update({'kind': 'self', 'text': url_or_text})
    return api_action('/api/submit', fields)

def usage():
    print('Usage: reddit.py check')
    print('       reddit.py login')
    print('       reddit.py comment <t3_post_or_t1_comment_id> <text>')
    print('       reddit.py submit <subreddit> <title> <url-or-selftext>')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()
    elif sys.argv[1] == 'check':
        check_profile()
    elif sys.argv[1] == 'login':
        get_session()
    elif sys.argv[1] == 'comment' and len(sys.argv) >= 4:
        try:
            ok = comment(sys.argv[2], sys.argv[3])
            sys.exit(0 if ok else 1)
        except Exception as e:
            print(f'Error: {e}')
            sys.exit(1)
    elif sys.argv[1] == 'submit' and len(sys.argv) >= 5:
        try:
            ok = submit(sys.argv[2], sys.argv[3], sys.argv[4])
            sys.exit(0 if ok else 1)
        except Exception as e:
            print(f'Error: {e}')
            sys.exit(1)
    else:
        usage()
        sys.exit(2)
