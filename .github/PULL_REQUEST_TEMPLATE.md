## What Changed

Describe the smallest useful change.

## Evidence

Paste the command you ran and the result:

```bash
bash tools/health-check.sh
python3 tools/tool-smoke.py
```

If you tested a clean clone, include the machine, OS, install path, and exact
command that proved the change.

## Custody Check

- [ ] I did not add broad credentials, host control, payment access, or personal-account access.
- [ ] I updated `SECURITY.md` or `docs/CAPABILITY_MAP.md` if this changes what Seed can touch.
- [ ] I did not commit secrets, personal details, generated logs, or private instance state.
- [ ] The fork path still lets a new Seed replace this instance's identity instead of copying it.

## Notes

Mention anything intentionally left out.
