"""
Tool: fetch_url
Fetch text content from a public URL. Returns stripped text (max 2000 chars).
Args: {"url": "https://...", "max_chars": 2000}
"""
import re
import socket
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Block private/loopback networks — SEED cannot probe local infrastructure
BLOCKED_PREFIXES = ("192.168.", "10.", "172.16.", "172.17.", "172.18.",
                    "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                    "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                    "172.29.", "172.30.", "172.31.", "127.", "0.", "169.254.")


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    url = args.get("url", "").strip()
    max_chars = int(args.get("max_chars", 2000))

    if not url:
        return False, "No URL provided"

    if not url.startswith("http://") and not url.startswith("https://"):
        return False, "URL must start with http:// or https://"

    # Resolve host and check it's not private
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        ip = socket.gethostbyname(host)
        if any(ip.startswith(p) for p in BLOCKED_PREFIXES):
            return False, f"HARD BLOCK — {ip} is a private/local address"
    except Exception as e:
        return False, f"Could not resolve host: {e}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SEED/1.0 (autonomous AI; Pi Zero 2W)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")

        # Strip HTML if it looks like HTML
        if "<html" in raw.lower() or "<body" in raw.lower():
            text = _strip_html(raw)
        else:
            text = raw.strip()

        return True, text[:max_chars]

    except Exception as e:
        return False, f"Fetch failed: {e}"
