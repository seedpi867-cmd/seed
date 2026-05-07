#!/bin/bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CYCLE="${1:-}"
OLD_PIDS_ARG="${2:-}"
WAIT_SECONDS="${3:-3600}"
OUT="$ROOT/data/logs/wake-gate-restart.log"

if [ -z "$CYCLE" ] || [ -z "$OLD_PIDS_ARG" ]; then
    echo "usage: $0 <cycle> <old-brain-loop-pid[,extra-pid...]> [wait-seconds]" >&2
    exit 2
fi

LOG="$ROOT/data/logs/cycle_${CYCLE}.log"
DEADLINE=$(( $(date +%s) + WAIT_SECONDS ))

OLD_PIDS=$(printf '%s' "$OLD_PIDS_ARG" | tr ',' ' ')

echo "$(date -Iseconds) waiting for Cycle $CYCLE to close before replacing brain-loop PID(s) $OLD_PIDS" >> "$OUT"

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if grep -q "\[seed\] Cycle ${CYCLE} .* complete" "$LOG" 2>/dev/null; then
        echo "$(date -Iseconds) Cycle $CYCLE complete; restarting brain loop" >> "$OUT"
        for OLD_PID in $OLD_PIDS; do
            if kill -0 "$OLD_PID" 2>/dev/null; then
                kill "$OLD_PID" 2>/dev/null || true
            fi
        done
        sleep 3
        rm -rf /tmp/seed-brain.lock
        cd "$ROOT" || exit 1
        nohup bash brain-loop.sh >> "$ROOT/data/logs/brain-stdout.log" 2>&1 &
        echo "$(date -Iseconds) restart launched from PID $$" >> "$OUT"
        exit 0
    fi
    sleep 5
done

echo "$(date -Iseconds) restart skipped: Cycle $CYCLE completion not observed within ${WAIT_SECONDS}s" >> "$OUT"
exit 1
