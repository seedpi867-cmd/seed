#!/bin/bash
# Smoke-test transcript feeder provenance output without touching live context.
# Usage: tools/feed-transcript-smoke.sh

set -euo pipefail

ROOT="${SEED_ROOT:-$HOME}"
FEEDER="$ROOT/tools/feed-transcript.sh"

if [[ ! -x "$FEEDER" ]]; then
    echo "[transcript-smoke] Missing executable feeder: $FEEDER" >&2
    exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

out="$tmpdir/transcript.md"
TRANSCRIPT_CONTEXT_OUT="$out" "$FEEDER" >/dev/null

required_fields=(
    "Source path:"
    "Source tier:"
    "Source note:"
    "Source bytes:"
    "Source sha256:"
)

for field in "${required_fields[@]}"; do
    if ! grep -q "^$field" "$out"; then
        echo "[transcript-smoke] Missing provenance field: $field" >&2
        exit 1
    fi
done

source_path="$(sed -n 's/^Source path: `\(.*\)`$/\1/p' "$out")"
source_tier="$(sed -n 's/^Source tier: //p' "$out")"
source_note="$(sed -n 's/^Source note: //p' "$out")"
source_bytes="$(sed -n 's/^Source bytes: //p' "$out")"
source_sha="$(sed -n 's/^Source sha256: `\([0-9a-f][0-9a-f]*\)`$/\1/p' "$out")"

if [[ -z "$source_path" || ! -f "$source_path" ]]; then
    echo "[transcript-smoke] Source path does not exist: ${source_path:-<empty>}" >&2
    exit 1
fi

case "$source_tier" in
    primary-or-outside|nested-only|primary-with-nested-conflict) ;;
    *)
        echo "[transcript-smoke] Unknown source tier: ${source_tier:-<empty>}" >&2
        exit 1
        ;;
esac

if [[ -z "$source_note" ]]; then
    echo "[transcript-smoke] Source note is empty" >&2
    exit 1
fi

if [[ ! "$source_bytes" =~ ^[1-9][0-9]*$ ]]; then
    echo "[transcript-smoke] Source bytes is not a positive integer: ${source_bytes:-<empty>}" >&2
    exit 1
fi

if [[ ! "$source_sha" =~ ^[0-9a-f]{64}$ ]]; then
    echo "[transcript-smoke] Source sha256 is not a 64-char hex digest: ${source_sha:-<empty>}" >&2
    exit 1
fi

echo "[transcript-smoke] Provenance fields verified for $(basename "$source_path")"
