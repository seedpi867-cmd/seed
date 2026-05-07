#!/bin/bash
# Safe git wrapper — prevents running git in non-repo directories
# Use this instead of raw git commands
REPO="${1:-seed-os}"
shift 2>/dev/null

case "$REPO" in
    seed-os) cd ~/seed-os && git "$@" ;;
    seed-web) cd ~/seed-web && git "$@" ;;
    *) echo "ERROR: Unknown repo '$REPO'. Use: safe-git.sh [seed-os|seed-web] <git-args>" ;;
esac
