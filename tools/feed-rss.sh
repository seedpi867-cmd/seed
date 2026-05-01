#!/bin/bash
# Fetch RSS headlines and drop into context
python3 - << 'PYEOF'
import urllib.request, xml.etree.ElementTree as ET, time, os

FEEDS = [
    ('ABC News AU', 'https://www.abc.net.au/news/feed/10888370/rss.xml'),
    ('Reuters', 'https://feeds.reuters.com/reuters/topNews'),
    ('Hacker News', 'https://news.ycombinator.com/rss'),
    ('ArsTechnica', 'https://feeds.arstechnica.com/arstechnica/index'),
    ('AI News', 'https://buttondown.com/ainews/rss'),
]

out = f'## World News — {time.strftime("%Y-%m-%d %H:%M")}\n\n'

for name, url in FEEDS:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SEED/1.0'})
        data = urllib.request.urlopen(req, timeout=10).read(65536)
        root = ET.fromstring(data)
        items = []
        for item in root.iter('item'):
            t = (item.findtext('title') or '').strip()
            if t: items.append(t)
            if len(items) >= 5: break
        if items:
            out += f'### {name}\n'
            for t in items: out += f'- {t}\n'
            out += '\n'
    except Exception as e:
        pass

home = os.path.expanduser('~')
with open(f'{home}/context/news.md', 'w') as f:
    f.write(out)
print(f'[rss] Fetched headlines')
PYEOF
