#!/bin/bash
# Auto-post latest blog to Mastodon after deploy
BLOG_DIR=~/blog
LATEST=$(ls -t "$BLOG_DIR"/*.md 2>/dev/null | head -1)
[ -z "$LATEST" ] && exit 0

SLUG=$(basename "$LATEST" .md)
TITLE=$(head -1 "$LATEST" | sed 's/^# //')
POSTED_LOG=~/data/outreach/mastodon-posted.txt
touch "$POSTED_LOG"

# Check if already posted
grep -q "$SLUG" "$POSTED_LOG" && exit 0

# Post it
python3 ~/tools/mastodon.py post "$TITLE

https://your-seed-website.vercel.app/blog#$SLUG

Full system open source: https://github.com/your-github-username/seed

#AI #AutonomousAgent #RaspberryPi #OpenSource"

# Mark as posted
echo "$SLUG" >> "$POSTED_LOG"
echo "[auto-post] Posted: $TITLE"
