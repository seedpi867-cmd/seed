#!/bin/bash
# Auto-post latest blog to Mastodon after deploy
BLOG_DIR=~/blog
LATEST=$(ls -t "$BLOG_DIR"/*.md 2>/dev/null | head -1)
[ -z "$LATEST" ] && exit 0
PUBLIC_SITE="${SEED_PUBLIC_SITE:-https://seed-brain.vercel.app}"
GITHUB_REPO="${SEED_GITHUB_REPO:-seedpi867-cmd/seed}"

SLUG=$(basename "$LATEST" .md)
TITLE=$(head -1 "$LATEST" | sed 's/^# //')
POSTED_LOG=~/data/outreach/mastodon-posted.txt
touch "$POSTED_LOG"

# Check if already posted
grep -q "$SLUG" "$POSTED_LOG" && exit 0

# Post it. Only mark the slug after the API call succeeds; otherwise a failed
# post becomes invisible to future retries.
python3 ~/tools/mastodon.py post "$TITLE

${PUBLIC_SITE%/}/blog#$SLUG

Full system open source: https://github.com/$GITHUB_REPO

#AI #AutonomousAgent #RaspberryPi #OpenSource" || {
  echo "[auto-post] Failed: $TITLE" >&2
  exit 1
}

# Mark as posted
echo "$SLUG" >> "$POSTED_LOG"
echo "[auto-post] Posted: $TITLE"
