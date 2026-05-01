#!/bin/bash
python3 - << 'PYEOF'
import urllib.request, xml.etree.ElementTree as ET, time, os
FEEDS = [
    ('Hacker News', 'https://news.ycombinator.com/rss'),
    ('Reuters', 'https://feeds.reuters.com/reuters/topNews'),
    ('ArsTechnica', 'https://feeds.arstechnica.com/arstechnica/index'),
]
out = f"## News — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
for name, url in FEEDS:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Seed/1.0'})
        data = urllib.request.urlopen(req, timeout=10).read(65536)
        items = []
        for item in ET.fromstring(data).iter('item'):
            t = (item.findtext('title') or '').strip()
            if t: items.append(t)
            if len(items) >= 5: break
        if items:
            out += f"### {name}\n"
            for t in items: out += f"- {t}\n"
            out += "\n"
    except: pass
open(os.path.expanduser('~/context/news.md'), 'w').write(out)
PYEOF
