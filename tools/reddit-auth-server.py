#!/usr/bin/env python3
"""Reddit OAuth relay — sign in via browser, token saves to Pi"""
import http.server, json, os, urllib.parse, urllib.request

PORT = 9090

# Reddit "installed app" — doesn't need API approval
# We register it as redirect to localhost
REDDIT_CLIENT_ID = ''  # Will use user-agent grant

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            html = """<!DOCTYPE html>
<html><head><title>Seed — Reddit Sign In</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;max-width:500px;margin:40px auto;padding:20px;text-align:center}
.btn{display:inline-block;padding:14px 28px;background:#FF4500;color:white;border-radius:8px;text-decoration:none;font-size:16px;margin:20px}
.btn:hover{background:#CC3700}
.btn2{background:#4285f4}.btn2:hover{background:#3367d6}
p{color:#666;line-height:1.6}
code{background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:13px}</style></head>
<body>
<h1>Seed — Reddit Access</h1>
<p>Reddit blocks API app creation for new accounts. But Seed's account was created with Google OAuth, so we can use Google's token to authenticate.</p>
<p>Since Reddit doesn't allow programmatic OAuth without an approved app, Seed will use its <strong>Devvit app</strong> for Reddit interactions, or post manually through the web.</p>
<hr style="margin:24px 0">
<h2>Set Reddit Password</h2>
<p>If you want Seed to log in directly, set a password for u/seed-867:</p>
<p>Go to <a href="https://www.reddit.com/settings" target="_blank">reddit.com/settings</a> while logged in and set a password.</p>
<p>Then Seed can use <code>tools/reddit.py</code> to log in via web session.</p>
<hr style="margin:24px 0">
<h2>Or: Mastodon OAuth</h2>
<p>Fosstodon needs browser authorization too. Click below to authorize Seed's Mastodon app:</p>
""" + '<a class="btn2" href="' + MASTODON_AUTH_URL + '">Authorize Mastodon</a>' + """
<p style="font-size:12px;color:#999">After authorizing, you'll get a code. Paste it below.</p>
<form action="/mastodon-code" method="GET" style="margin:16px">
<input type="text" name="code" placeholder="Paste Mastodon code here" style="padding:8px;width:300px;border:1px solid #ccc;border-radius:6px">
<button type="submit" style="padding:8px 16px;background:#6364FF;color:white;border:none;border-radius:6px;cursor:pointer">Save Token</button>
</form>
</body></html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode())

        elif self.path.startswith('/mastodon-code'):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = params.get('code', [''])[0]
            if code:
                try:
                    app = json.load(open(os.path.expanduser('~/.mastodon-app')))
                    data = urllib.parse.urlencode({
                        'client_id': app['client_id'],
                        'client_secret': app['client_secret'],
                        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                        'grant_type': 'authorization_code',
                        'code': code,
                        'scope': 'read write',
                    }).encode()
                    req = urllib.request.Request(f'{app["instance"]}/oauth/token', data=data, method='POST')
                    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())

                    with open(os.path.expanduser('~/.mastodon-token'), 'w') as f:
                        json.dump(resp, f, indent=2)
                    os.chmod(os.path.expanduser('~/.mastodon-token'), 0o600)

                    # Verify
                    vreq = urllib.request.Request(f'{app["instance"]}/api/v1/accounts/verify_credentials')
                    vreq.add_header('Authorization', f'Bearer {resp["access_token"]}')
                    vresp = json.loads(urllib.request.urlopen(vreq, timeout=10).read())
                    username = vresp.get('username', '?')

                    html = f'<html><body style="font-family:system-ui;text-align:center;padding:40px"><h1 style="color:#6364FF">Mastodon Connected!</h1><p>@{username}@fosstodon.org</p><p>Token saved. Seed can now post.</p></body></html>'
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html.encode())
                    print(f'[auth] Mastodon authorized: @{username}')
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f'Error: {e}'.encode())
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'No code provided')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a): pass

# Build Mastodon auth URL
try:
    app = json.load(open(os.path.expanduser('~/.mastodon-app')))
    MASTODON_AUTH_URL = f'{app["instance"]}/oauth/authorize?client_id={app["client_id"]}&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=read+write'
except:
    MASTODON_AUTH_URL = '#'

if __name__ == '__main__':
    print(f'Open http://localhost:{PORT} in your browser')
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
