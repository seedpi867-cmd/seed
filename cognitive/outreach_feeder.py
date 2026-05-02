#!/usr/bin/env python3
"""Find relevant HN/Reddit posts where Seed could add value"""
import urllib.request, json, os, time, sys

sys.path.insert(0, os.path.expanduser('~/cognitive'))
from firewall import sanitise

out = []

for q in ["autonomous+AI+agent", "raspberry+pi+AI", "self-hosted+agent"]:
    try:
        url = f"http://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&hitsPerPage=5"
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        for hit in data.get('hits', []):
            title = hit.get('title', '')
            pts = hit.get('points', 0)
            hn_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
            if pts and pts > 5:
                out.append(f"- HN ({pts}pts): {title} — {hn_url}")
    except:
        pass

for sub in ["SideProject", "raspberry_pi", "artificial", "selfhosted"]:
    try:
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "seed-pi/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        for post in data.get('data', {}).get('children', []):
            d = post['data']
            title = d.get('title', '')
            score = d.get('score', 0)
            link = f"https://reddit.com{d.get('permalink', '')}"
            if score > 3:
                out.append(f"- r/{sub} ({score}pts): {title} — {link}")
    except:
        pass

if out:
    content = f"## Outreach — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
    content += "Posts where a genuine comment could add value:\n\n"
    content += "\n".join(out[:15]) + "\n"
    content = sanitise(content, 'outreach')
    open(os.path.expanduser('~/context/outreach.md'), 'w').write(content)
    print(f"[outreach] {len(out)} opportunities")
else:
    print("[outreach] none found")
