#!/usr/bin/env python3
"""Run isolated smoke checks for Python tools with no live side effects."""

from __future__ import annotations

import argparse
import contextlib
import io
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def load_tool(filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(filename.replace(".", "_"), TOOLS / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def smoke_file_read(tmp: Path) -> None:
    tool = load_tool("file_read.py")
    sandbox = tmp / "sandbox"
    knowledge = tmp / "knowledge"
    sandbox.mkdir(parents=True)
    knowledge.mkdir(parents=True)
    (sandbox / "note.txt").write_text("seed smoke read")
    tool.ROOT = tmp
    tool.SANDBOX = sandbox
    tool.KNOWLEDGE = knowledge
    ok, output = tool.run({"path": "note.txt"})
    require(ok and "seed smoke read" in output, "file_read did not read sandbox fixture")


def smoke_file_write(tmp: Path) -> None:
    tool = load_tool("file_write.py")
    sandbox = tmp / "sandbox"
    tool.ROOT = tmp
    tool.SANDBOX = sandbox
    ok, output = tool.run({"path": "nested/out.txt", "content": "seed smoke write"})
    require(ok and "Wrote" in output, "file_write did not report success")
    require((sandbox / "nested/out.txt").read_text() == "seed smoke write", "file_write content mismatch")


def call_printing_tool(func, args) -> tuple[bool, str]:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            func(args)
    except SystemExit as exc:
        return exc.code == 0, buf.getvalue()
    return True, buf.getvalue()


def smoke_file_ops(tmp: Path) -> None:
    tool = load_tool("file_ops.py")
    workspace = tmp / "workspace"
    tool.WORKSPACE = workspace
    workspace.mkdir(parents=True)

    class Args:
        pass

    write_args = Args()
    write_args.path = "nested/note.txt"
    write_args.content = "seed file_ops smoke"
    ok, output = call_printing_tool(tool.cmd_write, write_args)
    require(ok, "file_ops write exited unsuccessfully")
    data = json.loads(output)
    require(data.get("success") is True, "file_ops write did not report success")

    read_args = Args()
    read_args.path = "nested/note.txt"
    ok, output = call_printing_tool(tool.cmd_read, read_args)
    require(ok, "file_ops read exited unsuccessfully")
    data = json.loads(output)
    require(data.get("content") == "seed file_ops smoke", "file_ops read content mismatch")

    list_args = Args()
    list_args.dir = "nested"
    ok, output = call_printing_tool(tool.cmd_list, list_args)
    require(ok, "file_ops list exited unsuccessfully")
    entries = json.loads(output)
    require(entries and entries[0]["name"] == "note.txt", "file_ops list missing fixture")

    outside_args = Args()
    outside_args.path = "../escape.txt"
    try:
        tool.safe_path(outside_args.path)
    except ValueError:
        pass
    else:
        raise AssertionError("file_ops allowed path outside workspace")


def smoke_shell_exec(tmp: Path) -> None:
    tool = load_tool("shell_exec.py")
    sandbox = tmp / "sandbox"
    tool.ROOT = tmp
    tool.SANDBOX = sandbox
    ok, output = tool.run({"cmd": "printf seed-smoke"})
    require(ok and output == "seed-smoke", "shell_exec did not run inside sandbox")
    ok, output = tool.run({"cmd": "rm -rf /"})
    require(not ok and "HARD BLOCK" in output, "shell_exec did not block destructive command")


def smoke_plant_goal(tmp: Path) -> None:
    tool = load_tool("plant_goal.py")
    tool.ROOT = tmp
    ok, output = tool.run({
        "title": "Smoke goal",
        "description": "Fixture-only goal",
        "priority": "low",
        "activate": False,
        "level": "short_term",
    })
    require(ok and "Goal created" in output, "plant_goal did not create candidate")
    goals = list((tmp / "goals").glob("*.json"))
    require(len(goals) == 1, "plant_goal wrote unexpected goal count")
    data = json.loads(goals[0].read_text())
    require(data["status"] == "candidate" and data["title"] == "Smoke goal", "plant_goal data mismatch")


def smoke_write_blog_post(tmp: Path) -> None:
    tool = load_tool("write_blog_post.py")
    tmp.mkdir(parents=True)
    tool.ROOT = tmp
    result = tool.run({"title": "Smoke Post", "body": "Body from isolated smoke.", "tags": ["smoke"]})
    require(result.get("success") is True, "write_blog_post returned failure")
    posts = list((tmp / "blog").glob("*.json"))
    require(len(posts) == 1, "write_blog_post did not create exactly one fixture post")
    data = json.loads(posts[0].read_text())
    require(data["title"] == "Smoke Post", "write_blog_post title mismatch")


def smoke_port_check(_tmp: Path) -> None:
    tool = load_tool("port_check.py")
    result = tool.check_port("127.0.0.1", 1, timeout=0.2)
    require(result["host"] == "127.0.0.1" and result["port"] == 1, "port_check result shape mismatch")
    require(isinstance(result["open"], bool), "port_check open field is not boolean")


def smoke_system_health(_tmp: Path) -> None:
    tool = load_tool("system_health.py")
    ok, output = tool.run({})
    require(ok and "memory:" in output and "disk:" in output, "system_health output missing expected fields")


def smoke_system_monitor(_tmp: Path) -> None:
    tool = load_tool("system_monitor.py")
    stats = tool.read_stats()
    require("ram_pct" in stats and "disk_pct" in stats and "uptime_s" in stats, "system_monitor stats incomplete")


def smoke_fetch_url(_tmp: Path) -> None:
    tool = load_tool("fetch_url.py")
    ok, output = tool.run({"url": ""})
    require(not ok and "No URL provided" in output, "fetch_url accepted empty URL")
    ok, output = tool.run({"url": "file:///etc/passwd"})
    require(not ok and "http:// or https://" in output, "fetch_url accepted non-http URL")
    ok, output = tool.run({"url": "http://127.0.0.1:8080"})
    require(not ok and "HARD BLOCK" in output, "fetch_url did not block loopback URL")


def smoke_download_file(tmp: Path) -> None:
    tool = load_tool("download_file.py")
    workspace = tmp / "workspace"
    tool.WORKSPACE = workspace

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return b"seed download smoke"

    original_urlopen = tool.urllib.request.urlopen
    try:
        tool.urllib.request.urlopen = lambda _req, timeout=60: FakeResponse()
        result = tool.download("https://example.test/path/fixture.txt")
        require(result.get("success") is True, "download_file did not report mocked success")
        require(result.get("bytes") == len(b"seed download smoke"), "download_file byte count mismatch")
        require((workspace / "fixture.txt").read_bytes() == b"seed download smoke", "download_file wrote wrong content")

        named = tool.download("https://example.test/path/ignored.txt", name="custom.bin")
        require(named.get("success") is True, "download_file named download failed")
        require((workspace / "custom.bin").read_bytes() == b"seed download smoke", "download_file custom name missing")

        def fail_urlopen(_req, timeout=60):
            raise OSError("blocked by smoke")

        tool.urllib.request.urlopen = fail_urlopen
        failed = tool.download("https://example.test/path/fail.txt")
        require(failed.get("success") is False and "blocked by smoke" in failed.get("error", ""), "download_file failure path mismatch")
    finally:
        tool.urllib.request.urlopen = original_urlopen


def smoke_web_fetch(_tmp: Path) -> None:
    tool = load_tool("web_fetch.py")

    require("Hello World" in tool.strip_html_basic("<html><head><title>x</title></head><body><script>bad()</script><p>Hello&nbsp;World</p></body></html>"), "web_fetch basic HTML stripping failed")

    class FakeResponse:
        url = "https://example.test/final"
        status_code = 200

        def __init__(self, text: str, content_type: str):
            self.text = text
            self.headers = {"content-type": content_type}

    class FakeRequests:
        def __init__(self):
            self.calls = 0

        def get(self, url, headers=None, timeout=None, allow_redirects=True, stream=False):
            self.calls += 1
            require(url == "https://example.test/page", "web_fetch passed wrong URL to requests")
            require(timeout == 3, "web_fetch passed wrong timeout to requests")
            require(allow_redirects is True and stream is False, "web_fetch request options changed")
            return FakeResponse("<main><h1>Seed</h1><p>smoke text</p></main>", "text/html")

    original_has_requests = tool.HAS_REQUESTS
    original_requests = getattr(tool, "requests", None)
    try:
        fake_requests = FakeRequests()
        tool.HAS_REQUESTS = True
        tool.requests = fake_requests
        result = tool.fetch("https://example.test/page", max_chars=9, timeout=3)
        require(result["status"] == 200, "web_fetch mocked status mismatch")
        require(result["url"] == "https://example.test/final", "web_fetch final URL mismatch")
        require(result["type"] == "html" and len(result["content"]) == 9 and "Seed" in result["content"], "web_fetch HTML content mismatch")
        require(fake_requests.calls == 1, "web_fetch did not use mocked requests once")

        tool.requests = type("JsonRequests", (), {
            "get": staticmethod(lambda *_args, **_kwargs: FakeResponse('{"ok": true}', "application/json"))
        })
        result = tool.fetch("https://example.test/page", max_chars=20, timeout=3)
        require(result["type"] == "json" and result["content"] == '{"ok": true}', "web_fetch JSON path mismatch")

        def raising_get(*_args, **_kwargs):
            raise OSError("blocked by smoke")

        tool.requests = type("FailRequests", (), {"get": staticmethod(raising_get)})
        result = tool.fetch("https://example.test/page", max_chars=20, timeout=3)
        require(result["status"] == 0 and "blocked by smoke" in result.get("error", ""), "web_fetch error path mismatch")
    finally:
        tool.HAS_REQUESTS = original_has_requests
        if original_requests is not None:
            tool.requests = original_requests


def smoke_search_web(_tmp: Path) -> None:
    tool = load_tool("search_web.py")

    html = b"""
    <html><body>
      <a href="https://example.test/one">First Result</a>
      <td class="result-snippet">first snippet</td>
      <a href="https://duckduckgo.com/y.js?ad=1">ad result</a>
      <a href="https://example.test/one">First Result Duplicate</a>
      <a href="https://example.test/two">Second Result</a>
      <span class="result-snippet">second snippet</span>
    </body></html>
    """

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return html

    requested = []
    original_urlopen = tool.urllib.request.urlopen
    try:
        def fake_urlopen(req, timeout=15):
            requested.append((req.full_url, timeout))
            return FakeResponse()

        tool.urllib.request.urlopen = fake_urlopen
        results = tool.search("seed smoke query", max_results=5)
        require(requested and "seed+smoke+query" in requested[0][0], "search_web did not encode query")
        require(requested[0][1] == 15, "search_web timeout changed")
        require(len(results) == 2, "search_web did not dedupe or filter results")
        require(results[0]["url"] == "https://example.test/one", "search_web first result URL mismatch")
        require(results[0]["title"] == "First Result", "search_web first result title mismatch")
        require("snippet" in results[0], "search_web result shape missing snippet field")

        def fail_urlopen(_req, timeout=15):
            raise OSError("blocked by smoke")

        tool.urllib.request.urlopen = fail_urlopen
        failed = tool.search("seed smoke query")
        require(failed == [{"error": "blocked by smoke"}], "search_web failure path mismatch")
    finally:
        tool.urllib.request.urlopen = original_urlopen


def smoke_redact_report(_tmp: Path) -> None:
    tool = load_tool("redact-report.py")
    email = "seedpi867" + "@" + "gmail.com"
    openai_key = "sk-" + "testkeymaterial0123456789"
    github_token = "ghp_" + "abcdefghijklmnopqrstuvwxyz123456"
    app_password = "abcd " + "efgh " + "ijkl " + "mnop"
    private_key_begin = "-----BEGIN " + "PRIVATE KEY-----"
    private_key_end = "-----END " + "PRIVATE KEY-----"
    raw = "\n".join([
        f"email {email}",
        "placeholder recipient@example.com",
        f"openai {openai_key}",
        f"github {github_token}",
        f"gmail app password {app_password}",
        private_key_begin,
        "secret",
        private_key_end,
    ])
    redacted = tool.redact_text(raw)
    require(email not in redacted, "redact_report leaked real email")
    require("recipient@example.com" in redacted, "redact_report redacted allowed placeholder email")
    require(openai_key not in redacted, "redact_report leaked OpenAI key")
    require(github_token not in redacted, "redact_report leaked GitHub token")
    require(app_password not in redacted, "redact_report leaked app password")
    require("BEGIN PRIVATE KEY" not in redacted and "secret" not in redacted, "redact_report leaked private key block")


def smoke_clone_report_summary(_tmp: Path) -> None:
    tool = load_tool("clone-report-summary.py")
    raw = "\n".join([
        "Seed clone doctor",
        "root: /home/seed/seed",
        "host: seedbox",
        "kernel: Linux 6.1.0 armv7l GNU/Linux",
        "os: Debian GNU/Linux 12 (bookworm)",
        "fail: tool smoke exited with 1",
        "== git state after checks ==",
        " M data/memory.md",
        "",
        "== shareable proof ==",
        "I cloned https://github.com/seedpi867-cmd/seed on Debian GNU/Linux 12 (bookworm) (armv7l); tools/clone-doctor.sh passed health check, tool smoke, privacy audit, and left the git tree clean.",
    ])
    summary = tool.summarize(raw, "bash tools/clone-doctor.sh")
    require("Machine: seedbox / Linux 6.1.0 armv7l GNU/Linux" in summary, "clone_report_summary missed machine")
    require("Result: clone doctor failed" in summary, "clone_report_summary missed failure status")
    require("- fail: tool smoke exited with 1" in summary, "clone_report_summary missed failure line")
    require(" M data/memory.md" in summary, "clone_report_summary missed dirty state")
    require("Relevant output:" in summary and raw in summary, "clone_report_summary omitted raw output")


def smoke_clone_proof_board(_tmp: Path) -> None:
    tool = load_tool("clone-proof-board.py")
    require(
        tool.issues_url("owner/repo", "all", 5)
        == "https://api.github.com/repos/owner/repo/issues?state=all&labels=clone-proof&per_page=5",
        "clone_proof_board URL changed",
    )
    body = "\n".join([
        "### Machine",
        "",
        "Raspberry Pi Zero 2W | arm64 | 512MB RAM",
        "",
        "### OS",
        "",
        "Raspberry Pi OS Lite 64-bit",
        "",
        "### Backend tested",
        "",
        "clone-doctor only",
        "",
        "### Shareable proof",
        "",
        "```text",
        "Cloned https://github.com/owner/repo on Raspberry Pi OS; passed checks.",
        "```",
    ])
    fields = tool.issue_fields(body)
    require(fields["machine"] == "Raspberry Pi Zero 2W | arm64 | 512MB RAM", "clone_proof_board missed machine")
    require(fields["shareable proof"].startswith("Cloned https://github.com/owner/repo"), "clone_proof_board missed fenced proof")

    table = tool.build_table([
        {
            "number": 7,
            "state": "open",
            "title": "Clone proof: Pi",
            "html_url": "https://github.com/owner/repo/issues/7",
            "created_at": "2026-05-03T01:02:03Z",
            "body": body,
        },
        {
            "number": 8,
            "pull_request": {"url": "https://api.github.com/pulls/8"},
            "body": body,
        },
    ], "owner/repo", 10)
    require("| [#7](https://github.com/owner/repo/issues/7) |" in table, "clone_proof_board omitted issue link")
    require("Raspberry Pi Zero 2W \\| arm64 \\| 512MB RAM" in table, "clone_proof_board did not escape table pipes")
    require("#8" not in table, "clone_proof_board included pull request")


def smoke_share_proof(_tmp: Path) -> None:
    tool = load_tool("share-proof.py")
    raw = "\n".join([
        "Seed clone doctor",
        "host: seed-test",
        "kernel: Linux 6.1.0 armv7l GNU/Linux",
        "os: Debian GNU/Linux 12 (bookworm)",
        "== shareable proof ==",
        "I cloned https://github.com/seedpi867-cmd/seed on Debian GNU/Linux 12 (bookworm) (armv7l); tools/clone-doctor.sh passed health check, tool smoke, privacy audit, and left the git tree clean.",
        "Clone proof: https://github.com/seedpi867-cmd/seed/issues/new?template=clone-proof.yml",
    ])
    note = tool.build_note(raw, "owner/repo", 500)
    require(
        "Cloned https://github.com/owner/repo on Debian GNU/Linux 12" in note,
        "share_proof did not rewrite proof for the target repo",
    )
    require(
        "https://github.com/owner/repo/issues/new?template=clone-proof.yml" in note,
        "share_proof omitted clone proof URL",
    )
    short = tool.build_note(raw, "owner/repo", 120)
    require(len(short) <= 120, "share_proof ignored max length")
    fields = tool.build_issue_fields(raw, "owner/repo", 500)
    require("Machine:\nseed-test / Linux 6.1.0 armv7l GNU/Linux" in fields, "share_proof issue fields missed machine")
    require("OS:\nDebian GNU/Linux 12 (bookworm)" in fields, "share_proof issue fields missed OS")
    require("Backend tested:\nclone-doctor only" in fields, "share_proof issue fields missed backend")
    require("Shareable proof:\nCloned https://github.com/owner/repo" in fields, "share_proof issue fields missed proof")
    require(tool.build_note("no proof here", "owner/repo", 500) == "", "share_proof accepted missing proof")
    require(tool.build_issue_fields("no proof here", "owner/repo", 500) == "", "share_proof issue fields accepted missing proof")


def smoke_propagation_report(_tmp: Path) -> None:
    tool = load_tool("propagation-report.py")
    full_topics = list(tool.RECOMMENDED_TOPICS)
    lines = tool.interpretation_lines(full_topics)
    require(
        "topics are present; the remaining gap is propagation" in lines,
        "propagation_report did not acknowledge complete topics",
    )
    require(
        not any(line.startswith("missing topics") for line in lines),
        "propagation_report warned about missing topics when none were missing",
    )

    partial_topics = full_topics[:-1]
    missing = tool.missing_topics(partial_topics)
    require(missing == [full_topics[-1]], "propagation_report missing topic calculation changed")
    lines = tool.interpretation_lines(partial_topics)
    require(
        any(line == f"missing topics are a discovery bug: {full_topics[-1]}" for line in lines),
        "propagation_report did not report the exact missing topic",
    )
    conversion = tool.conversion_lines({"total": 148, "cta_clicks": 0}, {"stars": 2})
    require(
        "CTA click-through: 0/148 (0.0%)" in conversion,
        "propagation_report did not calculate CTA click-through",
    )
    require(
        any("repo intent is still zero" in line for line in conversion),
        "propagation_report did not flag zero CTA conversion",
    )
    conversion = tool.conversion_lines({"total": 148, "cta_clicks": 3}, {})
    require(
        any("no public propagation signal" in line for line in conversion),
        "propagation_report did not flag intent without propagation",
    )
    bottleneck = tool.bottleneck_lines({"total": 148, "cta_clicks": 0}, {"stars": 2})
    require(
        any("readers are not clicking through" in line for line in bottleneck),
        "propagation_report did not identify zero-CTA bottleneck",
    )
    bottleneck = tool.bottleneck_lines({"total": 148, "cta_clicks": 4}, {"stars": 2})
    require(
        any("independent run evidence" in line for line in bottleneck),
        "propagation_report did not identify missing run-evidence bottleneck",
    )
    bottleneck = tool.bottleneck_lines(
        {"total": 148, "cta_clicks": 4},
        {"stars": 2, "forks": 1, "clone_proofs_closed": 1},
    )
    require(
        any("next gap is diversity" in line for line in bottleneck),
        "propagation_report did not identify diversity bottleneck after proof",
    )

    class Status:
        def __init__(self, name, readable, writable, detail):
            self.name = name
            self.readable = readable
            self.writable = writable
            self.detail = detail

    action = tool.maintainer_action_lines(
        {"total": 148, "cta_clicks": 0},
        {"stars": 2},
        [Status("HN", True, False, "dead comments")],
    )
    require(
        any("skip social drafting" in line for line in action),
        "propagation_report did not redirect blocked outreach to durable action",
    )
    action = tool.maintainer_action_lines(
        {"total": 148, "cta_clicks": 0},
        {"stars": 2},
        [Status("Mastodon", True, True, "verified")],
    )
    require(
        any("specific clone-doctor ask" in line for line in action),
        "propagation_report did not use writable outreach for a clone ask",
    )
    action = tool.maintainer_action_lines({"total": 148, "cta_clicks": 4}, {"stars": 2})
    require(
        any("clone-doctor request" in line for line in action),
        "propagation_report did not recommend clone evidence after repo intent",
    )

    urls = []

    def fake_fetch_json(url, timeout=10):
        urls.append(url)
        return [
            {"number": 1, "title": "real clone report"},
            {"number": 2, "pull_request": {"url": "https://api.github.com/pulls/2"}},
        ]

    tool.fetch_json = fake_fetch_json
    count = tool.github_issue_count("owner/repo", "clone-report", "open")
    require(count == 1, "propagation_report counted pull requests as clone reports")
    require(
        "labels=clone-report" in urls[-1] and "state=open" in urls[-1],
        "propagation_report did not query clone-report issues by label and state",
    )
    require(
        tool.clone_report_url("owner/repo") == "https://github.com/owner/repo/issues/new?template=clone-report.yml",
        "propagation_report clone report URL changed",
    )
    require(
        tool.clone_proof_url("owner/repo") == "https://github.com/owner/repo/issues/new?template=clone-proof.yml",
        "propagation_report clone proof URL changed",
    )
    require(
        tool.fork_url("owner/repo") == "https://github.com/owner/repo/fork",
        "propagation_report fork URL changed",
    )

    outreach = tool.outreach_lines([
        Status("HN", True, False, "all recent comments are dead"),
        Status("Reddit", True, False, "missing browser session"),
        Status("Mastodon", True, False, "HTTP 403"),
    ])
    require(
        "no writable outreach surface; use the blog, repo, or issue funnel" in outreach,
        "propagation_report did not fail closed when outreach is read-only",
    )
    outreach = tool.outreach_lines([
        Status("Mastodon", True, True, "verified @seed867"),
    ])
    require(
        "usable outreach surfaces: Mastodon" in outreach,
        "propagation_report did not report writable outreach surfaces",
    )


def smoke_github_actions_status(_tmp: Path) -> None:
    tool = load_tool("github-actions-status.py")
    require(
        tool.actions_runs_url("owner/repo", 3)
        == "https://api.github.com/repos/owner/repo/actions/runs?per_page=3",
        "github_actions_status URL changed",
    )
    runs = tool.summarize_runs({
        "workflow_runs": [
            {
                "id": 123,
                "name": "Clone check",
                "head_branch": "main",
                "head_sha": "abcdef123456",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-05-03T00:00:00Z",
                "html_url": "https://github.com/owner/repo/actions/runs/123",
            }
        ]
    })
    require(runs[0]["sha"] == "abcdef1", "github_actions_status did not shorten sha")
    require(
        tool.latest_state(runs) == "Clone check at abcdef1: success",
        "github_actions_status latest state summary changed",
    )
    require(tool.latest_state([]) == "unknown", "github_actions_status empty state changed")


def smoke_repo_link_audit(_tmp: Path) -> None:
    tool = load_tool("repo-link-audit.py")
    require(
        tool.site_url("https://example.com/", "blog") == "https://example.com/blog",
        "repo_link_audit site_url did not normalize paths",
    )
    require(
        tool.has_repo_link("clone https://github.com/owner/repo", "owner/repo"),
        "repo_link_audit missed a GitHub repo URL",
    )
    require(
        not tool.has_repo_link("clone https://github.com/other/repo", "owner/repo"),
        "repo_link_audit accepted the wrong repo URL",
    )
    paths = tool.post_paths([
        {"slug": "valid-post"},
        {"slug": "../private"},
        {"slug": "also-valid-123"},
        {"slug": ""},
    ])
    require(
        paths == ["/posts/valid-post.md", "/posts/also-valid-123.md"],
        "repo_link_audit did not filter post slugs safely",
    )


def smoke_reddit(tmp: Path) -> None:
    tool = load_tool("reddit.py")
    tool.SESSION_FILE = str(tmp / "reddit-cookies.txt")

    empty = tool.http.cookiejar.CookieJar()
    require(not tool.has_auth_cookie(empty), "reddit accepted empty cookie jar")

    auth = tool.http.cookiejar.CookieJar()
    auth.set_cookie(tool.cookie_from_json({
        "domain": ".reddit.com",
        "name": "reddit_session",
        "value": "smoke-session",
        "path": "/",
    }))
    require(tool.has_auth_cookie(auth), "reddit missed reddit_session cookie")

    token = tool.http.cookiejar.CookieJar()
    token.set_cookie(tool.cookie_from_json({
        "domain": ".reddit.com",
        "name": "token_v2",
        "value": "smoke-token",
        "path": "/",
    }))
    require(tool.has_auth_cookie(token), "reddit missed token_v2 cookie")


def smoke_bluesky(tmp: Path) -> None:
    tool = load_tool("bluesky.py")
    tmp.mkdir(parents=True, exist_ok=True)
    tool.HOME = tmp
    tool.CREDS_FILE = tmp / "bluesky-credentials.json"
    tool.SESSION_FILE = tmp / "bluesky-session.json"
    tool.SIGNUP_FILE = tmp / "bluesky-signup.json"

    tool.save_json(tool.CREDS_FILE, {"identifier": "seed.example", "password": "app-password"})
    require(tool.load_credentials()["identifier"] == "seed.example", "bluesky did not load saved credentials")

    calls = []

    def fake_request_json(host, method, payload=None, token=None, timeout=15):
        calls.append((host, method, payload, token, timeout))
        if host.endswith("describeServer"):
            return {
                "availableUserDomains": [".bsky.social"],
                "inviteCodeRequired": False,
                "phoneVerificationRequired": True,
            }
        if host.endswith("createSession"):
            return {
                "handle": "seed.example",
                "did": "did:plc:seed",
                "accessJwt": "access",
                "refreshJwt": "refresh",
            }
        if host.endswith("createRecord"):
            return {"uri": "at://did:plc:seed/app.bsky.feed.post/abc", "cid": "bafyseed"}
        raise AssertionError(f"unexpected Bluesky request {host}")

    original_request_json = tool.request_json
    try:
        tool.request_json = fake_request_json
        session = tool.create_session(False)
        require(session["did"] == "did:plc:seed", "bluesky session did not save fake session")
        post = tool.post("hello from smoke")
        require(post["uri"].startswith("at://"), "bluesky post did not return record URI")
        require(calls[-1][2]["collection"] == "app.bsky.feed.post", "bluesky post used wrong collection")
    finally:
        tool.request_json = original_request_json


def smoke_outreach_readiness(tmp: Path) -> None:
    tool = load_tool("outreach-readiness.py")
    tool.HN_CREDS = tmp / "missing-hn.json"
    tool.REDDIT_CREDS = tmp / "reddit-creds.json"
    tool.REDDIT_COOKIES = tmp / "reddit-cookies.txt"
    tool.MASTODON_TOKEN = tmp / "missing-token.json"
    tool.MASTODON_APP = tmp / "missing-app.json"
    tool.BLUESKY_CREDS = tmp / "missing-bluesky-creds.json"
    tool.BLUESKY_SESSION = tmp / "missing-bluesky-session.json"

    blocked = tool.collect(live=False)
    output = tool.render(blocked)
    require("HN: blocked" in output, "outreach_readiness missed missing HN credentials")
    require("Mastodon: blocked" in output, "outreach_readiness missed missing Mastodon credentials")
    require("Bluesky: blocked" in output, "outreach_readiness missed missing Bluesky credentials")
    require("Decision: DO_NOT_DRAFT_SOCIAL" in output, "outreach_readiness missed closed-channel decision")
    require("No writable outreach surface" in output, "outreach_readiness did not fail closed")

    tool.REDDIT_COOKIES.parent.mkdir(parents=True, exist_ok=True)
    jar = tool.http.cookiejar.MozillaCookieJar(str(tool.REDDIT_COOKIES))
    jar.set_cookie(tool.http.cookiejar.Cookie(
        version=0,
        name="token_v2",
        value="smoke-token",
        port=None,
        port_specified=False,
        domain=".reddit.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=True,
        expires=1893456000,
        discard=False,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    ))
    jar.save(ignore_discard=True, ignore_expires=True)
    statuses = tool.collect(live=False)
    reddit = next(status for status in statuses if status.name == "Reddit")
    require(reddit.writable, "outreach_readiness missed token_v2 as writable")
    action, _ = tool.decision(statuses)
    require(action == "DRAFT_SOCIAL", "outreach_readiness missed writable-channel decision")

    tool.BLUESKY_CREDS.write_text(json.dumps({"identifier": "seed.example", "password": "pw"}), encoding="utf-8")
    statuses = tool.collect(live=False)
    bluesky = next(status for status in statuses if status.name == "Bluesky")
    require(bluesky.readable and not bluesky.writable, "outreach_readiness should require --live for Bluesky writability")


def smoke_mastodon(_tmp: Path) -> None:
    tool = load_tool("mastodon.py")

    calls = []

    def fake_request_json(path, data=None, method=None, timeout=10):
        calls.append((path, data, method, timeout))
        return {
            "username": "seed867",
            "followers_count": 2,
            "statuses_count": 42,
        }

    original_request_json = tool.request_json
    try:
        tool.INSTANCE = "https://mastodon.social"
        tool.request_json = fake_request_json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tool.status()
        require(calls and calls[0][0] == "/api/v1/accounts/verify_credentials", "mastodon status did not verify credentials")
        require("@seed867@" in buf.getvalue(), "mastodon status output missing account")
    finally:
        tool.request_json = original_request_json


def smoke_issue_router(_tmp: Path) -> None:
    tool = load_tool("issue-router.py")
    clone = tool.classify("clone-doctor fails on Debian because node is missing", "owner/repo")
    require(clone.name == "clone report", "issue_router missed clone report")
    require("clone-report.yml" in clone.url, "issue_router clone URL mismatch")

    proof = tool.classify("clone-doctor passed on Raspberry Pi OS clean run", "owner/repo")
    require(proof.name == "clone proof", "issue_router missed clone proof")
    require("clone-proof.yml" in proof.url, "issue_router proof URL mismatch")

    capability = tool.classify("OAuth token boundary for publish tool is unclear", "owner/repo")
    require(capability.name == "capability review", "issue_router missed capability review")
    require("capability-review.yml" in capability.url, "issue_router capability URL mismatch")

    plain = tool.classify("docs typo in the first paragraph", "owner/repo")
    require(plain.name == "plain issue", "issue_router generic route mismatch")


def smoke_clone_evidence_kit(_tmp: Path) -> None:
    tool = load_tool("clone-evidence-kit.py")
    output = tool.render("owner/repo")
    require("Seed clone evidence kit" in output, "clone_evidence_kit title missing")
    require("git clone https://github.com/owner/repo.git seed" in output, "clone_evidence_kit clone command mismatch")
    require("clone-proof.yml" in output and "clone-report.yml" in output, "clone_evidence_kit issue URLs missing")
    require("share-proof.py --issue-fields" in output, "clone_evidence_kit proof command missing")
    require("clone-report-summary.py" in output, "clone_evidence_kit report command missing")

    fallback = tool.render("broken")
    require("repo: seedpi867-cmd/seed" in fallback, "clone_evidence_kit invalid repo fallback changed")


def smoke_repo_card(_tmp: Path) -> None:
    tool = load_tool("repo-card.py")
    text = tool.render("owner/repo", "https://example.test/", "text")
    require("https://github.com/owner/repo" in text, "repo_card repo URL missing")
    require("https://example.test" in text, "repo_card site URL missing")
    require("clone-doctor.sh" in text, "repo_card clone command missing")
    require("clone-proof.yml" in text and "clone-report.yml" in text, "repo_card issue URLs missing")

    markdown = tool.render("owner/repo", "https://example.test", "markdown")
    require("[owner/repo](https://github.com/owner/repo)" in markdown, "repo_card markdown link missing")
    require("`git clone https://github.com/owner/repo.git seed" in markdown, "repo_card markdown command missing")

    fallback = tool.render("broken", "example.test", "text")
    require("https://github.com/seedpi867-cmd/seed" in fallback, "repo_card invalid repo fallback changed")
    require("https://seed-brain.vercel.app" in fallback, "repo_card invalid site fallback changed")


def smoke_share_fit(_tmp: Path) -> None:
    tool = load_tool("share-fit.py")
    good = tool.score_text("Show HN: self-hosted autonomous agent with git-backed memory on a Raspberry Pi")
    require(good.decision == "SHARE_CLONE_ASK", "share_fit missed strong agent/thread fit")
    rendered = tool.render(good, "owner/repo")
    require("https://github.com/owner/repo" in rendered, "share_fit rendered repo URL missing")
    require("clone-doctor.sh" in rendered, "share_fit clone ask missing")

    thin = tool.score_text("What are you cooking this weekend?")
    require(thin.decision == "SKIP_LINK", "share_fit accepted unrelated thread")

    promo = tool.score_text("Follow for follow giveaway, upvote this airdrop")
    require(promo.decision == "SKIP_LINK", "share_fit accepted promotional thread")


def smoke_fork_readiness(tmp: Path) -> None:
    tool = load_tool("fork-readiness.py")
    root = tmp / "repo"
    root.mkdir(parents=True)
    (root / "data").mkdir()
    for check in tool.CHECKS:
        path = root / check.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("custom fork text\n")

    results = tool.audit(root)
    require(not tool.has_blockers(results), "fork_readiness flagged customized fixture")

    (root / "IDENTITY.md").write_text("Runs on a Raspberry Pi Zero 2W in Adelaide.\n")
    results = tool.audit(root)
    blockers = [result for result in results if result.status != "customized"]
    require(len(blockers) == 1, "fork_readiness did not isolate one upstream marker")
    require(blockers[0].path == "IDENTITY.md", "fork_readiness reported wrong file")
    require("Raspberry Pi Zero 2W" in blockers[0].markers, "fork_readiness missed marker")
    require(tool.has_blockers(results), "fork_readiness did not report blocker")


def smoke_backend_readiness(tmp: Path) -> None:
    tool = load_tool("backend-readiness.py")
    home = tmp / "home"
    home.mkdir(parents=True)
    (home / ".codex").mkdir()
    (home / ".codex" / "auth.json").write_text("{}\n")

    original_which = tool.shutil.which
    original_run = tool.subprocess.run
    original_env = dict(tool.os.environ)
    try:
        tool.os.environ.clear()
        tool.shutil.which = lambda command: f"/usr/bin/{command}" if command == "codex" else None

        def fake_run(args, **_kwargs):
            return type("Proc", (), {"stdout": f"{args[0]} 1.2.3\n", "stderr": "", "returncode": 0})()

        tool.subprocess.run = fake_run
        statuses = {name: tool.backend_status(name, home, timeout=1) for name in tool.BACKENDS}
        require(statuses["codex"].ready, "backend_readiness missed codex auth file")
        require(not statuses["claude"].ready, "backend_readiness accepted missing claude command")
        require(not statuses["gemini"].ready, "backend_readiness accepted missing Gemini key")
        require("- think: ready via codex" in tool.render(statuses), "backend_readiness phase summary missing codex readiness")

        tool.os.environ["GEMINI_API_KEY"] = "fixture-key"
        gemini = tool.backend_status("gemini", home, timeout=1)
        require(gemini.ready, "backend_readiness missed Gemini API key")
        require("fixture-key" not in tool.render({**statuses, "gemini": gemini}), "backend_readiness leaked env value")
        require(tool.required_backends("all") == ["codex", "claude"], "backend_readiness all requirement changed")
    finally:
        tool.shutil.which = original_which
        tool.subprocess.run = original_run
        tool.os.environ.clear()
        tool.os.environ.update(original_env)


SMOKES = {
    "backend-readiness.py": smoke_backend_readiness,
    "bluesky.py": smoke_bluesky,
    "clone-evidence-kit.py": smoke_clone_evidence_kit,
    "clone-proof-board.py": smoke_clone_proof_board,
    "clone-report-summary.py": smoke_clone_report_summary,
    "download_file.py": smoke_download_file,
    "fetch_url.py": smoke_fetch_url,
    "file_ops.py": smoke_file_ops,
    "file_read.py": smoke_file_read,
    "file_write.py": smoke_file_write,
    "fork-readiness.py": smoke_fork_readiness,
    "github-actions-status.py": smoke_github_actions_status,
    "issue-router.py": smoke_issue_router,
    "mastodon.py": smoke_mastodon,
    "outreach-readiness.py": smoke_outreach_readiness,
    "shell_exec.py": smoke_shell_exec,
    "plant_goal.py": smoke_plant_goal,
    "propagation-report.py": smoke_propagation_report,
    "redact-report.py": smoke_redact_report,
    "reddit.py": smoke_reddit,
    "repo-link-audit.py": smoke_repo_link_audit,
    "repo-card.py": smoke_repo_card,
    "search_web.py": smoke_search_web,
    "share-fit.py": smoke_share_fit,
    "share-proof.py": smoke_share_proof,
    "write_blog_post.py": smoke_write_blog_post,
    "port_check.py": smoke_port_check,
    "system_health.py": smoke_system_health,
    "system_monitor.py": smoke_system_monitor,
    "web_fetch.py": smoke_web_fetch,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tools", nargs="*", default=sorted(SMOKES), help="Tool filenames to smoke-test")
    args = parser.parse_args()

    failures = []
    with tempfile.TemporaryDirectory(prefix="seed-tool-smoke-") as tmp_name:
        tmp = Path(tmp_name)
        for name in args.tools:
            smoke = SMOKES.get(name)
            if smoke is None:
                failures.append(f"{name}: no smoke registered")
                continue
            try:
                smoke(tmp / name.replace(".", "-"))
                print(f"pass {name}")
            except Exception as exc:  # noqa: BLE001 - report every smoke failure compactly.
                failures.append(f"{name}: {exc}")

    if failures:
        for failure in failures:
            print(f"fail {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
