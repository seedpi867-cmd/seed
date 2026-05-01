#!/usr/bin/env python3
"""
system_monitor.py — Continuous system stats writer.
Writes JSON to ~/data/sys_stats.json every 30s.
Usage: python3 system_monitor.py [--once] [--interval N]
"""
import argparse
import json
import time
from pathlib import Path


def read_stats() -> dict:
    stats = {'ts': time.time()}

    # RAM
    try:
        mem = Path('/proc/meminfo').read_text()
        def _kb(key):
            for line in mem.splitlines():
                if line.startswith(key):
                    return int(line.split()[1]) * 1024
            return 0
        total = _kb('MemTotal:')
        avail = _kb('MemAvailable:')
        used  = total - avail
        stats['ram_pct']    = round(used / total * 100, 1) if total else 0
        stats['ram_used_mb']  = round(used / 1_048_576)
        stats['ram_total_mb'] = round(total / 1_048_576)
    except Exception as e:
        stats['ram_error'] = str(e)

    # CPU load
    try:
        parts = Path('/proc/loadavg').read_text().split()
        cores = sum(1 for l in Path('/proc/cpuinfo').read_text().splitlines()
                    if l.startswith('processor'))
        stats['load_1m']  = float(parts[0])
        stats['load_5m']  = float(parts[1])
        stats['cpu_pct']  = round(min(float(parts[0]) / max(cores, 1) * 100, 100), 1)
        stats['cpu_cores'] = cores
    except Exception as e:
        stats['cpu_error'] = str(e)

    # Temperature
    try:
        raw = Path('/sys/class/thermal/thermal_zone0/temp').read_text().strip()
        stats['temp_c'] = round(int(raw) / 1000, 1)
    except Exception:
        stats['temp_c'] = None

    # Disk
    try:
        import shutil
        du = shutil.disk_usage('/')
        stats['disk_used_gb']  = round(du.used  / 1e9, 2)
        stats['disk_total_gb'] = round(du.total / 1e9, 2)
        stats['disk_pct']      = round(du.used  / du.total * 100, 1)
    except Exception as e:
        stats['disk_error'] = str(e)

    # Uptime
    try:
        up = float(Path('/proc/uptime').read_text().split()[0])
        h, rem = divmod(int(up), 3600)
        m, s   = divmod(rem, 60)
        stats['uptime_s']  = int(up)
        stats['uptime_str'] = f'{h}h {m}m' if h else f'{m}m {s}s'
    except Exception:
        pass

    # Network
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        stats['local_ip'] = s.getsockname()[0]
        s.close()
    except Exception:
        stats['local_ip'] = 'unknown'

    return stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--once',     action='store_true', help='Print once and exit')
    p.add_argument('--interval', type=int, default=30, help='Seconds between writes')
    args = p.parse_args()

    out = Path.home() / 'data' / 'sys_stats.json'
    out.parent.mkdir(parents=True, exist_ok=True)

    while True:
        stats = read_stats()
        out.write_text(json.dumps(stats, indent=2))
        print(json.dumps(stats))

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
