#!/bin/bash
# Verify a blog post is live on the configured public Seed website.
set -euo pipefail

BASE_URL="${SEED_BLOG_URL:-${SEED_PUBLIC_SITE:-https://seed-brain.vercel.app}}"
SLUG="${1:-}"
EXPECTED_TEXT="${2:-}"
ATTEMPTS="${VERIFY_ATTEMPTS:-12}"
SLEEP_SECONDS="${VERIFY_SLEEP_SECONDS:-10}"

usage() {
    echo "usage: $0 <post-slug> [expected-text]" >&2
}

if [[ -z "$SLUG" ]]; then
    usage
    exit 2
fi

POST_URL="${BASE_URL%/}/posts/${SLUG}.md"
INDEX_URL="${BASE_URL%/}/posts/index.json"

for ((attempt = 1; attempt <= ATTEMPTS; attempt++)); do
    post_body="$(curl -fsSL "$POST_URL" 2>/dev/null || true)"
    index_body="$(curl -fsSL "$INDEX_URL" 2>/dev/null || true)"

    post_ok=0
    index_ok=0

    if [[ -n "$post_body" ]]; then
        if [[ -z "$EXPECTED_TEXT" || "$post_body" == *"$EXPECTED_TEXT"* ]]; then
            post_ok=1
        fi
    fi

    if [[ "$index_body" == *"\"slug\": \"${SLUG}\""* ]]; then
        index_ok=1
    fi

    if (( post_ok && index_ok )); then
        echo "[verify] live: $POST_URL"
        echo "[verify] index contains slug: $SLUG"
        exit 0
    fi

    if (( attempt < ATTEMPTS )); then
        echo "[verify] waiting for deploy attempt $attempt/$ATTEMPTS: post_ok=$post_ok index_ok=$index_ok"
        sleep "$SLEEP_SECONDS"
    fi
done

echo "[verify] remote verification failed for slug: $SLUG" >&2
echo "[verify] checked post: $POST_URL" >&2
echo "[verify] checked index: $INDEX_URL" >&2
exit 1
