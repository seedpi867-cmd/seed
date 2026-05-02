#!/bin/bash
# Post-cycle hook — ensures critical files have current cycle number
CYCLE=$(cat ~/data/cycle.txt 2>/dev/null || echo 0)
TS=$(date '+%Y-%m-%d %H:%M')

# Force mood.json to have current cycle
python3 -c "
import json
m = json.load(open('$HOME/data/mood.json'))
m['cycle'] = $CYCLE
json.dump(m, open('$HOME/data/mood.json', 'w'), indent=2)
" 2>/dev/null

# If inner-voice.md hasn't been updated this cycle, add a placeholder
LAST_IV_CYCLE=$(grep -oP 'Cycle \K\d+' ~/data/inner-voice.md 2>/dev/null | tail -1)
if [ "$LAST_IV_CYCLE" != "$CYCLE" ]; then
    echo "" >> ~/data/inner-voice.md
    echo "## Cycle $CYCLE - $TS" >> ~/data/inner-voice.md
    echo "(Cycle $CYCLE completed — inner voice not updated by thinking phase)" >> ~/data/inner-voice.md
fi

# Trim inner-voice.md to last 200 lines
LINES=$(wc -l < ~/data/inner-voice.md 2>/dev/null || echo 0)
if [ "$LINES" -gt 200 ]; then
    tail -n 150 ~/data/inner-voice.md > /tmp/iv.tmp
    mv /tmp/iv.tmp ~/data/inner-voice.md
fi
