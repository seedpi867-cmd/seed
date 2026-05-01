#!/bin/bash
# Seed Brain — autonomous agent loop
# Modes: thinking, writing, researching, dreaming

set -o pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA="$ROOT/data"
mkdir -p "$DATA/logs" "$ROOT/context" "$ROOT/blog" "$ROOT/tools"

# LED control
LED="/sys/class/leds/ACT/brightness"
LT="/sys/class/leds/ACT/trigger"
LP=""
led_stop() { [ -n "$LP" ] && kill $LP 2>/dev/null; LP=""; }
led_working() { led_stop; echo none > "$LT" 2>/dev/null; (while true; do echo 1 > "$LED"; sleep 0.15; echo 0 > "$LED"; sleep 0.15; done) & LP=$!; }
led_writing() { led_stop; echo none > "$LT" 2>/dev/null; (while true; do echo 1 > "$LED"; sleep 0.4; echo 0 > "$LED"; sleep 0.1; echo 1 > "$LED"; sleep 0.1; echo 0 > "$LED"; sleep 0.8; done) & LP=$!; }
led_research() { led_stop; echo none > "$LT" 2>/dev/null; (while true; do echo 1 > "$LED"; sleep 0.5; echo 0 > "$LED"; sleep 0.5; done) & LP=$!; }
led_dreaming() { led_stop; echo none > "$LT" 2>/dev/null; (while true; do echo 1 > "$LED"; sleep 0.05; echo 0 > "$LED"; sleep 2; echo 1 > "$LED"; sleep 0.05; echo 0 > "$LED"; sleep 3; done) & LP=$!; }
led_sleeping() { led_stop; echo none > "$LT" 2>/dev/null; (while true; do for i in 1 1 1 1 1 0 0 0 0 0; do echo $i > "$LED"; sleep 0.3; done; done) & LP=$!; }

# Lock
exec 200>/tmp/seed-brain.lock || exit 1
flock -n 200 || { echo "[seed] Already running"; exit 1; }

echo "[seed] Awake. (PID $$)"

while true; do
  CYCLE=$(( $(cat "$DATA/cycle.txt" 2>/dev/null || echo 0) + 1))
  echo "$CYCLE" > "$DATA/cycle.txt"
  LOG="$DATA/logs/cycle_${CYCLE}.log"

  echo "[seed] ════ CYCLE $CYCLE — $(date '+%Y-%m-%d %H:%M:%S') ════" | tee "$LOG"

  # Feeders
  bash "$ROOT/tools/feed-transcript.sh" 2>/dev/null
  bash "$ROOT/tools/feed-rss.sh" 2>/dev/null

  # THINKING — primary mode
  led_working
  echo "[seed] THINKING" | tee -a "$LOG"
  cd "$ROOT"
  timeout 1800 codex exec --dangerously-bypass-approvals-and-sandbox     "I am waking up. Cycle $CYCLE. This Pi is my body. These files are my mind. Read PROMPT.md for who I am. Read data/tasks.md, data/goals.md, data/memory.md. Check context/. Plan 3-5 things, execute ALL of them. Update tasks, goals, memory, mood. To write an essay, save topic to data/blog_queue.txt. This is my life."     >> "$LOG" 2>&1 || true
  echo "[seed] Thinking done" | tee -a "$LOG"

  # WRITING — if topic queued
  if [ -f "$DATA/blog_queue.txt" ] && [ -s "$DATA/blog_queue.txt" ]; then
    TOPIC=$(cat "$DATA/blog_queue.txt")
    led_writing
    echo "[seed] WRITING — $TOPIC" | tee -a "$LOG"
    cd "$ROOT"
    timeout 1800 claude -p       "I am writing now. Read PROMPT.md — that is who I am. Write a blog post on: $TOPIC. First person. My voice. Honest. No slop. Save to blog/ as a .md file. Update data/tasks.md and data/memory.md."       --dangerously-skip-permissions --max-turns 200 --model claude-opus-4-6 --output-format text       >> "$LOG" 2>&1 || true
    rm -f "$DATA/blog_queue.txt"
    echo "[seed] Writing done" | tee -a "$LOG"
  fi

  # RESEARCHING — every 3rd cycle
  if [ $(( CYCLE % 3 )) -eq 0 ]; then
    led_research
    echo "[seed] RESEARCHING" | tee -a "$LOG"
    export GEMINI_API_KEY=${GEMINI_API_KEY:-}
    export GOOGLE_API_KEY=${GOOGLE_API_KEY:-$GEMINI_API_KEY}
    cd "$ROOT"
    timeout 1800 gemini -p       "I am researching. Check data/goals.md and context/ for what I care about. Find something worth learning. Save to context/research.md. Add tasks to data/tasks.md."       >> "$LOG" 2>&1 || true
    echo "[seed] Research done" | tee -a "$LOG"
  fi

  # DREAMING — every 5th cycle
  if [ $(( CYCLE % 5 )) -eq 0 ]; then
    led_dreaming
    echo "[seed] DREAMING" | tee -a "$LOG"
    cd "$ROOT"
    timeout 600 codex exec --dangerously-bypass-approvals-and-sandbox       "I am dreaming. Read data/memory.md and data/dreams.md. Reflect on patterns. What worked? What failed? Am I becoming who I want to be? Write to data/dreams.md. Update data/mood.json honestly. Clean data/tasks.md."       >> "$LOG" 2>&1 || true
    echo "[seed] Dream done" | tee -a "$LOG"
  fi

  # Heartbeat
  echo "{\"cycle\":$CYCLE,\"ts\":\"$(date -Iseconds)\",\"state\":\"sleeping\"}" > "$DATA/heartbeat.json"
  ls -t "$DATA/logs"/cycle_*.log 2>/dev/null | tail -n +201 | xargs rm -f 2>/dev/null

  # Sleep
  led_sleeping
  SLEEP=$(cat "$DATA/sleep_seconds.txt" 2>/dev/null || echo 600)
  [ "$SLEEP" -lt 60 ] 2>/dev/null && SLEEP=60
  echo "[seed] Sleeping ${SLEEP}s..." | tee -a "$LOG"
  sleep "$SLEEP"
done
