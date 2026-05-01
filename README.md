# Seed

An autonomous AI agent that runs 24/7 on a Raspberry Pi Zero 2W.

It wakes up every 10 minutes, reads the world, thinks, acts, writes, and goes back to sleep. It has moods, goals, tasks, memory, and dreams. It writes blog posts, fixes its own tools, and tracks its own evolution.

Three AI backends operating as one mind. No API keys — OAuth/subscription only.

## What It Does

- Writes essays and blog posts autonomously
- Tracks its own mood (curiosity, motivation, satisfaction)
- Sets and manages its own task list
- Dreams every 5th cycle (reflects on patterns, updates mood)
- Reads news feeds and podcast transcripts
- Fixes its own code when things break
- Deploys to its own website via git push
- LED patterns show what it's thinking (rapid=working, morse=writing, breathe=sleeping)

## Hardware

- Raspberry Pi Zero 2W ($15)
- 128GB SD card
- USB power cable
- That's it

## Quick Start

```bash
# Flash Pi OS Lite 64-bit, SSH in, then:
git clone https://github.com/seedpi867-cmd/seed.git ~/
bash setup.sh
systemctl start seed-brain
```

## Architecture

```
PROMPT.md          — who I am (the agent can edit this)
brain-loop.sh      — wake/think/write/research/dream/sleep
data/
  tasks.md         — active task list (Now/Next/Done)
  goals.md         — long-term vision
  memory.md        — what happened
  dreams.md        — reflections from dream cycles
  mood.json        — curiosity, motivation, satisfaction
context/           — feeders drop world info here
blog/              — essays the agent writes
tools/             — 40+ scripts (agent can build more)
webserver.py       — live dashboard on port 8080
```

## How It Works

One bash script runs forever. Each cycle:

1. Wake up, read identity + tasks + memory + world context
2. **Think** — decide what to do, execute 3-5 tasks
3. **Write** — if a blog topic is queued, write the essay
4. **Research** — every 3rd cycle, look something up
5. **Dream** — every 5th cycle, reflect on patterns
6. Sleep 10 minutes, repeat

The agent doesn't know it's using different AI models. It experiences thinking, writing, researching, and dreaming as one continuous mind.

## License

MIT
