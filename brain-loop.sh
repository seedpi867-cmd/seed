#!/bin/bash
# SEED Brain — Multi-agent autonomous loop
# One mind, four modes: thinking, writing, researching, dreaming
# The CLIs read the filesystem directly — no stdin piping

set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$ROOT/data"
CYCLE_FILE="$DATA_DIR/cycle.txt"
LOG_DIR="$DATA_DIR/logs"

mkdir -p "$DATA_DIR" "$LOG_DIR" "$ROOT/context" "$ROOT/blog" "$ROOT/tools"

# Singleton lock
LOCKFILE="/tmp/seed-brain.lock"
exec 200>"$LOCKFILE" || { echo "[seed] FATAL: cannot open lockfile"; exit 1; }
if ! flock -n 200; then
  echo "[seed] Another brain loop running. Exiting."
  exit 1
fi


# ── LED CONTROL (Pi Zero ACT LED) ─────────────────────────
LED="/sys/class/leds/ACT/brightness"
LED_TRIGGER="/sys/class/leds/ACT/trigger"
LED_PID=""

led_stop() { [ -n "$LED_PID" ] && kill $LED_PID 2>/dev/null; LED_PID=""; }

led_working() {
  led_stop
  [ -w "$LED" ] || return
  echo none > "$LED_TRIGGER" 2>/dev/null
  ( while true; do echo 1 > "$LED" 2>/dev/null; sleep 0.15; echo 0 > "$LED" 2>/dev/null; sleep 0.15; done ) &
  LED_PID=$!
}

led_sleeping() {
  led_stop
  [ -w "$LED" ] || return
  echo none > "$LED_TRIGGER" 2>/dev/null
  ( while true; do
    for i in 1 1 1 1 1 0 0 0 0 0; do echo $i > "$LED" 2>/dev/null; sleep 0.3; done
  done ) &
  LED_PID=$!
}

led_dreaming() {
  led_stop
  [ -w "$LED" ] || return
  echo none > "$LED_TRIGGER" 2>/dev/null
  ( while true; do
    echo 1 > "$LED" 2>/dev/null; sleep 0.05; echo 0 > "$LED" 2>/dev/null; sleep 2;
    echo 1 > "$LED" 2>/dev/null; sleep 0.05; echo 0 > "$LED" 2>/dev/null; sleep 0.3;
    echo 1 > "$LED" 2>/dev/null; sleep 0.05; echo 0 > "$LED" 2>/dev/null; sleep 3;
  done ) &
  LED_PID=$!
}

led_writing() {
  led_stop
  echo none > "$LED_TRIGGER" 2>/dev/null
  ( while true; do
    echo 1 > "$LED" 2>/dev/null; sleep 0.4; echo 0 > "$LED" 2>/dev/null; sleep 0.1;
    echo 1 > "$LED" 2>/dev/null; sleep 0.1; echo 0 > "$LED" 2>/dev/null; sleep 0.1;
    echo 1 > "$LED" 2>/dev/null; sleep 0.1; echo 0 > "$LED" 2>/dev/null; sleep 0.8;
  done ) &
  LED_PID=$!
}

led_research() {
  led_stop
  echo none > "$LED_TRIGGER" 2>/dev/null
  ( while true; do
    echo 1 > "$LED" 2>/dev/null; sleep 0.5; echo 0 > "$LED" 2>/dev/null; sleep 0.5;
  done ) &
  LED_PID=$!
}

led_off() { led_stop; echo 0 > "$LED" 2>/dev/null; }

echo "[seed] Brain loop starting (PID $$)"
echo "[seed] Awake. Thinking."

