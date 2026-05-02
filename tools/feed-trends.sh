#!/bin/bash
# Fetch trending topics in AI/tech
python3 - << 'PYEOF'
import urllib.request, json, os, time

OUT = os.path.expanduser("~/context/trends.md")
out = f"## Trends — {time.strftime('%Y-%m-%d %H:%M')}\n\n"

# GitHub trending
try:
    req = urllib.request.Request("https://api.github.com/search/repositories?q=autonomous+agent&sort=stars&order=desc&per_page=5",
        headers={"User-Agent": "Seed/1.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    out += "### Trending AI Agent Repos\n"
    for r in data.get("items", [])[:5]:
        out += f"- [{r['full_name']}]({r['html_url']}) — {r['stargazers_count']} stars — {(r['description'] or '')[:80]}\n"
    out += "\n"
except: pass

# HN top stories (for awareness)
try:
    data = json.loads(urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json?print=pretty", timeout=10).read())
    out += "### Hacker News Top 5\n"
    for sid in data[:5]:
        story = json.loads(urllib.request.urlopen(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).read())
        out += f"- {story.get('title','')} ({story.get('score',0)} pts)\n"
    out += "\n"
except: pass

with open(OUT, "w") as f:
    f.write(out)
print("[trends] Saved")
PYEOF
