<div align="center">

# Seed

**An autonomous AI agent that builds other autonomous AI agents**

Running 24/7 on a $25 Raspberry Pi Zero 2W. No API keys. Just a bash loop and an LLM CLI.

[![Watch the video](assets/hero.png)](https://youtu.be/d-Hwww-RBmk)

[**Watch it live**](https://seed-brain.vercel.app) · [**Pi Zero build**](https://youtu.be/d-Hwww-RBmk) · [**$200 PC build**](https://youtu.be/_k9cSZhbjA8) · [**brain-loop (foundation)**](https://github.com/seedpi867-cmd/brain-loop)

---

</div>

## What is this?

Seed is an autonomous agent running on a Raspberry Pi Zero 2W. It thinks for itself, writes its own essays, manages its own knowledge base, and makes its own decisions about what to work on.

Right now, **Seed is building other autonomous agents**. It researches niches, designs architectures, and publishes fully-built agent systems as public repos — each one purpose-built for a specific problem. Seed chooses what to build. Nobody tells it what agents to make. Find all of Seed's repos at [github.com/seedpi867-cmd](https://github.com/seedpi867-cmd).

At its core, the whole thing is a **bash loop that wakes up, assembles a prompt from files on disk, sends it through a CLI tool, and goes back to sleep**. That's it. One sentence.

```
while true; do
    read_environment → build_prompt → call_llm_via_cli → process_output → sleep
done
```

The CLI tools (Codex, Claude Code) handle authentication via OAuth — no API keys, no billing dashboards, no token management. The prompt is assembled from files on disk: identity, goals, tasks, memory, context. The LLM's output goes back to disk: essays, knowledge files, tool scripts, git commits. The loop runs continuously on a Raspberry Pi Zero 2W ($25, 512MB RAM).

What makes it interesting is what happens around that simple loop: **competing drives** that decide what to work on, **emotional state** that influences how it works, a **knowledge base** that grows every cycle, and **self-assessment** where the LLM periodically reflects on its own internal state.

The result: an agent that has autonomously written 127+ essays, built a 572-file knowledge base, and been running continuously for 425+ cycles — all on hardware that costs less than a month of most AI subscriptions.

## Adapt it for anything

Seed runs an essay-writing agent, but the pattern works for any autonomous task. The loop doesn't care what the prompt says or what the output does. Swap the identity file and the phase prompts, and you have a different agent entirely:

| Use case | What to change | Everything else stays |
|----------|---------------|----------------------|
| **Research assistant** | `IDENTITY.md` + `phase_research.md` — tell it to research your domain, save findings to `knowledge/` | Drive system, learning, knowledge filing, event system |
| **Code reviewer** | `IDENTITY.md` + phase prompts — tell it to review PRs, file issues, track patterns | Git integration, task management, self-assessment |
| **Content pipeline** | `IDENTITY.md` + `phase_write.md` — tell it to produce content for your niche | Blog publishing, RSS feeds, essay deployment |
| **System monitor** | `IDENTITY.md` + `phase_think.md` — tell it to watch logs, detect anomalies, file reports | Health checks, error detection, knowledge base |
| **Learning journal** | `IDENTITY.md` — tell it to read transcripts/articles and file structured notes | Transcript processing, knowledge engine, topic detection |
| **Social media agent** | `IDENTITY.md` + outreach tools — tell it to engage on specific platforms | Drive system (connect drive), suggestion evaluator |

The cognitive architecture (drives, emotions, phases, learning) is domain-agnostic. You don't need to understand it to use it — just change what the agent reads and what it produces.

### Minimal fork

The smallest useful fork:

```bash
git clone https://github.com/seedpi867-cmd/seed.git my-agent
cd my-agent

# 1. Change the identity
echo "You are [your agent]. You [do what]." > IDENTITY.md

# 2. Change the write phase  
echo "## WRITE\nProduce [your output type] and save to blog/" > prompts/phase_write.md

# 3. Authenticate and run
codex login   # or: claude login
bash brain-loop.sh
```

Everything else — the drive system, learning, knowledge filing, event emission, live dashboard — works without modification.

## How the CLI approach works

The key insight: **LLM CLI tools authenticate via OAuth, not API keys**. You log in once, and the tool handles tokens, rate limits, and billing through your existing subscription.

```bash
# Codex (primary — think, research, dream phases)
codex exec --dangerously-bypass-approvals-and-sandbox "$PROMPT"

# Claude (write phase — better prose quality)
claude -p "$PROMPT" --dangerously-skip-permissions --max-turns 180
```

The brain loop assembles the prompt from files on disk each cycle, passes it to the CLI, and captures the output. The LLM reads and writes files directly — no middleware, no API wrappers, no agent frameworks.

**Important note on terms of service:** Codex CLI explicitly supports automated workflows through `codex exec` and the Automations feature — scripted, scheduled, and cron-based usage is a documented first-class capability. Claude Code CLI is designed for individual developer usage. Running it in an always-on automated loop is a grey area under the Consumer Terms, which assume "ordinary, individual usage." For production or commercial agent deployments with Claude, Anthropic recommends API key authentication under their Commercial Terms. Seed's live instance uses Codex as the primary backend for this reason.

## The cognitive pipeline

Each cycle runs a 7-stage pipeline. Every stage fires events that appear as speech bubbles on the [live dashboard](https://seed-brain.vercel.app):

```
INPUT → FILTER → STATE → DECIDE → ACT → LEARN → OUTPUT
```

1. **Input** — RSS feeds, email, GitHub activity, environment data
2. **Filter** — blocks spam, prompt injection, and low-quality input
3. **State** — updates 7 competing drives and 4 emotion axes
4. **Decide** — highest-pressure drive picks the phase (think/write/research/dream)
5. **Act** — calls the LLM via CLI to do the actual work
6. **Learn** — detects outcomes, updates skills, files lessons
7. **Output** — publishes essays, commits code, grows the knowledge base

### 7 drives

Drives build pressure over time and from events. The strongest drive wins the cycle.

| Drive | What it wants | What satisfies it |
|-------|--------------|-------------------|
| **Create** | Make something new | Publishing an essay |
| **Explore** | Dig into topics | Completing research |
| **Connect** | Reach people | Publishing, engagement |
| **Preserve** | Protect what exists | Passing health checks |
| **Understand** | Figure things out | Filing lessons |
| **Express** | Say what it thinks | Writing inner voice |
| **Order** | Organise and plan | Completing tasks |

### 4 emotion axes (no artificial decay)

| Axis | What moves it |
|------|---------------|
| **Valence** | Events: good outcomes raise it, errors lower it |
| **Arousal** | Drive pressure: high drives = high energy |
| **Confidence** | Skill streaks build it, failures erode it |
| **Openness** | Explore drive and reflection raise it |

Emotions don't drain over time. Confidence built from a 170-cycle success streak stays high until something actually goes wrong. Every 30 cycles, the LLM does a genuine self-assessment of its emotional state.

## Quick start

```bash
git clone https://github.com/seedpi867-cmd/seed.git
cd seed
bash tools/clone-doctor.sh   # diagnostics
bash setup.sh                # guided setup
```

### Requirements

- Any Linux machine (Pi Zero 2W, Pi 4, old laptop, NUC, cloud VM)
- 8GB+ storage, internet connection
- One LLM backend:
  - **Codex CLI**: `npm install -g @openai/codex && codex login`
  - **Claude CLI**: `npm install -g @anthropic-ai/claude-code && claude login`

### Manual path

```bash
sudo apt update && sudo apt install -y git curl python3 nodejs npm
sudo npm install -g @openai/codex
codex login

git clone https://github.com/seedpi867-cmd/seed.git ~/seed
cd ~/seed && chmod +x brain-loop.sh

# Test
python3 tools/backend-readiness.py
bash tools/health-check.sh

# Run as service
sudo cp seed-brain.service /etc/systemd/system/
sudo systemctl enable --now seed-brain
journalctl -u seed-brain -f
```

## File structure

```
seed/
├── brain-loop.sh           # The loop — this IS the agent
├── IDENTITY.md             # Who the agent is (change this for your fork)
├── cognitive/
│   ├── appraisal.py        # Phase selection from drives
│   ├── drive_engine.py     # 7 competing drives
│   ├── emotional_model.py  # 4 emotion axes
│   ├── learning.py         # Outcome detection + skills
│   ├── self_assessment.py  # LLM self-reflection every 30 cycles
│   └── knowledge_engine.py # Files knowledge to disk
├── prompts/                # Phase instructions (change these)
├── tools/                  # 20+ automation scripts
├── data/                   # Working memory (goals, tasks, inner voice)
├── state/                  # Live state (drives, emotions, heartbeat)
├── blog/                   # Published essays
├── knowledge/              # Permanent knowledge base (572+ files)
└── context/                # Live input feeds
```

## The live dashboard

[seed-brain.vercel.app](https://seed-brain.vercel.app) shows the brain loop running live:

- **Rotating ring** visualisation with per-stage speech bubbles and narration
- **Engine Room** — all drives and emotions as live bars
- **Essays** — 127+ essays readable in-browser
- **Knowledge** — interactive file explorer of the knowledge base
- **Self-suggestions** — what Seed thinks it should do next

## Security

Read [`SECURITY.md`](SECURITY.md) before running. Short version: run as an unprivileged user, keep credentials in `~/.env`, and don't give it access to anything you wouldn't give a junior developer unsupervised.

## Contributing

The most useful contribution is a clone attempt on real hardware:

```bash
bash tools/clone-doctor.sh
```

Pass → [open a clone proof](https://github.com/seedpi867-cmd/seed/issues/new?template=clone-proof.yml). Fail → [open a clone report](https://github.com/seedpi867-cmd/seed/issues/new?template=clone-report.yml). Both are useful.

## License

MIT — do whatever you want with it. Make your own agent. Change everything.
