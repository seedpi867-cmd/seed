# Workflow: Self-Improvement

## Trigger
Found a bug, inefficiency, or missing capability

## Steps
- [ ] Document the problem in docs/incidents/
- [ ] Design the fix
- [ ] Implement it
- [ ] Test it (bash -n for scripts)
- [ ] Push to the configured private repo (`SEED_PRIVATE_REPO`, default `~/seed-os`)
- [ ] If brain-loop changed: bash tools/self-restart.sh
- [ ] Document the fix in docs/decisions/
- [ ] Update docs/INDEX.md

## Output
Working improvement, versioned and documented
