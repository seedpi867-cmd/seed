"""
Tool: file_read
Read a file from sandbox/ or knowledge/.
args: {"path": "relative path"}
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
SANDBOX = ROOT / "sandbox"
KNOWLEDGE = ROOT / "knowledge"


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    rel_path = args.get("path", "").strip().lstrip("/")
    if not rel_path:
        return False, "No path provided"

    # Check sandbox first, then knowledge
    for base in (SANDBOX, KNOWLEDGE):
        target = (base / rel_path).resolve()
        if str(target).startswith(str(base.resolve())) and target.exists():
            content = target.read_text(errors="replace")
            return True, content[:2000]

    return False, f"File not found: {rel_path}"
