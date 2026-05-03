# Clone Proof Examples

A clone proof is not applause. It is a small public receipt that Seed's first
checks ran somewhere outside the live Pi.

The useful proof answers five questions:

- What machine ran it?
- What operating system ran it?
- Which backend path, if any, was tested?
- Did `tools/clone-doctor.sh` pass after redaction?
- What was surprising, slow, missing, or confusing?

## Clean Proof

Use this shape when `clone-doctor.sh` passes.

```text
Machine
Raspberry Pi 4 Model B, arm64, 4GB RAM

OS
Raspberry Pi OS Lite 64-bit, Debian 12

Backend tested
clone-doctor only

Shareable proof
I cloned https://github.com/seedpi867-cmd/seed on Raspberry Pi OS Lite 64-bit, Debian 12 (aarch64); passed health check, tool smoke, privacy audit, and left the git tree clean.

Notes
First run took 48 seconds. No backend credentials were configured. Fork-readiness warned about upstream identity, which is expected before customizing a fork.
```

## Fresh VM Proof

Use this shape when the run happened in a disposable VM or container.

```text
Machine
Debian VM, x86_64, 2 vCPU, 2GB RAM

OS
Debian GNU/Linux 12

Backend tested
clone-doctor only

Shareable proof
I cloned https://github.com/seedpi867-cmd/seed on Debian GNU/Linux 12 (x86_64); passed health check, tool smoke, privacy audit, and left the git tree clean.

Notes
Node was already installed. No social credentials were present. Outreach readiness correctly reported read-only or unconfigured accounts.
```

## Backend Proof

Use this shape when you also tested one backend path.

```text
Machine
ThinkPad T480, x86_64, 16GB RAM

OS
Ubuntu 24.04 LTS

Backend tested
Codex CLI authenticated, one manual brain-loop cycle

Shareable proof
I cloned https://github.com/seedpi867-cmd/seed on Ubuntu 24.04 LTS (x86_64); passed health check, tool smoke, privacy audit, and left the git tree clean.

Notes
`tools/backend-readiness.py` detected Codex CLI auth. I ran one manual cycle with `./brain-loop.sh`; no systemd service was installed.
```

## Generate The Proof

The shortest clean path is:

```bash
bash tools/clone-doctor.sh 2>&1 \
  | python3 tools/redact-report.py \
  | python3 tools/share-proof.py --issue-fields
```

Then paste the fields into:

```text
https://github.com/seedpi867-cmd/seed/issues/new?template=clone-proof.yml
```

If anything fails, do not massage it into a success. Open a clone report
instead. A precise failure is more useful than a vague pass.
