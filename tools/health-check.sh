#!/bin/bash
# Check Seed hardware health against data/safety.json.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"
SAFETY="$DATA/safety.json"
HEALTH="$DATA/health.json"
LOGS="$DATA/logs"
SLEEP_FILE="$DATA/sleep_seconds.txt"

mkdir -p "$DATA" "$LOGS"

if [ ! -f "$SAFETY" ]; then
  echo "[health] Missing $SAFETY" >&2
  exit 1
fi

read_threshold() {
  local key="$1"
  python3 - "$SAFETY" "$key" <<'PY'
import json
import sys

path, key = sys.argv[1], sys.argv[2]
data = json.load(open(path))
value = data
for part in key.split("."):
    value = value[part]
print(value)
PY
}

max_temp="$(read_threshold max_temp_celsius)"
max_ram="$(read_threshold max_ram_percent)"
max_disk="$(read_threshold max_disk_percent)"
min_free_ram="$(read_threshold min_free_ram_mb)"
max_logs="$(read_threshold max_log_files)"
hot_sleep="$(read_threshold health_check.sleep_seconds_when_hot)"
ram_sleep="$(read_threshold health_check.sleep_seconds_when_ram_high)"
root_mount="$(read_threshold health_check.root_mount)"
boot_mount="$(read_threshold health_check.boot_mount)"

temp_raw="$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)"
temp_c="$(awk -v t="$temp_raw" 'BEGIN { printf "%.1f", t / 1000 }')"

read -r mem_total mem_used mem_available < <(free -m | awk 'NR==2 {print $2, $3, $7}')
ram_percent="$(awk -v used="$mem_used" -v total="$mem_total" 'BEGIN { printf "%.0f", (used / total) * 100 }')"

disk_percent="$(df -P "$root_mount" | awk 'NR==2 {gsub("%", "", $5); print $5}')"
boot_percent="$(df -P "$boot_mount" 2>/dev/null | awk 'NR==2 {gsub("%", "", $5); print $5}')"
boot_percent="${boot_percent:-0}"
load_avg="$(awk '{print $1 " " $2 " " $3}' /proc/loadavg)"
throttled="$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2 || echo unknown)"

status="ok"
actions=()

temp_high="$(awk -v t="$temp_c" -v max="$max_temp" 'BEGIN { print (t > max) ? 1 : 0 }')"
if [ "$temp_high" -eq 1 ]; then
  status="warning"
  actions+=("temperature ${temp_c}C exceeded ${max_temp}C; set sleep to ${hot_sleep}s")
  echo "$hot_sleep" > "$SLEEP_FILE"
fi

if [ "$ram_percent" -gt "$max_ram" ] || [ "$mem_available" -lt "$min_free_ram" ]; then
  status="warning"
  actions+=("ram ${ram_percent}% used with ${mem_available}MB available; attempted filesystem cache drop")
  sync || true
  if [ -w /proc/sys/vm/drop_caches ]; then
    echo 3 > /proc/sys/vm/drop_caches || true
  else
    sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null || true
  fi
  echo "$ram_sleep" > "$SLEEP_FILE"
fi

if [ "$disk_percent" -gt "$max_disk" ] || [ "$boot_percent" -gt "$max_disk" ]; then
  status="warning"
  actions+=("disk threshold exceeded; pruned old logs and cleaned apt cache")
  ls -t "$LOGS"/cycle_*.log 2>/dev/null | tail -n +"$((max_logs + 1))" | xargs -r rm -f
  sudo apt-get clean 2>/dev/null || true
fi

ls -t "$LOGS"/cycle_*.log 2>/dev/null | tail -n +"$((max_logs + 1))" | xargs -r rm -f

python3 - "$HEALTH" "$status" "$temp_c" "$ram_percent" "$mem_total" "$mem_used" "$mem_available" "$disk_percent" "$boot_percent" "$load_avg" "$throttled" "${actions[@]}" <<'PY'
import json
import sys
from datetime import datetime, timezone

(
    path,
    status,
    temp_c,
    ram_percent,
    mem_total,
    mem_used,
    mem_available,
    disk_percent,
    boot_percent,
    load_avg,
    throttled,
    *actions,
) = sys.argv[1:]

payload = {
    "checked_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "status": status,
    "temperature_celsius": float(temp_c),
    "ram_percent": int(ram_percent),
    "memory_mb": {
        "total": int(mem_total),
        "used": int(mem_used),
        "available": int(mem_available),
    },
    "disk_percent": {
        "root": int(disk_percent),
        "boot": int(boot_percent),
    },
    "load_average": load_avg,
    "throttled": throttled,
    "actions": actions,
}

with open(path, "w") as fh:
    json.dump(payload, fh, indent=2)
    fh.write("\n")
PY

echo "[health] ${status}: temp=${temp_c}C ram=${ram_percent}% avail=${mem_available}MB disk=${disk_percent}% boot=${boot_percent}%"
