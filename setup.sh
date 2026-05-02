#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │     SEED — First Boot Setup     │"
echo "  └─────────────────────────────────┘"
echo ""

# Install CLIs
echo "Installing AI backends..."
sudo npm install -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli 2>&1 | tail -3

# Auth
echo ""
echo "Authenticate your AI backend:"
echo "  Claude:  claude login"
echo "  Codex:   codex login"
echo "  Gemini:  export GEMINI_API_KEY=your_key_here"
echo ""
read -p "Press enter after authenticating..."

# Install service
chmod +x "$ROOT/brain-loop.sh"
sudo cp "$ROOT/seed-brain.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable seed-brain

echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │     Ready!                      │"
echo "  │     Start: systemctl start seed-brain"
echo "  │     Watch: journalctl -u seed-brain -f"
echo "  └─────────────────────────────────┘"
