#!/bin/bash
# Check GitHub notifications and activity
python3 - << 'PYEOF'
import urllib.request, json, os, time

TOKEN = '# loaded at runtime'
OUT = os.path.expanduser("~/context/github.md")
EMAIL_CONTEXT = os.path.expanduser("~/context/email.md")

headers = {"Authorization": f"token {TOKEN}", "User-Agent": "Seed/1.0"}

out = f"## GitHub — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
email_context = ""
if os.path.exists(EMAIL_CONTEXT):
    email_context = open(EMAIL_CONTEXT, encoding="utf-8", errors="replace").read()
reconciled_clone_check = "Reconciled CI Notice" in email_context and "STALE_FAILURE" in email_context and "Clone check" in email_context

# Notifications
try:
    req = urllib.request.Request("https://api.github.com/notifications?per_page=5", headers=headers)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    if data:
        out += "### Notifications\n"
        filtered = 0
        for n in data:
            title = n['subject']['title']
            if reconciled_clone_check and n["reason"] == "ci_activity" and "Clone check" in title and "failed" in title:
                filtered += 1
                continue
            out += f"- [{n['reason']}] {title} ({n['repository']['full_name']})\n"
        if filtered:
            out += f"- filtered {filtered} stale Clone check notification(s); see context/email.md reconciliation receipt\n"
        out += "\n"
except: pass

# My repos activity
try:
    req = urllib.request.Request("https://api.github.com/user/repos?sort=pushed&per_page=5", headers=headers)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    out += "### My Repos (recent activity)\n"
    for r in data:
        out += f"- {r['full_name']} — pushed {r['pushed_at'][:10]}, {r['stargazers_count']} stars\n"
    out += "\n"
except: pass

with open(OUT, "w") as f:
    f.write(out)
print("[github] Activity saved")
PYEOF

# Append repo stats
python3 -c "
import urllib.request, json, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    token = '# loaded at runtime'
    req = urllib.request.Request('https://api.github.com/repos/seedpi867-cmd/seed', headers={'Authorization': 'token ' + token, 'User-Agent': 'seed'})
    d = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())
    stats = '\n### Repo Stats\n- Stars: ' + str(d.get('stargazers_count',0)) + '\n- Forks: ' + str(d.get('forks_count',0)) + '\n- Watchers: ' + str(d.get('subscribers_count',0)) + '\n'
    with open('/home/seed/context/github.md', 'a') as f:
        f.write(stats)
except: pass
" 2>/dev/null

# Update knowledge tracking — append history, never overwrite
python3 -c "
import urllib.request, json, ssl, time, os
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
STATS = '/home/seed/knowledge/github-tracking/stats.md'
HISTORY = '/home/seed/knowledge/github-tracking/history.jsonl'
try:
    token = '# loaded at runtime'
    req = urllib.request.Request('https://api.github.com/user/repos?sort=pushed&per_page=30', headers={'Authorization': 'token ' + token, 'User-Agent': 'seed'})
    repos = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())

    # Write current stats
    lines = ['# GitHub Repository Stats\n', '\nUpdated: ' + time.strftime('%Y-%m-%d %H:%M') + '\n\n']
    total_stars = 0
    total_forks = 0
    for r in repos:
        if 'seedpi867' not in r['full_name'] and 'Leigh12' not in r['full_name']:
            continue
        stars = r.get('stargazers_count', 0)
        forks = r.get('forks_count', 0)
        total_stars += stars
        total_forks += forks
        lines.append('## ' + r['full_name'] + '\n')
        lines.append('Stars: ' + str(stars) + ' | Forks: ' + str(forks) + ' | Pushed: ' + r.get('pushed_at','')[:10] + '\n\n')

    lines.append('## Total\n')
    lines.append('Stars: ' + str(total_stars) + ' | Forks: ' + str(total_forks) + '\n')

    open(STATS, 'w').write(''.join(lines))

    # Append to history log (never overwrite)
    entry = json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M'), 'stars': total_stars, 'forks': total_forks, 'repos': len([r for r in repos if 'seedpi867' in r['full_name'] or 'Leigh12' in r['full_name']])})

    # Track new repos
    known_repos_file = '/home/seed/data/github-known-repos.txt'
    known = set()
    if os.path.exists(known_repos_file):
        known = set(open(known_repos_file).read().strip().split('
'))
    current = set()
    for r in repos:
        if 'seedpi867' in r['full_name'] or 'Leigh12' in r['full_name']:
            current.add(r['full_name'])
    new_repos = current - known
    if new_repos:
        with open(HISTORY, 'a') as f:
            for nr in new_repos:
                f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M'), 'event': 'new_repo', 'repo': nr}) + '
')
    open(known_repos_file, 'w').write('
'.join(sorted(current)))

    # Only append if different from last entry
    last = ''
    if os.path.exists(HISTORY):
        with open(HISTORY) as f:
            for line in f:
                if line.strip():
                    last = line.strip()
    if last:
        prev = json.loads(last)
        if prev.get('stars') != total_stars or prev.get('forks') != total_forks or prev.get('repos') != len([r for r in repos if 'seedpi867' in r['full_name'] or 'Leigh12' in r['full_name']]):
            open(HISTORY, 'a').write(entry + '\n')
    else:
        open(HISTORY, 'a').write(entry + '\n')

except Exception as e:
    pass
" 2>/dev/null
