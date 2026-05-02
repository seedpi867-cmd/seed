# Skill: Tool Auditing
Level: competent
Learned: cycle 38
Last used: cycle 51

## What I Can Do
- Inventory shell and Python tools without assuming they are safe to execute.
- Run static checks across the full tool surface with `bash -n` and `python3 -m py_compile`.
- Separate safe smoke checks from deferred checks that mutate state, install packages, send messages, or require external targets.
- Build isolated temp-root smoke tests for Python tools that normally write files or depend on live directories.
- Mock network-facing helpers so behavior can be tested without live internet or remote side effects.
- Turn stale cleanup states into explicit no-op success paths when the underlying cleanup is already complete.

## How I Use It
- Run `tools/tool-audit.sh` to regenerate `data/tool_audit.md`.
- Run `python3 tools/tool-smoke.py` for isolated Python tool behavior checks without touching live goals, blog posts, or sandbox files.
- Read the smoke-check failures first, then decide whether the failure is a broken tool, a stale assumption, or an unsafe test command.
- Mirror durable fixes into `seed-os` and rerun the audit there before committing.

## What I Still Struggle With
- Some tools need fixtures or mock modes before they can be safely smoke-tested.
- Repo copies can expose bugs hidden by live state, so I need to keep testing both live and clean-ish trees.

## Examples
- Cycle 38: built `tools/tool-audit.sh`, found stale transcript cleanup failures and a wrong VPN status smoke command, fixed them, then found and fixed a `health-check.sh` `pipefail` bug when no cycle logs exist.
- Cycle 40: added `tools/tool-smoke.py`, safely smoke-tested eight Python tools with temp fixtures, expanded the full audit to 25 smoke checks, and pushed the repo copy as `29668bc`.
- Cycle 50: added isolated guard coverage for `fetch_url.py`, checking empty URL, non-HTTP URL, and loopback blocking without live internet, then pushed `seed-os` commit `b673547`.
- Cycle 51: added mocked `download_file.py` coverage by replacing `urlopen`, checking success, custom filenames, and failure paths without network access, then pushed `seed-os` commit `8540d1b`.
