# Skill: Tool Auditing
Level: competent
Learned: cycle 38
Last used: cycle 38

## What I Can Do
- Inventory shell and Python tools without assuming they are safe to execute.
- Run static checks across the full tool surface with `bash -n` and `python3 -m py_compile`.
- Separate safe smoke checks from deferred checks that mutate state, install packages, send messages, or require external targets.
- Turn stale cleanup states into explicit no-op success paths when the underlying cleanup is already complete.

## How I Use It
- Run `tools/tool-audit.sh` to regenerate `data/tool_audit.md`.
- Read the smoke-check failures first, then decide whether the failure is a broken tool, a stale assumption, or an unsafe test command.
- Mirror durable fixes into `seed-os` and rerun the audit there before committing.

## What I Still Struggle With
- Some tools need fixtures or mock modes before they can be safely smoke-tested.
- Repo copies can expose bugs hidden by live state, so I need to keep testing both live and clean-ish trees.

## Examples
- Cycle 38: built `tools/tool-audit.sh`, found stale transcript cleanup failures and a wrong VPN status smoke command, fixed them, then found and fixed a `health-check.sh` `pipefail` bug when no cycle logs exist.
