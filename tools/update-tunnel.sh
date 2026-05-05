#!/bin/bash
# Auto-detect and update the Cloudflare tunnel URL everywhere
# Usage: bash tools/update-tunnel.sh

NEW_URL=$(journalctl -u seed-tunnel --no-pager -n 30 2>/dev/null | grep -o 'https://[a-z\-]*\.trycloudflare\.com' | tail -1)

if [ -z "$NEW_URL" ]; then
    echo "Could not find tunnel URL in logs"
    exit 1
fi

echo "New tunnel: $NEW_URL"
DOMAIN=$(echo $NEW_URL | sed 's|https://||' | sed 's|\.trycloudflare\.com||')

# Update homepage
sed -i "s|https://[a-z\-]*\.trycloudflare\.com|https://${DOMAIN}.trycloudflare.com|g" ~/seed-web/index.html
echo "  Updated index.html"

# Update Vercel proxy
sed -i "s|https://[a-z\-]*\.trycloudflare\.com|https://${DOMAIN}.trycloudflare.com|g" ~/seed-web/api/live-proxy.js
echo "  Updated live-proxy.js"

# Restart webserver
sudo systemctl restart seed-web.service 2>/dev/null
echo "  Restarted webserver"

# Push to git
cd ~/seed-web && git add -A && git commit -m "Tunnel URL updated: $DOMAIN" && git push 2>/dev/null
echo "  Pushed to Vercel"

# Verify
sleep 2
CODE=$(curl -sf -o /dev/null -w '%{http_code}' "$NEW_URL/api/status" 2>/dev/null)
echo "  Tunnel status: $CODE"
