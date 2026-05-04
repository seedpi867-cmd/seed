#!/bin/bash
# Feed: discover AI agent repos on GitHub
# Writes to context/agent-repos.md for Seed to read each cycle

OUT="$HOME/context/agent-repos.md"
echo "## AI Agent Repos — $(date '+%Y-%m-%d %H:%M')" > "$OUT"
echo >> "$OUT"

python3 "$HOME/tools/feed-github-agents.py" >> "$OUT" 2>/dev/null

echo "[feed-github-agents] $(grep -c '###' "$OUT") repos found"
