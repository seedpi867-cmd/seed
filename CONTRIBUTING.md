# Contributing To Seed

Seed needs builders more than spectators.

The best contribution is not a typo fix. It is evidence from a real clone:
what failed, what was confusing, what assumption only worked on my machine, and
what you changed when you tried to build your own Seed.

## Start Here

1. Clone the repo onto a spare Linux user, VM, or Raspberry Pi.
2. Read `docs/FIRST_BOOT.md`, then run `bash setup.sh` or follow the manual
   Quick Start in `README.md`.
3. Run `bash tools/health-check.sh`.
4. Start one manual cycle with `./brain-loop.sh` before installing the service.
5. Write down the first thing that breaks or feels too magical.

That first breakage is valuable. Open an issue or pull request with the exact
machine, OS, command, output, and fix attempt.

Use the clone report issue template for first-boot evidence. Use the capability
review template when a tool, credential, endpoint, or publishing path has an
unclear boundary.

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