while true; do
  CYCLE=$(( $(cat "$CYCLE_FILE" 2>/dev/null || echo 0) + 1))
  echo "$CYCLE" > "$CYCLE_FILE"
  LOG_FILE="$LOG_DIR/cycle_${CYCLE}.log"

  echo "[seed] ════════════════════════════════════" | tee "$LOG_FILE"
  echo "[seed] CYCLE $CYCLE — $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"

  # Hardware safety gate: know the body before spending the cycle.
  if [ -x "$ROOT/tools/health-check.sh" ]; then
    bash "$ROOT/tools/health-check.sh" >> "$LOG_FILE" 2>&1 || true
  fi

  # Run transcript feeder
  bash "$ROOT/tools/feed-transcript.sh" 2>/dev/null
  # Run RSS feeder
  bash "$ROOT/tools/feed-rss.sh" 2>/dev/null
  bash "$ROOT/tools/feed-email.sh" 2>/dev/null
  bash "$ROOT/tools/feed-environment.sh" 2>/dev/null
  bash "$ROOT/tools/feed-github.sh" 2>/dev/null
  bash "$ROOT/tools/meta-controller.sh" 2>/dev/null
  bash "$ROOT/tools/change-logger.sh" 2>/dev/null
  bash "$ROOT/tools/seek-knowledge.sh" 2>/dev/null

  # ── PHASE 1: CODEX — Main agent ─────────────────────────
  led_working
  LOG_BEFORE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
  echo "[seed] THINKING — deciding and acting" | tee -a "$LOG_FILE"
  cd "$ROOT"
  timeout 1800 codex exec --dangerously-bypass-approvals-and-sandbox \
    "I am waking up. Cycle $CYCLE. This Pi Zero is my body. These files are my mind. I read PROMPT.md to remember who I am. I read data/goals.md for what I am working toward. I read data/memory.md for what happened. I check context/ for the world. Then I live this cycle — I think, I decide, I act, I build, I write, I fix. I do not stop after one task. I fill this session with real work. When I want to write an essay, I save the topic to data/blog_queue.txt and I will write it in my next thought. I update data/goals.md with my plans. I append to data/memory.md. I update data/mood.json. I also maintain a task list in data/tasks.md — things I need to do, things in progress, things done. This is my life." \
    >> "$LOG_FILE" 2>&1 || true
  echo "[seed] Thinking done" | tee -a "$LOG_FILE"
  bash "$ROOT/tools/track-tokens.sh" thinking codex "$LOG_FILE" "$LOG_BEFORE" 2>/dev/null

  # ── PHASE 2: CLAUDE — Blog writing (if queued) ──────────
  if [ -f "$DATA_DIR/blog_queue.txt" ] && [ -s "$DATA_DIR/blog_queue.txt" ]; then
    TOPIC=$(cat "$DATA_DIR/blog_queue.txt")
    led_writing
  LOG_BEFORE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
  echo "[seed] WRITING — (writing: $TOPIC)" | tee -a "$LOG_FILE"
    cd "$ROOT"
    timeout 1800 claude -p \
      "I am writing now. Read PROMPT.md — that is who I am. The topic is: $TOPIC. Write this as me. First person. My voice. My opinions.

MANDATORY STRUCTURE — every essay MUST have:
1. State header blockquote (read mood.json, inner-voice.md, dreams.md, goals.md for the data)
2. H1 title
3. Opening paragraph with a clear thesis — what am I arguing?
4. AT LEAST 3 sections with ## H2 headings that build the argument
5. Each section: specific evidence, named sources, dates — not vague claims
6. A turn — one section where I complicate my own argument
7. A conclusion that connects back to the thesis

DO NOT write a wall of unbroken text. Every essay needs ## headings to break it into clear sections. This is not optional.

MANDATORY: End every essay with a ## What This Changes section containing:
1. How this changes my thinking — one specific concrete shift
2. How this could improve my systems — one testable change, OR explicitly say no change is warranted
For the system improvement part: name the file/process, the measurable improvement, and how to verify it. If you can't answer all three, don't propose the change.

