#!/bin/bash
# Check email and drop summaries into context/
python3 - << 'PYEOF'
import imaplib, email, importlib.util, os, sys, time
from email.header import decode_header

USER = os.environ.get("SEED_EMAIL_USER", "")
PASS = os.environ.get("SEED_EMAIL_APP_PASSWORD", "").replace(" ", "")
IMAP = "imap.gmail.com"
OUT = os.path.expanduser("~/context/email.md")
RECONCILER = os.path.expanduser("~/tools/ci-email-reconciler.py")


def email_configured():
    return bool(USER and PASS)


def reconcile_ci_notice(path):
    if not os.path.exists(path) or not os.path.exists(RECONCILER):
        return
    text = open(path, encoding="utf-8", errors="replace").read()
    if "Run failed:" not in text or "Workflow:" not in text:
        return

    spec = importlib.util.spec_from_file_location("ci_email_reconciler", RECONCILER)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    try:
        verdict, reason, notice, named, latest = module.reconcile_text(text)
    except Exception as exc:
        print(f"[email] CI notice reconciliation unavailable: {exc}")
        return

    if verdict not in {"STALE_FAILURE", "CURRENT_SUCCESS"}:
        print(f"[email] CI notice remains active: {verdict}")
        return

    lines = [
        f"## Emails — {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "### Reconciled CI Notice",
        f"- Verdict: {verdict}",
        f"- Reason: {reason}",
        f"- Notice: {notice.repo} {notice.workflow} {notice.branch} {notice.sha[:7]}",
        f"- {module.summarize_run('named', named)}",
        f"- {module.summarize_run('latest', latest)}",
        "",
        "The earlier failure email has expired as current action pressure. Treat it as history unless a newer failure appears.",
        "",
    ]
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"[email] CI notice reconciled: {verdict}")

try:
    if not email_configured():
        print("[email] Skipped: SEED_EMAIL_USER or SEED_EMAIL_APP_PASSWORD is not set")
    else:
        m = imaplib.IMAP4_SSL(IMAP)
        m.login(USER, PASS)
        m.select("INBOX")

        # Get unread emails
        _, nums = m.search(None, "UNSEEN")
        ids = nums[0].split()

        if not ids:
            print("[email] No new emails")
        else:
            out = f"## Emails — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
            for eid in ids[-10:]:  # last 10 unread
                _, data = m.fetch(eid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])

                subj = msg["Subject"] or "(no subject)"
                parts = decode_header(subj)
                subj = parts[0][0]
                if isinstance(subj, bytes):
                    subj = subj.decode(parts[0][1] or "utf-8", errors="replace")

                frm = msg["From"] or "unknown"
                date = msg["Date"] or ""

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")[:500]
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:500]

                out += f"### From: {frm}\n"
                out += f"Subject: {subj}\n"
                out += f"Date: {date}\n"
                out += f"\n{body}\n\n---\n\n"

            with open(OUT, "w") as f:
                f.write(out)
            print(f"[email] {len(ids)} new emails saved to context/")

        m.logout()
except Exception as e:
    print(f"[email] Error: {e}")

reconcile_ci_notice(OUT)
PYEOF
