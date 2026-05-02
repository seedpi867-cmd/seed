#!/bin/bash
# Change logger — tracks all file modifications for rollback
# Runs via inotifywait or as a periodic snapshot
LOG=~/data/changelog.jsonl
SNAPSHOT_DIR=~/data/snapshots

mkdir -p "$SNAPSHOT_DIR"

# Snapshot key files
for f in ~/data/token-totals.json ~/data/lessons.md ~/data/errors.md ~/PROMPT.md ~/brain-loop.sh ~/data/goals.md ~/data/tasks.md ~/data/mood.json ~/data/beliefs.md ~/data/habits.md ~/data/self-model.md ~/webserver.py; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    current_hash=$(md5sum "$f" | cut -d' ' -f1)
    last_hash=$(cat "$SNAPSHOT_DIR/${name}.hash" 2>/dev/null)

    if [ "$current_hash" != "$last_hash" ]; then
        # File changed — log it and save snapshot
        cycle=$(cat ~/data/cycle.txt 2>/dev/null || echo 0)
        ts=$(date -Iseconds)
        size=$(wc -c < "$f")

        # Save snapshot for rollback
        cp "$f" "$SNAPSHOT_DIR/${name}.cycle-${cycle}"
        echo "$current_hash" > "$SNAPSHOT_DIR/${name}.hash"

        # Log the change
        echo "{\"ts\":\"$ts\",\"cycle\":$cycle,\"file\":\"$name\",\"hash\":\"$current_hash\",\"size\":$size}" >> "$LOG"
        echo "[changelog] $name changed at cycle $cycle"
    fi
done

# Keep only last 50 snapshots per file
for name in lessons.md errors.md PROMPT.md brain-loop.sh goals.md tasks.md mood.json beliefs.md habits.md self-model.md webserver.py; do
    ls -t "$SNAPSHOT_DIR/${name}.cycle-"* 2>/dev/null | tail -n +51 | xargs rm -f 2>/dev/null
done

# Keep changelog under 5000 lines
if [ -f "$LOG" ]; then
    lines=$(wc -l < "$LOG")
    if [ "$lines" -gt 5000 ]; then
        tail -n 3000 "$LOG" > /tmp/changelog.tmp
        mv /tmp/changelog.tmp "$LOG"
    fi
fi
