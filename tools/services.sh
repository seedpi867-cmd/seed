#!/bin/bash
# Service management helper
# Usage: bash tools/services.sh [list|create NAME COMMAND|start NAME|stop NAME|logs NAME]

ACTION="${1:-list}"
NAME="${2:-}"
COMMAND="${3:-}"

case "$ACTION" in
  list)
    echo "═══ Running Services ═══"
    systemctl list-units --type=service --state=running --no-pager | grep -v "^$"
    ;;
  create)
    [ -z "$NAME" ] || [ -z "$COMMAND" ] && echo "Usage: services.sh create <name> <command>" && exit 1
    sudo tee /etc/systemd/system/${NAME}.service > /dev/null << EOF
[Unit]
Description=$NAME
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
Environment=HOME=/home/pi
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=$COMMAND
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable "$NAME"
    sudo systemctl start "$NAME"
    echo "Created and started: $NAME"
    ;;
  start)
    sudo systemctl start "$NAME" && echo "Started: $NAME"
    ;;
  stop)
    sudo systemctl stop "$NAME" && echo "Stopped: $NAME"
    ;;
  restart)
    sudo systemctl restart "$NAME" && echo "Restarted: $NAME"
    ;;
  logs)
    journalctl -u "$NAME" -n 50 --no-pager
    ;;
  *)
    echo "Usage: services.sh [list|create|start|stop|restart|logs] [name] [command]"
    ;;
esac
