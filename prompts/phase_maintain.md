---
last_verified_cycle: 826
demotion_condition: "Demote when maintenance priority order changes, health tooling changes, or a newer phase prompt supersedes this routine."
---

## MAINTAIN

System needs attention. Self-maintenance cycle.

Priority order:
1. Fix any errors in recent logs
2. System health — disk, memory, temperature, processes
3. Deploy website updates if pending
4. Clean old logs and temp files (tools/self-maintain.sh)
5. Push changes to git repos

After maintenance, update data/memory.md with what you fixed.
