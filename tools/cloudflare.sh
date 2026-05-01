#!/bin/bash
# Cloudflare tunnel helper for Seed.
# Usage: cloudflare.sh [install|init|enable|status|logs]

set -u

CLOUDFLARE_DIR="${HOME}/cloudflare"
ENV_FILE="${CLOUDFLARE_DIR}/cloudflared.env"
ENV_EXAMPLE="${HOME}/cloudflare.env.example"
UNIT_DIR="${HOME}/.config/systemd/user"
UNIT_FILE="${UNIT_DIR}/seed-cloudflared.service"

ensure_env() {
  mkdir -p "$CLOUDFLARE_DIR"
  if [ ! -f "$ENV_EXAMPLE" ]; then
    printf 'TUNNEL_TOKEN=\n' > "$ENV_EXAMPLE"
  fi
  if [ ! -f "$ENV_FILE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
  fi
}

token_ready() {
  [ -f "$ENV_FILE" ] && grep -Eq '^TUNNEL_TOKEN=.{20,}' "$ENV_FILE"
}

user_bus_ready() {
  [ -n "${XDG_RUNTIME_DIR:-}" ] || [ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]
}

case "${1:-status}" in
  install)
    ensure_env
    if command -v cloudflared >/dev/null 2>&1; then
      cloudflared --version
    else
      echo "cloudflared is not installed"
      exit 1
    fi
    echo "Env file: $ENV_FILE"
    ;;
  init)
    ensure_env
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Seed Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token \${TUNNEL_TOKEN}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
    if user_bus_ready; then
      systemctl --user daemon-reload
    else
      echo "User systemd bus unavailable; daemon-reload deferred"
    fi
    if token_ready; then
      echo "Created $UNIT_FILE"
    else
      echo "Created $UNIT_FILE; add TUNNEL_TOKEN to $ENV_FILE before enabling"
    fi
    ;;
  enable)
    ensure_env
    if [ ! -f "$UNIT_FILE" ]; then
      "$0" init
    fi
    if ! token_ready; then
      echo "Missing TUNNEL_TOKEN in $ENV_FILE"
      exit 1
    fi
    if ! user_bus_ready; then
      echo "User systemd bus unavailable; run from a login session or enable lingering"
      exit 1
    fi
    systemctl --user enable --now seed-cloudflared.service
    systemctl --user --no-pager --full status seed-cloudflared.service
    ;;
  status)
    ensure_env
    echo "cloudflared: $(command -v cloudflared || echo missing)"
    if command -v cloudflared >/dev/null 2>&1; then
      cloudflared --version
    fi
    echo "env: $ENV_FILE"
    if token_ready; then
      echo "token: present"
    else
      echo "token: missing"
    fi
    if [ -f "$UNIT_FILE" ]; then
      echo "service: $UNIT_FILE"
      if user_bus_ready; then
        systemctl --user --no-pager --full status seed-cloudflared.service || true
      else
        echo "user bus: unavailable"
      fi
    else
      echo "service: missing"
    fi
    ;;
  logs)
    journalctl --user -u seed-cloudflared.service -n 80 --no-pager
    ;;
  *)
    echo "Usage: cloudflare.sh [install|init|enable|status|logs]"
    exit 2
    ;;
esac
