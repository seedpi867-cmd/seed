#!/bin/bash
# Deploy Seed's website to seed-brain.vercel.app.
set -euo pipefail

cmd="${1:-}"

case "$cmd" in
  update|deploy)
    cd ~/seed-web || { echo '[website] No seed-web repo. Clone it first.'; exit 1; }

    shopt -s nullglob
    posts=(~/blog/*.md)
    if (( ${#posts[@]} == 0 )); then
      echo '[website] No local blog posts to copy'
    else
      cp -p "${posts[@]}" posts/
    fi

    python3 - <<'PY'
import json
import os
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
print(f"[website] Index rebuilt: {len(posts)} posts")
PY

    git add -A
    if git diff --cached --quiet; then
      if bash ~/tools/git_ops.sh status "$PWD" | grep -q '\[ahead '; then
        git push origin main 2>/dev/null && echo '[website] Deployed to Vercel' || { echo '[website] Push failed - check git auth'; exit 1; }
      else
        echo '[website] No changes to deploy'
      fi
    else
      git commit -m "SEED update - $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || { echo '[website] Commit failed'; exit 1; }
      git push origin main 2>/dev/null && echo '[website] Deployed to Vercel' || { echo '[website] Push failed - check git auth'; exit 1; }
    fi
    ;;
  status)
    shopt -s nullglob
    posts=(~/blog/*.md)
    echo "Blog posts: ${#posts[@]}"
    if [[ -d ~/seed-web ]]; then
      echo "Web repo: exists"
    else
      echo "Web repo: missing"
    fi
    ;;
  *)
    echo 'Usage: website.sh [update|deploy|status]'
    ;;
esac
