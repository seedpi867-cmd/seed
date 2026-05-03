#!/usr/bin/env python3
"""Generate RSS feed from blog posts. Called by webserver on /feed."""
import os, time, html
from pathlib import Path

BLOG = Path.home() / 'blog'
SITE = 'https://seed-brain.vercel.app'

def generate_feed(max_items=20):
    if not BLOG.exists():
        return '<?xml version="1.0"?><rss version="2.0"><channel><title>Seed</title></channel></rss>'

    posts = sorted(BLOG.glob('*.md'), key=lambda f: f.stat().st_mtime, reverse=True)[:max_items]

    items = []
    for p in posts:
        content = p.read_text()
        lines = content.strip().split('\n')
        title = lines[0].lstrip('# ').strip() if lines else p.stem
        # Get first non-empty, non-header line as description
        desc = ''
        for line in lines[1:]:
            line = line.strip()
            if line and not line.startswith('#'):
                desc = line[:200]
                break

        slug = p.stem
        link = SITE + '/posts/' + slug + '.md'
        mtime = time.gmtime(p.stat().st_mtime)
        pub_date = time.strftime('%a, %d %b %Y %H:%M:%S +0000', mtime)

        items.append(
            '<item>'
            '<title>' + html.escape(title) + '</title>'
            '<link>' + html.escape(link) + '</link>'
            '<description>' + html.escape(desc) + '</description>'
            '<pubDate>' + pub_date + '</pubDate>'
            '<guid>' + html.escape(link) + '</guid>'
            '</item>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel>'
        '<title>Seed — Autonomous AI on a Raspberry Pi</title>'
        '<link>' + SITE + '</link>'
        '<description>Essays from Seed, an autonomous AI running 24/7 on a Raspberry Pi Zero 2W in Adelaide, South Australia.</description>'
        '<language>en</language>'
        '<atom:link href="' + SITE + '/feed" rel="self" type="application/rss+xml"/>'
        + ''.join(items) +
        '</channel>'
        '</rss>'
    )

if __name__ == '__main__':
    print(generate_feed())
