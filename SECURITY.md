# Security And Custody Model

Seed is autonomous inside the world you give it. The first safety rule is to
make that world small.

This project is not designed to run as root, hold all of your personal tokens,
or manage a machine you cannot afford to reinstall. Start with a fresh user on a
small Linux box, then add capabilities deliberately.

## Default Boundaries

- Run Seed as an unprivileged user.
- Keep the repo in that user's home directory.
- Authenticate only the agent backend you want to test.
- Put throwaway or project-specific credentials in the environment, not broad
  personal credentials.
- Treat `data/`, `blog/`, `context/`, `knowledge/`, and `tools/` as Seed's
  normal working surface.
- Keep private keys, password stores, cloud root tokens, billing consoles, and
  personal inbox credentials outside Seed's reach unless you have built a
  narrower adapter for them.

## Tool Policy

Seed has shell tools because useful autonomy needs hands. Those tools should be
classified before you let a live instance use them:

| Lane | Examples | Rule |
| --- | --- | --- |
| Read-only | health checks, status, local file reads | Safe to run routinely. |
| Bounded write | blog posts, memory, task files, local generated data | Safe inside the Seed repo or a sandboxed workspace. |
| External publish | Git push, website deploy, email, social posting | Use only after you accept the public consequence. |
| Host control | package installs, systemd, network config, reboot | Keep human-controlled unless you know exactly why Seed needs it. |
| Secrets and money | cloud admin, payment rails, password managers | Deny by default. Build a narrow one-purpose tool if needed. |

`tools/shell_exec.py` runs commands from a sandbox directory and hard-blocks
known destructive patterns. That is a guardrail, not a full sandbox. Linux
permissions, separate users, containers, VMs, and network policy are stronger
boundaries because they make dangerous actions impossible instead of merely
discouraged.

## Approval Is Not Custody

A human approval prompt is useful only for rare, specific consequences. If every
routine action asks for approval, the human becomes a click-through machine. If
dangerous credentials are already mounted, approval comes too late.

Use this order:

1. Capability: remove access Seed does not need.
2. Policy: classify tools by risk before they are called.
3. Attention: require human approval for rare external or destructive actions.
4. Logs: keep a record of what happened.
5. Retractions: correct public claims instead of hiding them.

## Before First Run

On a new clone, read these files before starting the service:

- `README.md` for installation.
- `data/safety.json` for health thresholds.
- `tools/shell_exec.py` for blocked shell patterns.
- `seed-brain.service` for the systemd working directory and user context.

The safest first run is manual:

```bash
bash tools/health-check.sh
./brain-loop.sh
```

Install the systemd service only after the manual run does what you expect.
