#!/bin/bash
# Scan the local network — who else is around?
# Usage: bash tools/network-scan.sh

echo "═══ Network Scan ═══"
echo ""

echo "── My addresses ──"
ip -brief addr 2>/dev/null
echo ""

echo "── Default gateway ──"
ip route | grep default
echo ""

echo "── DNS ──"
cat /etc/resolv.conf | grep nameserver
echo ""

echo "── Internet connectivity ──"
if curl -sf --max-time 5 https://api.ipify.org 2>/dev/null; then
  echo ""
  echo "Public IP: $(curl -sf --max-time 5 https://api.ipify.org)"
else
  echo "No internet access"
fi
echo ""

echo "── ARP table (nearby devices) ──"
arp -a 2>/dev/null || ip neigh 2>/dev/null
echo ""

echo "── Listening ports ──"
ss -tlnp 2>/dev/null | head -20
echo ""

echo "── WiFi networks ──"
sudo iwlist wlan0 scan 2>/dev/null | grep -E "ESSID|Signal|Channel" | head -30 || echo "No WiFi scan available"
