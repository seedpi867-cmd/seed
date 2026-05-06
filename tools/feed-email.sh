#!/bin/bash
# Check email and drop summaries into context/
python3 - << 'PYEOF'
import imaplib, email, os, time
from email.header import decode_header

USER = os.environ.get("SEED_EMAIL_USER", "")
PASS = os.environ.get("SEED_EMAIL_APP_PASSWORD", "").replace(" ", "")
IMAP = "imap.gmail.com"
OUT = os.path.expanduser("~/context/email.md")

try:
    if not USER or not PASS:
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
PYEOF
