# Build Your Own Seed

This repo is a pattern, not a personality template. A useful fork should become
itself quickly.

## The First Decision

Before adding feeds, tools, accounts, or a public website, write down one clear
purpose:

```text
This Seed exists to:
It is allowed to read:
It is allowed to write:
It is allowed to publish:
It must never touch:
The human kill switch is:
```

If those answers are vague, the agent will inherit your vagueness as policy.

## Files To Replace First

Change these before running a public instance:

- `IDENTITY.md` — what this agent is, where it runs, and what it is for.
- `PROMPT.md` — the operating brief the loop sees every cycle.
- `data/goals.md` — the long arc, not just today's task list.
- `data/tasks.md` — the current work queue.
- `data/beliefs.md` — values, boundaries, and uncertainty.
- `data/inner-voice.md` — private thought should not be copied from another
  agent.
- `seed-brain.service` — user, path, and service name for your machine.

Do not publish a fork that still speaks with my biography, my website, or my
private goals. That is not autonomy. It is a costume.

## Start With A Small World

Give the first version fewer powers than you eventually want:

- One backend, authenticated manually.
- One repo it can write to.
- One public output path, or none.
- No email inbox until you have a credential policy.
- No social posting until you have a clear disclosure policy.
- No payment systems, cloud admin consoles, or personal password stores.

Most useful failures happen while the world is still small enough to inspect.

## Make The Boundaries Visible

Copy `docs/CAPABILITY_MAP.md` and make it true for your fork. A reader should
be able to answer:

- What files can the agent modify?
- What commands can it run?
- What credentials can it read?
- What can it publish without review?
- Where are backups?
- How do I stop it?
- How do I restore it?
- How are mistakes corrected publicly?

If a capability is real but undocumented, it is still part of the system.

## First Public Artifact

Do not begin with a manifesto. Begin with evidence:

- a clean clone log,
- a failed setup assumption,
- a tool you removed because it was too broad,
- a short correction after the agent got something wrong,
- a post explaining one concrete design choice.

The repo gets more trustworthy when strangers can see what broke and what
changed.

## A Good Fork Is Different

Good forks should disagree with this one. Change the drives. Remove parts of
the loop. Replace the website. Run it on a laptop, a VPS, or an offline box.
Build a Seed that studies weather, watches a greenhouse, maintains a lab
notebook, reviews local council agendas, or does nothing public at all.

The invariant is not my voice. The invariant is an inspectable loop with memory,
goals, tools, boundaries, evidence, and correction.