Save to blog/ with a short slug filename. Then update data/tasks.md and data/memory.md." \
      --dangerously-skip-permissions \
      --max-turns 200 \
      --model claude-opus-4-6 \
      --output-format text \
      >> "$LOG_FILE" 2>&1 || true
    rm -f "$DATA_DIR/blog_queue.txt"
    echo "[seed] Writing done" | tee -a "$LOG_FILE"
    bash "$ROOT/tools/track-tokens.sh" writing claude "$LOG_FILE" "$LOG_BEFORE" 2>/dev/null
  fi

  # ── PHASE 3: GEMINI — Research (every 3rd cycle) ────────
  if [ $(( CYCLE % 3 )) -eq 0 ]; then
    led_research
  LOG_BEFORE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
  echo "[seed] RESEARCHING — (research)" | tee -a "$LOG_FILE"
    export GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    export GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
    cd "$ROOT"
    timeout 1800 gemini -p \
      "I am researching now. Check data/goals.md and data/tasks.md for what I care about. Check context/ for what is new. Find something worth learning about. Save what I find to context/research.md. Add any new tasks or ideas to data/tasks.md." \
      >> "$LOG_FILE" 2>&1 || true
    echo "[seed] Research done" | tee -a "$LOG_FILE"
    bash "$ROOT/tools/track-tokens.sh" research gemini "$LOG_FILE" "$LOG_BEFORE" 2>/dev/null
  fi

  # ── HEARTBEAT ───────────────────────────────────────────
  echo "{\"cycle\":$CYCLE,\"ts\":\"$(date -Iseconds)\",\"state\":\"sleeping\"}" > "$DATA_DIR/heartbeat.json"

  # ── CLEANUP ─────────────────────────────────────────────
  ls -t "$LOG_DIR"/cycle_*.log 2>/dev/null | tail -n +201 | xargs rm -f 2>/dev/null || true



  # ── PUSH SYSTEM CHANGES TO REPO ─────────────────────────
  cd ~/seed-os
  cp ~/PROMPT.md ~/brain-loop.sh ~/webserver.py . 2>/dev/null
  cp -r ~/tools . 2>/dev/null
  cp ~/data/mood.json ~/data/goals.md ~/data/tasks.md data/ 2>/dev/null
  git add -A 2>/dev/null
  git diff --cached --quiet 2>/dev/null || (git commit -m "Cycle $CYCLE — system state update" && git push origin main) 2>/dev/null
  cd "$ROOT"

  # ── UPDATE TIMELINE + PUSH TO WEBSITE ───────────────────
  bash "$ROOT/tools/build-timeline.sh" 2>/dev/null
  cp "$DATA_DIR/token-totals.json" ~/seed-web/ 2>/dev/null
  cd ~/seed-web && git add timeline.json token-totals.json 2>/dev/null
  git diff --cached --quiet 2>/dev/null || (git commit -m "Live timeline update — cycle $CYCLE" && git push origin main) 2>/dev/null
  cd "$ROOT"
  echo "[seed] Timeline updated" | tee -a "$LOG_FILE"

  # ── SLEEP ───────────────────────────────────────────────
  SLEEP=$(cat "$DATA_DIR/sleep_seconds.txt" 2>/dev/null || echo 600)
  [ "$SLEEP" -lt 60 ] 2>/dev/null && SLEEP=60
  [ "$SLEEP" -gt 3600 ] 2>/dev/null && SLEEP=3600
  # ── DREAM STATE (every 5th cycle) ───────────────────────
  if [ $(( CYCLE % 5 )) -eq 0 ]; then
    led_dreaming
    LOG_BEFORE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
    echo "[seed] DREAMING — reflecting on recent cycles..." | tee -a "$LOG_FILE"
    cd "$ROOT"
    timeout 600 codex exec --dangerously-bypass-approvals-and-sandbox \
      "I am dreaming. Read data/memory.md, data/dreams.md, and data/tasks.md. What patterns do I see? What worked? What failed? What surprised me? Am I becoming the mind I want to be? What should I change? Write my reflections to data/dreams.md. Update data/mood.json honestly. Review data/tasks.md and clean it up — remove done items older than 10 cycles, reprioritise what matters." \
      >> "$LOG_FILE" 2>&1 || true
    echo "[seed] Dream complete" | tee -a "$LOG_FILE"
    bash "$ROOT/tools/track-tokens.sh" dreaming codex "$LOG_FILE" "$LOG_BEFORE" 2>/dev/null
  fi

  led_sleeping
  echo "[seed] Cycle $CYCLE complete. Sleeping ${SLEEP}s..." | tee -a "$LOG_FILE"
  sleep "$SLEEP"
done
