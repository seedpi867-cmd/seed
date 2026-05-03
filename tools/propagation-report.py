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
import urllib.parse
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


def missing_topics(topics):
    return [topic for topic in RECOMMENDED_TOPICS if topic not in set(topics)]


def github_web_url(repo):
    return f"https://github.com/{repo}"


def clone_report_url(repo):
    return f"{github_web_url(repo)}/issues/new?template=clone-report.yml"


def clone_proof_url(repo):
    return f"{github_web_url(repo)}/issues/new?template=clone-proof.yml"


def fork_url(repo):
    return f"{github_web_url(repo)}/fork"


def interpretation_lines(topics):
    lines = [
        "visitors are attention",
        "stars, forks, clone proofs, and clone reports are propagation",
    ]
    missing = missing_topics(topics)
    if missing:
        lines.append(
            "missing topics are a discovery bug: " + ", ".join(missing)
        )
    else:
        lines.append("topics are present; the remaining gap is propagation")
    lines.append("a useful proof includes the exact machine, OS, and checks that passed")
    lines.append("a useful report includes the exact machine, OS, command, and failure")
    return lines


def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Seed propagation report"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def github_issue_count(repo, label, state):
    label = urllib.parse.quote(label)
    url = (
        f"https://api.github.com/repos/{repo}/issues"
        f"?state={state}&labels={label}&per_page=100"
    )
    issues = fetch_json(url)
    return len([issue for issue in issues if "pull_request" not in issue])


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
        "clone_reports_open": github_issue_count(repo, "clone-report", "open"),
        "clone_reports_closed": github_issue_count(repo, "clone-report", "closed"),
        "clone_proofs_open": github_issue_count(repo, "clone-proof", "open"),
        "clone_proofs_closed": github_issue_count(repo, "clone-proof", "closed"),
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
        print(f"- clone proofs open: {gh['clone_proofs_open']}")
        print(f"- clone proofs closed: {gh['clone_proofs_closed']}")
        print(f"- clone reports open: {gh['clone_reports_open']}")
        print(f"- clone reports closed: {gh['clone_reports_closed']}")
        print(f"- subscribers: {gh['subscribers']}")
        print(f"- watchers: {gh['watchers']}")
        print(f"- topics: {', '.join(gh['topics']) if gh['topics'] else '(none)'}")
        print(f"- pushed at: {gh['pushed_at']}")
        if missing_topics(gh["topics"]):
            print()
            print("Discovery gap")
            print("- this repo is missing GitHub topics used by topic search")
            print("- missing topics: " + ", ".join(missing_topics(gh["topics"])))
            print(
                "- authenticated fix: gh repo edit "
                f"{repo} --add-topic {','.join(missing_topics(gh['topics']))}"
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
        print("- CTA clicks: not tracked by the public site API")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Website: unavailable ({exc})")

    print()
    print("Interpretation")
    for line in interpretation_lines(gh.get("topics", []) if "gh" in locals() else []):
        print(f"- {line}")

    print()
    print("Next actions")
    print(f"- clone: git clone {github_web_url(repo)}.git seed")
    print(f"- share a clean run: {clone_proof_url(repo)}")
    print(f"- report a real run: {clone_report_url(repo)}")
    print(f"- fork it: {fork_url(repo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
