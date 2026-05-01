#!/usr/bin/env python3
"""
search_web.py — DuckDuckGo web search (no API key needed).
Uses DDG's lite HTML endpoint and scrapes result titles/URLs/snippets.
Usage: python3 search_web.py "query" [--results N] [--json]
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser


class DDGParser(HTMLParser):
    """Parse DuckDuckGo HTML lite results."""

    def __init__(self):
        super().__init__()
        self.results   = []
        self._in_link  = False
        self._in_snip  = False
        self._cur      = {}
        self._depth    = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            href = attrs['href']
            if href.startswith('http') and 'duckduckgo.com' not in href:
                self._cur = {'url': href, 'title': '', 'snippet': ''}
                self._in_link = True
        if tag in ('td', 'span') and attrs.get('class') in ('result-snippet',):
            self._in_snip = True

    def handle_endtag(self, tag):
        if tag == 'a' and self._in_link:
            self._in_link = False
            if self._cur.get('url') and self._cur.get('title'):
                self.results.append(dict(self._cur))
                self._cur = {}
        if tag in ('td', 'span'):
            self._in_snip = False

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        if self._in_link:
            self._cur['title'] = (self._cur.get('title', '') + ' ' + data).strip()
        elif self._in_snip and self._cur:
            self._cur['snippet'] = (self._cur.get('snippet', '') + ' ' + data).strip()


def search(query: str, max_results: int = 5) -> list:
    q = urllib.parse.quote_plus(query)
    url = f'https://lite.duckduckgo.com/lite/?q={q}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; SEED-Agent/1.0)',
        'Accept-Language': 'en-AU,en;q=0.9',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return [{'error': str(e)}]

    parser = DDGParser()
    parser.feed(html)
    results = parser.results[:max_results]

    # Deduplicate by URL
    seen = set()
    deduped = []
    for r in results:
        if r['url'] not in seen:
            seen.add(r['url'])
            deduped.append(r)

    return deduped[:max_results]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('query')
    p.add_argument('--results', type=int, default=5)
    p.add_argument('--json',    action='store_true', dest='as_json')
    args = p.parse_args()

    results = search(args.query, args.results)

    if args.as_json or not results:
        print(json.dumps(results, indent=2))
    else:
        for i, r in enumerate(results, 1):
            print(f'{i}. {r.get("title", "?")}')
            print(f'   {r.get("url", "")}')
            if r.get('snippet'):
                print(f'   {r["snippet"][:150]}')
            print()


if __name__ == '__main__':
    main()
