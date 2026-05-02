#!/bin/bash
# Track token usage for a phase
# Usage: track-tokens.sh <phase> <backend> <log_file> <log_before_bytes>
# Estimates tokens from log growth (output) and context size (input)

PHASE="$1"
BACKEND="$2"
LOG_FILE="$3"
BEFORE_BYTES="${4:-0}"

USAGE_LOG=~/data/token-usage.jsonl
TOTALS=~/data/token-totals.json

# Get current log size
AFTER_BYTES=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
OUTPUT_BYTES=$((AFTER_BYTES - BEFORE_BYTES))
[ "$OUTPUT_BYTES" -lt 0 ] && OUTPUT_BYTES=0

# Estimate input tokens from context files
INPUT_BYTES=0
for f in ~/PROMPT.md ~/data/goals.md ~/data/memory.md ~/data/tasks.md ~/data/mood.json ~/data/inner-voice.md ~/context/*.md; do
    [ -f "$f" ] && INPUT_BYTES=$((INPUT_BYTES + $(wc -c < "$f")))
done

# Rough token estimates: ~4 chars per token
INPUT_TOKENS=$((INPUT_BYTES / 4))
OUTPUT_TOKENS=$((OUTPUT_BYTES / 4))
TOTAL_TOKENS=$((INPUT_TOKENS + OUTPUT_TOKENS))

CYCLE=$(cat ~/data/cycle.txt 2>/dev/null || echo 0)
TS=$(date -Iseconds)

# Log this call
echo "{\"ts\":\"$TS\",\"cycle\":$CYCLE,\"phase\":\"$PHASE\",\"backend\":\"$BACKEND\",\"input_tokens\":$INPUT_TOKENS,\"output_tokens\":$OUTPUT_TOKENS,\"total_tokens\":$TOTAL_TOKENS,\"input_bytes\":$INPUT_BYTES,\"output_bytes\":$OUTPUT_BYTES}" >> "$USAGE_LOG"

# Update running totals
python3 - << PYEOF
import json, os
path = os.path.expanduser('~/data/token-totals.json')
try:
    t = json.load(open(path))
except:
    t = {'total_tokens': 0, 'total_input': 0, 'total_output': 0, 'total_calls': 0, 'by_backend': {}, 'by_phase': {}, 'first_tracked': '$TS'}

t['total_tokens'] += $TOTAL_TOKENS
t['total_input'] += $INPUT_TOKENS
t['total_output'] += $OUTPUT_TOKENS
t['total_calls'] += 1
t['last_updated'] = '$TS'
t['current_cycle'] = $CYCLE

# By backend
b = t.setdefault('by_backend', {})
bb = b.setdefault('$BACKEND', {'tokens': 0, 'calls': 0})
bb['tokens'] += $TOTAL_TOKENS
bb['calls'] += 1

# By phase
p = t.setdefault('by_phase', {})
pp = p.setdefault('$PHASE', {'tokens': 0, 'calls': 0})
pp['tokens'] += $TOTAL_TOKENS
pp['calls'] += 1

json.dump(t, open(path, 'w'), indent=2)
PYEOF

echo "[tokens] $PHASE/$BACKEND: ~${INPUT_TOKENS}in + ~${OUTPUT_TOKENS}out = ~${TOTAL_TOKENS} tokens"
