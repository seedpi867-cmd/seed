#!/bin/bash
# Manage Seed's own cron jobs
# Usage: manage-cron.sh add "*/10 * * * * /home/seed/tools/something.sh"
# Usage: manage-cron.sh remove "something.sh"
# Usage: manage-cron.sh list

case "$1" in
    add)
        (crontab -l 2>/dev/null; echo "$2") | sort -u | crontab -
        echo "Added: $2"
        ;;
    remove)
        crontab -l 2>/dev/null | grep -v "$2" | crontab -
        echo "Removed crons matching: $2"
        ;;
    list)
        crontab -l 2>/dev/null
        ;;
    *)
        echo "Usage: manage-cron.sh [add|remove|list] [cron-expression]"
        ;;
esac
