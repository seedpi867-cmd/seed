"""
Tool: system_health
Report Pi system stats: CPU, RAM, disk, temp, uptime.
args: {} (no args needed)
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    def _read(cmd):
        try:
            return subprocess.check_output(cmd, shell=True, text=True, timeout=5).strip()
        except Exception:
            return "?"

    mem_cmd = "free -m | awk '/Mem:/ {printf \"%dMB used / %dMB total\", $3, $2}'"
    disk_cmd = "df -h / | awk 'NR==2 {printf \"%s used / %s total\", $3, $2}'"
    temp_cmd = "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1fC\", $1/1000}'"
    load_cmd = "cat /proc/loadavg | cut -d' ' -f1-3"

    lines = [
        "uptime: " + _read("uptime -p"),
        "memory: " + _read(mem_cmd),
        "disk: " + _read(disk_cmd),
        "temp: " + _read(temp_cmd),
        "load: " + _read(load_cmd),
    ]

    return True, "\n".join(lines)


if __name__ == "__main__":
    ok, output = run({})
    print(output)
    raise SystemExit(0 if ok else 1)
