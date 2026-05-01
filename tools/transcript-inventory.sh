#!/bin/bash
# Build a compact inventory of the transcript archive.
# Usage: tools/transcript-inventory.sh [output-file]

set -euo pipefail

ROOT="${TRANSCRIPT_ROOT:-$HOME/knowledge/transcripts}"
OUT="${1:-$HOME/data/transcript_inventory.md}"

if [[ ! -d "$ROOT" ]]; then
    echo "Transcript root missing: $ROOT" >&2
    exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

find "$ROOT" -type f -name '*.txt' -print | sort > "$tmp"

total=$(wc -l < "$tmp" | awk '{print $1}')
unique=$(sed 's#.*/##' "$tmp" | sort -u | wc -l | awk '{print $1}')
duplicate_names=$(sed 's#.*/##' "$tmp" | sort | uniq -d | wc -l | awk '{print $1}')

{
    echo "# Transcript Inventory"
    echo
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "Root: $ROOT"
    echo
    echo "- Total transcript files: $total"
    echo "- Unique basenames: $unique"
    echo "- Duplicate basenames: $duplicate_names"
    echo
    echo "## Largest Files"
    echo
    while IFS= read -r file; do
        bytes=$(wc -c < "$file" | awk '{print $1}')
        printf '%s\t%s\n' "$bytes" "$file"
    done < "$tmp" | sort -nr | awk -F '\t' -v root="$ROOT/" 'NR <= 20 { sub("^" root, "", $2); printf "- %s bytes - %s\n", $1, $2 }'
    echo
    echo "## Duplicate Basename Samples"
    echo
    sed 's#.*/##' "$tmp" | sort | awk 'seen[$0]++ == 1 && count++ < 40 { printf "- %s\n", $0 }'
    echo
    echo "## First 40 Files"
    echo
    awk -v root="$ROOT/" 'NR <= 40 { sub("^" root, ""); printf "- %s\n", $0 }' "$tmp"
} > "$OUT"

echo "Wrote $OUT"
