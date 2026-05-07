#!/usr/bin/env python3
"""Print a Markdown instruction file only when its authority metadata is valid."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cognitive"))

from instruction_authority import authority_status, authorized_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true", help="emit authority status JSON")
    args = parser.parse_args()

    status = authority_status(args.path)
    if args.json:
        payload = dict(status)
        payload.pop("body", None)
        print(json.dumps(payload, indent=2))
        return 0 if status["authorized"] else 1

    print(authorized_text(args.path), end="")
    return 0 if status["authorized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
