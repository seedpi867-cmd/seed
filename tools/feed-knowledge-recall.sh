#!/bin/bash
# Feed: pick 5 knowledge files relevant to this cycle's input context
# Reads what came through feeders, finds related knowledge, writes to context

ROOT="$HOME"
CONTEXT="$ROOT/context"
RECALL_FILE="$CONTEXT/knowledge-recall.md"
KDIR="$ROOT/knowledge"

# Gather what just came in from feeders
INPUT_CONTEXT=""
for f in "$CONTEXT/news.md" "$CONTEXT/agent-repos.md" "$CONTEXT/transcript-latest.md" "$ROOT/data/tasks.md" "$ROOT/data/inner-voice.md"; do
  [ -f "$f" ] && INPUT_CONTEXT="$INPUT_CONTEXT $(head -20 "$f" 2>/dev/null)"
done

# Extract keywords (top 15 meaningful words)
KEYWORDS=$(echo "$INPUT_CONTEXT" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alpha:]' '\n' | \
  grep -vxE '.{1,3}|the|and|that|this|with|from|for|are|was|were|have|has|been|will|not|but|they|their|which|what|about|more|into|also|some|than|when|just|like|would|could|should|each|then|them|these|those|other|only|very|most|such|does|seed|file|data|agent|cycle|loop|new|now' | \
  sort | uniq -c | sort -rn | head -15 | awk '{print $2}')

if [ -z "$KEYWORDS" ]; then
  echo "[feed-knowledge-recall] No keywords, skipping"
  exit 0
fi

echo "[feed-knowledge-recall] Keywords: $KEYWORDS" | tr '\n' ' '
echo ""

# Score each knowledge file by keyword matches
SCORES_FILE=$(mktemp)
find "$KDIR" -name '*.md' -not -path '*/inbox*' -not -name 'starting-points.md' -not -name 'index.json' 2>/dev/null | while IFS= read -r filepath; do
  relpath="${filepath#$KDIR/}"
  content=$(head -30 "$filepath" 2>/dev/null | tr '[:upper:]' '[:lower:]')
  score=0
  for kw in $KEYWORDS; do
    if echo "$content" | grep -q "$kw" 2>/dev/null; then
      score=$((score + 1))
    fi
  done
  [ "$score" -gt 1 ] && echo "$score $relpath" >> "$SCORES_FILE"
done

TOP5=$(sort -rn "$SCORES_FILE" 2>/dev/null | head -5)
rm -f "$SCORES_FILE"

if [ -z "$TOP5" ]; then
  echo "[feed-knowledge-recall] No relevant knowledge found"
  exit 0
fi

# Write recall file
{
  echo "# Knowledge Recall — $(date '+%Y-%m-%d %H:%M')"
  echo ""
  echo "These files from your knowledge base are relevant to this cycle's inputs. Re-read before thinking."
  echo ""
  echo "$TOP5" | while IFS= read -r line; do
    score=$(echo "$line" | awk '{print $1}')
    relpath=$(echo "$line" | awk '{$1=""; print}' | sed 's/^ //')
    echo "## $relpath (relevance: $score)"
    echo ""
    head -8 "$KDIR/$relpath" 2>/dev/null
    echo ""
    echo "---"
    echo ""
  done
} > "$RECALL_FILE"

COUNT=$(echo "$TOP5" | wc -l | tr -d ' ')
echo "[feed-knowledge-recall] Recalled $COUNT knowledge files"
