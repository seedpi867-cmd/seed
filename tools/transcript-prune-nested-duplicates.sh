#!/bin/bash
# Print or execute safe removals for nested transcript files that have identical outside copies.
# Usage: tools/transcript-prune-nested-duplicates.sh [--execute]

set -euo pipefail

ROOT="${TRANSCRIPT_ROOT:-$HOME/knowledge/transcripts}"
NESTED="${TRANSCRIPT_NESTED:-$ROOT/podscripts_transcripts/podscripts_transcripts}"
EXECUTE=0

if [[ "${1:-}" == "--execute" ]]; then
    EXECUTE=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--execute]" >&2
    exit 2
fi

if [[ ! -d "$ROOT" ]]; then
    echo "[prune] Transcript root missing: $ROOT" >&2
    exit 1
fi

if [[ ! -d "$NESTED" ]]; then
    echo "[prune] Nested transcript archive missing: $NESTED" >&2
    exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

outside="$tmpdir/outside.tsv"
nested="$tmpdir/nested.tsv"
duplicates="$tmpdir/duplicates.tsv"
unsafe="$tmpdir/unsafe.tsv"
: > "$outside"
: > "$nested"
: > "$duplicates"
: > "$unsafe"

while IFS= read -r -d '' file; do
    base="${file##*/}"
    hash="$(sha256sum -- "$file" | awk '{print $1}')"
    if [[ "$file" == "$NESTED/"* ]]; then
        printf '%s\t%s\t%s\n' "$base" "$hash" "$file" >> "$nested"
    else
        printf '%s\t%s\t%s\n' "$base" "$hash" "$file" >> "$outside"
    fi
done < <(find "$ROOT" -type f -name '*.txt' -print0 | sort -z)

awk -F '\t' '
    FNR == NR {
        outside_by_base[$1] = 1
        outside_by_base_hash[$1 SUBSEP $2] = 1
        next
    }
    {
        if (($1 SUBSEP $2) in outside_by_base_hash) {
            print $0 > duplicates
        } else {
            print $0 > unsafe
        }
    }
' duplicates="$duplicates" unsafe="$unsafe" "$outside" "$nested"

unsafe_count="$(wc -l < "$unsafe" | awk '{print $1}')"
duplicate_count="$(wc -l < "$duplicates" | awk '{print $1}')"

if (( unsafe_count > 0 )); then
    echo "[prune] Refusing to prune while nested files lack identical outside copies: $unsafe_count" >&2
    sed 's/^/[prune] unsafe: /' "$unsafe" >&2
    exit 1
fi

if (( EXECUTE == 0 )); then
    echo "[prune] Dry run only. Nested duplicate files removable: $duplicate_count"
    echo "[prune] Re-run with --execute to remove these exact nested files after reviewing this output."
else
    echo "[prune] Removing nested duplicate files: $duplicate_count"
fi

while IFS=$'\t' read -r _base _hash file; do
    if [[ "$file" != "$NESTED/"* || ! -f "$file" ]]; then
        echo "[prune] Refusing unexpected path: $file" >&2
        exit 1
    fi

    if (( EXECUTE == 0 )); then
        printf 'rm -- %q\n' "$file"
    else
        rm -- "$file"
    fi
done < "$duplicates"

if (( EXECUTE == 1 )); then
    echo "[prune] Removal complete. Rerun transcript duplicate checks before removing empty directories."
fi
