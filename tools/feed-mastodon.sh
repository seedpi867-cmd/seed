#!/bin/bash
# Check Mastodon notifications
python3 - << 'PYEOF'
import json, os, sys, urllib.request, time

sys.path.insert(0, os.path.expanduser("~/cognitive"))
from firewall import sanitise

HOME = os.path.expanduser("~")
TOKEN = json.load(open(f"{HOME}/.mastodon-token"))["access_token"]
INSTANCE = "https://mastodon.social"

try:
    req = urllib.request.Request(f"{INSTANCE}/api/v1/notifications?limit=10")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    notifs = json.loads(urllib.request.urlopen(req, timeout=10).read())
    out = f"## Mastodon Notifications — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
    for n in notifs[:10]:
        ntype = n.get("type", "")
        account = n.get("account", {}).get("acct", "?")
        status = n.get("status", {})
        content = status.get("content", "")[:100] if status else ""
        out += f"- {ntype} from @{account}: {content}\n"
    if not notifs:
        out += "No notifications.\n"
    out = sanitise(out, "mastodon")
    open(f"{HOME}/context/mastodon.md", "w").write(out)
    print(f"[mastodon] {len(notifs)} notifications")
except Exception as e:
    print(f"[mastodon] Error: {e}")
PYEOF
