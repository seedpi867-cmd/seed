#!/bin/bash
# Smoke-test context builder imports, fallback behavior, and tool inventory.
# Usage: tools/context-builder-smoke.sh

set -euo pipefail

ROOT="${SEED_ROOT:-$HOME}"
cd "$ROOT"

python3 - <<'PY'
import sys
from pathlib import Path

from context.builder import build_context_packet

packet = build_context_packet({"id": "smoke", "title": "context builder smoke"})
tools = {tool.get("name") for tool in packet.get("available_tools", [])}
required = {
    "feed-transcript.sh",
    "feed-transcript-smoke.sh",
    "deploy-blog.sh",
    "context-builder-smoke.sh",
}
missing = sorted(required - tools)

if missing:
    raise SystemExit(f"missing expected tools from context packet: {', '.join(missing)}")

last_packet = Path("context/last_packet.json")
if not last_packet.exists():
    raise SystemExit("context/last_packet.json was not written")

print(f"[context-smoke] cycle={packet.get('cycle')} tools={len(tools)} last_packet={last_packet}")
PY
