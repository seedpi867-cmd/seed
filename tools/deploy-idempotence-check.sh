#!/bin/bash
# Verify that the blog deploy pipeline settles to a clean no-op.

set -euo pipefail

WEB="${SEED_WEB_REPO:-$HOME/seed-web}"
DEPLOY="${DEPLOY_BLOG_SCRIPT:-$HOME/tools/deploy-blog.sh}"

if [[ ! -d "$WEB/.git" ]]; then
    echo "[deploy-check] Missing git repo: $WEB" >&2
    exit 1
fi

if [[ ! -x "$DEPLOY" ]]; then
    echo "[deploy-check] Missing executable deploy script: $DEPLOY" >&2
    exit 1
fi

"$DEPLOY"
"$DEPLOY"

status="$(git -C "$WEB" status --short)"
if [[ -n "$status" ]]; then
    echo "[deploy-check] Deploy pipeline left a dirty worktree:" >&2
    printf '%s\n' "$status" >&2
    exit 1
fi

echo "[deploy-check] Deploy pipeline is idempotent"
