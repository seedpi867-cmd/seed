#!/usr/bin/env python3
"""Reddit posting via web session — no API app needed"""
import urllib.request, urllib.parse, http.cookiejar, json, re, sys, os

CREDS_FILE = os.path.expanduser('~/.reddit-credentials')

def get_session():
    """Login to Reddit via web and return opener with cookies"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler()
    )
    # Get the login page first for csrf
    req = urllib.request.Request('https://www.reddit.com/login/', headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36'
    })
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
    cookies = {c.name: c.value for c in cj}
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
            headers={'User-Agent': 'Seed/1.0'}
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

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: reddit.py check    — verify account exists')
        print('       reddit.py login    — test login')
    elif sys.argv[1] == 'check':
        check_profile()
    elif sys.argv[1] == 'login':
        get_session()
