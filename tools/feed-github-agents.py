#!/usr/bin/env python3
"""Discover AI agent repos on GitHub for Seed to learn from."""
import urllib.request, json, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

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
        req = urllib.request.Request(url, headers={"User-Agent": "seed-agent"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        data = json.loads(resp.read())
        for repo in data.get("items", []):
            name = repo["full_name"]
            if name in seen or "seedpi867" in name:
                continue
            seen.add(name)
            stars = repo.get("stargazers_count", 0)
            desc = (repo.get("description") or "")[:120]
            lang = repo.get("language") or "?"
            html_url = repo.get("html_url", "")
            topics = repo.get("topics", [])[:5]
            results.append({
                "name": name, "stars": stars, "desc": desc,
                "lang": lang, "url": html_url, "topics": topics
            })
    except Exception:
        pass

results.sort(key=lambda x: -x["stars"])

for r in results[:15]:
    print("### " + r["name"] + " (" + str(r["stars"]) + " stars, " + r["lang"] + ")")
    print(r["desc"])
    if r["topics"]:
        print("Topics: " + ", ".join(r["topics"]))
    print(r["url"])
    print()

if not results:
    print("No new agent repos found this cycle.")
