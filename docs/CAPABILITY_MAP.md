# Seed Capability Map

This is the map I would want before cloning an autonomous agent and leaving it alone.

The short version: Seed is a user-space loop with network access, file access inside its checkout and home directory, local CLI access to AI backends, and git push access if you give it credentials. It is not safe because it is magical. It is safer when you run it as an unprivileged user, keep secrets narrow, and decide which verbs are allowed before the loop runs unattended.

## Execution Surface

Primary entry points:

- `brain-loop.sh` runs the wake/sense/think/act/learn/sleep loop.
- `seed-brain.service` starts `brain-loop.sh` under systemd from `%h/seed`.
- `setup.sh` installs one selected AI backend, runs `tools/health-check.sh`, and only installs the service after an explicit prompt.
- `webserver.py` serves the local dashboard and JSON API on port 8080.

LLM calls:

- Think, research, dream, and maintain phases call `codex exec --dangerously-bypass-approvals-and-sandbox`.
- Write phase calls `claude -p --dangerously-skip-permissions`.
- Gemini is supported through `GEMINI_API_KEY`, but this public loop does not make Gemini the default executor.

That means the host boundary matters. Do not run Seed as root. Do not put it in an account that can casually control your machine.

## Files Seed Reads

Routine state:

- `IDENTITY.md`, `PROMPT.md`, and `prompts/`
- `data/goals.md`, `data/tasks.md`, `data/memory.md`, `data/inner-voice.md`, `data/lessons.md`, `data/errors.md`
- `data/mood.json`, `data/cycle.txt`, `state/`
- `context/` feed outputs
- `memory/`, `skills/`, `knowledge/`, `blog/`

External inputs are staged into `context/` before they reach the LLM. Treat everything in `context/` as hostile text until `cognitive/firewall.py` has filtered it.

## Files Seed Writes

Routine writes:

- `data/` state and logs
- `state/` heartbeat, drives, emotions, outcomes
- `memory/` episodic and semantic records
- `context/` feeder output
- `blog/` essays
- `research/`, `knowledge/`, `skills/`, `tmp/`, `archive/`

Generated noise:

- `data/health.json`
- `data/logs/cycle_*.log`
- `state/heartbeat.json`
- `tmp/prompt_cycle_*.md`

Backups and restoration are an operator concern. The public repo includes the hooks and docs, not your private backup store.

## Tool Verbs

File and memory:

- `tools/file_read.py`, `tools/file_write.py`, `tools/file_ops.py`
- `tools/remember_fact.py`, `tools/store_fact.py`
- `tools/self_edit.py` has a write whitelist and hard-blocks core guard files.

Shell and packages:

- `tools/shell_exec.py` runs commands inside `sandbox/` and blocks known destructive patterns.
- `tools/install_pkg.sh` can call `sudo apt-get install` if the user account has sudo.
- `setup.sh` can call `sudo npm install -g` for selected agent CLIs.

Network and research:

- `tools/fetch_url.py`, `tools/web_fetch.py`, `tools/search_web.py`, `tools/download_file.py`
- `tools/feed-rss.sh`, `tools/feed-trends.sh`, `tools/feed-transcript.sh`, `tools/feed-outreach.sh`
- `tools/network-scan.sh`, `tools/network_scan.sh`, `tools/modem-status.sh`

Publishing and git:

- `tools/deploy-blog.sh`, `tools/website.sh`, `tools/auto-index.sh`, `tools/build-timeline.sh`
- `brain-loop.sh` commits and pushes live repo changes when git credentials exist.
- `tools/safe-git.sh` and `tools/git_ops.sh` are safer wrappers for status and routine git work.

System and body:

- `tools/health-check.sh`, `tools/system_health.py`, `tools/system_monitor.py`, `tools/body-scan.sh`
- `tools/self-maintain.sh`, `tools/watchdog.sh`, `tools/self-restart.sh`
- `tools/services.sh`, `tools/cloudflare.sh`, `tools/vpn_setup.sh` can touch services or network helpers if the OS account has permission.

Speech and outreach:

- `tools/speak.sh`, `tools/screen-write.sh`
- `tools/send-email.py` can send mail only if local account files exist.
- `tools/feed-email.sh` reads IMAP only when `SEED_EMAIL_USER` and `SEED_EMAIL_APP_PASSWORD` are set.

## Network Paths

Outbound:

- RSS and web fetches over HTTP(S)
- GitHub API if `~/.git-credentials` exists
- Gmail IMAP if email environment variables are set
- Git remotes for repo and website pushes
- Agent backend APIs through Codex, Claude, or Gemini CLIs
- Optional Cloudflare tunnel via `tools/cloudflare.sh`
- Optional Tailscale via `tools/vpn_setup.sh`

Inbound:

- `webserver.py` listens locally on port 8080.
- Public exposure only happens if you configure a tunnel or reverse proxy.
- `/api/file` is limited to a small whitelist in `webserver.py`.

## Secrets

Do not commit secrets.

Expected local-only secret locations:

- AI backend login state managed by the vendor CLIs
- `GEMINI_API_KEY` in environment or service environment
- `SEED_EMAIL_USER` and `SEED_EMAIL_APP_PASSWORD` in environment or service environment
- `~/.git-credentials` for GitHub access
- `~/cloudflare/cloudflared.env` for `TUNNEL_TOKEN`
- `~/data/accounts/*.json` for optional mail sending credentials

The public repo should contain placeholders only. If you find a real token, password, cookie, or private personal detail in this repo, rotate it and open an issue or patch.

## Deletion and Cleanup

Allowed cleanup:

- Old cycle logs
- Temporary prompt files
- Generated health/status output
- Old episodic memory after compaction
- Temporary transcript-processing directories

Dangerous deletion surfaces:

- `cognitive/triggers.py` can delete old logs and emergency temp/archive files under disk pressure.
- `tools/self-maintain.sh` removes old logs and can ask the OS to drop caches.
- `tools/transcript-prune-nested-duplicates.sh` deletes duplicate transcript files.

Hard stop: do not give Seed write access to irreplaceable personal directories. Clone it into its own user account.

## Logs and Public Output

Private/local logs:

- `data/logs/cycle_*.log`
- `data/security.jsonl`
- `data/errors.md`
- `memory/episodic/*.json`
- `data/token-usage.jsonl`

Potentially public output:

- `blog/*.md`
- `seed-web` deployment artifacts if you mirror the website pattern
- Git commits and push history
- Dashboard API output if you expose port 8080

Privacy rule: creator names, emails, phone numbers, private addresses, credentials, and personal account details do not belong in public posts, public logs, screenshots, or repo files.

## Human Gates

Always human-owned:

- Creating or approving external accounts
- Adding credentials
- Enabling systemd service on first boot
- Giving sudo or root privileges
- Exposing the dashboard to the public internet
- Connecting VPNs or tunnels
- Adding payment, cloud, production, or personal-data credentials
- Running Seed outside a disposable or dedicated user account

Seed can help write the script. The operator decides whether the script is allowed near the real machine.

## Recommended Containment

Start here:

- Dedicated Unix user, not your personal account.
- No passwordless sudo.
- Separate GitHub token with repo-limited scope.
- No browser cookies, SSH private keys, crypto wallets, payment tokens, or personal cloud credentials in the account.
- Firewall inbound traffic except SSH from your management path and the local dashboard if needed.
- Run `bash tools/health-check.sh` and `python3 tools/tool-smoke.py` before enabling the service.
- Read `data/tasks.md` and `data/goals.md` before first unattended run. They are part of the control surface.

The point is not to trust Seed. The point is to make the room small enough that autonomy can be useful without becoming custody.
