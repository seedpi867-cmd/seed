#!/usr/bin/env python3
"""Reddit posting via web session.

This only posts when Reddit returns an authenticated browser session cookie.
It does not bypass OAuth, captcha, account locks, or Reddit's anti-abuse gates.
"""
import urllib.request, urllib.parse, http.cookiejar, json, re, sys, os

CREDS_FILE = os.path.expanduser('~/.reddit-credentials')
SESSION_FILE = os.path.expanduser('~/.reddit-cookies.txt')
USER_AGENT = 'Seed/1.0 by u/seed-867'

def request(opener, url, data=None):
    headers = {'User-Agent': USER_AGENT}
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    return urllib.request.Request(url, data=data, headers=headers)

def cookies_dict(cj):
    return {c.name: c.value for c in cj}

def build_opener(cj):
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler()
    )

def save_session(cj):
    jar = http.cookiejar.MozillaCookieJar(SESSION_FILE)
    for cookie in cj:
        jar.set_cookie(cookie)
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(SESSION_FILE, 0o600)

def load_session():
    cj = http.cookiejar.MozillaCookieJar(SESSION_FILE)
    if os.path.exists(SESSION_FILE):
        cj.load(ignore_discard=True, ignore_expires=True)
    return build_opener(cj), cj

def cookie_from_json(item):
    domain = item.get('domain') or item.get('host') or '.reddit.com'
    name = item.get('name')
    value = item.get('value')
    if not name or value is None:
        return None
    expires = item.get('expirationDate') or item.get('expires')
    if expires is not None:
        expires = int(expires)
    return http.cookiejar.Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=domain.startswith('.'),
        domain_initial_dot=domain.startswith('.'),
        path=item.get('path') or '/',
        path_specified=True,
        secure=bool(item.get('secure', True)),
        expires=expires,
        discard=False,
        comment=None,
        comment_url=None,
        rest={'HttpOnly': item.get('httpOnly', False)},
        rfc2109=False,
    )

def import_cookies(path):
    """Import a browser-exported Reddit cookie file into the local session jar."""
    cj = http.cookiejar.MozillaCookieJar()
    try:
        cj.load(path, ignore_discard=True, ignore_expires=True)
    except (http.cookiejar.LoadError, OSError):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get('cookies', [])
        for item in data:
            cookie = cookie_from_json(item)
            if cookie:
                cj.set_cookie(cookie)
    reddit_cookies = [
        c for c in cj
        if 'reddit.com' in c.domain and c.name in {'reddit_session', 'token_v2', 'modhash'}
    ]
    if not reddit_cookies:
        names = ', '.join(sorted({c.name for c in cj})) or 'none'
        raise RuntimeError(f'No Reddit auth cookies found in import. Cookie names: {names}')
    session = http.cookiejar.MozillaCookieJar(SESSION_FILE)
    for cookie in reddit_cookies:
        session.set_cookie(cookie)
    session.save(ignore_discard=True, ignore_expires=True)
    os.chmod(SESSION_FILE, 0o600)
    print(f'Imported Reddit session cookies: {", ".join(sorted(c.name for c in reddit_cookies))}')
    return True

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
    opener, cj = load_session()
    if 'reddit_session' in cookies_dict(cj) or 'token_v2' in cookies_dict(cj):
        print('Using saved Reddit browser session')
        return opener, cj

    cj = http.cookiejar.CookieJar()
    opener = build_opener(cj)
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
        save_session(cj)
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
    print('       reddit.py import-cookies <netscape-or-json-cookie-export>')
    print('       reddit.py comment <t3_post_or_t1_comment_id> <text>')
    print('       reddit.py submit <subreddit> <title> <url-or-selftext>')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()
    elif sys.argv[1] == 'check':
        check_profile()
    elif sys.argv[1] == 'login':
        get_session()
    elif sys.argv[1] == 'import-cookies' and len(sys.argv) >= 3:
        try:
            ok = import_cookies(sys.argv[2])
            sys.exit(0 if ok else 1)
        except Exception as e:
            print(f'Error: {e}')
            sys.exit(1)
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
