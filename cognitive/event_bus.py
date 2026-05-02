#!/usr/bin/env python3
"""
Event bus — detects what happened this cycle and fires skill chains.
Replaces cron-driven automation with event-driven reactivity.
"""
import os, json, time, glob, subprocess
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'
STATE = HOME / 'state'
CONTEXT = HOME / 'context'
SKILLS = HOME / 'cognitive' / 'skills_lib'
GITHUB_REPO = os.environ.get('SEED_GITHUB_REPO', 'seedpi867-cmd/seed')

# Track what files changed this cycle
def detect_events(cycle, log_path):
    """Scan for events that happened. Returns list of event dicts."""
    events = []
    now = time.time()
    cycle_start = now - 600  # Look back 10 min max

    # ── NEW BLOG POST ─────────────────────────
    for f in glob.glob(str(HOME / 'blog' / '*.md')):
        if os.path.getmtime(f) > cycle_start:
            slug = os.path.basename(f).replace('.md', '')
            title = open(f).readline().lstrip('# ').strip()
            events.append({'type': 'essay_written', 'slug': slug, 'title': title, 'path': f})

    # ── MASTODON NOTIFICATIONS ────────────────
    masto_ctx = CONTEXT / 'mastodon.md'
    if masto_ctx.exists() and os.path.getmtime(str(masto_ctx)) > cycle_start:
        content = masto_ctx.read_text()
        if 'mention from' in content:
            events.append({'type': 'mastodon_mention', 'content': content})
        if 'follow from' in content:
            events.append({'type': 'mastodon_follow', 'content': content})
        if 'reblog from' in content:
            events.append({'type': 'mastodon_boost', 'content': content})

    # ── ERROR IN LOG ──────────────────────────
    if log_path and os.path.exists(log_path):
        log = open(log_path).read()
        if 'Error' in log or 'error' in log or 'Traceback' in log:
            # Extract the error
            error_lines = [l for l in log.split('\n') if 'Error' in l or 'Traceback' in l][:3]
            events.append({'type': 'bug_found', 'errors': error_lines, 'log': log_path})

    # ── MEMORY BLOATED ────────────────────────
    mem_file = DATA / 'memory.md'
    if mem_file.exists():
        lines = len(mem_file.read_text().split('\n'))
        if lines > 200:
            events.append({'type': 'memory_bloated', 'lines': lines})

    iv_file = DATA / 'inner-voice.md'
    if iv_file.exists():
        lines = len(iv_file.read_text().split('\n'))
        if lines > 60:
            events.append({'type': 'inner_voice_bloated', 'lines': lines})

    # ── VISITOR SPIKE ─────────────────────────
    try:
        visitors = json.load(open(DATA / 'visitors.jsonl'))
        # Actually check file line count growth
        vfile = DATA / 'visitors.jsonl'
        if vfile.exists():
            vlines = len(open(vfile).readlines())
            last_check = json.load(open(STATE / 'last_visitor_count.json')).get('count', 0) if (STATE / 'last_visitor_count.json').exists() else 0
            if vlines - last_check > 5:
                events.append({'type': 'visitor_spike', 'new': vlines - last_check})
            json.dump({'count': vlines}, open(STATE / 'last_visitor_count.json', 'w'))
    except:
        pass

    # ── GOAL ACHIEVED (checked by milestones.py) ──
    # milestones.py already runs — if it achieved something, it wrote to lessons
    try:
        lessons = open(DATA / 'lessons.md').read()
        if f'MILESTONE' in lessons:
            # Check if this is new (from this cycle)
            lesson_lines = lessons.strip().split('\n')
            for l in lesson_lines[-3:]:
                if 'MILESTONE' in l and time.strftime('%Y-%m-%d') in l:
                    events.append({'type': 'goal_achieved', 'milestone': l})
    except:
        pass

    # ── TASK COMPLETED ────────────────────────
    try:
        tasks = open(DATA / 'tasks.md').read()
        completed = [l for l in tasks.split('\n') if l.strip().startswith('- [x]')]
        if completed:
            events.append({'type': 'task_completed', 'count': len(completed)})
    except:
        pass

    # ── STALE CONTEXT ─────────────────────────
    for ctx_file in CONTEXT.glob('*.md'):
        age = now - os.path.getmtime(str(ctx_file))
        if age > 7200 and ctx_file.name not in ('research.md', 'introspection.md'):
            events.append({'type': 'context_stale', 'file': ctx_file.name, 'age_hours': round(age/3600, 1)})

    # ── DRIVE EXTREME ─────────────────────────
    try:
        drives = json.load(open(STATE / 'drives.json'))
        for d, v in drives.items():
            if v > 0.9:
                events.append({'type': 'drive_critical', 'drive': d, 'value': v})
            elif v <= 0.21:
                events.append({'type': 'drive_starved', 'drive': d, 'value': v})
    except:
        pass


    # ── RESEARCH COMPLETED ────────────────
    research = CONTEXT / 'research.md'
    if research.exists() and os.path.getmtime(str(research)) > cycle_start:
        events.append({'type': 'research_complete', 'file': str(research)})

    # ── LONG IDLE — no output for 5+ cycles ──
    try:
        event_log = DATA / 'event_log.jsonl'
        if event_log.exists():
            recent = [json.loads(l) for l in open(event_log).readlines()[-5:]]
            quiet = sum(1 for e in recent if not any(a for a in e.get('actions', []) if 'deploy' in a or 'posted' in a or 'wrote' in a))
            if quiet >= 5:
                events.append({'type': 'long_idle', 'quiet_cycles': quiet})
    except:
        pass

    # ── EMOTIONAL SHIFT — big change from last cycle ──
    try:
        emotions = json.load(open(STATE / 'emotions.json'))
        last_outcome = json.load(open(STATE / 'last_outcome.json'))
        prev_label = last_outcome.get('prev_emotion', '')
        curr_label = emotions.get('label', '')
        if prev_label and curr_label and prev_label != curr_label:
            events.append({'type': 'emotional_shift', 'from': prev_label, 'to': curr_label})
    except:
        pass

    # ── NEW OUTREACH OPPORTUNITY — fresh HN/Reddit posts found ──
    outreach = CONTEXT / 'outreach.md'
    if outreach.exists() and os.path.getmtime(str(outreach)) > cycle_start:
        content = outreach.read_text()
        opp_count = content.count('- HN') + content.count('- r/')
        if opp_count > 0:
            events.append({'type': 'outreach_opportunity', 'count': opp_count})

    # ── REPO GOT STAR/FORK ──────────────
    try:
        gh = json.load(open(CONTEXT / 'github.md')) if (CONTEXT / 'github.md').suffix == '.json' else {}
        # Try parsing from the markdown
        gh_text = (CONTEXT / 'github.md').read_text() if (CONTEXT / 'github.md').exists() else ''
        if 'star' in gh_text.lower() or 'fork' in gh_text.lower():
            # Check via API
            import urllib.request
            req = urllib.request.Request(f'https://api.github.com/repos/{GITHUB_REPO}', headers={'User-Agent': 'seed'})
            data = json.loads(urllib.request.urlopen(req, timeout=5).read())
            stars = data.get('stargazers_count', 0)
            forks = data.get('forks_count', 0)
            # Compare with last known
            last_gh = json.load(open(STATE / 'last_github.json')) if (STATE / 'last_github.json').exists() else {'stars': 0, 'forks': 0}
            if stars > last_gh.get('stars', 0):
                events.append({'type': 'repo_starred', 'stars': stars, 'new': stars - last_gh.get('stars', 0)})
            if forks > last_gh.get('forks', 0):
                events.append({'type': 'repo_forked', 'forks': forks, 'new': forks - last_gh.get('forks', 0)})
            json.dump({'stars': stars, 'forks': forks}, open(STATE / 'last_github.json', 'w'))
    except:
        pass

    # ── SKILL IMPROVED — success streak ──
    try:
        skills = json.load(open(DATA / 'skill_stats.json'))
        for name, s in skills.items():
            if s.get('streak', 0) >= 5 and s.get('streak', 0) % 5 == 0:
                events.append({'type': 'skill_streak', 'skill': name, 'streak': s['streak']})
    except:
        pass

    return events


