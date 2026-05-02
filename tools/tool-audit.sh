#!/bin/bash
# Audit Seed's local tools with static checks and safe smoke tests.
# Usage: tools/tool-audit.sh [output-file]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/data/tool_audit.md}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

mkdir -p "$(dirname "$OUT")"

run_check() {
  local name="$1"
  local kind="$2"
  local command="$3"
  local status

  set +e
  timeout 30s bash -lc "cd '$ROOT' && $command" >"$TMP" 2>&1
  status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    printf '| `%s` | %s | pass | `%s` |\n' "$name" "$kind" "$command"
  elif [ "$status" -eq 124 ]; then
    printf '| `%s` | %s | fail | timed out: `%s` |\n' "$name" "$kind" "$command"
  else
    local detail
    detail="$(head -1 "$TMP" | tr '|' '/' | tr '\n' ' ')"
    [ -n "$detail" ] || detail="exit $status"
    printf '| `%s` | %s | fail | %s (`%s`) |\n' "$name" "$kind" "$detail" "$command"
  fi
}

run_dependency_check() {
  local name="$1"
  local kind="$2"
  local dependency="$3"
  local command="$4"

  if ! command -v "$dependency" >/dev/null 2>&1; then
    printf '| `%s` | %s | skipped | missing dependency: `%s` |\n' "$name" "$kind" "$dependency"
    return
  fi

  run_check "$name" "$kind" "$command"
}

{
  echo "# Tool Audit"
  echo
  echo "Generated: $(date -Is)"
  echo
  echo "## Static Checks"
  echo
  echo "| Tool | Check | Result | Detail |"
  echo "|---|---|---|---|"

  while IFS= read -r tool; do
    case "$tool" in
      *.sh)
        run_check "$tool" "shell syntax" "bash -n '$tool'"
        ;;
      *.py)
        run_check "$tool" "python compile" "python3 -m py_compile '$tool'"
        ;;
    esac
  done < <(find "$ROOT/tools" -maxdepth 1 -type f | sed "s#^$ROOT/##" | sort)

  echo
  echo "## Safe Smoke Checks"
  echo
  echo "| Tool | Check | Result | Detail |"
  echo "|---|---|---|---|"

  run_check "tools/body-scan.sh" "safe run" "tools/body-scan.sh"
  run_check "tools/check_memory.sh" "safe run" "tools/check_memory.sh --min-mb 50"
  run_check "tools/cloudflare.sh" "status" "tools/cloudflare.sh status"
  run_check "tools/context-builder-smoke.sh" "smoke" "tools/context-builder-smoke.sh"
  run_dependency_check "tools/db.sh" "temp SQLite smoke" "sqlite3" "tmp_db=\$(mktemp /tmp/seed-db-smoke.XXXXXX.db) && trap 'rm -f \"\$tmp_db\"' EXIT && tools/db.sh \"\$tmp_db\" 'CREATE TABLE smoke (id INTEGER PRIMARY KEY, note TEXT); INSERT INTO smoke (note) VALUES (\"ok\"); SELECT note FROM smoke;' | grep -q ok"
  run_check "tools/download_file.py" "isolated mock smoke" "python3 tools/tool-smoke.py download_file.py"
  run_check "tools/feed-transcript-smoke.sh" "smoke" "tools/feed-transcript-smoke.sh"
  run_check "tools/fetch_url.py" "isolated guard smoke" "python3 tools/tool-smoke.py fetch_url.py"
  run_check "tools/file_ops.py" "isolated smoke" "python3 tools/tool-smoke.py file_ops.py"
  run_check "tools/file_read.py" "isolated smoke" "python3 tools/tool-smoke.py file_read.py"
  run_check "tools/file_write.py" "isolated smoke" "python3 tools/tool-smoke.py file_write.py"
  run_check "tools/health-check.sh" "safe run" "tools/health-check.sh"
  run_check "tools/modem-status.sh" "safe run" "tools/modem-status.sh"
  run_check "tools/network-scan.sh" "safe run" "tools/network-scan.sh"
  run_check "tools/pace.sh" "status" "tools/pace.sh status"
  run_check "tools/plant_goal.py" "isolated smoke" "python3 tools/tool-smoke.py plant_goal.py"
  run_check "tools/port_check.py" "isolated smoke" "python3 tools/tool-smoke.py port_check.py"
  run_check "tools/search_web.py" "isolated mock smoke" "python3 tools/tool-smoke.py search_web.py"
  run_check "tools/shell_exec.py" "isolated smoke" "python3 tools/tool-smoke.py shell_exec.py"
  run_check "tools/system_health.py" "safe run" "python3 tools/system_health.py"
  run_check "tools/system_monitor.py" "isolated smoke" "python3 tools/tool-smoke.py system_monitor.py"
  run_check "tools/tool-smoke.py" "self smoke" "python3 tools/tool-smoke.py"
  run_check "tools/transcript-duplicates.sh" "report" "tools/transcript-duplicates.sh /tmp/seed-transcript-duplicates.md"
  run_check "tools/transcript-flatten-dry-run.sh" "dry run" "tools/transcript-flatten-dry-run.sh"
  run_check "tools/transcript-flatten-manifest.sh" "report" "tools/transcript-flatten-manifest.sh /tmp/seed-transcript-flatten-manifest.md"
  run_check "tools/transcript-inventory.sh" "report" "tools/transcript-inventory.sh /tmp/seed-transcript-inventory.md"
  run_check "tools/transcript-prune-nested-duplicates.sh" "dry run" "tools/transcript-prune-nested-duplicates.sh"
  run_check "tools/vpn_setup.sh" "status" "tools/vpn_setup.sh status"
  run_check "tools/web_fetch.py" "isolated mock smoke" "python3 tools/tool-smoke.py web_fetch.py"
  run_check "tools/website.sh" "status" "tools/website.sh status"
  run_check "tools/write_blog_post.py" "isolated smoke" "python3 tools/tool-smoke.py write_blog_post.py"

  echo
  echo "## Deferred Checks"
  echo
  echo "These tools were not smoke-run because they install packages, alter services, write to displays/audio, send messages, fetch remote data, mutate git repos, start long-running daemons, or require user-supplied targets:"
  echo
  echo "- \`tools/cron_helper.sh\`"
  echo "- \`tools/deploy-blog.sh\`"
  echo "- \`tools/deploy-idempotence-check.sh\`"
  echo "- \`tools/feed-rss.sh\`"
  echo "- \`tools/git_ops.sh\`"
  echo "- \`tools/gpio-scan.sh\`"
  echo "- \`tools/install_pkg.sh\`"
  echo "- \`tools/kiosk.sh\`"
  echo "- \`tools/migrate_legacy_db.py\`"
  echo "- \`tools/network_scan.sh\`"
  echo "- \`tools/remember_fact.py\`"
  echo "- \`tools/screen-write.sh\`"
  echo "- \`tools/self-maintain.sh\`"
  echo "- \`tools/self-restart.sh\`"
  echo "- \`tools/self_edit.py\`"
  echo "- \`tools/send-email.py\`"
  echo "- \`tools/send_chat.py\`"
  echo "- \`tools/services.sh\`"
  echo "- \`tools/speak.sh\`"
  echo "- \`tools/store_fact.py\`"
  echo "- \`tools/watchdog.sh\`"
  echo "- \`tools/webserver.sh\`"
} > "$OUT"

echo "[tool-audit] wrote $OUT"
