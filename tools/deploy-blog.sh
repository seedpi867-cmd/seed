#!/bin/bash
# Deploy blog posts to your-seed-website.vercel.app.
set -euo pipefail

WEB_REPO="${SEED_WEB_REPO:-$HOME/seed-web}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BLOG_DIR="${SEED_BLOG_DIR:-$ROOT/blog}"
DATA_DIR="${SEED_DATA_DIR:-$ROOT/data}"

SEED_ROOT="$ROOT" SEED_BLOG_DIR="$BLOG_DIR" SEED_WEB_REPO="$WEB_REPO" \
    bash "$ROOT/tools/build-timeline.sh" 2>/dev/null
cp "$DATA_DIR/token-totals.json" "$WEB_REPO"/ 2>/dev/null
cd "$WEB_REPO" || { echo "[deploy] No website repo at $WEB_REPO. Set SEED_WEB_REPO or clone it first."; exit 1; }

shopt -s nullglob
posts=("$BLOG_DIR"/*.md)
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

run_credential_claim_gate() {
    if (( ${#changed_slugs[@]} == 0 )); then
        return 0
    fi

    local gate="$ROOT/tools/credential_claim_gate.py"
    if [[ ! -f "$gate" ]]; then
        echo "[claim-gate] warning-only: scanner missing at $gate"
        return 0
    fi

    local slug post_path scan_output scan_status decision
    for slug in "${changed_slugs[@]}"; do
        post_path="posts/${slug}.md"
        scan_status=0
        scan_output="$(python3 "$gate" "$post_path" 2>&1)" || scan_status=$?
        decision="$(printf '%s' "$scan_output" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("decision", "unknown"))' 2>/dev/null || true)"
        if [[ -z "$decision" ]]; then
            decision="error"
        fi
        case "$decision" in
            block)
                echo "[claim-gate] blocking publish: ${slug} decision=block"
                return 2
                ;;
            warn)
                echo "[claim-gate] warning: ${slug} decision=warn"
                ;;
        esac
        if (( scan_status != 0 && scan_status != 2 )); then
            echo "[claim-gate] warning-only: scanner error for ${slug}"
        fi
    done
}

run_credential_claim_gate

verify_changed_posts() {
    if (( ${#changed_slugs[@]} == 0 )); then
        return 0
    fi

    for slug in "${changed_slugs[@]}"; do
        title="$(sed -n '1s/^# *//p' "posts/${slug}.md")"
        echo "[deploy] Verifying remote post: ${slug}"
        "$ROOT/tools/verify-blog-live.sh" "$slug" "$title"
    done
}

has_unpushed_commits() {
    bash "$ROOT/tools/git_ops.sh" status "$PWD" | grep -q '\[ahead '
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

bash "$ROOT/tools/auto-post-mastodon.sh" 2>/dev/null
