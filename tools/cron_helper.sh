#!/bin/bash
# cron_helper.sh — Add, list, or remove cron jobs for the seed user.
# Usage: bash cron_helper.sh list
#        bash cron_helper.sh add "*/5 * * * * /home/seedpi2w/seed/scripts/system_monitor.py --once"
#        bash cron_helper.sh remove "system_monitor"

CMD="${1:-list}"
shift || true

case "$CMD" in
  list)
    crontab -l 2>/dev/null || echo "(no crontab)"
    ;;
  add)
    ENTRY="${1:?Usage: cron_helper.sh add '<cron expression>'}"
    (crontab -l 2>/dev/null; echo "$ENTRY") | sort -u | crontab -
    echo "Added: $ENTRY"
    ;;
  remove)
    PATTERN="${1:?Usage: cron_helper.sh remove '<pattern>'}"
    TMP=$(mktemp)
    crontab -l 2>/dev/null | grep -v "$PATTERN" > "$TMP" || true
    crontab "$TMP"
    rm "$TMP"
    echo "Removed entries matching: $PATTERN"
    ;;
  run)
    # Run a script directly
    bash "${@}"
    ;;
  *)
    echo "Unknown: $CMD (use list|add|remove|run)" >&2
    exit 1
    ;;
esac
