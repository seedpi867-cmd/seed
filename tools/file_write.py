"""
Tool: file_write
Write text content to a file inside sandbox/.
args: {"path": "relative path", "content": "text"}
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
SANDBOX = ROOT / "sandbox"


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    rel_path = args.get("path", "").strip().lstrip("/")
    content = args.get("content", "")

    if not rel_path:
        return False, "No path provided"

    # Confine writes to sandbox/
    target = (SANDBOX / rel_path).resolve()
    if not str(target).startswith(str(SANDBOX.resolve())):
        return False, f"Path escapes sandbox: {rel_path}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return True, f"Wrote {len(content)} bytes to {rel_path}"
