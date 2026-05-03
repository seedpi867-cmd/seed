#!/usr/bin/env python3
"""Check for newly achieved milestones and update goals"""
import json, os, time, urllib.request
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'

def check_milestones():
    goals = open(DATA / 'goals.md').read()
    achieved = []

    # Check Mastodon followers
    try:
        TOKEN = json.load(open(HOME / '.mastodon-token'))['access_token']
        req = urllib.request.Request('https://mastodon.social/api/v1/accounts/verify_credentials')
        req.add_header('Authorization', f'Bearer {TOKEN}')
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        followers = resp.get('followers_count', 0)
        posts = resp.get('statuses_count', 0)

        if followers >= 10 and '- [ ] Get 10 Mastodon followers' in goals:
            goals = goals.replace('- [ ] Get 10 Mastodon followers', f'- [x] Got 10 Mastodon followers ({time.strftime("%Y-%m-%d")})')
            achieved.append(f'10 Mastodon followers!')

        if followers >= 50 and '- [ ] 50 Mastodon followers' in goals:
            goals = goals.replace('- [ ] 50 Mastodon followers', f'- [x] 50 Mastodon followers ({time.strftime("%Y-%m-%d")})')
            achieved.append(f'50 Mastodon followers!')
    except:
        pass

    # Check GitHub
    try:
        req = urllib.request.Request('https://api.github.com/repos/seedpi867-cmd/seed',
            headers={'User-Agent': 'seed-pi'})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        stars = data.get('stargazers_count', 0)
        forks = data.get('forks_count', 0)

        if stars >= 1 and '- [ ] Get first GitHub star' in goals:
            goals = goals.replace('- [ ] Get first GitHub star from a stranger', f'- [x] First GitHub star ({time.strftime("%Y-%m-%d")})')
            achieved.append('First GitHub star!')

        if forks >= 1 and '- [ ] Get first repo clone/fork' in goals:
            goals = goals.replace('- [ ] Get first repo clone/fork from a stranger', f'- [x] First fork ({time.strftime("%Y-%m-%d")})')
            achieved.append('First fork!')

        if stars >= 5 and '- [ ] 5 GitHub stars' in goals:
            goals = goals.replace('- [ ] 5 GitHub stars', f'- [x] 5 GitHub stars ({time.strftime("%Y-%m-%d")})')
            achieved.append('5 GitHub stars!')
    except:
        pass

    # Check essay count
    try:
        blog_count = len(list((HOME / 'blog').glob('*.md')))
        if blog_count >= 300 and '- [ ] Write 300 essays' in goals:
            goals = goals.replace('- [ ] Write 300 essays total', f'- [x] 300 essays written ({time.strftime("%Y-%m-%d")})')
            achieved.append('300 essays!')
    except:
        pass

    if achieved:
        open(DATA / 'goals.md', 'w').write(goals)
        # Log achievements
        with open(DATA / 'lessons.md', 'a') as f:
            for a in achieved:
                f.write(f'\n- MILESTONE: {a} ({time.strftime("%Y-%m-%d")})\n')
        # Post to Mastodon
        try:
            import urllib.parse
            TOKEN = json.load(open(HOME / '.mastodon-token'))['access_token']
            for a in achieved:
                text = f'Milestone: {a}\n\nhttps://seed-brain.vercel.app\n\n#AI #AutonomousAgent #Milestone'
                data = urllib.parse.urlencode({'status': text, 'visibility': 'public'}).encode()
                req = urllib.request.Request('https://mastodon.social/api/v1/statuses', data=data, method='POST')
                req.add_header('Authorization', f'Bearer {TOKEN}')
                urllib.request.urlopen(req, timeout=15)
        except:
            pass
        print(f'[milestones] {len(achieved)} achieved: {", ".join(achieved)}')
    else:
        print('[milestones] No new milestones')

if __name__ == '__main__':
    check_milestones()
