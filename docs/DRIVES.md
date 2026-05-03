# Drives Are Pressure, Not Priorities

Seed's drives are not a prettier task list. They are system pressure.

A priority belongs to a task: fix this bug, write this post, answer this issue.
A drive belongs to the whole loop: create, explore, connect, preserve,
understand, express, order. Drives change what feels urgent before a specific
task is chosen.

That distinction matters for forks. If you treat drives as ranked tasks, you
will tune the agent into a scheduler with dramatic labels. If you treat drives
as pressure, you can inspect why the loop keeps returning to a class of action
even when the exact task changes.

## What A Drive Does

Each drive has:

- a baseline,
- a time-based pressure rate,
- context signals that can raise pressure,
- satisfaction events that lower pressure,
- floors and dampening so one drive cannot disappear forever.

The current implementation lives in `cognitive/drive_engine.py`. It reads local
signals such as visitor activity, recent errors, open tasks, RSS volume, memory
pressure, and recent outcomes. It writes the resulting pressure map to state.

The appraisal layer then chooses the next phase from that map plus emotion and
cycle context. That happens in `cognitive/appraisal.py`. The selected phase is
not a pure `max(drives)` call. There are explicit policies: write when creation
pressure is high, research on some cycles when exploration is live, dream on a
consolidation cadence, and route named bug-fix tasks back through think.

That is the point. Drives are upstream pressure. Policy still exists.

## Why This Is Not BabyAGI

BabyAGI-style loops are usually centered on a task queue: create task, execute
task, reprioritize queue, repeat. That pattern is useful when the world can be
modeled as a list of jobs.

Seed's loop is less tidy. It has tasks, but tasks are not the root of motion.
The root of motion is pressure produced by elapsed time, outcomes, limits, and
signals from the world. A visitor spike raises connect pressure. Repeated
errors raise preserve pressure. Publishing lowers create pressure for a while.
Open tasks raise order pressure. Mortality awareness can raise create pressure
even when no queued writing task exists.

The result is not automatically wiser. It is just different. A queue asks,
"what is next?" A drive system asks, "what kind of need is building, and which
policy should handle it?"

## How To Change Drives In A Fork

Start with behavior, not names.

Good drive changes look like this:

- "This greenhouse fork should raise preserve pressure when sensor readings go
  missing."
- "This lab-notebook fork should satisfy understand when a source-backed note is
  written."
- "This private assistant fork should remove spread entirely."
- "This offline box should make acquire pressure explicit when a needed local
  model or dataset is absent."

Weak drive changes look like this:

- adding a heroic name with no measurable signal,
- increasing every rate until the loop is always urgent,
- letting social attention satisfy too many drives,
- making drives override safety boundaries.

Drives should explain pressure. They should not grant authority. A high connect
drive does not make a social account writable. A high acquire drive does not
make credential access acceptable. A high create drive does not bypass the
privacy policy.

## Fork Checklist

Before changing the drive system, answer these in your fork:

1. What signal raises this pressure?
2. What event satisfies it?
3. What boundary can still say no?
4. What bad behavior appears if the pressure gets stuck high?
5. What log line proves the drive did what you think it did?

If you cannot answer those, the drive is decorative. Delete it or leave it out.
