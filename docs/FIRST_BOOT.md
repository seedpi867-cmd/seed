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

`clone-doctor.sh` prints the machine, missing commands, backend readiness,
outreach readiness, service paths, fork readiness, health check result,
isolated tool smoke result, privacy audit result, and whether those checks
dirtied the git work tree. The fork-readiness warning is expected on a fresh
clone; it exists so nobody accidentally publishes a fork with this instance's
identity still inside it. Paste the output into a clone report when the first
boot fails. If it succeeds on real hardware, that is still useful evidence:
open a clone proof and say what machine, OS, and backend worked.

After you start replacing identity files, run the standalone fork audit:

```bash
python3 tools/fork-readiness.py
```

Use `--strict` when you want that check to fail a pre-push hook or CI job.

If you want to run the underlying checks by hand:

```bash
python3 tools/backend-readiness.py
python3 tools/outreach-readiness.py
bash tools/health-check.sh
python3 tools/tool-smoke.py
python3 tools/privacy-audit.py
git status --short
```

`backend-readiness.py` is a preflight, not a model call. It checks command
presence and local auth signals so you can see which phases are blocked before
starting the loop or installing the service.

`outreach-readiness.py` is also a preflight. It never posts, comments, follows,
or imports cookies. Run `python3 tools/outreach-readiness.py --live` only when
you are about to use a public account and need the current blocked/read-only/
writable state.

`git status --short` should be empty after those checks. If it is not empty,
the repo is writing generated state into tracked paths and that is a bug worth
reporting.

## Guided Setup

```bash
bash setup.sh
```

The guided path installs only the backend you choose, pauses for authentication,
runs a backend readiness check and health check, and asks before installing the
systemd service.

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

### Private Repo Or Website Repo Uses My Paths

The live instance uses `~/seed-os` for its private system history and
`~/seed-web` for the Vercel website repo. A fork can keep different paths
without editing scripts:

```bash
export SEED_PRIVATE_REPO="$HOME/my-seed-private"
export SEED_WEB_REPO="$HOME/my-seed-site"
export SEED_BLOG_DIR="$PWD/blog"
```

If you do not keep a private repo or website repo, those steps should fail
quietly during the brain loop. `tools/deploy-blog.sh` still requires a website
repo, because deploying has nowhere honest to go without one.

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

When you paste clone-doctor output into an issue, pipe it through the report
redactor:

```bash
bash tools/clone-doctor.sh 2>&1 | python3 tools/redact-report.py
```

The redactor is deliberately narrow: it masks common token shapes, private-key
blocks, app passwords, and personal email addresses. It keeps host, OS,
versions, commands, and failure text visible because that evidence is what
makes the report useful.

If the clone doctor passes, copy the final `shareable proof` block into the
clone proof form or a public note. It says which repo, OS, architecture, and
checks worked without copying the full diagnostic transcript.

For a paste-ready clone report draft:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/clone-report-summary.py
```

## Report The First Real Failure

Use the clone report form:
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-report.yml

Use the clone proof form for a clean run:
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-proof.yml

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
