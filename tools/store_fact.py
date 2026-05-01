"""
Tool: store_fact
Store a key/value fact into memory/facts/.
args: {"key": "fact_key", "value": "fact value", "category": "general"}
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    from runtime.common import store_fact
    key = args.get("key", "").strip()
    value = args.get("value", "")
    category = args.get("category", "general")

    if not key:
        return False, "No key provided"

    store_fact(key, value, category)
    return True, f"Stored fact: {key}"
