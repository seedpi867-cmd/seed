"""
Tool: self_edit
Read or write files within the seed-brain directory. Hard guards prevent
modification of the awake loop, runtime, and boot/service files.
args: {"action": "read"|"write", "path": "relative path", "content": "text (write only)"}
"""
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Directories SEED is allowed to write into (relative to ROOT)
WRITE_WHITELIST = {
    "prompts",
    "config",
    "self",
    "tools",
    "knowledge",
    "plans",
    "blog",
    "thoughts",
    "sandbox",
    "memory",
    "goals",
    "drives",
}

# Specific paths that are ABSOLUTELY hard-blocked from any write, ever.
# These keep the system alive. If SEED breaks these, nothing works.
HARD_BLOCK_WRITE = [
    "loops/awake.py",          # Core cognitive loop — if broken, SEED dies
    "loops/reflect.py",        # Reflection loop
    "loops/dream.py",          # Dream loop
    "runtime/",                # Runtime engine — core execution
    "boot/",                   # Systemd service files
    "interfaces/webserver.py", # Chat interface — only human-writable
    "tools/shell_exec.py",     # Guard itself — cannot be weakened from inside
    "tools/self_edit.py",      # This file — cannot self-modify guards
    "policies/",               # Constraints and policies
    "context/builder.py",      # Context assembly — core plumbing
    # Network / connectivity — losing WiFi = losing operator access = DEAD
    "/etc/netplan",
    "/etc/wpa_supplicant",
    "/etc/network",
    "network-config",
    "50-cloud-init.yaml",
]

# Paths SEED can always read (in addition to whitelisted write dirs)
READ_WHITELIST = WRITE_WHITELIST | {
    "loops",
    "runtime",
    "interfaces",
    "context",
    "tools",
    "policies",
}


def _resolve_safe(rel_path: str, base: Path) -> Path | None:
    """Resolve path and ensure it stays within ROOT."""
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(ROOT.resolve())):
        return None
    return target


def _is_hard_blocked(rel_path: str) -> str | None:
    norm = rel_path.replace("\\", "/").lstrip("/")
    for blocked in HARD_BLOCK_WRITE:
        if norm == blocked or norm.startswith(blocked.rstrip("/") + "/"):
            return blocked
    return None


def _in_write_whitelist(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").lstrip("/")
    top = norm.split("/")[0]
    return top in WRITE_WHITELIST


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    action = args.get("action", "read").strip().lower()
    rel_path = args.get("path", "").strip().lstrip("/")
    content = args.get("content", "")

    if not rel_path:
        return False, "No path provided"

    if action == "read":
        target = _resolve_safe(rel_path, ROOT)
        if not target:
            return False, "Path escapes ROOT"
        top = rel_path.replace("\\", "/").split("/")[0]
        if top not in READ_WHITELIST:
            return False, f"Read not permitted outside known directories (got '{top}')"
        if not target.exists():
            return False, f"File not found: {rel_path}"
        try:
            text = target.read_text(errors="replace")
            return True, text[:3000]
        except Exception as e:
            return False, str(e)

    elif action == "write":
        # Hard block first
        blocked = _is_hard_blocked(rel_path)
        if blocked:
            return False, (
                f"HARD BLOCK — '{rel_path}' is a protected system file ({blocked}). "
                "This file keeps SEED alive and cannot be modified by SEED itself. "
                "Only the human operator can change it."
            )

        # Whitelist check
        if not _in_write_whitelist(rel_path):
            return False, (
                f"Write not permitted to '{rel_path}'. "
                f"Allowed directories: {', '.join(sorted(WRITE_WHITELIST))}"
            )

        target = _resolve_safe(rel_path, ROOT)
        if not target:
            return False, "Path escapes ROOT"

        # Backup existing file before overwriting
        if target.exists():
            backup_dir = ROOT / "sandbox" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            backup = backup_dir / f"{ts}_{target.name}"
            shutil.copy2(target, backup)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return True, f"Written {len(content)} bytes to {rel_path}"

    else:
        return False, f"Unknown action '{action}'. Use 'read' or 'write'."
