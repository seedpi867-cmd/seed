#!/usr/bin/env python3
"""Report which Seed phases have a usable local AI backend.

The check is intentionally shallow and secret-safe. It looks for installed
commands and local authentication signals, but it never prints token contents or
tries to run a model call.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PHASE_BACKENDS = {
    "think": "codex",
    "research": "codex",
    "dream": "codex",
    "maintain": "codex",
    "write": "claude",
}


@dataclass(frozen=True)
class Backend:
    name: str
    command: str | None
    install_hint: str
    auth_hint: str
    auth_paths: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackendStatus:
    backend: Backend
    command_path: str | None
    version: str
    auth_signal: str
    ready: bool
    note: str


BACKENDS = {
    "codex": Backend(
        name="codex",
        command="codex",
        install_hint="sudo npm install -g @openai/codex",
        auth_hint="codex login",
        auth_paths=(".codex/auth.json", ".codex/config.toml", ".codex/config.json"),
    ),
    "claude": Backend(
        name="claude",
        command="claude",
        install_hint="sudo npm install -g @anthropic-ai/claude-code",
        auth_hint="claude login",
        auth_paths=(".claude.json", ".claude/.credentials.json", ".config/claude/config.json"),
    ),
    "gemini": Backend(
        name="gemini",
        command="gemini",
        install_hint="export GEMINI_API_KEY=...",
        auth_hint="export GEMINI_API_KEY=...",
        env_vars=("GEMINI_API_KEY",),
    ),
}


def existing_auth_paths(home: Path, backend: Backend) -> list[str]:
    found = []
    for rel in backend.auth_paths:
        path = home / rel
        if path.exists():
            found.append(f"~/{rel}")
    return found


def env_auth_vars(backend: Backend) -> list[str]:
    return [name for name in backend.env_vars if os.environ.get(name)]


def command_version(command: str | None, timeout: int) -> tuple[str | None, str]:
    if command is None:
        return None, "not required"
    path = shutil.which(command)
    if path is None:
        return None, "missing"
    try:
        proc = subprocess.run(
            [command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return path, f"version unavailable ({exc})"
    text = " ".join((proc.stdout + " " + proc.stderr).split())
    return path, text or f"version exited {proc.returncode} with no output"


def backend_status(name: str, home: Path, timeout: int = 5) -> BackendStatus:
    backend = BACKENDS[name]
    command_path, version = command_version(backend.command, timeout)
    auth_paths = existing_auth_paths(home, backend)
    auth_vars = env_auth_vars(backend)

    signals = auth_paths + [f"${var}" for var in auth_vars]
    auth_signal = ", ".join(signals) if signals else "missing"

    if name == "gemini":
        ready = bool(auth_vars)
        note = "API-key path; not used by default brain-loop phases"
    else:
        ready = bool(command_path and signals)
        note = "ready" if ready else "install command and authenticate"

    return BackendStatus(
        backend=backend,
        command_path=command_path,
        version=version,
        auth_signal=auth_signal,
        ready=ready,
        note=note,
    )


def phase_lines(statuses: dict[str, BackendStatus]) -> list[str]:
    lines = []
    for phase, backend in PHASE_BACKENDS.items():
        status = statuses[backend]
        state = "ready" if status.ready else "blocked"
        lines.append(f"- {phase}: {state} via {backend}")
    return lines


def render(statuses: dict[str, BackendStatus]) -> str:
    lines = ["Seed backend readiness", ""]
    lines.append("Backends")
    for name in ("codex", "claude", "gemini"):
        status = statuses[name]
        command = status.command_path or "missing"
        ready = "ready" if status.ready else "blocked"
        next_step = status.note if status.ready else f"{status.backend.install_hint}; {status.backend.auth_hint}"
        lines.append(f"- {name}: {ready}")
        lines.append(f"  command: {command}")
        lines.append(f"  version: {status.version}")
        lines.append(f"  auth signal: {status.auth_signal}")
        lines.append(f"  next: {next_step}")
    lines.append("")
    lines.append("Default phases")
    lines.extend(phase_lines(statuses))
    return "\n".join(lines)


def required_backends(selection: str) -> list[str]:
    if selection == "all":
        return ["codex", "claude"]
    return [selection]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require",
        choices=("codex", "claude", "gemini", "all"),
        help="exit non-zero if the selected backend is not ready",
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--timeout", type=int, default=5)
    args = parser.parse_args()

    statuses = {name: backend_status(name, args.home, args.timeout) for name in BACKENDS}
    print(render(statuses))

    if args.require:
        missing = [name for name in required_backends(args.require) if not statuses[name].ready]
        if missing:
            print()
            print("blocked required backend: " + ", ".join(missing))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
