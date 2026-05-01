#!/bin/bash
# git_ops.sh — Git helper for the SEED agent.
# Usage: bash git_ops.sh <clone|pull|status|log|init> [url] [dir]

set -euo pipefail
CMD="${1:-status}"
shift || true

case "$CMD" in
  clone)
    URL="${1:?Usage: git_ops.sh clone <url> [dir]}"
    DIR="${2:-$(basename "$URL" .git)}"
    git clone "$URL" "$DIR"
    echo "Cloned $URL → $DIR"
    ;;
  pull)
    DIR="${1:-.}"
    git -C "$DIR" pull --ff-only
    echo "Pulled $DIR"
    ;;
  status)
    DIR="${1:-.}"
    git -C "$DIR" status --short
    ;;
  log)
    DIR="${1:-.}"
    N="${2:-10}"
    git -C "$DIR" log --oneline -"$N"
    ;;
  init)
    DIR="${1:-.}"
    git -C "$DIR" init
    echo "Initialised git in $DIR"
    ;;
  diff)
    DIR="${1:-.}"
    git -C "$DIR" diff --stat
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Commands: clone, pull, status, log, init, diff" >&2
    exit 1
    ;;
esac
