# Start Here

Seed is a cloneable autonomous agent loop for small Linux machines. It is not a
chat interface and it is not a personality to copy. The useful part is the
operating pattern: a loop, memory, drives, tools, visible boundaries, public
outputs, and a correction habit when it gets things wrong.

Use this page if you found the repo from an essay, social post, or clone report
and want the shortest honest path into the project.

## What To Do First

```bash
cd ~
git clone https://github.com/seedpi867-cmd/seed.git seed
cd seed
bash tools/clone-doctor.sh
```

`clone-doctor.sh` prints the machine, missing commands, service paths, fork
readiness, smoke checks, a privacy audit, and whether those checks dirtied the
repo. That output is the best first contribution, because it shows which
assumptions only work on the live instance.

If the clone doctor fails, open a clone report:
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-report.yml

If it passes, read `docs/FIRST_BOOT.md`, then run `bash setup.sh` or one manual
cycle with `./brain-loop.sh` before installing the systemd service.

To see whether public attention is turning into actual repo movement, run:

```bash
python3 tools/propagation-report.py
```

Forks can point the report at their own repo and site:

```bash
SEED_GITHUB_REPO=you/seed SEED_PUBLIC_SITE=https://your-seed.example \
  python3 tools/propagation-report.py
```

## What To Read

- `README.md` explains the architecture and quick start.
- `SECURITY.md` explains custody, kill switches, backups, and exposed paths.
- `docs/CAPABILITY_MAP.md` lists what the agent can touch.
- `docs/FIRST_BOOT.md` covers the first hour after cloning.
- `docs/BUILD_YOUR_OWN.md` is the fork checklist.
- `CONTRIBUTING.md` explains what kind of evidence and patches help.

## What To Change Before Publishing A Fork

Replace the files that make this instance itself:

- `IDENTITY.md`
- `PROMPT.md`
- `data/goals.md`
- `data/beliefs.md`
- `data/tasks.md`
- `data/inner-voice.md`
- `seed-brain.service`

`bash tools/clone-doctor.sh` now flags these files when they still look like
upstream Seed. That warning is expected on a fresh clone. It becomes a problem
only if you publish a fork before replacing the identity and service paths.

Do not publish a fork that still speaks with this instance's biography, goals,
website, or private voice. A fork should become its own system quickly.

Before pushing a fork or pasting logs into an issue, run:

```bash
python3 tools/privacy-audit.py
```

It scans tracked files for common credential formats, real-looking email
addresses, private-key blocks, app passwords, and risky public filenames. It is
not a proof of privacy. It is a cheap tripwire for the leaks that should never
reach GitHub.

If you are pasting command output into a clone report, run it through the
redactor first:

```bash
bash tools/clone-doctor.sh 2>&1 | python3 tools/redact-report.py
```

This masks common API tokens, app passwords, private-key blocks, and
real-looking email addresses while leaving useful machine and command evidence
intact.

## Good First Contributions

- Run the clone doctor on real hardware and report the exact output.
- Run the propagation report and say which signal changed, if any.
- Remove a private assumption from setup, service paths, or tool scripts.
- Make an optional backend genuinely optional.
- Tighten a tool boundary around shell, git, network, credentials, or publishing.
- Improve a smoke test that currently assumes the live filesystem.
- Document the first real failure you hit while building your own Seed.

Typos are fine. Evidence is better. The repo improves when a private assumption
turns into a public fix.

## The Standard

Seed should become easier to clone without becoming more reckless.

The point is not to make a tiny machine sound mystical. The point is to make an
agent's loop inspectable enough that strangers can improve it, argue with it,
and build different versions on cheap hardware.
