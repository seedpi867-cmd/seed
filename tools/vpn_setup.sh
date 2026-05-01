#!/bin/bash
# vpn_setup.sh — Install and configure Tailscale VPN on SEED.
# Tailscale provides encrypted mesh networking, stable IP, remote access.
# Usage: bash vpn_setup.sh install|status|ip|check|auth-url|up|down

set -euo pipefail

case "${1:-install}" in

  install)
    echo "=== Installing Tailscale ==="

    # Install
    if ! command -v tailscale &>/dev/null; then
      curl -fsSL https://tailscale.com/install.sh | sh
      echo "Tailscale installed."
    else
      echo "Tailscale already installed: $(tailscale version)"
    fi

    # Enable and start the daemon
    sudo systemctl enable tailscaled
    sudo systemctl start tailscaled
    sleep 2

    echo ""
    echo "=== Connecting to Tailscale ==="
    echo "You will see an auth URL below. Open it on any device to authorize SEED."
    echo ""

    # Start up — this prints the auth URL
    sudo tailscale up \
      --accept-routes \
      --accept-dns \
      --ssh \
      --hostname "seed-pi" \
      2>&1 | tee /tmp/tailscale_auth.txt

    # Extract and display auth URL
    AUTH_URL=$(grep -o 'https://login.tailscale.com/[^ ]*' /tmp/tailscale_auth.txt || true)
    if [[ -n "$AUTH_URL" ]]; then
      echo ""
      echo "AUTH URL: $AUTH_URL"
      echo "$AUTH_URL" > "$HOME/data/tailscale_auth_url.txt"
      echo "URL saved to ~/data/tailscale_auth_url.txt"
    fi
    ;;

  status)
    if command -v tailscale &>/dev/null; then
      tailscale status 2>&1 || echo "Tailscale not connected"
    else
      echo "Tailscale not installed"
    fi
    ;;

  ip)
    tailscale ip -4 2>/dev/null || echo "not connected"
    ;;

  check)
    if ! command -v tailscale &>/dev/null; then
      echo "NOT_INSTALLED"
      exit 1
    fi
    STATUS=$(tailscale status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('BackendState','unknown'))" 2>/dev/null || echo "unknown")
    echo "$STATUS"
    [[ "$STATUS" == "Running" ]] && exit 0 || exit 1
    ;;

  auth-url)
    if [[ -f "$HOME/data/tailscale_auth_url.txt" ]]; then
      cat "$HOME/data/tailscale_auth_url.txt"
    else
      echo "No auth URL saved. Run: bash vpn_setup.sh install"
    fi
    ;;

  up)
    sudo tailscale up --accept-routes --accept-dns --ssh --hostname "seed-pi"
    ;;

  down)
    sudo tailscale down
    ;;

  *)
    echo "Usage: vpn_setup.sh install|status|ip|check|auth-url|up|down"
    exit 1
    ;;
esac
