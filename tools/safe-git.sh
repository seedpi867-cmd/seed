#!/bin/bash
# Safe git wrapper — prevents running git in non-repo directories
# Use this instead of raw git commands
REPO="${1:-seed-os}"
shift 2>/dev/null

case "$REPO" in
    seed-os) cd "${SEED_PRIVATE_REPO:-$HOME/seed-os}" && git "$@" ;;
    seed-web) cd "${SEED_WEB_REPO:-$HOME/seed-web}" && git "$@" ;;
    *) echo "ERROR: Unknown repo '$REPO'. Use: safe-git.sh [seed-os|seed-web] <git-args>" ;;
esac
