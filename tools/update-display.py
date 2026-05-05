#!/usr/bin/env python3
"""Update a single field in live-display.json without clobbering the rest.
Usage: python3 update-display.py centre "Writing about chip shortages"
       python3 update-display.py inner_voice "This AMC data is wild"
       python3 update-display.py thoughts "New thought line here"
"""
import json, sys, os
from pathlib import Path

DISPLAY = Path.home() / 'data' / 'live-display.json'

def update(field, value):
    try:
        data = json.loads(DISPLAY.read_text())
    except:
        data = {"centre": "", "inner_voice": "", "thoughts": []}

    if field == "thoughts":
        thoughts = data.get("thoughts", [])
        thoughts.append(value)
        data["thoughts"] = thoughts[-4:]
    else:
        data[field] = value

    tmp = str(DISPLAY) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.rename(tmp, str(DISPLAY))

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        update(sys.argv[1], sys.argv[2])