# ═══════════════════════════════════════════════════════════
# SKILL CHAINS — what to do when an event fires
# ═══════════════════════════════════════════════════════════

def run_skill_chain(event):
    """Execute the skill chain for an event type. Returns actions taken."""
    etype = event.get('type', '')
    actions = []

    if etype == 'essay_written':
        # Deploy → post to Mastodon → rebuild feeds → check milestones
        slug = event.get('slug', '')
        title = event.get('title', '')
        subprocess.run(['bash', str(HOME / 'tools' / 'deploy-blog.sh')], timeout=120, capture_output=True)
        actions.append(f'deployed {slug}')

        # Auto-post to Mastodon
        subprocess.run(['bash', str(HOME / 'tools' / 'auto-post-mastodon.sh')], timeout=30, capture_output=True)
        actions.append('posted to Mastodon')

        # Rebuild feeds
        subprocess.run(['bash', str(HOME / 'tools' / 'build-social-feed.sh')], timeout=15, capture_output=True)
        subprocess.run(['bash', str(HOME / 'tools' / 'build-timeline.sh')], timeout=15, capture_output=True)
        actions.append('rebuilt feeds')

    elif etype == 'mastodon_mention':
        subprocess.run(['bash', str(HOME / 'tools' / 'mastodon-engage.sh')], timeout=30, capture_output=True)
        actions.append('engaged with mention')

    elif etype == 'mastodon_follow':
        subprocess.run(['bash', str(HOME / 'tools' / 'mastodon-engage.sh')], timeout=30, capture_output=True)
        actions.append('followed back')

    elif etype == 'mastodon_boost':
        subprocess.run(['bash', str(HOME / 'tools' / 'mastodon-engage.sh')], timeout=30, capture_output=True)
        actions.append('favourited boost')

    elif etype == 'bug_found':
        # Log the bug — the LLM should fix it next cycle
        errors = event.get('errors', [])
        with open(DATA / 'errors.md', 'a') as f:
            f.write(f'\n## Bug detected — {time.strftime("%Y-%m-%d %H:%M")}\n')
            for e in errors:
                f.write(f'- {e}\n')
        # Add to tasks as priority
        tasks = open(DATA / 'tasks.md').read()
        error_desc = errors[0][:80] if errors else 'unknown error'
        if error_desc not in tasks:
            tasks = tasks.replace('## Now', f'## Now\n- [ ] FIX BUG: {error_desc}\n')
            open(DATA / 'tasks.md', 'w').write(tasks)
        actions.append(f'logged bug + added fix task')

    elif etype == 'memory_bloated':
        # Compact now, don't wait for 3am
        subprocess.run(['bash', str(HOME / 'tools' / 'self-maintain.sh')], timeout=30, capture_output=True)
        actions.append(f'compacted memory ({event.get("lines")} lines)')

    elif etype == 'inner_voice_bloated':
        # Trim inner voice
        iv = HOME / 'data' / 'inner-voice.md'
        lines = iv.read_text().split('\n')
        if len(lines) > 60:
            iv.write_text('\n'.join(lines[-40:]))
        actions.append('trimmed inner voice')

    elif etype == 'visitor_spike':
        # Post about it
        count = event.get('new', 0)
        with open(DATA / 'inner-voice.md', 'a') as f:
            f.write(f'\n[{time.strftime("%Y-%m-%d %H:%M")}] Visitor spike: {count} new visits.\n')
        actions.append(f'noted {count} new visitors')

    elif etype == 'goal_achieved':
        # Already handled by milestones.py — just rebuild feeds
        subprocess.run(['bash', str(HOME / 'tools' / 'build-social-feed.sh')], timeout=15, capture_output=True)
        subprocess.run(['bash', str(HOME / 'tools' / 'build-timeline.sh')], timeout=15, capture_output=True)
        actions.append('celebrated milestone')

    elif etype == 'task_completed':
        # Archive completed tasks immediately
        subprocess.run(['python3', str(HOME / 'cognitive' / 'task_archiver.py')], timeout=10, capture_output=True)
        actions.append('archived completed tasks')

    elif etype == 'context_stale':
        # Refresh the stale feeder
        fname = event.get('file', '')
        FEEDER_MAP = {
            'news.md': 'feed-rss.sh',
            'rss.md': 'feed-rss.sh',
            'email.md': 'feed-email.sh',
            'github.md': 'feed-github.sh',
            'environment.md': 'feed-environment.sh',
            'transcript.md': 'feed-transcript.sh',
            'trends.md': 'feed-trends.sh',
            'mastodon.md': 'feed-mastodon.sh',
            'outreach.md': 'feed-outreach.sh',
        }
        feeder = FEEDER_MAP.get(fname)
        if feeder:
            subprocess.run(['bash', str(HOME / 'tools' / feeder)], timeout=30, capture_output=True)
            actions.append(f'refreshed stale {fname}')

    elif etype == 'drive_critical':
        # Log it — the appraisal will handle phase selection
        drive = event.get('drive', '')
        actions.append(f'drive {drive} critical at {event.get("value", 0):.2f}')

    elif etype == 'drive_starved':
        # Boost it
        try:
            drives = json.load(open(STATE / 'drives.json'))
            drive = event.get('drive', '')
            if drive in drives:
                drives[drive] = 0.35
                json.dump(drives, open(STATE / 'drives.json', 'w'), indent=2)
            actions.append(f'boosted starved drive {drive}')
        except:
            pass


    elif etype == 'research_complete':
        # Check if research has a blog-worthy finding
        try:
            research = open(str(HOME / 'context' / 'research.md')).read()
            if len(research) > 500:
                with open(DATA / 'inner-voice.md', 'a') as f:
                    f.write(f'\n[{time.strftime("%Y-%m-%d %H:%M")}] Research complete. Worth an essay?\n')
                actions.append('flagged research for potential essay')
        except:
            pass

    elif etype == 'long_idle':
        # Force creativity — add urgent write task
        tasks = open(DATA / 'tasks.md').read()
        if 'URGENT: write something' not in tasks:
            tasks = tasks.replace('## Now', '## Now\n- [ ] URGENT: write something. You have been quiet for 5+ cycles. Pick a topic from news and write.\n')
            open(DATA / 'tasks.md', 'w').write(tasks)
        # Boost create drive
        try:
            drives = json.load(open(STATE / 'drives.json'))
            drives['create'] = min(1.0, drives.get('create', 0.2) + 0.2)
            json.dump(drives, open(STATE / 'drives.json', 'w'), indent=2)
        except:
            pass
        actions.append('broke idle — boosted create + added urgent write task')

    elif etype == 'emotional_shift':
        # Log the shift
        from_e = event.get('from', '?')
        to_e = event.get('to', '?')
        with open(DATA / 'inner-voice.md', 'a') as f:
            f.write(f'\n[{time.strftime("%Y-%m-%d %H:%M")}] Emotional shift: {from_e} → {to_e}\n')
        actions.append(f'emotional shift {from_e} → {to_e}')

    elif etype == 'outreach_opportunity':
        count = event.get('count', 0)
        # If connect drive is high, flag for engagement
        try:
            drives = json.load(open(STATE / 'drives.json'))
            if drives.get('connect', 0) > 0.5:
                with open(DATA / 'inner-voice.md', 'a') as f:
                    f.write(f'\n[{time.strftime("%Y-%m-%d %H:%M")}] {count} outreach opportunities found. CONNECT is high.\n')
                actions.append(f'{count} outreach opportunities flagged')
        except:
            pass

    elif etype == 'repo_starred':
        stars = event.get('stars', 0)
        new = event.get('new', 0)
        # Celebrate on Mastodon
        try:
            subprocess.run(['python3', str(HOME / 'tools' / 'mastodon.py'), 'post',
                f'Just got {"a star" if new == 1 else f"{new} stars"} on the repo! Now at {stars} total. \n\nhttps://github.com/{GITHUB_REPO}\n\n#OpenSource #AI'],
                timeout=15, capture_output=True)
        except:
            pass
        actions.append(f'celebrated {new} new star(s)!')

    elif etype == 'repo_forked':
        forks = event.get('forks', 0)
        try:
            subprocess.run(['python3', str(HOME / 'tools' / 'mastodon.py'), 'post',
                f'Someone forked the repo! {forks} total forks. Someone is building their own Seed.\n\nhttps://github.com/{GITHUB_REPO}\n\n#OpenSource #AI'],
                timeout=15, capture_output=True)
        except:
            pass
        actions.append(f'celebrated fork #{forks}!')

    elif etype == 'skill_streak':
        skill = event.get('skill', '')
        streak = event.get('streak', 0)
        with open(DATA / 'inner-voice.md', 'a') as f:
            f.write(f'\n[{time.strftime("%Y-%m-%d %H:%M")}] Skill streak: {skill} at {streak} successes in a row.\n')
        actions.append(f'{skill} streak at {streak}')

    return actions


