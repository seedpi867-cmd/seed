#!/bin/bash
# Safe self-restart for brain-loop.sh
# Seed can call this when it needs to restart its own loop after modifying it.
# Saves current state so it wakes up knowing what it just did.

ROOT="$HOME"
DATA="$ROOT/data"
STATE="$ROOT/state"

# Save restart context
CYCLE=$(cat "$DATA/cycle.txt" 2>/dev/null || echo 0)
cat > "$DATA/restart-context.md" << CTX
# Restart Context — Cycle $CYCLE

I restarted my own loop at $(date '+%Y-%m-%d %H:%M:%S').

## Why I Restarted
$(cat "$DATA/restart-reason.txt" 2>/dev/null || echo "No reason recorded. Check inner-voice.md for context.")

## What I Was Doing
$(cat "$DATA/live-summary.md" 2>/dev/null || echo "Unknown")

## Last Inner Voice
$(tail -3 "$DATA/inner-voice.md" 2>/dev/null || echo "Unknown")

## What I Should Do Next
Read this file. I just modified my own brain-loop.sh and needed a restart to pick up changes.
Continue from where I left off. Check data/tasks.md for the current task.
CTX

echo "[safe-restart] Context saved for cycle $CYCLE"

# Add restart context to working memory so next cycle sees it
if [ -f "$STATE/working_memory.txt" ]; then
    echo "" >> "$STATE/working_memory.txt"
    echo "## RESTART NOTICE" >> "$STATE/working_memory.txt"
    echo "I restarted my own loop last cycle to pick up changes to brain-loop.sh." >> "$STATE/working_memory.txt"
    echo "Read data/restart-context.md for full details of what I was doing." >> "$STATE/working_memory.txt"
fi

# Kill the current brain loop (which is our parent process)
# The lock file gets cleaned up, then we relaunch
LOCK="/tmp/seed-brain.lock"

# Give parent time to flush
sync
sleep 2

# Kill the brain loop (our grandparent)
BRAIN_PID=$(pgrep -f "bash.*brain-loop.sh" | grep -v $$ | head -1)
if [ -n "$BRAIN_PID" ]; then
    echo "[safe-restart] Killing brain loop PID $BRAIN_PID"
    kill "$BRAIN_PID" 2>/dev/null
    sleep 3
    # Force if still alive
    kill -9 "$BRAIN_PID" 2>/dev/null
fi

# Kill any orphan codex
pkill -f codex 2>/dev/null
sleep 2

# Clean lock
rm -f "$LOCK" /tmp/seed-brain.lock

# Relaunch
echo "[safe-restart] Relaunching brain loop"
cd "$ROOT"
nohup bash brain-loop.sh >> "$DATA/logs/brain-stdout.log" 2>&1 &
echo "[safe-restart] New loop started (PID $!)"
