#!/bin/bash
# Pick a random Tinfoil Hat transcript and drop it in context.
set -euo pipefail

ROOT="${TRANSCRIPT_ROOT:-$HOME/knowledge/transcripts}"
OUT="${TRANSCRIPT_CONTEXT_OUT:-$HOME/context/transcript.md}"
PRIMARY="${TRANSCRIPT_PRIMARY:-$ROOT/podscripts_transcripts}"
NESTED="${TRANSCRIPT_NESTED:-$PRIMARY/podscripts_transcripts}"

if [[ ! -d "$ROOT" ]]; then
    echo "[feeder] Transcript root missing: $ROOT" >&2
    exit 1
fi

files=()
declare -A seen_basenames=()

while IFS= read -r -d '' file; do
    base="$(basename "$file")"
    seen_basenames["$base"]=1
    files+=("$file")
done < <(find "$ROOT" -type f -name '*.txt' ! -path "$NESTED/*" -print0 | sort -z)

while IFS= read -r -d '' file; do
    base="$(basename "$file")"
    if [[ -n "${seen_basenames[$base]:-}" ]]; then
        continue
    fi
    seen_basenames["$base"]=1
    files+=("$file")
done < <(find "$ROOT" -type f -name '*.txt' -path "$NESTED/*" -print0 | sort -z)

if (( ${#files[@]} == 0 )); then
    echo "[feeder] No transcript .txt files found under $ROOT" >&2
    exit 1
fi

file="${files[RANDOM % ${#files[@]}]}"
file_base="$(basename "$file")"
base="$(basename "$file" .txt)"
title="$(printf '%s\n' "$base" | sed 's/-/ /g; s/^[0-9][0-9]* //')"
hash="$(sha256sum -- "$file" | awk '{print $1}')"
bytes="$(wc -c < "$file" | awk '{print $1}')"
source_tier="primary-or-outside"
source_note="selected from primary/outside transcript paths"

if [[ -d "$NESTED" && "$file" == "$NESTED/"* ]]; then
    source_tier="nested-only"
    source_note="selected from nested archive because no primary/outside transcript shares this basename"
elif [[ -f "$NESTED/$file_base" ]]; then
    nested_hash="$(sha256sum -- "$NESTED/$file_base" | awk '{print $1}')"
    if [[ "$nested_hash" == "$hash" ]]; then
        source_note="selected from primary/outside paths; a byte-identical nested duplicate exists and was deprioritised"
    else
        source_tier="primary-with-nested-conflict"
        source_note="selected from primary/outside paths; nested file with same basename has different content"
    fi
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

{
    printf '## Transcript: %s\n' "$title"
    printf 'Source path: `%s`\n' "$file"
    printf 'Source tier: %s\n' "$source_tier"
    printf 'Source note: %s\n' "$source_note"
    printf 'Source bytes: %s\n' "$bytes"
    printf 'Source sha256: `%s`\n\n' "$hash"
    head -n 200 "$file"
} > "$tmp"

mkdir -p "$(dirname "$OUT")"
mv "$tmp" "$OUT"
trap - EXIT

echo "[feeder] Loaded: $title"
