#!/bin/bash
# Check modem/cellular/SMS status
# Usage: bash tools/modem-status.sh

echo "═══ Modem Status ═══"
echo ""

echo "── ModemManager ──"
MODEM_IDX=$(mmcli -L 2>/dev/null | grep -oP '/Modem/\K\d+' | head -1)
if [ -n "$MODEM_IDX" ]; then
  echo "Modem found: index $MODEM_IDX"
  echo ""
  mmcli -m "$MODEM_IDX" 2>/dev/null
  echo ""
  echo "── SIM Info ──"
  mmcli -m "$MODEM_IDX" --sim 2>/dev/null || echo "No SIM details"
  echo ""
  echo "── Signal ──"
  mmcli -m "$MODEM_IDX" --signal-get 2>/dev/null || echo "No signal info"
else
  echo "No modem detected via ModemManager"
fi

echo ""
echo "── Gammu ──"
if command -v gammu &>/dev/null; then
  gammu identify 2>/dev/null || echo "Gammu cannot identify modem"
  echo ""
  gammu getsignal 2>/dev/null || echo "No signal info"
else
  echo "Gammu not installed"
fi

echo ""
echo "── Serial Devices ──"
for dev in /dev/ttyUSB* /dev/ttyACM*; do
  [ -c "$dev" ] && echo "  $dev ($(ls -la $dev | awk '{print $5, $6}'))"
done 2>/dev/null

echo ""
echo "── Network Connections ──"
nmcli connection show 2>/dev/null || echo "NetworkManager not available"
