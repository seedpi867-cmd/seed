#!/bin/bash
# Full hardware discovery — what am I made of?

echo "═══════════════════════════════════════"
echo "  BODY SCAN"
echo "═══════════════════════════════════════"
echo ""

echo "── Identity ──"
cat /proc/device-tree/model 2>/dev/null && echo ""
uname -a
echo ""

echo "── CPU ──"
if command -v lscpu >/dev/null 2>&1; then
  lscpu | grep -E "Model name|Architecture|CPU\(s\)|MHz"
else
  echo "lscpu: unavailable"
fi
echo ""

echo "── Memory ──"
if command -v free >/dev/null 2>&1; then
  free -h
elif [ -r /proc/meminfo ]; then
  awk '/MemTotal|MemAvailable|SwapTotal|SwapFree/ {print}' /proc/meminfo
else
  echo "Memory details unavailable"
fi
echo ""

echo "── Storage ──"
if command -v df >/dev/null 2>&1; then
  df -h / /boot/firmware 2>/dev/null || df -h /
else
  echo "df: unavailable"
fi
if command -v lsblk >/dev/null 2>&1; then
  lsblk
else
  echo "lsblk: unavailable"
fi
echo ""

echo "── Temperature ──"
temp=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
if [ -n "$temp" ]; then
  awk -v temp="$temp" 'BEGIN { printf "CPU: %.1f°C\n", temp / 1000 }'
else
  echo "Unknown"
fi
echo ""

echo "── Network Interfaces ──"
ip -brief addr 2>/dev/null || ip addr
echo ""

echo "── WiFi ──"
if command -v iwconfig >/dev/null 2>&1; then
  iwconfig 2>/dev/null | grep -v "no wireless"
else
  echo "iwconfig: unavailable"
fi
echo ""

echo "── USB Devices ──"
if command -v lsusb >/dev/null 2>&1; then
  lsusb
else
  echo "lsusb: unavailable"
fi
echo ""

echo "── Serial Ports ──"
ls -la /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/serial* 2>/dev/null || echo "None found"
echo ""

echo "── Display ──"
ls /dev/fb* 2>/dev/null && echo "Framebuffer: yes" || echo "Framebuffer: no"
ls /dev/dri/* 2>/dev/null
for card in /sys/class/drm/card*-*; do
  [ -f "$card/status" ] && echo "$(basename $card): $(cat $card/status)"
done 2>/dev/null
xrandr 2>/dev/null | head -5 || echo "No X display"
echo ""

echo "── Audio ──"
aplay -l 2>/dev/null || echo "No audio devices"
echo ""

echo "── GPIO ──"
[ -d /sys/class/gpio ] && echo "GPIO: available" || echo "GPIO: not found"
ls /sys/class/gpio/ 2>/dev/null
echo ""

echo "── I2C Devices ──"
for bus in /dev/i2c-*; do
  [ -c "$bus" ] && echo "Bus: $bus" && sudo i2cdetect -y ${bus##*-} 2>/dev/null
done
echo ""

echo "── SPI ──"
ls /dev/spidev* 2>/dev/null || echo "No SPI devices"
echo ""

echo "── Camera ──"
ls /dev/video* 2>/dev/null || echo "No cameras"
vcgencmd get_camera 2>/dev/null
echo ""

echo "── Modem ──"
mmcli -L 2>/dev/null || echo "ModemManager: no modems"
echo ""

echo "── Installed Languages ──"
for cmd in node python3 python gcc g++ rustc go java ruby; do
  path=$(which $cmd 2>/dev/null)
  [ -n "$path" ] && echo "  $cmd: $($cmd --version 2>&1 | head -1)"
done
echo ""

echo "── Key Tools ──"
for cmd in claude git sqlite3 npm pip3 pm2 nginx gammu ffmpeg espeak http-server tsx tmux; do
  path=$(which $cmd 2>/dev/null)
  [ -n "$path" ] && echo "  ✓ $cmd ($path)" || echo "  ✗ $cmd"
done
echo ""

echo "═══════════════════════════════════════"
echo "  Scan complete."
echo "═══════════════════════════════════════"
