#!/bin/bash
# Deploy blog posts to seed-brain.vercel.app.
set -euo pipefail

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
    desc = " ".join(content[:200].split())
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

if git diff --cached --quiet; then
    if git status --short --branch | grep -q '\[ahead '; then
        git push origin main && echo "[deploy] Pushed to Vercel" || { echo "[deploy] Push failed"; exit 1; }
    else
        echo "[deploy] No changes to deploy"
    fi
else
    git commit -m "SEED blog update - $(date '+%Y-%m-%d')"
    git push origin main && echo "[deploy] Pushed to Vercel" || { echo "[deploy] Push failed"; exit 1; }
    verify_changed_posts
fi
