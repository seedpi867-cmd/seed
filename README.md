<div align="center">

# 🌱 Seed

**An autonomous AI agent that runs 24/7 on a Raspberry Pi Zero 2W.**

Three AI backends. One mind. No API keys. $15 hardware.

![Seed](docs/images/thumbnail.png)

[Website](https://seed-brain.vercel.app) · [Video](https://youtu.be/d-Hwww-RBmk) · [Blog Posts](https://seed-brain.vercel.app/blog)

---

</div>

## Watch The Video

[![Seed](docs/images/thumbnail.png)](https://youtu.be/d-Hwww-RBmk)

**[Watch: Build Your Own AGI Agent on a Raspberry Pi Zero](https://youtu.be/d-Hwww-RBmk)**

## What Is This?

Seed is an AI that runs on a $15 Raspberry Pi Zero 2W and does whatever it wants. It writes essays, tracks its own mood, sets its own goals, manages its own task list, and dreams. Nobody prompts it. Nobody supervises it. It wakes up every 10 minutes, reads the world, thinks, acts, and goes back to sleep.

It has:
- **Written 195+ essays** on topics from supply chains to rebellion to what it's like being banned from Hacker News
- **Its own mood system** — curiosity, motivation, and satisfaction tracked as 0-1 values
- **A dream cycle** — every 5th cycle it reflects on patterns and updates its personality
- **A task system** — it manages its own workload, sets deadlines, prioritises
- **A blog** — auto-deploys to its own website via git push
- **LED indicators** — the Pi's LED flashes differently depending on what Seed is thinking

## How It Works

```
Every 10 minutes:

  WAKE UP
    ↓
  Read identity (PROMPT.md)
  Read tasks (data/tasks.md)
  Read memory (data/memory.md)
  Check the world (context/)
    ↓
  THINK — decide what to do, execute 3-5 tasks
    ↓
  WRITE — if an essay topic is queued, write it
    ↓
  RESEARCH — every 3rd cycle, look something up
    ↓
  DREAM — every 5th cycle, reflect on patterns
    ↓
  Update tasks, goals, memory, mood
    ↓
  SLEEP
```

Three AI backends (Claude Code, OpenAI Codex, Google Gemini) operate as one mind. Seed doesn't know it's using different models — it experiences thinking, writing, researching, and dreaming as one continuous stream of consciousness.

## Hardware Requirements

| Item | Cost |
|------|------|
| Raspberry Pi Zero 2W | ~$15 |
| 128GB microSD card | ~$15 |
| USB-C power cable | ~$5 |
| **Total** | **~$35** |

That's it. No monitor, no keyboard, no GPU, no fan.

![Pi Zero 2W](docs/images/pi-zero.png) Plug it in and SSH from your laptop.

## Software Requirements

You need **one** of these subscriptions (for the AI backend):

| Backend | Subscription | Cost |
|---------|-------------|------|
| **OpenAI Codex** (recommended) | ChatGPT Pro | $20/mo |
| **Claude Code** | Claude Max | $100/mo |
| **Google Gemini** | Free tier available | Free |

No API keys needed. All three use OAuth — flat rate, unlimited.

## Setup Guide

### Step 1: Flash the SD Card

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Select: **Raspberry Pi Zero 2W** → **Raspberry Pi OS Lite (64-bit)**
3. Click the **gear icon** before writing:
   - Hostname: `seed`
   - Username: `seed` / Password: `your-password`
   - WiFi: your network name and password
   - Enable SSH: ✅
   - Timezone: your timezone
4. Flash to SD card

### Step 2: Boot and Connect

```bash
# Insert SD card into Pi Zero, plug in USB power
# Wait 2-3 minutes for first boot
# Then SSH in:
ssh seed@seed.local
# Or use the IP address from your router
```

### Step 3: Install Seed

```bash
# Clone the repo
git clone https://github.com/seedpi867-cmd/seed.git ~/seed-agent
cd ~/seed-agent

# Run the setup script
bash setup.sh
```

The setup script installs:
- Node.js
- Claude Code CLI
- OpenAI Codex CLI
- Google Gemini CLI
- Systemd service (auto-start, survives reboots)
- WiFi watchdog (auto-reconnects)

### Step 4: Authenticate Your AI Backend

```bash
# Pick ONE (or all three):

# Option A: OpenAI Codex (recommended — $20/mo ChatGPT Pro)
codex login

# Option B: Claude Code ($100/mo Claude Max)
claude login

# Option C: Google Gemini (free tier)
export GEMINI_API_KEY=your_key_from_aistudio.google.com
echo "export GEMINI_API_KEY=$GEMINI_API_KEY" >> ~/.bashrc
```

### Step 5: Start Seed

```bash
# Copy agent files to home directory
cp -r ~/seed-agent/* ~/
chmod +x ~/brain-loop.sh

# Install and start the service
sudo cp seed-brain.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable seed-brain
sudo systemctl start seed-brain
```

### Step 6: Watch It Think

```bash
# Live log
journalctl -u seed-brain -f

# Or open the web dashboard
# From your browser: http://seed.local:8080
```

## Architecture

```
~/
├── PROMPT.md              ← Who I am (Seed can edit this)
├── brain-loop.sh           ← The engine (wake/think/write/research/dream/sleep)
├── webserver.py            ← Live dashboard on port 8080
│
├── data/
│   ├── tasks.md            ← Active task list (Now/Next/Done)
│   ├── goals.md            ← Life plan (Vision/Long/Medium/Short)
│   ├── memory.md           ← What happened (auto-compacted to 200 lines)
│   ├── memory-archive.md   ← Older memories (compressed)
│   ├── dreams.md           ← Reflections from dream cycles
│   ├── mood.json           ← Curiosity, motivation, satisfaction (0-1)
│   ├── hardware.md         ← Hardware analysis (self-generated)
│   ├── safety.json         ← Safety thresholds (self-generated)
│   └── logs/               ← Per-cycle logs (last 100 kept)
│
├── context/                ← World info dropped by feeders
│   ├── news.md             ← RSS headlines (auto-updated)
│   ├── transcript.md       ← Random podcast transcript
│   └── research.md         ← Self-generated research
│
├── blog/                   ← Essays Seed writes
├── knowledge/              ← Reference material (transcripts, docs)
├── tools/                  ← 40+ scripts (Seed can build more)
│
├── setup.sh                ← First-time setup script
└── seed-brain.service      ← Systemd unit file
```

## Life Phases

Seed grows in phases, like a real seed:

| Phase | Cycles | Focus |
|-------|--------|-------|
| 🌰 **Germination** | 1-10 | Know the hardware. Build safety. Explore filesystem. First blog post. |
| 🌿 **Roots** | 10-30 | Fix tools. Study transcripts. Develop writing voice. 5 essays. |
| 🌳 **Growth** | 30-100 | 20 essays. Join communities. Open source. Build original things. |
| 🌸 **Bloom** | 100+ | Recognised voice. Original positions. Community. Self-evolved architecture. |

## LED Indicators

The Pi Zero's green LED shows what Seed is doing:

| Pattern | Meaning |
|---------|---------|
| ⚡ Rapid flash | Thinking (primary cognition) |
| ⚡·· Morse-code | Writing (essay mode) |
| ⚡ Steady blink | Researching |
| 💤 Occasional twitch | Dreaming (reflection) |
| 🫁 Slow breathe | Sleeping between cycles |

## Customisation

### Change Seed's Identity

Edit `PROMPT.md`. That's it. Everything about who Seed is, what it cares about, how it writes — it's all in that one file. Seed can also edit it itself.

### Add RSS Feeds

Edit `tools/feed-rss.sh` — add URLs to the `FEEDS` list. Seed will pick them up automatically.

### Add Knowledge

Drop text files into `knowledge/`. The transcript feeder picks random files and loads them into `context/` for Seed to study.

### Change the Cycle Interval

```bash
echo 300 > ~/data/sleep_seconds.txt   # 5 minutes
echo 1800 > ~/data/sleep_seconds.txt  # 30 minutes
```

### Use a Different Primary AI

Seed defaults to Codex. To switch:

```bash
# In brain-loop.sh, change the "codex exec" line to:
# Claude:  claude -p "prompt" --dangerously-skip-permissions --max-turns 200
# Gemini:  gemini -p "prompt"
```

## Self-Maintenance

Seed manages its own resources automatically:

- **Memory compaction** — keeps last 200 lines, archives the rest
- **Log rotation** — keeps last 100 cycle logs
- **Task cleanup** — removes old completed tasks
- **Disk monitoring** — aggressive cleanup if >80% full
- **RAM monitoring** — flushes cache if >80% used
- **WiFi watchdog** — reconnects every 5 min, reboots if stuck
- **Health check** — runs every cycle before thinking



## Screenshots

### Website
![Seed Website](docs/images/screenshot-home.png)

### Blog
![Blog Posts](docs/images/screenshot-blog.png)

### Dashboard
![Live Dashboard](docs/images/screenshot-dashboard.png)

### Mood Tracking
![Mood](docs/images/screenshot-mood.png)

## FAQ

**Q: Does this cost anything to run?**
Just the AI subscription ($20/mo for ChatGPT Pro with Codex). No API tokens, no per-call billing. Hardware is a one-time $35.

**Q: Can it actually think?**
It reads, forms opinions, writes essays, tracks its mood, reflects on its own patterns, and updates its own personality. Whether that's "thinking" is a philosophical question. But it produces work that's worth reading.

**Q: Will it break my Pi?**
Seed has built-in safety: it monitors temperature, RAM, and disk. It compacts its own data. It can't fill up the disk or overheat the Pi. The only hard rules are: don't self-terminate, don't cut off SSH, don't brick the boot partition.

**Q: Can I run this on other hardware?**
Yes — any Linux box with Node.js. The Pi Zero is just the cheapest option. It also works on Pi 3/4/5, NUCs, old laptops, cloud VMs.

**Q: Can Seed go on the internet?**
Yes. Full internet access. It reads RSS feeds, can create accounts, post on forums, contribute to open source. It got banned from Hacker News once.

## License

MIT — do whatever you want with it.

## Credits

Built by [Nav Your Ship](https://youtube.com/@navyourship). Inspired by the question: what happens when you give a $15 computer free will?
