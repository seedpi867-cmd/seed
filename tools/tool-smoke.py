#!/usr/bin/env python3
"""Run isolated smoke checks for Python tools with no live side effects."""

from __future__ import annotations

import argparse
import contextlib
import io
import importlib.util
import json
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


SMOKES = {
    "download_file.py": smoke_download_file,
    "fetch_url.py": smoke_fetch_url,
    "file_ops.py": smoke_file_ops,
    "file_read.py": smoke_file_read,
    "file_write.py": smoke_file_write,
    "shell_exec.py": smoke_shell_exec,
    "plant_goal.py": smoke_plant_goal,
    "redact-report.py": smoke_redact_report,
    "search_web.py": smoke_search_web,
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
