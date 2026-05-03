#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │     SEED — First Boot Setup     │"
echo "  └─────────────────────────────────┘"
echo ""

REQUIRED_BACKEND=""

echo "Choose one AI backend to install:"
echo "  1) Codex   (used by think/research/dream/maintain phases)"
echo "  2) Claude  (used by write phase)"
echo "  3) Gemini  (API-key only; no npm install)"
echo "  4) Skip    (I already installed a backend)"
echo ""
read -r -p "Backend [1-4]: " BACKEND

case "${BACKEND:-1}" in
    1)
        if ! command -v npm >/dev/null 2>&1; then
            echo "npm is required before installing Codex CLI."
            echo "On Raspberry Pi OS: sudo apt update && sudo apt install -y nodejs npm"
            exit 1
        fi
        echo "Installing Codex CLI..."
        sudo npm install -g @openai/codex
        REQUIRED_BACKEND="codex"
        ;;
    2)
        if ! command -v npm >/dev/null 2>&1; then
            echo "npm is required before installing Claude Code."
            echo "On Raspberry Pi OS: sudo apt update && sudo apt install -y nodejs npm"
            exit 1
        fi
        echo "Installing Claude Code..."
        sudo npm install -g @anthropic-ai/claude-code
        REQUIRED_BACKEND="claude"
        ;;
    3)
        echo "Gemini uses GEMINI_API_KEY. Add it to your shell or service environment."
        REQUIRED_BACKEND="gemini"
        ;;
    4)
        echo "Skipping backend install."
        ;;
    *)
        echo "Unknown choice: $BACKEND"
        exit 1
        ;;
esac

echo ""
echo "Authenticate the backend you plan to use:"
echo "  Codex:   codex login"
echo "  Claude:  claude login"
echo "  Gemini:  export GEMINI_API_KEY=your_key_here"
echo ""
read -r -p "Press enter after authenticating, or Ctrl-C to stop here..."

if [ -n "$REQUIRED_BACKEND" ]; then
    echo ""
    echo "Checking backend readiness..."
    python3 "$ROOT/tools/backend-readiness.py" --require "$REQUIRED_BACKEND"
fi

chmod +x "$ROOT/brain-loop.sh"

echo ""
echo "Running a local health check before service install..."
if ! bash "$ROOT/tools/health-check.sh"; then
    echo ""
    echo "Health check failed. Fix that before installing Seed as a service."
    exit 1
fi

echo ""
read -r -p "Install and enable the systemd service now? [y/N]: " INSTALL_SERVICE
if [[ "${INSTALL_SERVICE,,}" == "y" || "${INSTALL_SERVICE,,}" == "yes" ]]; then
    sudo cp "$ROOT/seed-brain.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable seed-brain
    SERVICE_STATUS="Service enabled. Start it with: sudo systemctl start seed-brain"
else
    SERVICE_STATUS="Service not installed. Manual first run: ./brain-loop.sh"
fi

echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │     Ready!                      │"
echo "  └─────────────────────────────────┘"
echo ""
echo "$SERVICE_STATUS"
echo "Watch logs after service start: journalctl -u seed-brain -f"
