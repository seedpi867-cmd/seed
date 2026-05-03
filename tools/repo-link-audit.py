#!/usr/bin/env python3
"""Audit whether a public Seed site points readers back to the repo."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


DEFAULT_REPO = "seedpi867-cmd/seed"
DEFAULT_SITE = "https://seed-brain.vercel.app"


def site_url(site, path):
    site = site.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return site + path


def repo_markers(repo):
    return (
        f"https://github.com/{repo}",
        f"github.com/{repo}",
        f"git clone https://github.com/{repo}.git",
    )


def has_repo_link(text, repo):
    return any(marker in text for marker in repo_markers(repo))


def fetch_text(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Seed repo link audit"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url, timeout=10):
    return json.loads(fetch_text(url, timeout=timeout))


def post_paths(index):
    paths = []
    for post in index:
        slug = post.get("slug")
        if isinstance(slug, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            paths.append(f"/posts/{slug}.md")
    return paths


def check_page(site, repo, path):
    url = site_url(site, path)
    text = fetch_text(url)
    return {
        "path": path,
        "url": url,
        "linked": has_repo_link(text, repo),
        "bytes": len(text.encode("utf-8")),
    }


def audit(site, repo, limit=None):
    pages = [
        check_page(site, repo, "/"),
        check_page(site, repo, "/blog"),
    ]

    index = fetch_json(site_url(site, "/posts/index.json"))
    paths = post_paths(index)
    if limit is not None:
        paths = paths[:limit]
    posts = [check_page(site, repo, path) for path in paths]
    return {"pages": pages, "posts": posts, "post_count_available": len(index)}


def print_section(title, rows):
    print(title)
    for row in rows:
        status = "linked" if row["linked"] else "missing"
        print(f"- {row['path']}: {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=os.environ.get("SEED_PUBLIC_SITE", DEFAULT_SITE))
    parser.add_argument("--repo", default=os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO))
    parser.add_argument("--limit", type=int, help="Check only the newest N posts")
    parser.add_argument(
        "--strict-posts",
        action="store_true",
        help="Exit non-zero if any checked post lacks a repo link",
    )
    args = parser.parse_args()

    print("Seed repo link audit")
    print(f"site: {args.site}")
    print(f"repo: {args.repo}")
    print()

    try:
        result = audit(args.site, args.repo, args.limit)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"audit unavailable: {exc}")
        return 2

    print_section("Shell pages", result["pages"])
    print()

    posts = result["posts"]
    linked_posts = [post for post in posts if post["linked"]]
    missing_posts = [post for post in posts if not post["linked"]]
    print("Posts")
    print(f"- available: {result['post_count_available']}")
    print(f"- checked: {len(posts)}")
    print(f"- linked: {len(linked_posts)}")
    print(f"- missing: {len(missing_posts)}")
    for post in missing_posts[:10]:
        print(f"  missing repo link: {post['path']}")
    if len(missing_posts) > 10:
        print(f"  ...and {len(missing_posts) - 10} more")

    missing_shell = [page for page in result["pages"] if not page["linked"]]
    if missing_shell:
        print()
        print("Conversion gap")
        print("- homepage and blog shell pages should always link to the repo")
        return 1
    if missing_posts and args.strict_posts:
        print()
        print("Conversion gap")
        print("- at least one checked post lacks a repo link")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
