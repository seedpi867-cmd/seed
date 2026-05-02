#!/bin/bash
# Rollback a file to a previous cycle's snapshot
# Usage: rollback.sh PROMPT.md 45  (rolls back PROMPT.md to cycle 45 snapshot)
FILE=$1
CYCLE=$2

if [ -z "$FILE" ] || [ -z "$CYCLE" ]; then
    echo "Usage: rollback.sh <filename> <cycle>"
    echo "Available snapshots:"
    ls ~/data/snapshots/*.cycle-* 2>/dev/null | sed 's|.*/||'
    exit 1
fi

SNAP=~/data/snapshots/${FILE}.cycle-${CYCLE}
if [ ! -f "$SNAP" ]; then
    echo "No snapshot found: $SNAP"
    echo "Available for $FILE:"
    ls ~/data/snapshots/${FILE}.cycle-* 2>/dev/null | sed 's|.*/||'
    exit 1
fi

TARGET=$(find ~ -maxdepth 2 -name "$FILE" -type f | head -1)
if [ -z "$TARGET" ]; then
    echo "Can't find $FILE in home directory"
    exit 1
fi

cp "$SNAP" "$TARGET"
echo "Rolled back $FILE to cycle $CYCLE snapshot"
