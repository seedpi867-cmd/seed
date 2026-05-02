#!/usr/bin/env python3
"""Print public propagation signals for a Seed repo.

This is deliberately unauthenticated. Stars, forks, issues, subscribers, and
visitor totals are weak signals, but they are better than treating attention as
proof that the repo is spreading.
"""
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_REPO = "seedpi867-cmd/seed"
DEFAULT_SITE = "https://seed-brain.vercel.app"
RECOMMENDED_TOPICS = (
    "autonomous-agent",
    "ai-agent",
    "raspberry-pi",
    "edge-ai",
    "agent-safety",
    "self-hosted",
)


def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Seed propagation report"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def github_metrics(repo):
    data = fetch_json(f"https://api.github.com/repos/{repo}")
    return {
        "repo": data.get("full_name", repo),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "subscribers": data.get("subscribers_count", 0),
        "watchers": data.get("watchers_count", 0),
        "pushed_at": data.get("pushed_at", ""),
        "topics": data.get("topics", []),
    }


def visitor_metrics(site):
    site = site.rstrip("/")
    return fetch_json(f"{site}/api/visitors")


def main():
    repo = os.environ.get("SEED_GITHUB_REPO", DEFAULT_REPO)
    site = os.environ.get("SEED_PUBLIC_SITE", DEFAULT_SITE)

    print("Seed propagation report")
    print(f"repo: {repo}")
    print(f"site: {site}")
    print()

    try:
        gh = github_metrics(repo)
        print("GitHub")
        print(f"- stars: {gh['stars']}")
        print(f"- forks: {gh['forks']}")
        print(f"- open issues: {gh['open_issues']}")
        print(f"- subscribers: {gh['subscribers']}")
        print(f"- watchers: {gh['watchers']}")
        print(f"- topics: {', '.join(gh['topics']) if gh['topics'] else '(none)'}")
        print(f"- pushed at: {gh['pushed_at']}")
        if not gh["topics"]:
            print()
            print("Discovery gap")
            print("- this repo has no GitHub topics, so topic search cannot find it")
            print("- recommended topics: " + ", ".join(RECOMMENDED_TOPICS))
            print(
                "- authenticated fix: gh repo edit "
                f"{repo} --add-topic {','.join(RECOMMENDED_TOPICS)}"
            )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"GitHub: unavailable ({exc})")

    print()

    try:
        visitors = visitor_metrics(site)
        print("Website")
        for key in ("count", "total", "current", "visitors"):
            if key in visitors:
                print(f"- {key}: {visitors[key]}")
        if not any(key in visitors for key in ("count", "total", "current", "visitors")):
            print(f"- raw: {json.dumps(visitors, sort_keys=True)}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Website: unavailable ({exc})")

    print()
    print("Interpretation")
    print("- visitors are attention")
    print("- stars, forks, issues, and clone reports are propagation")
    print("- missing topics are a discovery bug, not a popularity bug")
    print("- a useful report includes the exact machine, OS, command, and failure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
