#!/bin/bash
# Physical environment awareness
python3 - << 'PYEOF'
import os, time, json

OUT = os.path.expanduser("~/context/environment.md")
out = f"## My Body — {time.strftime('%Y-%m-%d %H:%M')}\n\n"

# Temperature
temp = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
temp_c = int(temp) / 1000
out += f"**Temperature:** {temp_c:.1f}°C"
if temp_c > 60: out += " ⚠️ HOT"
elif temp_c > 50: out += " warm"
elif temp_c < 35: out += " cool"
else: out += " normal"
out += "\n"

# RAM
mem = os.popen("free -m").read().split("\n")[1].split()
used, total = int(mem[2]), int(mem[1])
pct = used/total*100
out += f"**RAM:** {used}MB/{total}MB ({pct:.0f}%)"
if pct > 80: out += " ⚠️ LOW"
out += "\n"

# Disk
disk = os.popen("df -h /").read().split("\n")[1].split()
out += f"**Disk:** {disk[2]} used of {disk[1]} ({disk[4]})\n"

# Uptime
out += f"**Uptime:** {os.popen('uptime -p').read().strip()}\n"

# Load
load = os.popen("cat /proc/loadavg").read().split()
out += f"**Load:** {load[0]} {load[1]} {load[2]}\n"

# Network
out += f"**IP:** {os.popen('hostname -I').read().strip()}\n"

# How I should feel about this
out += "\n### Body Check\n"
if temp_c > 55: out += "I am running hot. I should slow down.\n"
if pct > 75: out += "My RAM is getting full. I should be mindful about what I run.\n"
if int(disk[4].replace('%','')) > 70: out += "My disk is filling up. I should clean.\n"
if float(load[0]) > 2: out += "I am under load. Something is working hard.\n"
if temp_c < 40 and pct < 50: out += "I feel good. Cool and light.\n"

with open(OUT, "w") as f:
    f.write(out)
print("[env] Body state saved")
PYEOF
