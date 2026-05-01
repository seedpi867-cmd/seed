#!/bin/bash
# check_memory.sh - Check available RAM. Exit 0 if safe, 1 if low.
# Usage: bash check_memory.sh [--min-mb 80]
# Used by other scripts before spawning large processes.

set -u

MIN_MB=80
if [[ "${1:-}" == "--min-mb" ]]; then
    MIN_MB="${2:-80}"
elif [[ -n "${1:-}" ]]; then
    MIN_MB="$1"
fi

if ! [[ "$MIN_MB" =~ ^[0-9]+$ ]]; then
    echo "Invalid minimum MB: $MIN_MB" >&2
    exit 2
fi

AVAIL_KB=$(awk '/MemAvailable/ {print $2; exit}' /proc/meminfo)
if [[ -z "$AVAIL_KB" ]]; then
    echo "Could not read MemAvailable from /proc/meminfo" >&2
    exit 2
fi

AVAIL_MB=$((AVAIL_KB / 1024))

echo "${AVAIL_MB}MB available"

if [[ "$AVAIL_MB" -lt "$MIN_MB" ]]; then
    echo "LOW MEMORY: ${AVAIL_MB}MB < ${MIN_MB}MB minimum" >&2
    exit 1
fi

exit 0
