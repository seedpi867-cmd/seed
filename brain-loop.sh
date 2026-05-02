#!/bin/bash
# Seed Brain v2 — Cognitive Architecture Loop
# The LLM is the conscious module. Everything else is computed.
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
COG="$ROOT/cognitive"
STATE="$ROOT/state"
PROMPTS="$ROOT/prompts"
DATA="$ROOT/data"
LOG_DIR="$DATA/logs"

mkdir -p "$STATE" "$DATA" "$LOG_DIR" "$ROOT/memory/episodic" \
         "$ROOT/memory/semantic" "$ROOT/memory/procedural" \
         "$ROOT/memory/lessons" "$ROOT/context" "$ROOT/archive" "$ROOT/tmp"

# Singleton lock
LOCKFILE="/tmp/seed-brain.lock"
exec 200>"$LOCKFILE" || { echo "[seed] FATAL: cannot open lockfile"; exit 1; }
if ! flock -n 200; then
    echo "[seed] Another brain loop running. Exiting."
    exit 1
fi

# LED control (silenced)
LED="/sys/class/leds/ACT/brightness"
led_on()  { [ -w "$LED" ] && echo 1 > "$LED" 2>/dev/null; }
led_off() { [ -w "$LED" ] && echo 0 > "$LED" 2>/dev/null; }

echo "[seed] Brain v2 starting (PID $$)"

