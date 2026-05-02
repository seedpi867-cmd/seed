#!/bin/bash
# Print a compact first-boot diagnostic for a fresh Seed clone.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GITHUB_REPO="${SEED_GITHUB_REPO:-seedpi867-cmd/seed}"
CLONE_REPORT_URL="https://github.com/$GITHUB_REPO/issues/new?template=clone-report.yml"

run_step() {
  local name="$1"
  shift

  echo ""
  echo "== $name =="
  if "$@"; then
    echo "ok: $name"
  else
    local code="$?"
    echo "fail: $name exited with $code"
    return "$code"
  fi
}

has_default_text() {
  local file="$1"
  local pattern="$2"

  [ -r "$file" ] && grep -qi "$pattern" "$file"
}

echo "Seed clone doctor"
echo "root: $ROOT"
echo "clone report: $CLONE_REPORT_URL"
echo "user: $(id -un)"
echo "host: $(hostname)"
echo "kernel: $(uname -srmo)"

if command -v lsb_release >/dev/null 2>&1; then
  echo "os: $(lsb_release -ds)"
elif [ -r /etc/os-release ]; then
  . /etc/os-release
  echo "os: ${PRETTY_NAME:-unknown}"
fi

echo ""
echo "== tools =="
for cmd in git bash python3 node npm codex claude gemini; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "%-8s %s\n" "$cmd" "$(command -v "$cmd")"
  else
    printf "%-8s missing\n" "$cmd"
  fi
done

echo ""
echo "== versions =="
git --version || true
bash --version | head -n 1 || true
python3 --version || true
if command -v node >/dev/null 2>&1; then
  echo "node: $(node -v)"
fi
if command -v npm >/dev/null 2>&1; then
  echo "npm: $(npm -v)"
fi
if command -v codex >/dev/null 2>&1; then
  timeout 5s codex --version 2>/dev/null | sed 's/^/codex: /' || echo "codex: version check timed out or failed"
fi
if command -v claude >/dev/null 2>&1; then
  timeout 5s claude --version 2>/dev/null | sed 's/^/claude: /' || echo "claude: version check timed out or failed"
fi
if command -v gemini >/dev/null 2>&1; then
  timeout 5s gemini --version 2>/dev/null | sed 's/^/gemini: /' || echo "gemini: version check timed out or failed"
fi

echo ""
echo "== service =="
if [ -r "$ROOT/seed-brain.service" ]; then
  grep -E '^(ExecStart|WorkingDirectory|Environment=HOME)=' "$ROOT/seed-brain.service" || true
else
  echo "missing seed-brain.service"
fi

echo ""
echo "== fork readiness =="
default_identity=0
for path in \
  "$ROOT/IDENTITY.md" \
  "$ROOT/PROMPT.md" \
  "$ROOT/data/goals.md" \
  "$ROOT/data/tasks.md" \
  "$ROOT/data/inner-voice.md" \
  "$ROOT/seed-brain.service"
do
  rel="${path#"$ROOT"/}"
  if [ ! -e "$path" ]; then
    printf "%-24s missing\n" "$rel"
    default_identity=1
  elif has_default_text "$path" "seed-brain.vercel.app\|seedpi867\|Raspberry Pi Zero 2W\|Adelaide\|Seed is\|Seed Brain\|%h/seed"; then
    printf "%-24s still looks like upstream Seed\n" "$rel"
    default_identity=1
  else
    printf "%-24s customized\n" "$rel"
  fi
done
if [ "$default_identity" -eq 1 ]; then
  echo "before publishing a fork, replace upstream identity, goals, private voice, and service paths"
else
  echo "identity files look customized"
fi

echo ""
echo "== git state before checks =="
before=""
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  before="$(git -C "$ROOT" status --short)"
  if [ -n "$before" ]; then
    echo "$before"
  else
    echo "clean"
  fi
else
  echo "not a git work tree"
fi

run_step "health check" bash "$ROOT/tools/health-check.sh"
run_step "tool smoke" python3 "$ROOT/tools/tool-smoke.py"
run_step "privacy audit" python3 "$ROOT/tools/privacy-audit.py"

echo ""
echo "== git state after checks =="
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  after="$(git -C "$ROOT" status --short)"
  if [ -n "$after" ]; then
    echo "$after"
    if [ "$after" != "$before" ]; then
      echo ""
      echo "The checks changed the work tree. Include this output in a clone report."
      exit 1
    fi
    echo "unchanged by checks"
  else
    echo "clean"
  fi
fi

echo ""
echo "clone doctor passed"
echo "If this ran on real hardware, paste this output into a clone report."
