#!/bin/bash
# network_scan.sh — Discover devices on the local network.
# Uses arp-scan if available, falls back to ping sweep.
# Usage: bash network_scan.sh [--subnet 192.168.8.0/24] [--json]

SUBNET=""
AS_JSON=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --subnet) SUBNET="$2"; shift 2 ;;
        --json)   AS_JSON=true;  shift ;;
        *) shift ;;
    esac
done

# Auto-detect subnet if not specified
if [[ -z "$SUBNET" ]]; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    SUBNET=$(echo "$LOCAL_IP" | cut -d. -f1-3).0/24
fi

echo "# Scanning $SUBNET" >&2

if command -v arp-scan &>/dev/null; then
    RESULTS=$(sudo arp-scan "$SUBNET" 2>/dev/null | grep -E '^[0-9]' | awk '{print $1, $2, $3}')
elif command -v nmap &>/dev/null; then
    RESULTS=$(nmap -sn "$SUBNET" 2>/dev/null | grep -E 'report for|MAC Address' | \
        paste - - | sed 's/Nmap scan report for //; s/MAC Address: //')
else
    # Ping sweep fallback
    PREFIX=$(echo "$SUBNET" | cut -d. -f1-3)
    RESULTS=""
    for i in $(seq 1 254); do
        if ping -c1 -W1 "$PREFIX.$i" &>/dev/null 2>&1; then
            MAC=$(arp -n "$PREFIX.$i" 2>/dev/null | awk '/ether/{print $3}')
            RESULTS="$RESULTS\n$PREFIX.$i $MAC unknown"
        fi
    done
    RESULTS=$(echo -e "$RESULTS" | grep -v '^$')
fi

if $AS_JSON; then
    echo '["'"$(echo "$RESULTS" | tr '\n' '|' | sed 's/|/","/g; s/,"$//; s/^/"/')"'"]'
else
    echo "$RESULTS"
fi
