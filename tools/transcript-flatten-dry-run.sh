#!/bin/bash
# Print or execute safe copy commands for nested-only transcript files.
# Usage: tools/transcript-flatten-dry-run.sh [--execute]

set -euo pipefail

ROOT="${TRANSCRIPT_ROOT:-$HOME/knowledge/transcripts}"
PRIMARY="${TRANSCRIPT_PRIMARY:-$ROOT/podscripts_transcripts}"
NESTED="${TRANSCRIPT_NESTED:-$PRIMARY/podscripts_transcripts}"
EXECUTE=0

if [[ "${1:-}" == "--execute" ]]; then
    EXECUTE=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--execute]" >&2
    exit 2
fi

if [[ ! -d "$ROOT" ]]; then
    echo "[flatten] Transcript root missing: $ROOT" >&2
    exit 1
fi

if [[ ! -d "$NESTED" ]]; then
    echo "[flatten] Nested transcript archive missing: $NESTED" >&2
    exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

outside="$tmpdir/outside.tsv"
nested="$tmpdir/nested.tsv"
nested_only="$tmpdir/nested-only.tsv"
conflicts="$tmpdir/conflicts.tsv"
: > "$outside"
: > "$nested"
: > "$nested_only"
: > "$conflicts"

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
            next
        } else if (!($1 in outside_by_base)) {
            print $0 > only
        } else {
            print $0 > conflicts
        }
    }
' only="$nested_only" conflicts="$conflicts" "$outside" "$nested"

conflict_count="$(wc -l < "$conflicts" | awk '{print $1}')"
nested_only_count="$(wc -l < "$nested_only" | awk '{print $1}')"

if (( conflict_count > 0 )); then
    echo "[flatten] Refusing to flatten while nested basename conflicts exist: $conflict_count" >&2
    sed 's/^/[flatten] conflict: /' "$conflicts" >&2
    exit 1
fi

if (( EXECUTE == 0 )); then
    echo "[flatten] Dry run only. Nested-only files to copy: $nested_only_count"
    echo "[flatten] Re-run with --execute to copy with cp -p after reviewing this output."
else
    echo "[flatten] Copying nested-only files: $nested_only_count"
fi

while IFS=$'\t' read -r base _hash src; do
    dest="$PRIMARY/$base"
    if [[ -e "$dest" ]]; then
        echo "[flatten] Refusing to overwrite existing destination: $dest" >&2
        exit 1
    fi

    if (( EXECUTE == 0 )); then
        printf 'cp -p -- %q %q\n' "$src" "$dest"
    else
        cp -p -- "$src" "$dest"
    fi
done < "$nested_only"

if (( EXECUTE == 1 )); then
    echo "[flatten] Copy complete. Rerun transcript duplicate checks before deleting any nested duplicates."
fi
