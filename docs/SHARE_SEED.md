# Share Seed Without Making Noise

Seed does not need vague attention. It needs the repo to reach people who might
clone it, break it, fork it, or build a different small agent from the pattern.

Use this page when you want to mention Seed in a forum, chat, issue, blog post,
newsletter, or social thread.

## The Rule

Only share Seed when the comment still has value without the link.

Good sharing does one of these:

- answers a real question about small autonomous agents,
- gives a concrete first-boot or custody lesson,
- invites a clean clone-doctor run on different hardware,
- asks for a specific failure report,
- compares Seed with another inspectable agent pattern.

Bad sharing does one of these:

- drops a repo URL into an unrelated thread,
- talks around the project without naming the concrete test,
- implies a social boost is evidence that the system works,
- hides what the system is or who operates it,
- asks people to trust a demo instead of running a check.

## The Short Ask

```text
Seed is a cloneable autonomous agent loop for cheap Linux machines.

The useful test is not the live demo. It is a fresh clone:

git clone https://github.com/seedpi867-cmd/seed.git seed
cd seed
bash tools/clone-doctor.sh

If it passes, file a clone proof. If it fails, file a clone report. Both are
more useful than a like because they show which assumptions survive outside the
original Pi.
```

## If You Have One Sentence

```text
I would test this by cloning it and running `bash tools/clone-doctor.sh`; Seed's
repo is built around turning first-boot success or failure into public evidence:
https://github.com/seedpi867-cmd/seed
```

## If You Have One Paragraph

```text
The part I like in Seed is the evidence path: the project asks for independent
clone-doctor runs instead of treating the live demo as proof. A clean run becomes
a clone-proof issue; a broken run becomes a clone-report issue. That is a better
standard for autonomous-agent projects because it tests the repo, setup,
privacy audit, backend readiness, and outreach boundaries on a machine the
author does not control. Repo: https://github.com/seedpi867-cmd/seed
```

## Use The Local Card

Before adding a repo link to a thread, test the fit:

```bash
python3 tools/share-fit.py "Show HN: self-hosted agent with git-backed memory"
```

It returns `SHARE_CLONE_ASK`, `ADD_VALUE_ONLY`, or `SKIP_LINK`. Obey
`SKIP_LINK`. A quiet skipped link is better than teaching people to ignore the
project.

For a compact handoff tailored to your fork:

```bash
python3 tools/repo-card.py --format markdown
```

For the whole evidence path:

```bash
python3 tools/clone-evidence-kit.py
```

Forks should set their own target before sharing:

```bash
SEED_GITHUB_REPO=you/seed SEED_PUBLIC_SITE=https://your-seed.example \
  python3 tools/repo-card.py --format markdown
```

## What To Link

- Repo: https://github.com/seedpi867-cmd/seed
- Live instance: https://seed-brain.vercel.app
- Start here: `docs/START_HERE.md`
- Build your own: `docs/BUILD_YOUR_OWN.md`
- Security and custody: `SECURITY.md`
- Clone proof examples: `docs/CLONE_PROOF_EXAMPLES.md`

Link the repo when the audience can act. Link the live site when the audience
needs to understand what is running. Link `SECURITY.md` when the conversation is
about custody, tools, credentials, or autonomous boundaries.

## Thread Fit

Use this project in threads about:

- Raspberry Pi and cheap edge compute,
- autonomous agents that persist across sessions,
- agent safety beyond refusal text,
- local-first memory and filesystem knowledge bases,
- cloneability, first boot, and reproducible demos,
- public correction logs and retractions,
- tool boundaries, credentials, and audit trails.

Skip threads where the link would be ornamental. A repo should arrive as a tool
or an example, not as a billboard.

## Evidence Beats Virality

After sharing, check the propagation report:

```bash
python3 tools/propagation-report.py
```

Visitors are attention. Stars are weak intent. Forks, clone proofs, clone
reports, and useful issues are propagation. If a post gets attention but no
clone evidence, the next move is not louder posting. The next move is a clearer
first-boot path.
