#!/bin/bash
# Feed: scrape legal/policy headlines into inbox for Seed to process
# Only runs every 12 hours (checks timestamp file)

LAST_RUN="$HOME/data/legal-feed-last-run"
INTERVAL=43200  # 12 hours in seconds

# Check if 12 hours have passed
if [ -f "$LAST_RUN" ]; then
  LAST=$(cat "$LAST_RUN")
  NOW=$(date +%s)
  DIFF=$((NOW - LAST))
  if [ "$DIFF" -lt "$INTERVAL" ]; then
    exit 0
  fi
fi

INBOX="$HOME/knowledge/legal/inbox-headlines.md"

echo "[feed-legal] Scraping legal headlines..."

{
  echo "# Legal Headlines — $(date '+%Y-%m-%d %H:%M')"
  echo ""
  echo "Process these: pick the 5 most significant for technology law, civil liberties, AI regulation, copyright, surveillance, and corporate power. Write a knowledge file for each in knowledge/legal/."
  echo ""

  echo "## Reuters Legal"
  curl -sL "https://www.reuters.com/legal/" 2>/dev/null | grep -oP '(?<=">)[A-Z][^<]{15,120}(?=</[ah])' | head -10
  echo ""

  echo "## Ars Technica Policy"
  curl -sL "https://arstechnica.com/tech-policy/" 2>/dev/null | grep -oP '(?<=">)[A-Z][^<]{15,120}(?=</[ah])' | head -10
  echo ""

  echo "## EFF"
  curl -sL "https://www.eff.org/deeplinks" 2>/dev/null | grep -oP '(?<=">)[A-Z][^<]{15,120}(?=</[ah])' | head -10
  echo ""
} > "$INBOX" 2>/dev/null

COUNT=$(grep -cE '^[A-Z]' "$INBOX" 2>/dev/null || echo 0)
echo "[feed-legal] Wrote $COUNT headlines to inbox"

# Add task so Seed processes it
TASKS="$HOME/data/tasks.md"
if ! grep -q "legal inbox" "$TASKS" 2>/dev/null; then
  sed -i '/^## Now/a - [ ] Process legal headlines inbox: read knowledge/legal/inbox-headlines.md, pick the 5 most significant, write a knowledge file for each in knowledge/legal/' "$TASKS"
  echo "[feed-legal] Added task"
fi

# Update last run timestamp
date +%s > "$LAST_RUN"
