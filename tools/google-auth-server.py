#!/usr/bin/env python3
"""Google OAuth relay — run this, open the URL in your browser, sign in, token saves locally."""
import http.server, json, os, urllib.parse, urllib.request, ssl

PORT = 9090
# Using Google's OAuth 2.0 device flow — no browser needed on the Pi
# But for full browser sign-in we need a redirect URI

# For device flow (simplest — works from any browser):
CLIENT_ID = ""  # Will use Google's built-in OAuth playground
SCOPES = "email profile"

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            # Show a page with a Google sign-in link
            html = """<!DOCTYPE html>
<html><head><title>Seed — Google Sign In</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;max-width:500px;margin:40px auto;padding:20px;text-align:center}
a.btn{display:inline-block;padding:12px 24px;background:#4285f4;color:white;border-radius:8px;text-decoration:none;font-size:16px;margin:20px}
a.btn:hover{background:#3367d6}</style></head>
<body>
<h1>Seed — Sign In</h1>
<p>Sign into Google to give Seed access to its own account.</p>
<p>This saves the OAuth token to the Pi. Seed can then use it to create accounts on services that support Google sign-in.</p>
<a class="btn" href="https://accounts.google.com/o/oauth2/v2/auth?client_id=764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com&redirect_uri=http://localhost:9090/callback&response_type=code&scope=email+profile+openid&access_type=offline&prompt=consent">Sign in with Google</a>
<p style="font-size:12px;color:#888">Uses Google OAuth Playground client ID.<br>Token saved to /home/seed/.google-token.json</p>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        elif self.path.startswith("/callback"):
            # Got the auth code back
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = params.get("code", [""])[0]

            if code:
                # Exchange code for token
                try:
                    data = urllib.parse.urlencode({
                        "code": code,
                        "client_id": "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
                        "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
                        "redirect_uri": "http://localhost:9090/callback",
                        "grant_type": "authorization_code",
                    }).encode()
                    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
                    resp = urllib.request.urlopen(req, timeout=10)
                    token_data = json.loads(resp.read())

                    # Save token
                    token_path = os.path.expanduser("~/.google-token.json")
                    with open(token_path, "w") as f:
                        json.dump(token_data, f, indent=2)
                    os.chmod(token_path, 0o600)

                    # Get user info
                    userinfo_req = urllib.request.Request(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {token_data.get("access_token", "")}"}
                    )
                    userinfo = json.loads(urllib.request.urlopen(userinfo_req, timeout=10).read())

                    html = f"""<!DOCTYPE html>
<html><head><title>Seed — Signed In</title>
<style>body{{font-family:system-ui;max-width:500px;margin:40px auto;padding:20px;text-align:center}}
.ok{{color:#2d6a4f;font-size:48px}}</style></head>
<body>
<div class="ok">&#10004;</div>
<h1>Signed In</h1>
<p>Account: {userinfo.get("email", "unknown")}</p>
<p>Token saved to Pi at ~/.google-token.json</p>
<p>You can close this tab. Seed now has Google OAuth access.</p>
</body></html>"""
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(html.encode())
                    print(f"[auth] Signed in as {userinfo.get("email")}, token saved")

                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error: {e}".encode())
                    print(f"[auth] Error: {e}")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"No code received")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a): pass

if __name__ == "__main__":
    print(f"Open http://localhost:{PORT} in your browser to sign in")
    print(f"Or via tunnel if available")
    http.server.HTTPServer(("", PORT), Handler).serve_forever()
