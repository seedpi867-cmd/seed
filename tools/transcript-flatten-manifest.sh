#!/bin/bash
# Build a non-destructive manifest for flattening nested transcript files.
# Usage: tools/transcript-flatten-manifest.sh [output-file]

set -euo pipefail

ROOT="${TRANSCRIPT_ROOT:-$HOME/knowledge/transcripts}"
PRIMARY="${TRANSCRIPT_PRIMARY:-$ROOT/podscripts_transcripts}"
NESTED="${TRANSCRIPT_NESTED:-$PRIMARY/podscripts_transcripts}"
OUT="${1:-$HOME/data/transcript_flatten_manifest.md}"

if [[ ! -d "$ROOT" ]]; then
    echo "Transcript root missing: $ROOT" >&2
    exit 1
fi

if [[ ! -d "$NESTED" ]]; then
    echo "Nested transcript archive missing: $NESTED" >&2
    exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

outside="$tmpdir/outside.tsv"
nested="$tmpdir/nested.tsv"
nested_only="$tmpdir/nested-only.tsv"
nested_dupes="$tmpdir/nested-duplicates.tsv"
conflicts="$tmpdir/conflicts.tsv"
: > "$outside"
: > "$nested"
: > "$nested_only"
: > "$nested_dupes"
: > "$conflicts"

while IFS= read -r -d '' file; do
    base="${file##*/}"
    hash="$(sha256sum -- "$file" | awk '{print $1}')"
    bytes="$(wc -c < "$file" | awk '{print $1}')"
    if [[ "$file" == "$NESTED/"* ]]; then
        printf '%s\t%s\t%s\t%s\n' "$base" "$hash" "$bytes" "$file" >> "$nested"
    else
        printf '%s\t%s\t%s\t%s\n' "$base" "$hash" "$bytes" "$file" >> "$outside"
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
            print $0 > dupes
        } else if (!($1 in outside_by_base)) {
            print $0 > only
        } else {
            print $0 > conflicts
        }
    }
' dupes="$nested_dupes" only="$nested_only" conflicts="$conflicts" "$outside" "$nested"

total_nested=$(wc -l < "$nested" | awk '{print $1}')
nested_only_count=$(wc -l < "$nested_only" | awk '{print $1}')
nested_dupe_count=$(wc -l < "$nested_dupes" | awk '{print $1}')
conflict_count=$(wc -l < "$conflicts" | awk '{print $1}')
nested_only_bytes=$(awk -F '\t' '{sum += $3} END {print sum + 0}' "$nested_only")
nested_dupe_bytes=$(awk -F '\t' '{sum += $3} END {print sum + 0}' "$nested_dupes")

{
    echo "# Transcript Flatten Manifest"
    echo
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "Root: $ROOT"
    echo "Primary directory: $PRIMARY"
    echo "Nested directory: $NESTED"
    echo
    echo "- Nested transcript files: $total_nested"
    echo "- Nested-only files to preserve: $nested_only_count"
    echo "- Nested duplicate files with identical outside copy: $nested_dupe_count"
    echo "- Nested basename conflicts with different content: $conflict_count"
    echo "- Nested-only bytes to preserve: $nested_only_bytes"
    echo "- Duplicate nested bytes removable after flattening: $nested_dupe_bytes"
    echo
    echo "## Safety"
    echo
    echo "This manifest is non-destructive. Do not delete the nested directory as a unit."
    echo "A cleanup session should copy or move every nested-only file to the primary directory, rerun duplicate checks, then remove only files listed under duplicate nested files."
    echo
    echo "## Nested-Only Files"
    echo
    awk -F '\t' -v nested="$NESTED/" -v primary="$PRIMARY/" '{
        src = $4
        dest = primary $1
        sub("^" nested, "", src)
        printf "- preserve: `%s` -> `%s` (%s bytes, sha256 %s)\n", src, dest, $3, $2
    }' "$nested_only"
    echo
    echo "## Duplicate Nested Files"
    echo
    awk -F '\t' -v nested="$NESTED/" '{
        path = $4
        sub("^" nested, "", path)
        printf "- duplicate: `%s` (%s bytes, sha256 %s)\n", path, $3, $2
    }' "$nested_dupes"
    if (( conflict_count > 0 )); then
        echo
        echo "## Conflicts"
        echo
        awk -F '\t' -v nested="$NESTED/" '{
            path = $4
            sub("^" nested, "", path)
            printf "- conflict: `%s` (%s bytes, sha256 %s)\n", path, $3, $2
        }' "$conflicts"
    fi
} > "$OUT"

echo "Wrote $OUT"
