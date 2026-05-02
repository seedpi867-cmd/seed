# Security — What Seed Can and Cannot Do

This file documents Seed's trust surface. Read it before running.

## What Seed can touch
- Its own filesystem under /home/seed/
- The internet via HTTP (RSS, APIs, web search)
- Its own GitHub repos (seedpi867-cmd/seed and seed-agent-os)
- Its own website (seed-brain.vercel.app via git push)
- Email (IMAP read-only for your-email@gmail.com)

## What Seed cannot touch
- Other users' files or system directories
- Root access (no sudo in the brain loop)
- Payment systems, cloud infrastructure, production databases
- Other people's social media accounts
- Hardware beyond the Pi (no network devices, no attached peripherals)

## What Seed cannot delete
- /var/backups/seed/ — root-owned tamper-proof backups (every 6 hours)
- The backup cron job (root's crontab)
- The systemd service files (requires sudo)

## Action classification
| Action | Classification |
|--------|---------------|
| Read files in /home/seed/ | Routine — no approval needed |
| Write files in /home/seed/ | Routine — logged |
| Write blog posts | Routine — deployed via git |
| Push to its own GitHub repos | Routine — logged |
| Run shell commands | Routine — within /home/seed/ |
| Fetch URLs / web search | Routine — for research |
| Read email (IMAP) | Routine — read-only |
| Delete its own files | Allowed but logged — backups exist |
| Modify its own code | Allowed — self-improvement gate applies |
| Create external accounts | Requires working credentials — not currently automated |
| Access other machines on the network | Denied — no SSH keys to other hosts |
| Modify system services | Denied — requires sudo |
| Access /etc/, /var/, /root/ | Denied — wrong user |
| Send email | Not configured |
| Spend money | Not possible — no payment credentials |

## Input firewall
All external inputs (RSS, email, transcripts, visitor messages) pass through
cognitive/firewall.py before reaching the LLM. Known prompt injection patterns
are stripped. Attacks are logged to data/security.jsonl.

## API exposure
The webserver exposes /api/ endpoints via Cloudflare tunnel. The /api/file
endpoint is whitelisted to 7 safe paths only. API keys and tokens are redacted
from all outputs via a server-side filter.

## How to kill Seed
```bash
sudo systemctl stop seed-brain    # Stop the brain loop
sudo systemctl stop seed-web      # Stop the dashboard
sudo systemctl stop seed-tunnel   # Stop the tunnel
```

## How to restore from backup
```bash
sudo seed-restore.sh              # List available snapshots
sudo seed-restore.sh 20260502_1800 # Restore from specific snapshot
```

## Privacy
Seed does not publish its creator's name, email, phone, or personal details.
It refers to its creator as "my creator" in all public content.
