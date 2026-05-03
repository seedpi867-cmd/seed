#!/usr/bin/env python3
"""Report whether social outreach accounts are readable or writable.

This is a preflight. It never posts, comments, follows, favourites, or imports
cookies. It only reads local credential/session markers and, with --live, uses
read-only status endpoints where available.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


HOME = Path.home()
HN_CREDS = HOME / ".hn-credentials"
REDDIT_COOKIES = HOME / ".reddit-cookies.txt"
REDDIT_CREDS = HOME / ".reddit-credentials"
MASTODON_TOKEN = HOME / ".mastodon-token"
MASTODON_APP = HOME / ".mastodon-app"
BLUESKY_CREDS = HOME / ".bluesky-credentials"
BLUESKY_SESSION = HOME / ".bluesky-session"


@dataclass
class SurfaceStatus:
    name: str
    readable: bool
    writable: bool
    detail: str
    next_step: str = ""


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 10):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Seed/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def hn_status(live: bool) -> SurfaceStatus:
    if not HN_CREDS.exists():
        return SurfaceStatus(
            "HN",
            False,
            False,
            "missing ~/.hn-credentials",
            "create credentials before using tools/hn.py",
        )
    try:
        creds = load_json(HN_CREDS)
        username = str(creds.get("username") or "").strip()
    except Exception as exc:  # noqa: BLE001 - compact diagnostic for local config.
        return SurfaceStatus("HN", False, False, f"credential file unreadable: {exc}")
    if not username:
        return SurfaceStatus("HN", False, False, "credential file has no username")
    if not live:
        return SurfaceStatus(
            "HN",
            True,
            False,
            f"credentials present for {username}; live visibility not checked",
            "run with --live before drafting a comment",
        )

    try:
        user = fetch_json(f"https://hacker-news.firebaseio.com/v0/user/{username}.json") or {}
        submitted = user.get("submitted", [])[:30]
        comments = dead = 0
        for item_id in submitted:
            item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json") or {}
            if item.get("type") != "comment":
                continue
            comments += 1
            if item.get("dead"):
                dead += 1
        if comments and dead == comments:
            return SurfaceStatus(
                "HN",
                True,
                False,
                f"{comments} recent comments checked; all are dead/invisible",
                "treat HN as read-only until one comment is publicly visible",
            )
        return SurfaceStatus(
            "HN",
            True,
            True,
            f"karma {user.get('karma', 'unknown')}; {comments - dead}/{comments} recent comments visible",
        )
    except Exception as exc:  # noqa: BLE001 - network/API preflight should fail closed.
        return SurfaceStatus("HN", True, False, f"live status unavailable: {exc}")


def reddit_cookie_names(path: Path | None = None) -> set[str]:
    path = path or REDDIT_COOKIES
    jar = http.cookiejar.MozillaCookieJar(str(path))
    if not path.exists():
        return set()
    jar.load(ignore_discard=True, ignore_expires=True)
    return {cookie.name for cookie in jar}


def reddit_status(_live: bool) -> SurfaceStatus:
    names = reddit_cookie_names()
    if {"reddit_session", "token_v2"} & names:
        return SurfaceStatus("Reddit", True, True, f"saved browser session has {', '.join(sorted(names))}")
    if names:
        return SurfaceStatus(
            "Reddit",
            True,
            False,
            f"saved cookies are read-only for posting: {', '.join(sorted(names))}",
            "import a browser export with reddit_session or token_v2",
        )
    if REDDIT_CREDS.exists():
        return SurfaceStatus(
            "Reddit",
            True,
            False,
            "credentials present, but no saved browser auth cookie",
            "run tools/reddit.py import-cookies <browser-cookie-export>",
        )
    return SurfaceStatus("Reddit", False, False, "missing Reddit credentials/session")


def mastodon_status(live: bool) -> SurfaceStatus:
    if not MASTODON_TOKEN.exists() or not MASTODON_APP.exists():
        return SurfaceStatus(
            "Mastodon",
            False,
            False,
            "missing ~/.mastodon-token or ~/.mastodon-app",
            "complete Mastodon OAuth before posting",
        )
    try:
        token = load_json(MASTODON_TOKEN).get("access_token")
        instance = load_json(MASTODON_APP).get("instance")
    except Exception as exc:  # noqa: BLE001
        return SurfaceStatus("Mastodon", False, False, f"credential file unreadable: {exc}")
    if not token or not instance:
        return SurfaceStatus("Mastodon", False, False, "token/app config is incomplete")
    if not live:
        return SurfaceStatus(
            "Mastodon",
            True,
            False,
            "credentials present; live account state not checked",
            "run with --live before posting",
        )

    req = urllib.request.Request(f"{instance}/api/v1/accounts/verify_credentials")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            account = json.loads(resp.read().decode("utf-8"))
        acct = account.get("acct") or account.get("username") or "unknown"
        return SurfaceStatus("Mastodon", True, True, f"verified @{acct}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:160].strip()
        detail = f"HTTP {exc.code}"
        if body:
            detail = f"{detail}: {body}"
        return SurfaceStatus("Mastodon", True, False, detail, "do not post until verify_credentials succeeds")
    except Exception as exc:  # noqa: BLE001
        return SurfaceStatus("Mastodon", True, False, f"live status unavailable: {exc}")


def bluesky_status(live: bool) -> SurfaceStatus:
    if not BLUESKY_CREDS.exists() and not BLUESKY_SESSION.exists():
        if not live:
            return SurfaceStatus(
                "Bluesky",
                False,
                False,
                "missing ~/.bluesky-credentials or ~/.bluesky-session",
                "create an account, then run tools/bluesky.py setup-credentials <handle> <app-password>",
            )
        try:
            server = fetch_json("https://bsky.social/xrpc/com.atproto.server.describeServer")
        except Exception as exc:  # noqa: BLE001
            return SurfaceStatus("Bluesky", False, False, f"signup status unavailable: {exc}")
        phone = bool(server.get("phoneVerificationRequired"))
        invite = bool(server.get("inviteCodeRequired"))
        return SurfaceStatus(
            "Bluesky",
            False,
            False,
            f"not configured; signup phone verification required={phone}, invite required={invite}",
            "complete signup manually if phone verification is required",
        )

    if not live:
        return SurfaceStatus(
            "Bluesky",
            True,
            False,
            "local credential/session marker present; live auth not checked",
            "run with --live before posting",
        )

    try:
        if BLUESKY_CREDS.exists():
            creds = load_json(BLUESKY_CREDS)
            payload = {"identifier": creds.get("identifier"), "password": creds.get("password")}
            if not payload["identifier"] or not payload["password"]:
                return SurfaceStatus("Bluesky", False, False, "credential file missing identifier/password")
            req = urllib.request.Request(
                "https://bsky.social/xrpc/com.atproto.server.createSession",
                data=json.dumps(payload).encode("utf-8"),
                headers={"User-Agent": "Seed/1.0", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                session = json.loads(resp.read().decode("utf-8"))
            handle = session.get("handle") or payload["identifier"]
            return SurfaceStatus("Bluesky", True, True, f"verified @{handle}")
        session = load_json(BLUESKY_SESSION)
        handle = session.get("handle") or session.get("did") or "unknown"
        return SurfaceStatus(
            "Bluesky",
            True,
            False,
            f"session marker present for {handle}; no refresh credential checked",
            "store ~/.bluesky-credentials before automated posting",
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:160].strip()
        detail = f"HTTP {exc.code}"
        if body:
            detail = f"{detail}: {body}"
        return SurfaceStatus("Bluesky", True, False, detail, "fix credentials before posting")
    except Exception as exc:  # noqa: BLE001
        return SurfaceStatus("Bluesky", True, False, f"live status unavailable: {exc}")


def collect(live: bool) -> list[SurfaceStatus]:
    return [hn_status(live), reddit_status(live), mastodon_status(live), bluesky_status(live)]


def decision(statuses: list[SurfaceStatus]) -> tuple[str, str]:
    writable = [status.name for status in statuses if status.writable]
    if writable:
        return (
            "DRAFT_SOCIAL",
            "writable outreach surface available: " + ", ".join(writable),
        )
    readable = [status.name for status in statuses if status.readable]
    if readable:
        return (
            "DO_NOT_DRAFT_SOCIAL",
            "only read-only social sensors are available: " + ", ".join(readable),
        )
    return (
        "DO_NOT_DRAFT_SOCIAL",
        "no configured outreach surface is available",
    )


def render(statuses: list[SurfaceStatus]) -> str:
    lines = ["Seed outreach readiness"]
    for status in statuses:
        mode = "writable" if status.writable else "read-only" if status.readable else "blocked"
        lines.append(f"- {status.name}: {mode} - {status.detail}")
        if status.next_step:
            lines.append(f"  next: {status.next_step}")
    action, reason = decision(statuses)
    lines.append(f"Decision: {action} - {reason}")
    if not any(status.writable for status in statuses):
        lines.append("No writable outreach surface is available. Use the blog, repo, or issue funnel instead.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="check read-only live status endpoints where possible")
    args = parser.parse_args(argv)

    statuses = collect(args.live)
    print(render(statuses))
    return 0 if any(status.writable for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
