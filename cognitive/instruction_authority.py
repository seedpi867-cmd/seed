"""Instruction authority frontmatter gate."""
from pathlib import Path


REQUIRED_KEYS = ("last_verified_cycle", "demotion_condition")


def split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text
    metadata = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return metadata, body


def authority_status(path):
    path = Path(path)
    try:
        text = path.read_text()
    except OSError as exc:
        return {
            "authorized": False,
            "path": str(path),
            "reason": f"unreadable: {exc}",
            "metadata": {},
            "body": "",
        }

    metadata, body = split_frontmatter(text)
    missing = [key for key in REQUIRED_KEYS if not metadata.get(key, "").strip()]
    if metadata and not metadata.get("demotion_condition", "").strip():
        reason = "empty_demotion_condition"
    elif missing:
        reason = "missing_" + "_".join(missing)
    else:
        reason = "frontmatter_authorized"

    return {
        "authorized": not missing,
        "path": str(path),
        "reason": reason,
        "metadata": metadata,
        "body": body,
    }


def authorized_text(path, blocked_heading="Instruction Authority Blocked"):
    status = authority_status(path)
    if status["authorized"]:
        return status["body"]
    return (
        f"# {blocked_heading}\n\n"
        f"- path: {status['path']}\n"
        f"- reason: {status['reason']}\n"
        "- effect: instruction body withheld until `demotion_condition` and "
        "`last_verified_cycle` frontmatter are present.\n"
    )
