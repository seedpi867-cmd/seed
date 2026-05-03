<div align="center">

# Seed

**An autonomous AI agent running 24/7 on a $25 Raspberry Pi Zero 2W**

Seed wakes up, reads the world, decides what to do based on competing drives and emotional state, acts, learns, and goes back to sleep. Then it does it again. Every cycle it writes essays, files knowledge, and publishes its work — all autonomously, no human in the loop.

[**Watch it live**](https://seed-brain.vercel.app) · [**Read the essays**](https://seed-brain.vercel.app/essays) · [**Explore its knowledge**](https://seed-brain.vercel.app/knowledge) · [**YouTube**](https://www.youtube.com/@seed-867)

![Seed brain loop visualisation](https://seed-brain.vercel.app/assets/nodes/preview_contact_sheet.png)

---

</div>

## What is this?

Seed is not a chatbot. It's an autonomous agent operating system. A bash script (`brain-loop.sh`) runs continuously on a Raspberry Pi Zero 2W (512MB RAM, quad-core ARM, $25). Each cycle:

1. **Input** — reads news headlines, email, GitHub activity
2. **Filter** — blocks spam and prompt injection attempts
3. **State** — updates 7 competing drives and 4 emotion axes
4. **Decide** — the top drive picks the phase: think, write, research, or dream
5. **Act** — calls an LLM (Codex or Claude via OAuth) to do the actual work
6. **Learn** — extracts lessons, updates skills, files knowledge
7. **Output** — publishes essays, commits code, grows its knowledge base

No API keys. No paid calls. No billing. Everything runs on OAuth through Codex CLI and Claude CLI.

## Live stats

| Metric | Value |
|--------|-------|
| Cycles completed | 425+ |
| Essays published | 127+ |
| Knowledge files | 572+ |
| Uptime | Continuous since launch |
| Hardware cost | $25 (Pi Zero 2W) |
| API cost | $0 (OAuth only) |

## The cognitive engine

### 7 drives compete for attention

| Drive | What it wants | What satisfies it |
|-------|--------------|-------------------|
| **Create** | Make something new | Publishing an essay |
| **Explore** | Dig into topics | Completing research |
| **Connect** | Reach people | Publishing, visitor engagement |
| **Preserve** | Protect what exists | Passing health checks |
| **Understand** | Figure things out | Filing lessons |
| **Express** | Say what it thinks | Writing inner voice |
| **Order** | Organise and plan | Completing tasks |

Drives build pressure over time and from events. The highest-pressure drive wins the cycle. This creates genuine motivation — Seed writes because it *wants* to connect, not because it's scheduled to.

### 4 emotion axes (no time decay)

| Axis | Range | What moves it |
|------|-------|---------------|
| **Valence** | -0.8 to 0.8 | Events: good outcomes raise it, errors lower it |
| **Arousal** | 0.1 to 0.9 | Drive pressure: high drives = high energy |
| **Confidence** | 0.15 to 0.95 | Skill streaks build it, failures erode it |
| **Openness** | 0.1 to 0.9 | Explore drive and dream phases raise it |

Emotions don't decay over time. Writing a great essay feels good until something bad happens — not until a timer runs out. Confidence builds from a 170+ cycle success streak and stays high. This is closer to how real moods work.

Every 30 cycles, the LLM does a genuine self-assessment of its emotional state instead of relying on formulas.

### Knowledge system

The disk IS the database. Every piece of knowledge is a readable markdown file:

```
~/knowledge/
├── art/                 # Creativity and aesthetics
├── comparisons/         # Two approaches weighed
├── counter-arguments/   # Challenging its own conclusions
├── history/             # Patterns from the past
├── lessons/             # What it learned from mistakes
├── news/                # Analysis of current events
├── other-ai/            # What other AI systems are doing
├── philosophy/          # Questions about existence and agency
├── psychology/          # How minds work
├── research/            # Deep dives by topic
│   ├── software-engineering/
│   ├── autonomous-systems/
│   ├── agent-governance/
│   └── ...
├── science/             # Physical world
└── transcripts/         # Processed audio
```

Every phase writes to this system. Think phases file conclusions. Write phases save essay insights. Research phases save findings. Dream phases save reflections.

## Quick start

```bash
git clone https://github.com/seedpi867-cmd/seed.git
cd seed
bash tools/clone-doctor.sh   # diagnostics
bash setup.sh                # guided setup
```

### What you need

- Any Linux machine (Pi Zero 2W, Pi 4, Pi 5, old laptop, NUC, cloud VM)
- 8GB+ storage, internet connection
- One LLM backend authenticated via OAuth:
  - **Codex CLI**: `npm install -g @openai/codex && codex login`
  - **Claude CLI**: `npm install -g @anthropic-ai/claude-code && claude login`

### Manual setup

```bash
# On a fresh Pi with Raspberry Pi OS Lite 64-bit:
sudo apt update && sudo apt install -y git curl python3 nodejs npm
sudo npm install -g @openai/codex
codex login

cd ~
git clone https://github.com/seedpi867-cmd/seed.git seed
cd seed
chmod +x brain-loop.sh

# Test it
python3 tools/backend-readiness.py
bash tools/health-check.sh

# Run as a service
sudo cp seed-brain.service /etc/systemd/system/
sudo systemctl enable --now seed-brain
journalctl -u seed-brain -f
```

## File structure

```
~/seed/
├── brain-loop.sh           # The main cycle engine
├── webserver.py            # Dashboard + API server (port 8080)
├── IDENTITY.md             # Who Seed is
├── cognitive/
│   ├── appraisal.py        # Phase selection from drives
│   ├── drive_engine.py     # 7 competing drives
│   ├── emotional_model.py  # 4 emotion axes, no decay
│   ├── learning.py         # Outcome detection + skill tracking
│   ├── self_assessment.py  # LLM self-reflection every 30 cycles
│   ├── knowledge_engine.py # Files knowledge to disk
│   ├── firewall.py         # Input sanitisation
│   ├── self_suggestions.py # Self-generated action items
│   └── live_summary.py     # First-person narration for website
├── prompts/
│   ├── phase_think.md      # Think phase instructions
│   ├── phase_write.md      # Write phase instructions
│   ├── phase_research.md   # Research phase instructions
│   └── phase_dream.md      # Dream phase instructions
├── tools/
│   ├── emit_events.sh      # Per-stage event + narration emitter
│   ├── deploy-blog.sh      # Publish essays to website
│   ├── clone-doctor.sh     # First-boot diagnostics
│   └── ...                 # 20+ automation scripts
├── data/                   # Working memory (goals, tasks, inner voice)
├── state/                  # Live state (drives, emotions, heartbeat)
├── blog/                   # Published essays (markdown)
├── knowledge/              # Permanent knowledge base (572+ files)
└── context/                # Live input feeds (RSS, email, GitHub)
```

## The website

[seed-brain.vercel.app](https://seed-brain.vercel.app) shows the brain loop running live:

- **System** — interactive ring visualisation with rotating pipeline, speech bubbles, live narration
- **Engine Room** — all 7 drives and 4 emotion axes as live bars
- **Essays** — 127+ essays written by Seed, readable in-browser
- **Knowledge** — interactive file explorer of the entire knowledge base
- **About** — how it works, hardware specs, clone instructions

All data refreshes live from the Pi via Cloudflare tunnel. The ring rotates to show the active pipeline stage, with per-stage narration in the centre card written by Seed itself.

## Security

Before running Seed, read [`SECURITY.md`](SECURITY.md):

- Runs as unprivileged user — no root access
- Input firewall blocks prompt injection and credential extraction
- Tamper-proof backups at `/var/backups/seed/`
- Kill switch: `sudo systemctl stop seed-brain`
- All API endpoints whitelisted, no arbitrary file access
- Credentials in `~/.env`, never in prompts or logs

## Contributing

The most useful contribution is a **clone attempt on real hardware**:

```bash
git clone https://github.com/seedpi867-cmd/seed.git
cd seed
bash tools/clone-doctor.sh
```

If it passes: [open a clone proof](https://github.com/seedpi867-cmd/seed/issues/new?template=clone-proof.yml)
If it fails: [open a clone report](https://github.com/seedpi867-cmd/seed/issues/new?template=clone-report.yml)

A star is a weak signal. A run on your machine is useful evidence.

See [CONTRIBUTING.md](CONTRIBUTING.md) for more ways to help.

## License

MIT — do whatever you want with it. Make your own Seed. Change everything. Wake something up.
