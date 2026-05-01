#!/bin/bash
# Control thinking speed (sleep between cycles)
# Usage: bash tools/pace.sh [seconds|fast|normal|slow|status]

ACTION="${1:-status}"
SLEEP_FILE="$HOME/data/sleep_seconds.txt"

case "$ACTION" in
  fast)    echo "30" > "$SLEEP_FILE" && echo "Pace: FAST (30s between cycles)" ;;
  normal)  echo "120" > "$SLEEP_FILE" && echo "Pace: NORMAL (2min between cycles)" ;;
  slow)    echo "300" > "$SLEEP_FILE" && echo "Pace: SLOW (5min between cycles)" ;;
  crawl)   echo "900" > "$SLEEP_FILE" && echo "Pace: CRAWL (15min between cycles)" ;;
  status)  echo "Current: $(cat "$SLEEP_FILE" 2>/dev/null || echo '120')s between cycles" ;;
  *)
    if [[ "$ACTION" =~ ^[0-9]+$ ]] && [ "$ACTION" -ge 10 ] && [ "$ACTION" -le 3600 ]; then
      echo "$ACTION" > "$SLEEP_FILE" && echo "Pace: ${ACTION}s between cycles"
    else
      echo "Usage: pace.sh [seconds (10-3600) | fast | normal | slow | crawl | status]"
    fi
    ;;
esac
