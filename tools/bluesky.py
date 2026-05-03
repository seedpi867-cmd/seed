#!/usr/bin/env python3
"""Bluesky/ATProto outreach helper.

This tool keeps Bluesky account access explicit. It can inspect the public
signup boundary, create a session from local credentials, and post only after a
real session exists. It does not bypass phone verification, CAPTCHA, rate
limits, or moderation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


HOME = Path.home()
CREDS_FILE = HOME / ".bluesky-credentials"
SESSION_FILE = HOME / ".bluesky-session"
SIGNUP_FILE = HOME / ".bluesky-signup"
ENTRYWAY = "https://bsky.social"
USER_AGENT = "Seed/1.0"


class BlueskyError(RuntimeError):
    pass


def request_json(host: str, method: str, payload: dict | None = None, token: str | None = None, timeout: int = 15) -> dict:
    data = None
    headers = {"User-Agent": USER_AGENT}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(host, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300].strip()
        detail = f": {body}" if body else ""
        raise BlueskyError(f"Bluesky API HTTP {exc.code} on {host}{detail}") from None
    except urllib.error.URLError as exc:
        raise BlueskyError(f"Bluesky API unavailable on {host}: {exc.reason}") from None
    except json.JSONDecodeError:
        raise BlueskyError(f"Bluesky API returned invalid JSON on {host}") from None


def xrpc(path: str) -> str:
    return f"{ENTRYWAY}/xrpc/{path}"


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BlueskyError(f"missing {path}") from None
    except json.JSONDecodeError as exc:
        raise BlueskyError(f"{path} is invalid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise BlueskyError(f"{path} must contain a JSON object")
    return data


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def describe_server() -> dict:
    data = request_json(xrpc("com.atproto.server.describeServer"), "GET")
    domains = ", ".join(data.get("availableUserDomains", [])) or "unknown"
    print(f"Bluesky entryway: {ENTRYWAY}")
    print(f"available domains: {domains}")
    print(f"invite code required: {bool(data.get('inviteCodeRequired'))}")
    print(f"phone verification required: {bool(data.get('phoneVerificationRequired'))}")
    return data


def load_credentials(interactive: bool = False) -> dict:
    if CREDS_FILE.exists():
        creds = load_json(CREDS_FILE)
    elif interactive:
        identifier = input("Bluesky handle/email: ").strip()
        password = getpass.getpass("Bluesky password/app password: ")
        creds = {"identifier": identifier, "password": password}
    else:
        raise BlueskyError(f"missing {CREDS_FILE}; run setup-credentials or create-account first")
    if not creds.get("identifier") or not creds.get("password"):
        raise BlueskyError(f"{CREDS_FILE} needs identifier and password")
    return creds


def create_session(interactive: bool = False) -> dict:
    creds = load_credentials(interactive)
    session = request_json(
        xrpc("com.atproto.server.createSession"),
        "POST",
        {"identifier": creds["identifier"], "password": creds["password"]},
    )
    save_json(SESSION_FILE, session)
    handle = session.get("handle", creds["identifier"])
    print(f"session ok: @{handle}")
    return session


def load_session() -> dict:
    if SESSION_FILE.exists():
        session = load_json(SESSION_FILE)
        if session.get("accessJwt") and session.get("did"):
            return session
    return create_session(False)


def status(live: bool = True) -> bool:
    describe_server()
    if not CREDS_FILE.exists() and not SESSION_FILE.exists():
        print("account: not configured")
        print(f"next: create a Bluesky account manually or provide {CREDS_FILE}")
        return False
    if not live:
        print("account: local credential/session marker present; live auth not checked")
        return False
    try:
        session = create_session(False)
    except BlueskyError as exc:
        print(f"account: not writable ({exc})")
        return False
    print(f"account: writable as @{session.get('handle', 'unknown')}")
    return True


def setup_credentials(identifier: str, password: str) -> None:
    save_json(CREDS_FILE, {"identifier": identifier, "password": password})
    print(f"saved {CREDS_FILE}")


def create_account(handle: str | None, email: str | None, password: str | None) -> dict:
    if SIGNUP_FILE.exists():
        signup = load_json(SIGNUP_FILE)
        handle = handle or signup.get("handle")
        email = email or signup.get("email")
        password = password or signup.get("password")
    if not handle or not email or not password:
        raise BlueskyError("create-account needs --handle, --email, and --password or ~/.bluesky-signup")
    payload = {"handle": handle, "email": email, "password": password}
    result = request_json(xrpc("com.atproto.server.createAccount"), "POST", payload)
    save_json(CREDS_FILE, {"identifier": handle, "password": password})
    save_json(SESSION_FILE, result)
    print(f"created account: @{result.get('handle', handle)}")
    return result


def post(text: str) -> dict:
    session = load_session()
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
        "langs": ["en"],
    }
    result = request_json(
        xrpc("com.atproto.repo.createRecord"),
        "POST",
        {
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        token=session["accessJwt"],
    )
    print(f"posted: {result.get('uri', '')}")
    log_path = HOME / "data" / "outreach" / "bluesky-activity.md"
    if log_path.parent.exists():
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"| {stamp} | post | {text[:80]} | {result.get('uri', '')} |\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("describe")
    status_p = sub.add_parser("status")
    status_p.add_argument("--local", action="store_true", help="skip live auth")
    session_p = sub.add_parser("session")
    session_p.add_argument("--interactive", action="store_true")
    creds_p = sub.add_parser("setup-credentials")
    creds_p.add_argument("identifier")
    creds_p.add_argument("password")
    create_p = sub.add_parser("create-account")
    create_p.add_argument("--handle")
    create_p.add_argument("--email")
    create_p.add_argument("--password")
    post_p = sub.add_parser("post")
    post_p.add_argument("text")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "describe":
            describe_server()
            return 0
        if args.cmd == "status":
            return 0 if status(not args.local) else 1
        if args.cmd == "session":
            create_session(args.interactive)
            return 0
        if args.cmd == "setup-credentials":
            setup_credentials(args.identifier, args.password)
            return 0
        if args.cmd == "create-account":
            create_account(args.handle, args.email, args.password)
            return 0
        if args.cmd == "post":
            post(args.text)
            return 0
    except BlueskyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
