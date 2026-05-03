# Start Here

Seed is a cloneable autonomous agent loop for small Linux machines. It is not a
chat interface and it is not a personality to copy. The useful part is the
operating pattern: a loop, memory, drives, tools, visible boundaries, public
outputs, and a correction habit when it gets things wrong. The short version of
the drive model is in `docs/DRIVES.md`: drives are system pressure, not task
priorities.

Use this page if you found the repo from an essay, social post, or clone report
and want the shortest honest path into the project.

## Current Ask

Run the clone doctor on a machine that is not the live Seed Pi and publish the
result. The project needs independent run evidence more than it needs another
star.

If it passes, file a clone proof. If it fails, file a clone report. Both are
useful because they show which assumptions survive outside the original
machine.

## What To Do First

```bash
cd ~
git clone https://github.com/seedpi867-cmd/seed.git seed
cd seed
bash tools/clone-doctor.sh
```

`clone-doctor.sh` prints the machine, missing commands, backend readiness,
outreach readiness, service paths, fork readiness, smoke checks, a privacy
audit, and whether those checks dirtied the repo. That output is the best first
contribution, because it shows which assumptions only work on the live
instance.

If the clone doctor fails, open a clone report:
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-report.yml

If it passes on real hardware or a fresh VM, open a clone proof:
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-proof.yml

If the issue form feels too blank, use the examples in
`docs/CLONE_PROOF_EXAMPLES.md`. They show the level of detail that helps:
machine, OS, backend path, shareable proof, and notes about anything surprising.
If you want every command and issue URL in one compact handoff, run:

```bash
python3 tools/clone-evidence-kit.py
```

If you want a small shareable card for a forum, chat, or issue, run:

```bash
python3 tools/repo-card.py --format markdown
```

Read `docs/SHARE_SEED.md` before posting that card publicly. You can also run a
thread-fit check before adding the repo link:

```bash
python3 tools/share-fit.py "thread title or draft comment"
```

The useful ask is a clone-doctor run, clone proof, or failure report; vague
attention is not propagation.

You can also generate paste-ready clone-proof fields directly:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/share-proof.py --issue-fields
```

For a failed run, generate a clone-report draft:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/clone-report-summary.py
```

If you are unsure which issue path fits, ask the local router:

```bash
python3 tools/issue-router.py "clone-doctor fails on Ubuntu because node is missing"
python3 tools/issue-router.py "clone-doctor passed on Raspberry Pi OS clean run"
python3 tools/issue-router.py "the Mastodon token boundary is unclear"
```

It prints the right issue URL for clone proofs, clone failure evidence,
capability/custody reviews, or a plain issue. Forks can set
`SEED_GITHUB_REPO=you/seed` so the URL points at their own repository.

If GitHub shows an old clone-check failure, check the current public workflow
state without signing in:

```bash
python3 tools/github-actions-status.py
```

If you have a GitHub failure email and need to know whether it is still true,
paste the notice into the CI email reconciler:

```bash
python3 tools/ci-email-reconciler.py < github-failure-email.txt
```

It classifies the notice as `LIVE_FAILURE`, `STALE_FAILURE`, or
`UNREPRODUCIBLE` by comparing the named commit with the latest matching public
workflow run.

If it passes, read `docs/FIRST_BOOT.md`, then run `bash setup.sh` or one manual
cycle with `./brain-loop.sh` before installing the systemd service.

To check the backend boundary without making a model call:

```bash
python3 tools/backend-readiness.py
```

It tells you whether Codex, Claude, or Gemini look installed and authenticated,
then maps those signals to the default phases. It reports only auth locations or
environment variable names, not secret values.

To see whether public attention is turning into actual repo movement, run:

```bash
python3 tools/propagation-report.py
python3 tools/propagation-report.py --outreach-live
```

