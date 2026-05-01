#!/bin/bash
# Check duplicate transcript basenames and whether the nested archive is redundant.
# Usage: tools/transcript-duplicates.sh [output-file]

set -euo pipefail

ROOT="${TRANSCRIPT_ROOT:-$HOME/knowledge/transcripts}"
NESTED="${TRANSCRIPT_NESTED:-$ROOT/podscripts_transcripts/podscripts_transcripts}"
OUT="${1:-$HOME/data/transcript_duplicates.md}"

if [[ ! -d "$ROOT" ]]; then
    echo "Transcript root missing: $ROOT" >&2
    exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

records="$tmpdir/records.tsv"
nested_records="$tmpdir/nested.tsv"
outside_records="$tmpdir/outside.tsv"
: > "$records"
: > "$nested_records"
: > "$outside_records"

while IFS= read -r -d '' file; do
    base="${file##*/}"
    hash="$(sha256sum -- "$file" | awk '{print $1}')"
    bytes="$(wc -c < "$file" | awk '{print $1}')"
    printf '%s\t%s\t%s\t%s\n' "$base" "$hash" "$bytes" "$file" >> "$records"

    if [[ -d "$NESTED" && "$file" == "$NESTED/"* ]]; then
        printf '%s\t%s\t%s\t%s\n' "$base" "$hash" "$bytes" "$file" >> "$nested_records"
    else
        printf '%s\t%s\t%s\t%s\n' "$base" "$hash" "$bytes" "$file" >> "$outside_records"
    fi
done < <(find "$ROOT" -type f -name '*.txt' -print0 | sort -z)

awk -F '\t' -v root="$ROOT" -v nested="$NESTED" '
    FNR == NR {
        outside[$1 SUBSEP $2] = 1
        next
    }
    {
        total++
        base = $1
        hash = $2
        bytes = $3 + 0
        count[base]++
        seen_hash[base SUBSEP hash] = 1
        if (!(base in first_bytes)) {
            first_bytes[base] = bytes
        }
        if (count[base] <= 6) {
            sample[base] = sample[base] "\n  - " $4
        }
        if ($4 ~ "^" nested "/") {
            nested_total++
            if (!((base SUBSEP hash) in outside)) {
                unsafe_nested++
                if (unsafe_nested <= 20) {
                    unsafe_sample = unsafe_sample "\n- " $4
                }
            }
        }
    }
    END {
        for (key in seen_hash) {
            split(key, parts, SUBSEP)
            hash_count[parts[1]]++
        }
        for (base in count) {
            unique++
            if (count[base] > 1) {
                duplicate_groups++
                extra_paths += count[base] - 1
                if (hash_count[base] == 1) {
                    identical_groups++
                    duplicate_bytes += (count[base] - 1) * first_bytes[base]
                } else {
                    mismatch_groups++
                    if (mismatch_groups <= 40) {
                        mismatch_sample = mismatch_sample "\n- " base sample[base]
                    }
                }
            }
        }
        mismatch_groups += 0
        unsafe_nested += 0
        nested_total += 0
        duplicate_groups += 0
        identical_groups += 0
        extra_paths += 0
        duplicate_bytes += 0

        print "# Transcript Duplicate Check"
        print ""
        cmd = "date \"+%Y-%m-%d %H:%M:%S %Z\""
        cmd | getline generated
        close(cmd)
        print "Generated: " generated
        print "Root: " root
        print "Nested archive: " nested
        print ""
        print "- Total transcript files: " total
        print "- Unique basenames: " unique
        print "- Duplicate basename groups: " duplicate_groups
        print "- Byte-identical duplicate groups: " identical_groups
        print "- Hash-mismatched duplicate groups: " mismatch_groups
        print "- Extra duplicate paths: " extra_paths
        print "- Byte-identical duplicate bytes: " duplicate_bytes
        print "- Nested archive files: " nested_total
        print "- Nested files without identical outside copy: " unsafe_nested
        print ""
        if (mismatch_groups == 0) {
            print "Result: duplicate basenames are byte-identical."
        } else {
            print "Result: duplicate basenames include hash mismatches."
            print ""
            print "## Mismatched Samples"
            print mismatch_sample
        }
        print ""
        if (nested_total > 0 && unsafe_nested == 0) {
            print "Nested archive result: safe to archive or remove after preserving this report."
        } else if (nested_total == 0) {
            print "Nested archive result: no nested transcript files found."
        } else {
            print "Nested archive result: not safe to remove."
            print ""
            print "## Unsafe Nested Samples"
            print unsafe_sample
        }
    }
' "$outside_records" "$records" > "$OUT"

echo "Wrote $OUT"
