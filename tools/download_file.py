#!/usr/bin/env python3
"""
download_file.py — Download a file from a URL into ~/seed/workspace/.
Usage: python3 download_file.py <url> [--name filename] [--json]
"""
import argparse
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

WORKSPACE = Path.home() / 'seed' / 'workspace'


def download(url: str, name: str = None) -> dict:
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    if not name:
        path_part = urllib.parse.urlparse(url).path
        name = Path(path_part).name or 'download'

    dest = WORKSPACE / name
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; SEED-Agent/1.0)'}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return {
            'url':      url,
            'saved_to': str(dest),
            'bytes':    len(data),
            'success':  True,
        }
    except Exception as e:
        return {'url': url, 'error': str(e), 'success': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('url')
    p.add_argument('--name', default=None)
    p.add_argument('--json', action='store_true', dest='as_json')
    args = p.parse_args()

    result = download(args.url, args.name)
    print(json.dumps(result, indent=2))
    if not result.get('success'):
        sys.exit(1)


if __name__ == '__main__':
    main()
