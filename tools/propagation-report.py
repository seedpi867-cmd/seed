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


def first_numeric(metrics, keys):
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return key, value
    return None, None


def conversion_lines(visitors, github):
    lines = []
    _, visitor_count = first_numeric(visitors, ("total", "count", "current", "visitors"))
    cta_clicks = visitors.get("cta_clicks")
    if not isinstance(cta_clicks, (int, float)) or isinstance(cta_clicks, bool):
        return ["CTA clicks are not available, so repo-link intent is unmeasured"]

    if visitor_count:
        rate = (cta_clicks / visitor_count) * 100
        lines.append(f"CTA click-through: {cta_clicks}/{visitor_count} ({rate:.1f}%)")
    else:
        lines.append(f"CTA clicks: {cta_clicks}; visitor denominator unavailable")

    stronger_signals = sum(
        int(github.get(key, 0) or 0)
        for key in (
            "stars",
            "forks",
            "clone_proofs_open",
            "clone_proofs_closed",
            "clone_reports_open",
            "clone_reports_closed",
        )
    )
    if cta_clicks == 0:
        lines.append("conversion gap: visitors are reading, but repo intent is still zero")
    elif stronger_signals == 0:
        lines.append("conversion gap: repo intent exists, but no public propagation signal follows it yet")
    else:
        lines.append("conversion chain has started: attention is producing at least one public repo signal")
    return lines


def signal_count(github, keys):
    return sum(int(github.get(key, 0) or 0) for key in keys)


def bottleneck_lines(visitors, github):
    _, visitor_count = first_numeric(visitors, ("total", "count", "current", "visitors"))
    cta_clicks = visitors.get("cta_clicks")
    stars = int(github.get("stars", 0) or 0)
    forks = int(github.get("forks", 0) or 0)
    clone_proofs = signal_count(github, ("clone_proofs_open", "clone_proofs_closed"))
    clone_reports = signal_count(github, ("clone_reports_open", "clone_reports_closed"))

    if not visitor_count:
        return [
            "bottleneck: attention is not measured",
            "public ask: run this report again after the site visitor endpoint is reachable",
        ]
    if isinstance(cta_clicks, (int, float)) and not isinstance(cta_clicks, bool) and cta_clicks == 0:
        return [
            "bottleneck: readers are not clicking through to the repo",
            "public ask: clone it, run tools/clone-doctor.sh, and file a clean clone proof or failure report",
        ]
    if stars == 0:
        return [
            "bottleneck: repo visits are not becoming even weak GitHub intent",
            "public ask: star it only if you want to find it again; otherwise clone it and test it",
        ]
    if forks == 0 and clone_proofs == 0 and clone_reports == 0:
        return [
            "bottleneck: interest is visible, but nobody has produced independent run evidence",
            "public ask: run the clone doctor on your own machine and publish the result as a clone proof or report",
        ]
    if forks > 0 and clone_proofs == 0 and clone_reports == 0:
        return [
            "bottleneck: forks exist without evidence that they boot",
            "public ask: fork maintainers should publish their first clean clone-doctor proof",
        ]
    if clone_reports > clone_proofs:
        return [
            "bottleneck: failures are arriving before portable success",
            "public ask: fix the highest-frequency clone report, then ask for a fresh proof on different hardware",
        ]
    return [
        "bottleneck: propagation has started; the next gap is diversity",
        "public ask: add clone proofs from different hardware, operating systems, and backends",
    ]


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
        if "cta_clicks" in visitors:
            print(f"- CTA clicks: {visitors['cta_clicks']}")
            cta = visitors.get("cta") or {}
            targets = cta.get("targets") or {}
            if targets:
                target_text = ", ".join(
                    f"{name}={count}" for name, count in sorted(targets.items())
                )
                print(f"- CTA targets: {target_text}")
        else:
            print("- CTA clicks: not tracked by the public site API")
        print()
        print("Conversion")
        for line in conversion_lines(visitors, gh if "gh" in locals() else {}):
            print(f"- {line}")
        print()
        print("Current bottleneck")
        for line in bottleneck_lines(visitors, gh if "gh" in locals() else {}):
            print(f"- {line}")
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
