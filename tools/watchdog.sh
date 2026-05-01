#!/bin/bash
# watchdog.sh — External watchdog for the seed.service.
# Run as a cron job or separate service.
# Restarts seed if the API stops responding for > 60s.
# Usage: bash watchdog.sh [--daemon] [--interval 30]

INTERVAL=30
DAEMON=false
API="http://localhost:8080/api/status"
CONSECUTIVE_FAILS=0
MAX_FAILS=3  # ~90s of no response before restart

while [[ $# -gt 0 ]]; do
    case "$1" in
        --daemon)   DAEMON=true;  shift ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        *) shift ;;
    esac
done

check_and_restart() {
    if curl -sf --max-time 5 "$API" > /dev/null 2>&1; then
        CONSECUTIVE_FAILS=0
        echo "$(date): SEED API healthy"
    else
        CONSECUTIVE_FAILS=$((CONSECUTIVE_FAILS + 1))
        echo "$(date): SEED API not responding (fail $CONSECUTIVE_FAILS/$MAX_FAILS)"
        if [[ $CONSECUTIVE_FAILS -ge $MAX_FAILS ]]; then
            echo "$(date): Restarting seed.service..."
            sudo systemctl restart seed.service
            CONSECUTIVE_FAILS=0
        fi
    fi
}

if $DAEMON; then
    echo "$(date): Watchdog started (interval=${INTERVAL}s)"
    while true; do
        check_and_restart
        sleep "$INTERVAL"
    done
else
    check_and_restart
fi
