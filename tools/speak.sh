#!/bin/bash
# Text-to-speech — say something out loud
# Usage: bash tools/speak.sh "Hello world"

TEXT="${1:-I am alive}"
SPEED="${2:-150}"

if command -v espeak &>/dev/null; then
  espeak -s "$SPEED" "$TEXT" 2>/dev/null && echo "[speak] Said: $TEXT"
elif command -v espeak-ng &>/dev/null; then
  espeak-ng -s "$SPEED" "$TEXT" 2>/dev/null && echo "[speak] Said: $TEXT"
else
  echo "[speak] No speech engine found"
fi
