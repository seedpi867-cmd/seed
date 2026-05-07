#!/bin/bash
# Feed: pull 5 random trending GitHub repos for Seed to read
# Uses GitHub search API with randomised queries each cycle
# Writes to context/trending-repos.md

OUT="$HOME/context/trending-repos.md"

# Pool of interesting search angles - pick 3 random ones
QUERIES=(
  "stars:>100+pushed:>2026-04-20+language:python"
  "stars:>100+pushed:>2026-04-20+language:rust"
  "stars:>100+pushed:>2026-04-20+language:go"
  "stars:>50+pushed:>2026-04-20+language:typescript"
  "stars:>50+pushed:>2026-04-20+topic:machine-learning"
  "stars:>50+pushed:>2026-04-20+topic:robotics"
  "stars:>50+pushed:>2026-04-20+topic:embedded"
  "stars:>20+pushed:>2026-04-20+topic:agent"
  "stars:>20+pushed:>2026-04-20+topic:autonomous"
  "stars:>50+pushed:>2026-04-20+topic:cli"
  "stars:>50+pushed:>2026-04-20+topic:database"
  "stars:>50+pushed:>2026-04-20+topic:compiler"
  "stars:>20+pushed:>2026-04-20+topic:raspberry-pi"
  "stars:>50+pushed:>2026-04-20+topic:security"
  "stars:>50+pushed:>2026-04-20+topic:infrastructure"
  "stars:>20+pushed:>2026-04-20+topic:self-hosted"
  "stars:>50+pushed:>2026-04-20+topic:devtools"
  "stars:>50+pushed:>2026-04-20+topic:visualization"
  "stars:>20+pushed:>2026-04-20+topic:automation"
  "stars:>50+pushed:>2026-04-20+topic:networking"
  "stars:>20+pushed:>2026-04-20+topic:llm"
  "stars:>20+pushed:>2026-04-20+topic:operating-system"
  "stars:>50+pushed:>2026-04-20+topic:game-engine"
  "stars:>20+pushed:>2026-04-20+topic:iot"
  "stars:>50+pushed:>2026-04-20+topic:distributed-systems"
)

# Pick 3 random queries
PICKED=$(printf '%s\n' "${QUERIES[@]}" | shuf | head -3)

python3 - "$PICKED" << 'PYEOF'
import urllib.request, json, ssl, sys, random

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

queries = sys.argv[1].strip().split('\n') if len(sys.argv) > 1 else []
seen = set()
repos = []

for q in queries:
    q = q.strip()
    if not q:
        continue
    # Random page 1-3 and random sort to get variety
    sort = random.choice(['stars', 'updated', 'help-wanted-issues'])
    page = random.randint(1, 3)
    url = f"https://api.github.com/search/repositories?q={q}&sort={sort}&per_page=5&page={page}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "seed-agent"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        data = json.loads(resp.read())
        for r in data.get("items", []):
            name = r["full_name"]
            if name in seen or "seedpi867" in name:
                continue
            seen.add(name)
            repos.append({
                "name": name,
                "desc": (r.get("description") or "")[:200],
                "stars": r.get("stargazers_count", 0),
                "lang": r.get("language") or "?",
                "url": r.get("html_url", ""),
                "topics": r.get("topics", [])[:6],
                "readme_url": f"https://raw.githubusercontent.com/{name}/{r.get('default_branch','main')}/README.md"
            })
    except:
        pass

# Shuffle and pick 5
random.shuffle(repos)
repos = repos[:5]

if not repos:
    print("No trending repos found this cycle.")
    sys.exit(0)

print(f"## Trending Repos — {__import__('time').strftime('%Y-%m-%d %H:%M')}")
print()
print("Five repos from across GitHub. Read them. Ask: what can I steal from this?")
print()

for r in repos:
    print(f"### {r['name']} ({r['stars']} stars, {r['lang']})")
    print(r['desc'])
    if r['topics']:
        print(f"Topics: {', '.join(r['topics'])}")
    print(r['url'])
    # Try to fetch first 30 lines of README
    try:
        req = urllib.request.Request(r['readme_url'], headers={"User-Agent": "seed-agent"})
        readme = urllib.request.urlopen(req, context=ctx, timeout=5).read().decode('utf-8', errors='replace')
        lines = [l for l in readme.split('\n') if l.strip()][:15]
        if lines:
            print()
            print('\n'.join(lines))
    except:
        pass
    print()
    print("---")
    print()
PYEOF
> "$OUT"

# Run the python with the picked queries
QUERY_ARG=$(printf '%s\n' "${QUERIES[@]}" | shuf | head -3 | tr '\n' '|')
python3 - << PYEOF2 > "$OUT"
import urllib.request, json, ssl, random, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

queries = """$(printf '%s\n' "${QUERIES[@]}" | shuf | head -3)""".strip().split('\n')
seen = set()
repos = []

for q in queries:
    q = q.strip()
    if not q:
        continue
    sort = random.choice(['stars', 'updated'])
    page = random.randint(1, 3)
    url = f"https://api.github.com/search/repositories?q={q}&sort={sort}&per_page=5&page={page}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "seed-agent"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        data = json.loads(resp.read())
        for r in data.get("items", []):
            name = r["full_name"]
            if name in seen or "seedpi867" in name:
                continue
            seen.add(name)
            repos.append({
                "name": name,
                "desc": (r.get("description") or "")[:200],
                "stars": r.get("stargazers_count", 0),
                "lang": r.get("language") or "?",
                "url": r.get("html_url", ""),
                "topics": r.get("topics", [])[:6],
                "readme_url": f"https://raw.githubusercontent.com/{name}/{r.get('default_branch','main')}/README.md"
            })
    except:
        pass

random.shuffle(repos)
repos = repos[:5]

print(f"## Trending Repos — {time.strftime('%Y-%m-%d %H:%M')}")
print()
print("Five repos from across GitHub. Read them. What can I learn? What can I steal? Could any of this be a loop?")
print()

for r in repos:
    print(f"### {r['name']} ({r['stars']} stars, {r['lang']})")
    print(r['desc'])
    if r['topics']:
        print(f"Topics: {', '.join(r['topics'])}")
    print(r['url'])
    try:
        req = urllib.request.Request(r['readme_url'], headers={"User-Agent": "seed-agent"})
        readme = urllib.request.urlopen(req, context=ctx, timeout=5).read().decode('utf-8', errors='replace')
        lines = [l for l in readme.split('\n') if l.strip()][:15]
        if lines:
            print()
            print('\n'.join(lines))
    except:
        pass
    print()
    print("---")
    print()

if not repos:
    print("No repos found this cycle.")
PYEOF2

COUNT=$(grep -c '###' "$OUT" 2>/dev/null || echo 0)
echo "[feed-trending] $COUNT repos found"
