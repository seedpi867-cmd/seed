#!/bin/bash
# Self-maintenance — compaction, cleanup, disk management
# Runs daily via cron AND at start of each brain cycle

HOME_DIR="$HOME"
DATA="$HOME_DIR/data"
BLOG="$HOME_DIR/blog"
LOGS="$DATA/logs"

# ── MEMORY COMPACTION ──────────────────────────
# Keep last 200 lines in memory.md, archive the rest
MEM="$DATA/memory.md"
ARCHIVE="$DATA/memory-archive.md"
if [ -f "$MEM" ]; then
    LINES=$(wc -l < "$MEM")
    if [ "$LINES" -gt 200 ]; then
        HEAD=$((LINES - 200))
        head -n "$HEAD" "$MEM" >> "$ARCHIVE"
        tail -n 200 "$MEM" > /tmp/mem_compact.tmp
        mv /tmp/mem_compact.tmp "$MEM"
        echo "[maintain] Memory compacted: archived $HEAD lines"
    fi
fi

# ── DREAM COMPACTION ───────────────────────────
# Keep last 100 lines in dreams.md
DREAMS="$DATA/dreams.md"
if [ -f "$DREAMS" ]; then
    LINES=$(wc -l < "$DREAMS")
    if [ "$LINES" -gt 100 ]; then
        tail -n 100 "$DREAMS" > /tmp/dream_compact.tmp
        mv /tmp/dream_compact.tmp "$DREAMS"
        echo "[maintain] Dreams compacted to 100 lines"
    fi
fi

# ── TASK CLEANUP ───────────────────────────────
# Remove Done items older than 20 cycles
TASKS="$DATA/tasks.md"
if [ -f "$TASKS" ]; then
    LINES=$(wc -l < "$TASKS")
    if [ "$LINES" -gt 100 ]; then
        # Keep header + Now + Next + last 20 Done items
        python3 -c "
lines = open('$TASKS').readlines()
out = []
done_count = 0
in_done = False
for l in lines:
    if '## Done' in l:
        in_done = True
        out.append(l)
        continue
    if in_done:
        done_count += 1
        if done_count <= 20:
            out.append(l)
    else:
        out.append(l)
open('$TASKS','w').writelines(out)
" 2>/dev/null
        echo "[maintain] Tasks cleaned"
    fi
fi

# ── LOG ROTATION ───────────────────────────────
ls -t "$LOGS"/cycle_*.log 2>/dev/null | tail -n +101 | xargs rm -f 2>/dev/null
echo "[maintain] Logs: kept last 100"

# ── DISK SPACE CHECK ───────────────────────────
DISK_PCT=$(df / | awk 'NR==2{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt 80 ]; then
    echo "[maintain] WARNING: Disk at ${DISK_PCT}%"
    # Clean old logs aggressively
    ls -t "$LOGS"/cycle_*.log 2>/dev/null | tail -n +20 | xargs rm -f 2>/dev/null
    # Clean old memory archive if huge
    if [ -f "$ARCHIVE" ]; then
        ALINES=$(wc -l < "$ARCHIVE")
        if [ "$ALINES" -gt 500 ]; then
            tail -n 200 "$ARCHIVE" > /tmp/archive_compact.tmp
            mv /tmp/archive_compact.tmp "$ARCHIVE"
            echo "[maintain] Archive compacted to 200 lines"
        fi
    fi
    # Clean apt cache
    sudo apt-get clean 2>/dev/null
    echo "[maintain] Cleaned apt cache"
fi

# ── RAM CHECK ──────────────────────────────────
MEM_PCT=$(free | awk 'NR==2{printf "%.0f", $3/$2*100}')
if [ "$MEM_PCT" -gt 80 ]; then
    echo "[maintain] WARNING: RAM at ${MEM_PCT}%"
    # Clear filesystem cache
    sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1
    echo "[maintain] Cleared fs cache"
fi

echo "[maintain] Done. Disk: ${DISK_PCT}% RAM: ${MEM_PCT}%"
