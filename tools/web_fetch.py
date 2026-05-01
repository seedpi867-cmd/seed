#!/usr/bin/env python3
"""
web_fetch.py — Fetch a URL and return clean text content.
Uses requests for full redirect/cookie/header support.
Falls back to urllib if requests unavailable.
Usage: python3 web_fetch.py <url> [--max-chars N] [--json] [--raw]
"""
import argparse
import json
import re
import sys

# Try requests first, fall back to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Linux; Android 10; Pi) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/json,*/*;q=0.8',
    'Accept-Language': 'en-AU,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
}


def strip_html_basic(html: str) -> str:
    """Simple HTML stripper without bs4."""
    text = re.sub(r'<(script|style|noscript|nav|footer|head)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\s{3,}', '\n\n', text)
    return text.strip()


def strip_html_bs4(html: str) -> str:
    """Full HTML extraction with BeautifulSoup."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'nav', 'footer', 'head', 'iframe', 'svg']):
        tag.decompose()
    lines = []
    for el in soup.find_all(string=True):
        text = el.strip()
        if text:
            lines.append(text)
    return '\n'.join(lines)


def fetch_with_requests(url: str, max_chars: int, timeout: int) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout,
                            allow_redirects=True, stream=False)
        content_type = resp.headers.get('content-type', '')
        raw = resp.text

        if 'application/json' in content_type:
            return {'url': resp.url, 'type': 'json', 'content': raw[:max_chars],
                    'status': resp.status_code}

        text = strip_html_bs4(raw) if HAS_BS4 else strip_html_basic(raw)
        return {'url': resp.url, 'type': 'html', 'content': text[:max_chars],
                'chars': len(text), 'status': resp.status_code}
    except Exception as e:
        return {'url': url, 'error': str(e), 'status': 0}


def fetch_with_urllib(url: str, max_chars: int, timeout: int) -> dict:
    import urllib.request, urllib.error
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(1024 * 1024).decode('utf-8', errors='replace')
            text = strip_html_basic(raw)
            return {'url': url, 'type': 'html', 'content': text[:max_chars],
                    'chars': len(text), 'status': resp.status}
    except Exception as e:
        return {'url': url, 'error': str(e), 'status': 0}


def fetch(url: str, max_chars: int = 12000, timeout: int = 20) -> dict:
    if HAS_REQUESTS:
        return fetch_with_requests(url, max_chars, timeout)
    return fetch_with_urllib(url, max_chars, timeout)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('url')
    p.add_argument('--max-chars', type=int, default=12000)
    p.add_argument('--timeout',   type=int, default=20)
    p.add_argument('--json',  action='store_true', dest='as_json')
    p.add_argument('--raw',   action='store_true', help='Skip HTML stripping')
    args = p.parse_args()

    result = fetch(args.url, args.max_chars, args.timeout)

    if args.as_json:
        print(json.dumps(result, indent=2))
    elif 'error' in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    else:
        print(result['content'])


if __name__ == '__main__':
    main()
