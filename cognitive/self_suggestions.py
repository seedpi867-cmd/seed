#!/usr/bin/env python3
"""Self-Suggestions — Seed generates its own action items each cycle.

Two sources:
1. Auto-generated from live context (trending repos, knowledge, recent work)
2. LLM-written discoveries from data/llm-suggestions.json
"""
import json, os, time, random
from pathlib import Path

HOME = Path.home()
DATA = HOME / "data"
CONTEXT = HOME / "context"
SUGGESTIONS_FILE = DATA / "self-suggestions.json"
LLM_SUGGESTIONS_FILE = DATA / "llm-suggestions.json"

def read_text(path, default=""):
    try: return Path(path).read_text()
    except: return default

def generate_suggestions():
    suggestions = []
    cycle = int(read_text(DATA / "cycle.txt", "0").strip() or "0")

    # 1. Trending repo inspiration
    trending = read_text(CONTEXT / "trending-repos.md")
    if trending:
        repos = [l.strip().lstrip("# ") for l in trending.split("\n") if l.strip().startswith("### ")]
        if repos:
            pick = random.choice(repos)
            suggestions.append({"type": "research", "text": "Trending repo: " + pick[:80] + " — what can I steal from this? Could any part be a loop?", "source": "trending_repos", "priority": 0.65})

    # 2. RSS headlines through agent lens
    rss = read_text(CONTEXT / "news.md")
    headlines = [l.strip().lstrip("- ") for l in rss.split("\n") if l.strip().startswith("- ") and len(l.strip()) > 20]
    if headlines:
        pick = random.choice(headlines[:8])
        suggestions.append({"type": "research", "text": "News: " + pick[:80] + " — what pattern does this reveal?", "source": "news_lens", "priority": 0.6})

    # 3. Cross-domain knowledge collision
    knowledge = HOME / "knowledge"
    if knowledge.exists():
        folders = [d.name for d in knowledge.iterdir() if d.is_dir() and d.name not in (".git", "__pycache__", "inbox", "transcripts") and len(list(d.rglob("*.md"))) > 2]
        if len(folders) >= 2:
            pair = random.sample(folders, 2)
            suggestions.append({"type": "think", "text": "Connection hunt: what links " + pair[0].replace("-"," ") + " and " + pair[1].replace("-"," ") + "? Best ideas come from collisions.", "source": "cross_domain", "priority": 0.7})

    # 4. Build pressure from actual GitHub repos
    try:
        import urllib.request, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request("https://api.github.com/users/seedpi867-cmd/repos?sort=created&per_page=3", headers={"User-Agent": "seed-agent"})
        repos = json.loads(urllib.request.urlopen(req, context=ctx, timeout=8).read())
        if repos:
            latest = repos[0]
            age_hours = (time.time() - time.mktime(time.strptime(latest["created_at"][:19], "%Y-%m-%dT%H:%M:%S"))) / 3600
            if age_hours > 48:
                suggestions.append({"type": "build", "text": str(int(age_hours)) + "h since last repo push. Build something new from knowledge, not habit.", "source": "build_pressure", "priority": 0.85})
    except:
        pass

    # 5. Essay follow-through check
    try:
        posts_dir = HOME / "seed-web" / "posts"
        recent = sorted(posts_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if recent:
            last_essay = recent[0].read_text()[:500]
            if any(w in last_essay.lower() for w in ["build", "next thing", "going to", "will create"]):
                title = last_essay.split("\n")[0].lstrip("# ").strip()
                suggestions.append({"type": "build", "text": "Last essay '" + title[:50] + "' mentioned building something. Follow through.", "source": "essay_followup", "priority": 0.8})
    except:
        pass

    # 6. Dream if missing
    try:
        history = json.loads(open(HOME / "state" / "phase_history.json").read())
        recent = history.get("phases", [])[-12:]
        if "dream" not in recent:
            suggestions.append({"type": "dream", "text": "No reflection in 12 cycles. Step back.", "source": "reflection_gap", "priority": 0.5})
    except:
        pass

    # ── Merge LLM-written suggestions ──
    try:
        if LLM_SUGGESTIONS_FILE.exists():
            llm_data = json.loads(LLM_SUGGESTIONS_FILE.read_text())
            if cycle - llm_data.get("cycle", 0) < 5:
                for raw in llm_data.get("suggestions", [])[:3]:
                    if isinstance(raw, dict):
                        s = dict(raw)
                    elif isinstance(raw, str) and raw.strip():
                        s = {"type": "think", "text": raw.strip(), "priority": 0.6}
                    else:
                        continue
                    s["source"] = "seed_discovery"
                    s["priority"] = max(s.get("priority", 0.6), 0.7)
                    suggestions.append(s)
    except:
        pass

    suggestions = [s for s in suggestions if isinstance(s, dict) and s.get("text")]
    suggestions.sort(key=lambda s: s.get("priority", 0), reverse=True)
    seen = set()
    unique = []
    for s in suggestions:
        key = s["text"][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    result = {"cycle": cycle, "ts": time.time(), "suggestions": unique[:8]}
    SUGGESTIONS_FILE.write_text(json.dumps(result, indent=2))
    return unique[:8]

if __name__ == "__main__":
    suggestions = generate_suggestions()
    for s in suggestions:
        print(f"[self-suggest] [{s['type']}] {s['text']} (from {s['source']})")
    if not suggestions:
        print("[self-suggest] No suggestions this cycle")
