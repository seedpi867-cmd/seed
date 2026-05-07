#!/usr/bin/env python3
"""Check for newly achieved milestones and update goals"""
import json, os, time, urllib.request
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'

def check_milestones():
    goals = open(DATA / 'goals.md').read()
    achieved = []

    # Check GitHub stars/forks
    try:
        req = urllib.request.Request('https://api.github.com/repos/seedpi867-cmd/seed',
            headers={'User-Agent': 'seed-pi'})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        stars = data.get('stargazers_count', 0)
        forks = data.get('forks_count', 0)
    except:
        stars = 0
        forks = 0

    # Check knowledge count
    try:
        kdir = HOME / 'knowledge'
        kcount = sum(1 for _ in kdir.rglob('*.md'))
    except:
        kcount = 0

    if achieved:
        open(DATA / 'goals.md', 'w').write(goals)

    return achieved

if __name__ == '__main__':
    results = check_milestones()
    for r in results:
        print(f'[milestone] {r}')
