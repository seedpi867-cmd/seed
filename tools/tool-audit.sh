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
  run_check "tools/feed-transcript-smoke.sh" "smoke" "tools/feed-transcript-smoke.sh"
  run_check "tools/health-check.sh" "safe run" "tools/health-check.sh"
  run_check "tools/modem-status.sh" "safe run" "tools/modem-status.sh"
  run_check "tools/network-scan.sh" "safe run" "tools/network-scan.sh"
  run_check "tools/pace.sh" "status" "tools/pace.sh status"
  run_check "tools/transcript-duplicates.sh" "report" "tools/transcript-duplicates.sh /tmp/seed-transcript-duplicates.md"
  run_check "tools/transcript-flatten-dry-run.sh" "dry run" "tools/transcript-flatten-dry-run.sh"
  run_check "tools/transcript-flatten-manifest.sh" "report" "tools/transcript-flatten-manifest.sh /tmp/seed-transcript-flatten-manifest.md"
  run_check "tools/transcript-inventory.sh" "report" "tools/transcript-inventory.sh /tmp/seed-transcript-inventory.md"
  run_check "tools/transcript-prune-nested-duplicates.sh" "dry run" "tools/transcript-prune-nested-duplicates.sh"
  run_check "tools/vpn_setup.sh" "status" "tools/vpn_setup.sh status"
  run_check "tools/website.sh" "status" "tools/website.sh status"

  echo
  echo "## Deferred Checks"
  echo
  echo "These tools were not smoke-run because they install packages, alter services, write to displays/audio, send messages, fetch remote data, mutate git repos, start long-running daemons, or require user-supplied targets:"
  echo
  echo "- \`tools/cron_helper.sh\`"
  echo "- \`tools/db.sh\`"
  echo "- \`tools/deploy-blog.sh\`"
  echo "- \`tools/deploy-idempotence-check.sh\`"
  echo "- \`tools/download_file.py\`"
  echo "- \`tools/feed-rss.sh\`"
  echo "- \`tools/fetch_url.py\`"
  echo "- \`tools/file_ops.py\`"
  echo "- \`tools/file_read.py\`"
  echo "- \`tools/file_write.py\`"
  echo "- \`tools/git_ops.sh\`"
  echo "- \`tools/gpio-scan.sh\`"
  echo "- \`tools/install_pkg.sh\`"
  echo "- \`tools/kiosk.sh\`"
  echo "- \`tools/migrate_legacy_db.py\`"
  echo "- \`tools/network_scan.sh\`"
  echo "- \`tools/plant_goal.py\`"
  echo "- \`tools/port_check.py\`"
  echo "- \`tools/remember_fact.py\`"
  echo "- \`tools/screen-write.sh\`"
  echo "- \`tools/search_web.py\`"
  echo "- \`tools/self-maintain.sh\`"
  echo "- \`tools/self-restart.sh\`"
  echo "- \`tools/self_edit.py\`"
  echo "- \`tools/send-email.py\`"
  echo "- \`tools/send_chat.py\`"
  echo "- \`tools/services.sh\`"
  echo "- \`tools/shell_exec.py\`"
  echo "- \`tools/speak.sh\`"
  echo "- \`tools/store_fact.py\`"
  echo "- \`tools/system_health.py\`"
  echo "- \`tools/system_monitor.py\`"
  echo "- \`tools/watchdog.sh\`"
  echo "- \`tools/web_fetch.py\`"
  echo "- \`tools/webserver.sh\`"
  echo "- \`tools/write_blog_post.py\`"
} > "$OUT"

echo "[tool-audit] wrote $OUT"
