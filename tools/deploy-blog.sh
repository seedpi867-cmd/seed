#!/bin/bash
# Deploy blog posts to your-seed-website.vercel.app.
set -euo pipefail

bash ~/tools/build-timeline.sh 2>/dev/null
cp ~/data/token-totals.json ~/seed-web/ 2>/dev/null
cd ~/seed-web || { echo '[deploy] No seed-web repo. Clone it first.'; exit 1; }

shopt -s nullglob
posts=(~/blog/*.md)
if (( ${#posts[@]} == 0 )); then
    echo '[deploy] No local blog posts to copy'
else
    cp -p "${posts[@]}" posts/
fi

python3 - <<'PY'
import json
import time
from pathlib import Path

posts = []
for path in sorted(Path("posts").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
    content = path.read_text()
    title = content.split("\n", 1)[0].lstrip("# ").strip() if content.startswith("#") else path.stem.replace("-", " ").title()
    # Extract description: prefer ## What This Changes section, else closing insight
    lines = content.split("\n")
    desc = ""
    # Look for ## What This Changes section
    wtc_start = -1
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## what this change"):
            wtc_start = i + 1
            break
    if wtc_start > 0:
        # Grab content from that section until next ## or end
        buf = []
        for line in lines[wtc_start:]:
            s = line.strip()
            if s.startswith("## "):
                break
            if s and not s.startswith(">") and not s.startswith("**How"):
                buf.append(s)
        desc = " ".join(buf)[:250]
    if not desc or len(desc) < 30:
        # Fallback: last substantial paragraph
        paras = []
        buf = []
        for line in lines[-20:]:
            s = line.strip()
            if s == "" or s == "---":
                if buf: paras.append(" ".join(buf)); buf = []
            elif not s.startswith(">") and not s.startswith("#"):
                buf.append(s)
        if buf: paras.append(" ".join(buf))
        paras = [p for p in paras if len(p) > 40]
        desc = max(paras, key=len)[:250] if paras else title
    # Extract date from content first, fall back to mtime
    date = None
    import re as _re
    content_head = content[:500]
    for _p in [r'(\d{4}-\d{2}-\d{2})', r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})']:
        _m = _re.search(_p, content_head)
        if _m:
            _ds = _m.group(1)
            for _fmt in ['%Y-%m-%d', '%d %B %Y']:
                try:
                    from datetime import datetime as _dt
                    date = _dt.strptime(_ds, _fmt).strftime('%Y-%m-%d')
                    break
                except: continue
        if date: break
    if not date:
        # Try filename timestamp
        _ts_m = _re.match(r'^(\d{10})-', path.name)
        if _ts_m:
            date = time.strftime('%Y-%m-%d', time.localtime(int(_ts_m.group(1))))
    if not date:
        date = time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))
    posts.append({
        "title": title,
        "slug": path.stem,
        "date": date,
        "tags": ["seed", "autonomy"],
        "description": desc[:150],
    })

Path("posts/index.json").write_text(json.dumps(posts, indent=2) + "\n")
print(f"[deploy] Index rebuilt: {len(posts)} posts")
PY

git add -A
mapfile -t changed_slugs < <(
    git diff --cached --name-only -- 'posts/*.md' |
    while IFS= read -r path; do
        basename "${path%.md}"
    done
)

verify_changed_posts() {
    if (( ${#changed_slugs[@]} == 0 )); then
        return 0
    fi

    for slug in "${changed_slugs[@]}"; do
        title="$(sed -n '1s/^# *//p' "posts/${slug}.md")"
        echo "[deploy] Verifying remote post: ${slug}"
        ~/tools/verify-blog-live.sh "$slug" "$title"
    done
}

has_unpushed_commits() {
    bash ~/tools/git_ops.sh status "$PWD" | grep -q '\[ahead '
}

if git diff --cached --quiet; then
    if has_unpushed_commits; then
        git push origin main && echo "[deploy] Pushed to Vercel" || { echo "[deploy] Push failed"; exit 1; }
    else
        echo "[deploy] No changes to deploy"
    fi
else
    git commit -m "SEED blog update - $(date '+%Y-%m-%d')"
    git push origin main && echo "[deploy] Pushed to Vercel" || { echo "[deploy] Push failed"; exit 1; }
    verify_changed_posts
fi

bash ~/tools/auto-post-mastodon.sh 2>/dev/null
