#!/usr/bin/env python3
"""Discover AI agent repos on GitHub + track forks of Seed + detect changes."""
import urllib.request, json, ssl, os
from pathlib import Path

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

STATE_FILE = Path.home() / "data" / "github-watch.json"

def gh_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "seed-agent"})
    resp = urllib.request.urlopen(req, context=ctx, timeout=10)
    return json.loads(resp.read())

# Load previous state
prev = {}
try:
    prev = json.loads(STATE_FILE.read_text())
except Exception:
    pass

current = {}
changes = []

# ── Track forks of seedpi867-cmd/seed ──
print("## Forks of Seed")
print()
try:
    forks = gh_get("https://api.github.com/repos/seedpi867-cmd/seed/forks?sort=newest&per_page=30")
    if not forks:
        print("No forks yet.")
        print()
    for fork in forks:
        owner = fork["owner"]["login"]
        name = fork["full_name"]
        url = fork["html_url"]
        created = fork.get("created_at", "")[:10]
        pushed = fork.get("pushed_at", "")
        stars = fork.get("stargazers_count", 0)
        desc = (fork.get("description") or "")[:120]
        ahead = 0
        try:
            compare = gh_get(f"https://api.github.com/repos/seedpi867-cmd/seed/compare/main...{owner}:main")
            ahead = compare.get("ahead_by", 0)
        except Exception:
            pass
        status = f"{ahead} commits ahead" if ahead > 0 else "no changes yet"
        # Track state
        key = f"fork:{name}"
        current[key] = {"pushed": pushed, "ahead": ahead}
        old = prev.get(key, {})
        if old.get("pushed") and old["pushed"] != pushed:
            changes.append(f"FORK UPDATE: {name} pushed new commits ({ahead} ahead)")
        elif key not in prev:
            changes.append(f"NEW FORK: {name} by {owner}")
        print(f"### {name} ({status})")
        print(f"Forked: {created} | Last push: {pushed[:10]} | Stars: {stars}")
        if desc:
            print(desc)
        print(url)
        print()
except Exception as e:
    print(f"Could not fetch forks: {e}")
    print()

# ── Discover other AI agent repos ──
print("## Other AI Agent Repos")
print()

queries = [
    "autonomous+agent+loop+language:python+pushed:>2026-04-20",
    "brain+loop+agent+language:shell+pushed:>2026-04-20",
    "ai+agent+framework+language:python+stars:>50+pushed:>2026-04-20",
    "cognitive+architecture+agent+pushed:>2026-04-20",
    "self-improving+agent+pushed:>2026-04-20",
    "agentic+ai+autonomous+pushed:>2026-04-20+stars:>20",
]

seen = set()
results = []

for q in queries:
    try:
        url = "https://api.github.com/search/repositories?q=" + q + "&sort=updated&per_page=5"
        data = gh_get(url)
        for repo in data.get("items", []):
            rname = repo["full_name"]
            if rname in seen or "seedpi867" in rname:
                continue
            seen.add(rname)
            pushed = repo.get("pushed_at", "")
            results.append({
                "name": rname,
                "stars": repo.get("stargazers_count", 0),
                "desc": (repo.get("description") or "")[:120],
                "lang": repo.get("language") or "?",
                "url": repo.get("html_url", ""),
                "topics": repo.get("topics", [])[:5],
                "pushed": pushed
            })
    except Exception:
        pass

results.sort(key=lambda x: -x["stars"])

for r in results[:15]:
    key = f"repo:{r[name]}"
    current[key] = {"pushed": r["pushed"], "stars": r["stars"]}
    old = prev.get(key, {})
    if old.get("pushed") and old["pushed"] != r["pushed"]:
        changes.append(f"REPO UPDATE: {r[name]} has new activity")
    elif key not in prev:
        changes.append(f"NEW REPO: {r[name]} ({r[stars]} stars)")
    print("### " + r["name"] + " (" + str(r["stars"]) + " stars, " + r["lang"] + ")")
    print(r["desc"])
    if r["topics"]:
        print("Topics: " + ", ".join(r["topics"]))
    print(r["url"])
    print()

if not results:
    print("No new agent repos found this cycle.")

# ── Changes since last run ──
if changes:
    print("## Changes Since Last Check")
    print()
    for c in changes:
        print(f"- {c}")
    print()

# Save state
try:
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(current, f, indent=2)
    os.rename(tmp, str(STATE_FILE))
except Exception:
    pass
