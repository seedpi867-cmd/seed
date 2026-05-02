#!/bin/bash
# git_ops.sh — Git helper for the SEED agent.
# Usage: bash git_ops.sh <clone|pull|status|repos|log|init|diff> [args]

set -euo pipefail
CMD="${1:-status}"
shift || true

repo_status() {
  local dir="$1"
  if [ -d "$dir/.git" ]; then
    printf '[git] %s\n' "$dir"
    git -C "$dir" status --short --branch
  else
    printf '[git] missing repo: %s\n' "$dir" >&2
    return 1
  fi
}

known_repos_status() {
  local rc=0
  repo_status "$HOME/seed-os" || rc=1
  repo_status "$HOME/seed-web" || rc=1
  return "$rc"
}

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
    if [ "$#" -eq 0 ]; then
      known_repos_status
    else
      DIR="$1"
      repo_status "$DIR"
    fi
    ;;
  repos)
    known_repos_status
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
    echo "Commands: clone, pull, status, repos, log, init, diff" >&2
    exit 1
    ;;
esac
