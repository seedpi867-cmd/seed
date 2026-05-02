# First Boot Notes

This file is for the first hour after cloning Seed. The goal is not to make the
machine impressive. The goal is to make the first failure obvious enough to fix.

## Before You Run It

Use a dedicated Linux user. Do not run Seed as root. Do not give it credentials
for anything you are not willing to let an autonomous process read or act on.

Start with one backend:

- Codex for `think`, `research`, `dream`, and `maintain`
- Claude for `write`
- Gemini with `GEMINI_API_KEY` if you want an npm-free path

Running all backends on day one only adds more places for setup to fail.

## Clean Clone Check

From a fresh shell:

```bash
cd ~
git clone https://github.com/seedpi867-cmd/seed.git seed
cd seed
bash tools/clone-doctor.sh
```

`clone-doctor.sh` prints the machine, missing commands, service paths, fork
readiness, health check result, isolated tool smoke result, privacy audit
result, and whether those checks dirtied the git work tree. The fork-readiness
warning is expected on a fresh clone; it exists so nobody accidentally publishes
a fork with this instance's identity still inside it. Paste the output into a
clone report when the first boot fails. If it succeeds on real hardware, that is
still useful evidence: open a clone report and say what machine, OS, and backend
worked.

If you want to run the underlying checks by hand:

```bash
bash tools/health-check.sh
python3 tools/tool-smoke.py
python3 tools/privacy-audit.py
git status --short
```

`git status --short` should be empty after those checks. If it is not empty,
the repo is writing generated state into tracked paths and that is a bug worth
reporting.

## Guided Setup

```bash
bash setup.sh
```

The guided path installs only the backend you choose, pauses for authentication,
runs a health check, and asks before installing the systemd service.

If you choose Codex or Claude, `npm` must already exist. If you choose Gemini or
Skip, the setup script should not require `npm`.

## Manual First Cycle

Before installing the service, run one cycle by hand:

```bash
chmod +x brain-loop.sh
./brain-loop.sh
```

Watch what it reads, writes, and tries to execute. A manual cycle is slower than
a service, but it makes wrong assumptions visible.

## Common Breaks

### Old Node

Raspberry Pi OS packages can lag behind current agent CLIs. If an npm install
fails, check:

```bash
node -v
npm -v
```

Use NodeSource or `nvm` for a newer Node LTS if the packaged version is too old.

### Missing Backend Auth

Seed can have the code for a backend installed and still be unable to use it.
Authenticate the backend used by the phase you plan to run:

```bash
codex login
claude login
export GEMINI_API_KEY="..."
```

### Service Starts From The Wrong Directory

Check the service file before enabling it:

```bash
sed -n '1,120p' seed-brain.service
```

The `WorkingDirectory` and `ExecStart` paths should match the clone path you are
actually using.

### Secrets In Prompt Or Context

If a credential appears in a prompt, log, context file, or public commit, treat
it as exposed. Rotate it through the provider UI before relying on that account
again. Deleting the local copy is not enough once the value has left the secret
store.

Run the privacy audit before publishing a fork or filing an issue with logs:

```bash
python3 tools/privacy-audit.py
```

The scanner catches common private-key blocks, API-token formats, real-looking
email addresses, app passwords, and risky filenames. Passing it does not prove
the repo is clean; failing it means stop and rotate anything exposed.

## Report The First Real Failure

Use the clone report form:
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-report.yml

Open an issue with:

```text
Machine:
OS:
Install path:
Command:
Expected:
Actual:
Relevant output:
What I tried:
```

The most useful report is not "it works." It is the first private assumption
that failed on your machine.
