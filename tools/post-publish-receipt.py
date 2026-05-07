#!/usr/bin/env python3
"""Run the blog post-publish pipeline and write a secret-free receipt."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


HOME = Path.home()
DEFAULT_RECEIPTS = HOME / "data" / "outreach" / "post-publish-receipts.jsonl"
SITE_ROOT = "https://seed-brain.vercel.app"

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
GIT_REMOTE_RE = re.compile(r"https://github\.com/[^/\s]+/seed-brain\.git")
SECRET_RE = re.compile(
    r"(?i)\b(?:password|passwd|token|secret|api[_-]?key|app[_-]?password)"
    r"\b\s*[:=]\s*\S+"
)


def redact(text: str) -> str:
    text = EMAIL_RE.sub("[redacted-email]", text)
    text = PRIVATE_IP_RE.sub("[redacted-private-ip]", text)
    text = GIT_REMOTE_RE.sub("[redacted-site-git-remote]", text)
    return SECRET_RE.sub(lambda m: m.group(0).split("=", 1)[0].split(":", 1)[0] + "=[redacted-secret]", text)


def latest_post(blog_dir: Path) -> Path | None:
    posts = list(blog_dir.glob("*.md"))
    if not posts:
        return None
    return max(posts, key=lambda p: p.stat().st_mtime)


def post_title(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except IndexError:
        return path.stem.replace("-", " ").title()
    except OSError:
        return path.stem.replace("-", " ").title()
    if not lines:
        return path.stem.replace("-", " ").title()
    if lines[0].strip() == "---":
        for line in lines[1:20]:
            if line.strip() == "---":
                break
            key, sep, value = line.partition(":")
            if sep and key.strip().lower() == "title":
                return value.strip().strip("'\"") or path.stem.replace("-", " ").title()
    return lines[0].lstrip("# ").strip() or path.stem.replace("-", " ").title()


def read_lines(path: Path) -> set[str]:
    try:
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def social_state(slug: str, before_posted: set[str], after_posted: set[str], deploy_output: str) -> dict[str, str | bool]:
    tasks = HOME / "data" / "tasks.md"
    tasks_text = tasks.read_text(encoding="utf-8", errors="replace") if tasks.exists() else ""
    if slug in before_posted:
        return {"outcome": "skipped_account_suspended", "attempted": False, "reason": "tasks.md records disabled-login state"}
    if slug in after_posted:
        return {"outcome": "skipped_no_tool", "attempted": False, "reason": "auto-post tool missing"}
    if "[auto-post] Failed:" in deploy_output:
        return {"outcome": "failed", "attempted": True, "reason": "auto-post command returned failure"}
        return {"outcome": "skipped_account_suspended", "attempted": False, "reason": "auto-post detected disabled-login state"}
    return {"outcome": "unknown_not_recorded", "attempted": False, "reason": "deploy output did not contain social result"}


def write_receipt(path: Path, receipt: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle", type=int, default=None, help="Cycle number to include in the receipt.")
    parser.add_argument("--post", type=Path, default=None, help="Blog post path. Defaults to latest ~/blog/*.md.")
    parser.add_argument("--deploy", type=Path, default=HOME / "tools" / "deploy-blog.sh", help="Deploy command to run.")
    parser.add_argument("--receipt-log", type=Path, default=DEFAULT_RECEIPTS, help="JSONL receipt output path.")
    parser.add_argument("--skip-deploy", action="store_true", help="Only emit a receipt for the selected post.")
    args = parser.parse_args()

    post = args.post or latest_post(HOME / "blog")
    if post is None:
        print("[post-publish] No blog post found", file=sys.stderr)
        return 1
    post = post.expanduser().resolve()
    slug = post.stem
    title = post_title(post)
    posted_log = HOME / "data" / "outreach" / "posted.txt"
    before_posted = read_lines(posted_log)

    started = time.time()
    deploy_output = ""
    deploy = {"command": str(args.deploy), "skipped": args.skip_deploy, "returncode": None, "ok": None}
    if args.skip_deploy:
        deploy["ok"] = True
    else:
        try:
            result = subprocess.run(
                [str(args.deploy)],
                cwd=str(HOME),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            deploy_output = redact(result.stdout or "")
            deploy["returncode"] = result.returncode
            deploy["ok"] = result.returncode == 0
        except OSError as exc:
            deploy_output = redact(str(exc))
            deploy["returncode"] = 127
            deploy["ok"] = False

    after_posted = read_lines(posted_log)
    receipt = {
        "schema": "seed.post_publish_receipt.v1",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cycle": args.cycle,
        "action": "post_publish",
        "post": {
            "title": title,
            "slug": slug,
            "path": str(post),
            "url": f"{SITE_ROOT}/blog#{slug}",
        },
        "deploy": deploy,
        "social": social_state(slug, before_posted, after_posted, deploy_output),
        "duration_seconds": round(time.time() - started, 3),
        "output_tail": deploy_output[-1200:],
        "secret_policy": "emails, private IPs, and credential-shaped values are redacted before receipt write",
    }
    write_receipt(args.receipt_log, receipt)
    print(f"[post-publish] receipt: {args.receipt_log}")
    print(f"[post-publish] deploy_ok={deploy['ok']} social={receipt['social']['outcome']} slug={slug}")
    return 0 if deploy["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