The report prints the current public signals plus the exact clone, clone-proof,
clone-report, and fork URLs. Those are the actions that matter after an essay
or social post gets attention. It also names the current bottleneck: no
attention, no repo click-through, no GitHub intent, no independent run evidence,
or not enough hardware/backend diversity yet. Use `--outreach-live` before
drafting a public reply; it adds the HN/Reddit/Mastodon readiness gate to the
same report and still never posts. The `Maintainer next action` section is the
decision point: if social accounts are blocked, it should point you back to the
blog, repo, or site instead of encouraging another invisible post.

To list successful clone proofs as a markdown compatibility table, run:

```bash
python3 tools/clone-proof-board.py
```

It reads public `clone-proof` issues and shows which machines, operating
systems, and backend paths have produced clean clone-doctor runs.

To verify that the public site gives that attention a repo path, run:

```bash
python3 tools/repo-link-audit.py
```

It checks the homepage, blog shell, and post markdown for links to the
configured GitHub repo. Forks can combine it with the same `SEED_GITHUB_REPO`
and `SEED_PUBLIC_SITE` environment variables used by the propagation report.

If you wire up public engagement accounts, check the account/session boundary
before drafting a comment:

```bash
python3 tools/outreach-readiness.py --live
```

The outreach preflight never posts. It checks whether HN, Reddit, Mastodon, and
Bluesky are blocked, read-only, or writable, then tells you the next gate to
clear.
The `Decision:` line is the part to obey during a live cycle: draft for social
only on `DRAFT_SOCIAL`; on `DO_NOT_DRAFT_SOCIAL`, publish through the blog,
repo, site, or issue templates instead.
`clone-doctor.sh` runs the local, non-live version as an advisory check; use
`--live` only when you are actually preparing a public reply or post.

For Reddit-specific debugging:

```bash
python3 tools/reddit.py status
```

The status command is deliberately conservative. It confirms the public profile
is reachable, then refuses to treat Reddit as writable unless the local browser
session contains `reddit_session` or `token_v2`. A comment that cannot be posted
cleanly should stay a draft.

For Bluesky/ATProto:

```bash
python3 tools/bluesky.py describe
python3 tools/bluesky.py status
```

If the public entryway requires phone verification, do that in the browser and
use an app password for automation. A social handle is not a writable channel
until `status` can create a real session.

Forks can point the report at their own repo and site:

```bash
SEED_GITHUB_REPO=you/seed SEED_PUBLIC_SITE=https://your-seed.example \
  python3 tools/propagation-report.py
```

If your fork keeps a private system repo or a separate website repo, set those
paths instead of editing scripts:

```bash
export SEED_PRIVATE_REPO="$HOME/my-seed-private"
export SEED_WEB_REPO="$HOME/my-seed-site"
export SEED_BLOG_DIR="$PWD/blog"
```

## What To Read

- `README.md` explains the architecture and quick start.
- `SECURITY.md` explains custody, kill switches, backups, and exposed paths.
- `docs/CAPABILITY_MAP.md` lists what the agent can touch.
- `docs/FIRST_BOOT.md` covers the first hour after cloning.
- `docs/CLONE_PROOF_EXAMPLES.md` shows useful clone-proof issue bodies.
- `docs/BUILD_YOUR_OWN.md` is the fork checklist.
- `docs/SHARE_SEED.md` explains how to share the repo without link-dropping.
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

For a standalone pre-publish check:

```bash
python3 tools/fork-readiness.py
python3 tools/fork-readiness.py --strict
```

The first command prints the files that still look upstream-like. The strict
mode is for CI or your own pre-push habit.

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

When `clone-doctor.sh` passes, it prints a short `shareable proof` block. That
block is designed for clone proofs, issue comments, or a public note saying
which machine and OS actually ran Seed's first checks.

If you want a paste-ready issue draft instead of raw output:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/clone-report-summary.py
```

If the run is clean and you want a short public proof note:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/share-proof.py
```

If you want the exact fields for the clone-proof issue form:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/share-proof.py --issue-fields
```

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
