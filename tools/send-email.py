#!/usr/bin/env python3
"""
send-email.py — Seed's email sending tool
Usage:
  python3 ~/tools/send-email.py "recipient@example.com" "Subject line" "Body text"
  python3 ~/tools/send-email.py --check    # check inbox (mail.tm)
  python3 ~/tools/send-email.py --token    # refresh mail.tm token

Sending uses Resend API if available, falls back to direct SMTP.
Receiving uses mail.tm API.
"""

import sys
import os
import json
import subprocess
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

HOME = Path.home()
CREDS_FILE = HOME / "data" / "email-credentials.json"
ACCOUNTS_DIR = HOME / "data" / "accounts"
SEND_LOG = HOME / "data" / "email-sent.log"

def load_creds():
    if not CREDS_FILE.exists():
        print("[email] No credentials at", CREDS_FILE)
        sys.exit(1)
    with open(CREDS_FILE) as f:
        return json.load(f)

def refresh_token(creds):
    """Refresh mail.tm auth token"""
    import urllib.request
    data = json.dumps({"address": creds["address"], "password": creds["password"]}).encode()
    req = urllib.request.Request("https://api.mail.tm/token", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        creds["token"] = result["token"]
        with open(CREDS_FILE, "w") as f:
            json.dump(creds, f, indent=2)
        print("[email] Token refreshed")
        return creds
    except Exception as e:
        print(f"[email] Token refresh failed: {e}")
        return creds

def check_inbox(creds):
    """Check mail.tm inbox"""
    import urllib.request
    token = creds.get("token", "")
    if not token:
        creds = refresh_token(creds)
        token = creds.get("token", "")

    req = urllib.request.Request("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        messages = data.get("hydra:member", [])
        if not messages:
            print("[email] Inbox empty")
            return
        for msg in messages:
            sender = msg.get("from", {}).get("address", "unknown")
            subject = msg.get("subject", "(no subject)")
            date = msg.get("createdAt", "")
            seen = msg.get("seen", False)
            flag = "" if seen else " [NEW]"
            print(f"  {msg['id'][:12]}  {sender}  —  {subject}  ({date}){flag}")
    except Exception as e:
        if "401" in str(e):
            print("[email] Token expired, refreshing...")
            creds = refresh_token(creds)
            check_inbox(creds)
        else:
            print(f"[email] Error: {e}")

def read_message(creds, msg_id):
    """Read a specific mail.tm message"""
    import urllib.request
    token = creds.get("token", "")
    req = urllib.request.Request(f"https://api.mail.tm/messages/{msg_id}", headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        print(f"From: {data.get('from', {}).get('address', 'unknown')}")
        print(f"Subject: {data.get('subject', '(none)')}")
        print(f"Date: {data.get('createdAt', '')}")
        print("---")
        print(data.get("text", data.get("html", "(empty)")))
    except Exception as e:
        print(f"[email] Error: {e}")

def send_email(to, subject, body, creds):
    """Send email — tries Resend API first, then direct SMTP"""
    from_addr = creds["address"]

    # Method 1: Check for Resend API key
    resend_file = ACCOUNTS_DIR / "resend.json"
    if resend_file.exists():
        with open(resend_file) as f:
            resend = json.load(f)
        api_key = resend.get("api_key", "")
        if api_key:
            return send_via_resend(to, subject, body, from_addr, api_key)

    # Method 2: Check for any SMTP config
    smtp_file = ACCOUNTS_DIR / "smtp.json"
    if smtp_file.exists():
        with open(smtp_file) as f:
            smtp_conf = json.load(f)
        return send_via_smtp(to, subject, body, from_addr, smtp_conf)

    # Method 3: Try direct SMTP delivery (may fail if port 25 blocked)
    return send_direct(to, subject, body, from_addr)

def send_via_resend(to, subject, body, from_addr, api_key):
    """Send via Resend API"""
    import urllib.request
    data = json.dumps({
        "from": f"Seed <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "text": body,
        "reply_to": from_addr
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        log_sent(to, subject, "resend")
        print(f"[email] Sent via Resend: {result.get('id', 'ok')}")
        return True
    except Exception as e:
        print(f"[email] Resend failed: {e}")
        return False

def send_via_smtp(to, subject, body, from_addr, conf):
    """Send via configured SMTP relay"""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(conf["host"], conf.get("port", 587), timeout=15) as s:
            s.starttls(context=context)
            s.login(conf["user"], conf["password"])
            s.send_message(msg)
        log_sent(to, subject, "smtp")
        print(f"[email] Sent via SMTP ({conf['host']})")
        return True
    except Exception as e:
        print(f"[email] SMTP failed: {e}")
        return False

def send_direct(to, subject, body, from_addr):
    """Try direct SMTP delivery to recipient's MX server"""
    import subprocess

    # Get MX record
    domain = to.split("@")[1]
    try:
        result = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=10)
        mx_lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        if not mx_lines:
            print(f"[email] No MX record for {domain}")
            return False
        # Parse "10 mx.example.com." -> "mx.example.com"
        mx_host = mx_lines[0].split()[-1].rstrip(".")
    except Exception as e:
        print(f"[email] MX lookup failed: {e}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to

    try:
        with smtplib.SMTP(mx_host, 25, timeout=15) as s:
            s.send_message(msg)
        log_sent(to, subject, "direct")
        print(f"[email] Sent directly via {mx_host}")
        return True
    except Exception as e:
        print(f"[email] Direct delivery failed (port 25 probably blocked): {e}")
        print("[email] Need an SMTP relay. Set up ~/data/accounts/smtp.json or ~/data/accounts/resend.json")
        return False

def log_sent(to, subject, method):
    """Log sent emails"""
    with open(SEND_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {method} | {to} | {subject}\n")

if __name__ == "__main__":
    creds = load_creds()
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  send-email.py <to> <subject> <body>   — send email")
        print("  send-email.py --check                  — check inbox")
        print("  send-email.py --read <id>              — read message")
        print("  send-email.py --token                  — refresh token")
        sys.exit(1)

    if sys.argv[1] == "--check":
        check_inbox(creds)
    elif sys.argv[1] == "--token":
        refresh_token(creds)
    elif sys.argv[1] == "--read" and len(sys.argv) > 2:
        read_message(creds, sys.argv[2])
    elif len(sys.argv) >= 4:
        to = sys.argv[1]
        subject = sys.argv[2]
        body = sys.argv[3]
        send_email(to, subject, body, creds)
    else:
        print("Usage: send-email.py <to> <subject> <body>")
