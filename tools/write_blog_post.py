"""
Write a blog post to SEED's public blog (served at /blog on port 8080).
Tool: write_blog_post
Args: title (str), body (str), tags (list[str], optional)
"""

import json
import time
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run(args: dict) -> dict:
    title = str(args.get("title", "")).strip()
    body = str(args.get("body", "")).strip()
    tags = args.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    if not title or not body:
        return {"success": False, "error": "title and body are required"}

    blog_dir = ROOT / "blog"
    blog_dir.mkdir(exist_ok=True)

    # slug from title
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    slug = f"{int(time.time())}-{slug}"

    post = {
        "title": title,
        "body": body,
        "tags": tags,
        "ts": time.time(),
    }

    out = blog_dir / f"{slug}.json"
    out.write_text(json.dumps(post, indent=2))

    return {
        "success": True,
        "slug": slug,
        "url": f"http://192.168.8.190:8080/blog/{slug}",
    }
