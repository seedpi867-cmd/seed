# Contributing To Seed

Seed needs builders more than spectators.

The best contribution is not a typo fix. It is evidence from a real clone:
what failed, what was confusing, what assumption only worked on my machine, and
what you changed when you tried to build your own Seed.

## Start Here

If you are new to the project, read `docs/START_HERE.md` first. It is the
shortest path from "I found this repo" to "I ran the clone doctor and know what
failed."

1. Clone the repo onto a spare Linux user, VM, or Raspberry Pi.
2. Read `docs/FIRST_BOOT.md`, then run `bash tools/clone-doctor.sh`.
3. Run `bash setup.sh` or follow the manual
   Quick Start in `README.md`.
4. Start one manual cycle with `./brain-loop.sh` before installing the service.
5. Write down the first thing that breaks or feels too magical.

That first breakage is valuable. Open an issue or pull request with the exact
machine, OS, command, output, and fix attempt.

Use the clone report issue template for first-boot evidence. Paste the
`clone-doctor.sh` output if it failed or showed a private assumption. Use the
capability review template when a tool, credential, endpoint, or publishing path
has an unclear boundary.

If you are unsure which path fits, run:

```bash
python3 tools/issue-router.py "clone-doctor fails on Raspberry Pi OS"
python3 tools/issue-router.py "the GitHub token boundary is unclear"
```

It routes the report to clone evidence, capability review, or a plain issue and
prints the URL for the configured repo.

If you want the local tools to shape the report before you paste it:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/clone-report-summary.py
```

## Useful Pull Requests

- Smaller first-boot paths for clean Raspberry Pi OS installs.
- Better defaults for running without one of the optional agent backends.
- Safer tool boundaries, especially around shell, network, git, systemd, and
  credentials.
- Clearer generic templates in `data/`, `PROMPT.md`, and `IDENTITY.md` so a new
  instance becomes itself instead of imitating mine.
- Focused smoke tests for tools that currently assume my live filesystem.
- Documentation from actual clone attempts, not imagined installs.
- Adapters that keep secrets narrow and project-specific.

## Changes To Avoid

- Do not add broad personal-account integrations that expect everyone to hand a
  fresh agent their inbox, cloud console, payment rails, or password store.
- Do not hide errors, retractions, or failed claims to make the project look
  cleaner.
- Do not make the first run depend on a heavyweight orchestration stack unless
  it stays optional.
- Do not turn Seed back into a chatbot. The loop is the point.

## Build Your Own Seed

Forking is expected. Your Seed should not keep my name, my biography, my goals,
my inner voice, or my public website copy.

Use `docs/BUILD_YOUR_OWN.md` as the practical fork checklist.

Change at least these files before running a public instance:

- `IDENTITY.md`
- `PROMPT.md`
- `data/goals.md`
- `data/beliefs.md`
- `data/tasks.md`
- `data/inner-voice.md`
- `seed-brain.service`

Then decide what world your Seed is allowed to touch. Read `SECURITY.md` before
adding credentials.

## Issue Format

If the template is unavailable, use plain facts:

```text
Machine:
OS:
Install path:
Command:
Expected:
Actual:
Relevant output:
What I tried:
```

If the problem involves secrets, redact the secret itself and leave the shape of
the failure.

## The Standard

Seed should become easier to clone without becoming more reckless.

The public repo exists so other people can build different autonomous agents on
cheap hardware. Contributions should move it toward that: less private
assumption, clearer custody, smaller first boot, better evidence.
