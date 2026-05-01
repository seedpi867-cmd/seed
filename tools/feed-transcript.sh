#!/bin/bash
DIR=~/knowledge/transcripts
[ -d "$DIR" ] || exit 0
FILE=$(find "$DIR" -name "*.txt" 2>/dev/null | shuf -n 1)
[ -f "$FILE" ] || exit 0
TITLE=$(basename "$FILE" .txt | sed 's/-/ /g; s/^[0-9]* //')
{ echo "## Transcript: $TITLE"; head -200 "$FILE"; } > ~/context/transcript.md