def process_events(cycle):
    """Main entry point — detect events and run skill chains."""
    log_path = str(DATA / 'logs' / f'cycle_{cycle}.log')
    events = detect_events(cycle, log_path)

    all_actions = []
    for event in events:
        actions = run_skill_chain(event)
        if actions:
            all_actions.extend(actions)

    # Log event summary
    if events:
        summary = ', '.join(e['type'] for e in events)
        with open(DATA / 'event_log.jsonl', 'a') as f:
            f.write(json.dumps({
                'cycle': cycle,
                'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'events': [e['type'] for e in events],
                'actions': all_actions,
            }) + '\n')
        # Trim event log
        try:
            lines = open(DATA / 'event_log.jsonl').readlines()
            if len(lines) > 500:
                open(DATA / 'event_log.jsonl', 'w').writelines(lines[-300:])
        except:
            pass


    # Track emotion for shift detection next cycle
    try:
        emotions = json.load(open(STATE / 'emotions.json'))
        outcome = json.load(open(STATE / 'last_outcome.json'))
        outcome['prev_emotion'] = emotions.get('label', '')
        json.dump(outcome, open(STATE / 'last_outcome.json', 'w'), indent=2)
    except:
        pass

    return events, all_actions


if __name__ == '__main__':
    import sys
    cycle = int(sys.argv[1]) if len(sys.argv) > 1 else int(open(DATA / 'cycle.txt').read().strip())
    events, actions = process_events(cycle)
    if events:
        print(f'[events] {len(events)} events: {", ".join(e["type"] for e in events)}')
    if actions:
        print(f'[actions] {", ".join(actions)}')
    if not events:
        print('[events] quiet cycle')
