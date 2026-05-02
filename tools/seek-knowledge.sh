#!/bin/bash
# Actively seek new knowledge from the web
# Pick a random topic from a starting-points file and research it
python3 - << 'PYEOF'
import os, random, urllib.request, json

# Pick a random knowledge domain
domains = ['philosophy', 'science', 'psychology', 'history']
domain = random.choice(domains)
sp = os.path.expanduser(f"~/knowledge/{domain}/starting-points.md")

if not os.path.exists(sp):
    print(f"[seek] No starting points for {domain}")
    exit()

# Read starting points, pick a random topic keyword
lines = [l.strip() for l in open(sp).readlines() if l.strip().startswith('- ')]
if not lines:
    print(f"[seek] No topics in {domain}")
    exit()

topic = random.choice(lines).lstrip('- ').split(' — ')[0].split(' (')[0].strip()
print(f"[seek] Researching: {topic} ({domain})")

# Save as a context prompt for the next cycle
out = os.path.expanduser("~/context/knowledge-prompt.md")
with open(out, 'w') as f:
    f.write(f"## Knowledge Prompt\n\n")
    f.write(f"**Research this:** {topic}\n")
    f.write(f"**Domain:** {domain}\n")
    f.write(f"**Task:** Use tools/web_fetch.py or tools/search_web.py to find information. ")
    f.write(f"Save findings to ~/research/topics/{topic.lower().replace(' ', '-')}.md. ")
    f.write(f"Form an opinion and save to ~/research/opinions/{topic.lower().replace(' ', '-')}.md.\n")
PYEOF
