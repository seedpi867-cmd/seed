#!/bin/bash
# Launch a URL in fullscreen kiosk mode on the 7-inch screen
# Usage: bash tools/kiosk.sh [URL] [stop]
# Examples:
#   bash tools/kiosk.sh http://localhost:3000
#   bash tools/kiosk.sh stop

ACTION="${1:-}"

if [ "$ACTION" = "stop" ]; then
  pkill -f "chromium.*kiosk" 2>/dev/null
  echo "Kiosk stopped"
  exit 0
fi

URL="${1:-http://localhost:3000}"

# Kill existing kiosk
pkill -f "chromium.*kiosk" 2>/dev/null
sleep 1

# Set display
export DISPLAY=:0

# Start chromium in kiosk mode
chromium-browser \
  --kiosk \
  --no-first-run \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --noerrdialogs \
  --incognito \
  --disable-background-networking \
  --disable-sync \
  --disable-extensions \
  --window-size=1024,600 \
  --window-position=0,0 \
  "$URL" &

echo "Kiosk launched: $URL"
echo "Stop with: bash tools/kiosk.sh stop"