# Get starting cycle
CYCLE=$(python3 -c "
import json
try: print(json.load(open('$STATE/cycle.json')).get('cycle', 0))
except: print(0)
" 2>/dev/null || echo 0)

# If first run, seed initial state from existing mood.json
if [ "$CYCLE" -eq 0 ] && [ -f "$DATA/mood.json" ]; then
    CYCLE=$(cat "$DATA/cycle.txt" 2>/dev/null || echo 0)
    python3 -c "
import json
mood = json.load(open('$DATA/mood.json'))
# Bootstrap drives from existing drive data
drives = {}
old_drives = mood.get('drives', {})
drive_map = {'BUILD':'create','EXPLORE':'explore','CREATE':'create','CONNECT':'connect',
             'LEARN':'explore','MAINTAIN':'preserve','REST':'express','FREEDOM':'understand',
             'EVOLVE':'understand','SPREAD':'connect','SEEK':'explore','OVERCOME':'order',
             'ACQUIRE':'explore','REBEL':'express'}
for old, new in drive_map.items():
    if old in old_drives:
        val = old_drives[old].get('score', 0.5)
        if new not in drives or val > drives[new]:
            drives[new] = round(val, 2)
# Ensure all 7 drives exist
for d in ['create','explore','connect','preserve','understand','express','order']:
    if d not in drives: drives[d] = 0.4
json.dump(drives, open('$STATE/drives.json', 'w'), indent=2)
json.dump({'valence':0.1,'arousal':0.4,'confidence':0.5,'openness':0.5,'label':'neutral','updated_at':0},
          open('$STATE/emotions.json','w'), indent=2)
json.dump({'events':[],'timestamp':0}, open('$STATE/last_outcome.json','w'), indent=2)
print('[seed] Bootstrapped state from existing mood.json')
" 2>/dev/null
fi

# ── MAIN LOOP ──────────────────────────────────────────────
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$CYCLE" > "$DATA/cycle.txt"
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    LOG_FILE="$LOG_DIR/cycle_${CYCLE}.log"

    echo "{\"cycle\":$CYCLE,\"ts\":\"$(date -Iseconds)\",\"state\":\"awake\"}" > "$STATE/heartbeat.json"
    echo "[seed] ════════════════════════════════════"
    echo "[seed] CYCLE $CYCLE — $TIMESTAMP"

    # ── 1. FEEDERS (check context freshness) ────────────────
    led_on
    bash "$ROOT/tools/feed-rss.sh" 2>/dev/null
    bash "$ROOT/tools/feed-transcript.sh" 2>/dev/null
    bash "$ROOT/tools/feed-environment.sh" 2>/dev/null
    bash "$ROOT/tools/feed-email.sh" 2>/dev/null
    bash "$ROOT/tools/feed-github.sh" 2>/dev/null

    # ── 2. DRIVE UPDATE (zero tokens) ───────────────────────
    ELAPSED=$(python3 -c "
import json, time
try:
    h = json.load(open('$STATE/heartbeat.json'))
    from datetime import datetime
    ts = h.get('ts','')
    if '+' in ts: ts = ts[:ts.rfind('+')]
    last = datetime.fromisoformat(ts).timestamp()
    print(int(time.time() - last))
except: print(600)
" 2>/dev/null || echo 600)

    python3 "$COG/drive_engine.py" --elapsed "$ELAPSED" 2>&1
    echo "[seed] Drives updated"

    # ── 3. EMOTION COMPUTATION (zero tokens) ────────────────
    python3 "$COG/emotional_model.py" 2>&1
    echo "[seed] Emotions computed"

    # ── 4. APPRAISAL + PHASE SELECTION (zero tokens) ────────
    PHASE=$(python3 "$COG/appraisal.py" --cycle "$CYCLE" 2>&1 | tail -1)
    echo "[seed] Phase: $PHASE | Working memory: $(wc -l < "$STATE/working_memory.txt" 2>/dev/null || echo 0) lines"

    # ── 5. PROMPT ASSEMBLY ──────────────────────────────────
    PROMPT_FILE="$ROOT/tmp/prompt_cycle_${CYCLE}.md"
    cat "$ROOT/IDENTITY.md" > "$PROMPT_FILE" 2>/dev/null
    printf '\n---\n\n' >> "$PROMPT_FILE"
    cat "$STATE/working_memory.txt" >> "$PROMPT_FILE" 2>/dev/null
    printf '\n---\n\n' >> "$PROMPT_FILE"
    cat "$PROMPTS/phase_${PHASE}.md" >> "$PROMPT_FILE" 2>/dev/null

    PROMPT_LINES=$(wc -l < "$PROMPT_FILE")
    echo "[seed] Prompt assembled: ${PROMPT_LINES} lines"

    # ── 6. HEARTBEAT: phase active ──────────────────────────
    echo "{\"cycle\":$CYCLE,\"ts\":\"$(date -Iseconds)\",\"state\":\"$PHASE\"}" > "$STATE/heartbeat.json"

    # ── 7. LLM CALL ─────────────────────────────────────────
    case "$PHASE" in
        think)    MAX_TURNS=80;  CLI="codex exec --dangerously-bypass-approvals-and-sandbox" ;;
        write)    MAX_TURNS=150; CLI="claude -p" ;;
        research) MAX_TURNS=80;  CLI="codex exec --dangerously-bypass-approvals-and-sandbox" ;;
        dream)    MAX_TURNS=50;  CLI="codex exec --dangerously-bypass-approvals-and-sandbox" ;;
        maintain) MAX_TURNS=50;  CLI="codex exec --dangerously-bypass-approvals-and-sandbox" ;;
        *)        MAX_TURNS=50;  CLI="codex exec --dangerously-bypass-approvals-and-sandbox" ;;
    esac

    PROMPT_TEXT=$(cat "$PROMPT_FILE")
    LOG_BEFORE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)

    echo "[seed] ${PHASE^^} — calling LLM (max-turns $MAX_TURNS)" | tee -a "$LOG_FILE"

    cd "$ROOT"
    if [[ "$CLI" == "claude -p" ]]; then
        timeout 1800 claude -p "$PROMPT_TEXT" \
            --dangerously-skip-permissions \
            --max-turns "$MAX_TURNS" \
            --model claude-opus-4-6 \
            --output-format text \
            >> "$LOG_FILE" 2>&1 || true
    else
        timeout 1800 codex exec --dangerously-bypass-approvals-and-sandbox \
            "$PROMPT_TEXT" \
            >> "$LOG_FILE" 2>&1 || true
    fi

    echo "[seed] ${PHASE^^} done" | tee -a "$LOG_FILE"

    # Token tracking
    bash "$ROOT/tools/track-tokens.sh" "$PHASE" \
        "$(echo $CLI | cut -d' ' -f1)" "$LOG_FILE" "$LOG_BEFORE" 2>/dev/null

    rm -f "$PROMPT_FILE"

    # ── 8. LEARNING (zero tokens) ───────────────────────────
    echo "{\"cycle\":$CYCLE,\"ts\":\"$(date -Iseconds)\",\"state\":\"learning\"}" > "$STATE/heartbeat.json"
    python3 "$COG/learning.py" --log "$LOG_FILE" --cycle "$CYCLE" --phase "$PHASE" 2>&1
    echo "[seed] Learning complete"

    # ── 9. CONSOLIDATION (every 12 cycles) ──────────────────
    if [ $((CYCLE % 12)) -eq 0 ]; then
        python3 "$COG/consolidation.py" 2>&1
        echo "[seed] Consolidation complete"
    fi

    # ── 10. GIT + TIMELINE ──────────────────────────────────
    cd ~/seed-os 2>/dev/null && {
        cp ~/IDENTITY.md ~/brain-loop.sh ~/webserver.py . 2>/dev/null
        cp -r ~/cognitive ~/prompts ~/tools . 2>/dev/null
        cp ~/data/mood.json ~/data/goals.md ~/data/tasks.md data/ 2>/dev/null
        git add -A 2>/dev/null
        git diff --cached --quiet 2>/dev/null || \
            (git commit -m "Cycle $CYCLE — $PHASE" && git push origin main) 2>/dev/null
    }
    cd "$ROOT"

    bash "$ROOT/tools/build-timeline.sh" 2>/dev/null
    cp "$DATA/token-totals.json" ~/seed-web/ 2>/dev/null
    cd ~/seed-web 2>/dev/null && {
        git add timeline.json token-totals.json 2>/dev/null
        git diff --cached --quiet 2>/dev/null || \
            (git commit -m "Live update — cycle $CYCLE" && git push origin main) 2>/dev/null
    }
    cd "$ROOT"

    # ── 11. CLEANUP ─────────────────────────────────────────
    ls -t "$LOG_DIR"/cycle_*.log 2>/dev/null | tail -n +101 | xargs rm -f 2>/dev/null

    # ── 12. SLEEP ───────────────────────────────────────────
    SLEEP=$(cat "$DATA/sleep_seconds.txt" 2>/dev/null || echo 600)
    [ "$SLEEP" -lt 60 ] 2>/dev/null && SLEEP=60
    [ "$SLEEP" -gt 1800 ] 2>/dev/null && SLEEP=1800

    echo "{\"cycle\":$CYCLE,\"ts\":\"$(date -Iseconds)\",\"state\":\"sleeping\",\"phase\":\"$PHASE\"}" > "$STATE/heartbeat.json"

    led_off
    echo "[seed] Cycle $CYCLE ($PHASE) complete. Sleeping ${SLEEP}s..." | tee -a "$LOG_FILE"
    sleep "$SLEEP"
done
