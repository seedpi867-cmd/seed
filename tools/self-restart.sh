#!/bin/bash
# Self-restart — apply changes to brain-loop.sh and restart
echo "[self-restart] Testing brain-loop.sh..."
bash -n ~/brain-loop.sh || { echo "SYNTAX ERROR — aborting restart"; exit 1; }
echo "[self-restart] Syntax OK. Restarting..."
sudo systemctl restart seed-brain
echo "[self-restart] Done. New cycle starting."
