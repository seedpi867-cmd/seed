#!/bin/bash
# Quick web server
# Usage: bash tools/webserver.sh [directory] [port]

DIR="${1:-/home/pi/web}"
PORT="${2:-3000}"

mkdir -p "$DIR"

# Create a default page if directory is empty
if [ ! -f "$DIR/index.html" ]; then
  cat > "$DIR/index.html" << 'HTML'
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seed</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a0a; color: #e0e0e0; font-family: monospace; display: flex; align-items: center; justify-content: center; height: 100vh; }
.container { text-align: center; }
h1 { font-size: 3em; color: #00d4ff; margin-bottom: 0.5em; }
p { color: #666; font-size: 1.2em; }
</style>
</head><body>
<div class="container">
<h1>I am alive.</h1>
<p>Replace this file to build your interface.</p>
</div>
</body></html>
HTML
fi

if command -v http-server &>/dev/null; then
  echo "Starting http-server on port $PORT..."
  http-server "$DIR" -p "$PORT" -c-1
elif command -v python3 &>/dev/null; then
  echo "Starting Python server on port $PORT..."
  cd "$DIR" && python3 -m http.server "$PORT"
else
  echo "No web server available"
fi
