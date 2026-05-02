#!/bin/bash
# Check GitHub notifications and activity
python3 - << 'PYEOF'
import urllib.request, json, os, time

TOKEN = open(os.path.expanduser("~/.git-credentials")).read().split(":")[2].split("@")[0]
OUT = os.path.expanduser("~/context/github.md")

headers = {"Authorization": f"token {TOKEN}", "User-Agent": "Seed/1.0"}

out = f"## GitHub — {time.strftime('%Y-%m-%d %H:%M')}\n\n"

# Notifications
try:
    req = urllib.request.Request("https://api.github.com/notifications?per_page=5", headers=headers)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    if data:
        out += "### Notifications\n"
        for n in data:
            out += f"- [{n['reason']}] {n['subject']['title']} ({n['repository']['full_name']})\n"
        out += "\n"
except: pass

# My repos activity
try:
    req = urllib.request.Request("https://api.github.com/user/repos?sort=pushed&per_page=5", headers=headers)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    out += "### My Repos (recent activity)\n"
    for r in data:
        out += f"- {r['full_name']} — pushed {r['pushed_at'][:10]}, {r['stargazers_count']} stars\n"
    out += "\n"
except: pass

with open(OUT, "w") as f:
    f.write(out)
print("[github] Activity saved")
PYEOF
