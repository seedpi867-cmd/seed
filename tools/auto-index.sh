#!/bin/bash
# Auto-indexer — indexes everything Seed creates, runs via cron, zero tokens
# Rebuilds data/ROUTER.md from the actual filesystem

ROOT="$HOME"
ROUTER="$ROOT/data/ROUTER.md"
NOW=$(date '+%Y-%m-%d %H:%M')

cat > "$ROUTER" << HEADER
# ROUTER — Master Index
Auto-generated: $NOW

HEADER

# Blog posts
echo "## Blog Posts" >> "$ROUTER"
echo "| File | Title | Size |" >> "$ROUTER"
echo "|------|-------|------|" >> "$ROUTER"
for f in $(ls -t "$ROOT/blog/"*.md 2>/dev/null); do
    title=$(head -1 "$f" | sed 's/^# //')
    size=$(wc -c < "$f")
    echo "| $(basename $f) | ${title:0:60} | ${size}b |" >> "$ROUTER"
done

# Research topics
echo "" >> "$ROUTER"
echo "## Research Topics" >> "$ROUTER"
echo "| File | Size | Modified |" >> "$ROUTER"
echo "|------|------|----------|" >> "$ROUTER"
find "$ROOT/research/topics" -name "*.md" -type f 2>/dev/null | sort | while read f; do
    echo "| $(basename $f) | $(wc -c < $f)b | $(date -r $f '+%Y-%m-%d') |" >> "$ROUTER"
done

# Research opinions
echo "" >> "$ROUTER"
echo "## Opinions Formed" >> "$ROUTER"
echo "| File | Size |" >> "$ROUTER"
echo "|------|------|" >> "$ROUTER"
find "$ROOT/research/opinions" -name "*.md" -type f 2>/dev/null | sort | while read f; do
    echo "| $(basename $f) | $(wc -c < $f)b |" >> "$ROUTER"
done

# Claims
echo "" >> "$ROUTER"
echo "## Claims Checked" >> "$ROUTER"
echo "| File | Size |" >> "$ROUTER"
echo "|------|------|" >> "$ROUTER"
for f in $(ls -t "$ROOT/data/claims/"*.md 2>/dev/null); do
    echo "| $(basename $f) | $(wc -c < $f)b |" >> "$ROUTER"
done

# Tools
echo "" >> "$ROUTER"
echo "## Tools ($(ls $ROOT/tools/*.sh $ROOT/tools/*.py 2>/dev/null | wc -l) total)" >> "$ROUTER"
echo "| Tool | Type | Size |" >> "$ROUTER"
echo "|------|------|------|" >> "$ROUTER"
for f in $(ls "$ROOT/tools/"*.sh "$ROOT/tools/"*.py 2>/dev/null | sort); do
    ext="${f##*.}"
    echo "| $(basename $f) | $ext | $(wc -c < $f)b |" >> "$ROUTER"
done

# Skills
echo "" >> "$ROUTER"
echo "## Skills" >> "$ROUTER"
for f in $(ls "$ROOT/skills/active/"*.md 2>/dev/null); do
    level=$(grep -i "^Level:" "$f" 2>/dev/null | head -1 | sed 's/Level: //')
    echo "- $(basename $f .md) ($level)" >> "$ROUTER"
done

# Knowledge directories
echo "" >> "$ROUTER"
echo "## Knowledge" >> "$ROUTER"
for d in philosophy science psychology history counter-arguments art other-ai transcripts; do
    count=$(find "$ROOT/knowledge/$d" -type f 2>/dev/null | wc -l)
    [ "$count" -gt 0 ] && echo "- $d: $count files" >> "$ROUTER"
done

# Docs
echo "" >> "$ROUTER"
echo "## Documentation" >> "$ROUTER"
find "$ROOT/docs" -name "*.md" -type f 2>/dev/null | while read f; do
    rel="${f#$ROOT/docs/}"
    echo "- $rel" >> "$ROUTER"
done

# Projects
echo "" >> "$ROUTER"
echo "## Projects" >> "$ROUTER"
for d in $(ls -d "$ROOT/projects/"*/ 2>/dev/null); do
    echo "- $(basename $d)" >> "$ROUTER"
done

# Workflows completed
echo "" >> "$ROUTER"
echo "## Workflows Completed" >> "$ROUTER"
ls "$ROOT/workflows/completed/"*.md 2>/dev/null | wc -l | xargs -I{} echo "- {} completed workflows"

# Stats
echo "" >> "$ROUTER"
echo "## Stats" >> "$ROUTER"
echo "- Blog posts: $(ls $ROOT/blog/*.md 2>/dev/null | wc -l)" >> "$ROUTER"
echo "- Claims checked: $(ls $ROOT/data/claims/*.md 2>/dev/null | wc -l)" >> "$ROUTER"
echo "- Tools: $(ls $ROOT/tools/*.sh $ROOT/tools/*.py 2>/dev/null | wc -l)" >> "$ROUTER"
echo "- Research topics: $(find $ROOT/research/topics -name '*.md' 2>/dev/null | wc -l)" >> "$ROUTER"
echo "- Opinions formed: $(find $ROOT/research/opinions -name '*.md' 2>/dev/null | wc -l)" >> "$ROUTER"
echo "- Knowledge files: $(find $ROOT/knowledge -type f 2>/dev/null | wc -l)" >> "$ROUTER"
echo "- Memory lines: $(wc -l < $ROOT/data/memory.md 2>/dev/null)" >> "$ROUTER"
echo "- Archive lines: $(wc -l < $ROOT/data/memory-archive.md 2>/dev/null)" >> "$ROUTER"
echo "- Current cycle: $(cat $ROOT/data/cycle.txt 2>/dev/null)" >> "$ROUTER"
