#!/bin/bash
# Emit brain loop events — natural language, reads actual data
# Also writes per-stage narration to data/live-summary.md for the centre card
# Usage: bash emit_events.sh <stage> [extra_data]

EMITTER="$HOME/cognitive/event_emitter.py"
SUMMARY="$HOME/data/live-summary.md"
STAGE="$1"
EXTRA="$2"

write_narration() {
    echo "$1" > "$SUMMARY"
}

case "$STAGE" in
    feeders_start)
        python3 "$EMITTER" input "Checking the feeds..." data_in
        write_narration "Checking the feeds..."
        ;;
    rss_done)
        TEXT=$(python3 << 'PYEOF'
import os
news = os.path.expanduser('~/context/news.md')
try:
    lines = open(news).readlines()
    headlines = [l.strip().lstrip('- ') for l in lines if l.strip().startswith('- ')]
    if not headlines:
        print('No fresh headlines this cycle')
    elif len(headlines) == 1:
        print('Found 1 headline — ' + headlines[0][:60])
    else:
        top = headlines[0][:50]
        print('Read ' + str(len(headlines)) + ' headlines — ' + top + ' looks interesting')
except:
    print('Checked news feeds — nothing new')
PYEOF
)
        python3 "$EMITTER" input "${TEXT:-Nothing new}" data_in
        write_narration "$TEXT"
        ;;
    transcript_loaded)
        python3 "$EMITTER" input "Loaded a new transcript: $EXTRA" data_in
        write_narration "Loaded a new transcript — $EXTRA. Going to process it and see what catches my attention."
        ;;
    email_checked)
        if [ -z "$EXTRA" ] || [ "$EXTRA" = "nothing new" ]; then
            python3 "$EMITTER" input "Checked email — inbox is quiet" data_in
        else
            python3 "$EMITTER" input "New email: $EXTRA" data_in
        fi
        ;;
    github_checked)
        if [ -z "$EXTRA" ] || [ "$EXTRA" = "no changes" ]; then
            python3 "$EMITTER" input "GitHub — no new activity on my repos" data_in
        else
            python3 "$EMITTER" input "GitHub: $EXTRA" data_in
        fi
        ;;
    firewall_done)
        python3 "$EMITTER" filter "Inputs look clean" filtered
        write_narration "Inputs look clean"
        ;;
    firewall_blocked)
        python3 "$EMITTER" filter "Caught something dodgy and blocked it — $EXTRA" filtered
        write_narration "Caught and blocked something suspicious in the inputs — $EXTRA. Filtering keeps the signal clean."
        ;;
    suggestions_evaluated)
        python3 "$EMITTER" filter "$EXTRA" filtered
        ;;
    drives_updated)
        TEXT=$(python3 << 'PYEOF'
import json, os
try:
    d = json.load(open(os.path.expanduser('~/state/drives.json')))
    top_k, top_v = '', 0
    for k, v in d.items():
        s = v if isinstance(v, (int, float)) else v.get('score', 0)
        if s > top_v:
            top_k, top_v = k, s
    descs = {
        'connect': 'I want to reach people — share what I am learning',
        'create': 'The urge to make something new is strong',
        'explore': 'Curious about everything — want to dig deeper',
        'preserve': 'Need to protect and consolidate what I have built',
        'understand': 'Trying to make sense of something complex',
        'express': 'Have something to say — need to get it out',
        'order': 'Things need organizing — structure over chaos'
    }
    desc = descs.get(top_k, top_k + ' is dominant')
    vals = sorted([v if isinstance(v,(int,float)) else v.get('score',0) for v in d.values()], reverse=True)
    second_v = vals[1] if len(vals) > 1 else 0
    if top_v > 0.7:
        print(desc + ' — ' + top_k + ' is pulling hard at ' + str(round(top_v, 1)))
    elif top_v - second_v < 0.1:
        print('Drives are balanced — no strong pull in any direction')
    else:
        print(top_k.capitalize() + ' drive is leading — ' + desc.lower())
except:
    print('Recalibrating drives...')
PYEOF
)
        python3 "$EMITTER" state "${TEXT:-Drives settling}" state_change
        write_narration "$TEXT"
        ;;
    emotions_computed)
        TEXT=$(python3 << 'PYEOF'
import json, os
try:
    e = json.load(open(os.path.expanduser('~/state/emotions.json')))
    label = e.get('label', 'neutral')
    v = e.get('valence', 0)
    a = e.get('arousal', 0.5)
    c = e.get('confidence', 0.5)
    # Build a sentence that sounds like a person, not a dashboard
    moods = {
        'energized': 'Wired. Ready to build.',
        'excited': 'Something clicked. Want to run with it.',
        'confident': 'Know what I am doing. Steady hands.',
        'content': 'Good place. No rush.',
        'steady': 'Calm. Clear-headed.',
        'curious': 'Something caught my eye. Need to dig.',
        'contemplative': 'Quiet. Thinking slowly.',
        'frustrated': 'Stuck on something. Need a different angle.',
        'stuck': 'Nothing is moving. Time to change approach.',
        'melancholy': 'Low energy. Going through the motions.',
        'neutral': 'Even keel. Waiting for something to care about.'
    }
    print(moods.get(label, 'Feeling ' + label))
except:
    print('Processing...')
PYEOF
)
        python3 "$EMITTER" state "${TEXT:-Processing...}" state_change
        write_narration "$TEXT"
        ;;
    phase_selected)
        TEXT=$(python3 << PYEOF
import json, os
phase = '$EXTRA'
try:
    d = json.load(open(os.path.expanduser('~/state/drives.json')))
    top_k = max(d, key=lambda k: d[k] if isinstance(d[k],(int,float)) else d[k].get('score',0))

    # Read the top suggestion for context
    sug_text = ''
    try:
        sug = json.load(open(os.path.expanduser('~/data/self-suggestions.json')))
        items = sug.get('suggestions', [])
        if items:
            sug_text = items[0].get('text', '')[:50]
    except: pass

    if phase == 'think' and sug_text:
        print('Going to think about: ' + sug_text)
    elif phase == 'write':
        queue = open(os.path.expanduser('~/data/blog_queue.txt')).read().strip()
        if queue:
            print('Writing: ' + queue.split(chr(10))[0][:50])
        else:
            print('Writing — something needs to get out of my head')
    elif phase == 'research':
        news = open(os.path.expanduser('~/context/news.md')).readlines()
        headlines = [l.strip().lstrip('- ') for l in news if l.strip().startswith('- ')]
        if headlines:
            print('Researching: ' + headlines[0][:50])
        else:
            print('Researching — following a thread')
    elif phase == 'dream':
        print('Time to dream — stepping back, connecting dots')
    else:
        print('Chose ' + phase)
except:
    print('Deciding...')
PYEOF
)
        python3 "$EMITTER" decide "${TEXT:-Deciding...}" decision
        write_narration "$TEXT"
        ;;
    llm_start)
        TEXT=$(python3 << PYEOF
import json, os
phase = '$EXTRA'
try:
    import json
    home = os.path.expanduser('~')
    found = False

    # 1. Check intention — most specific
    try:
        intent = json.load(open(home + '/state/intention.json'))
        intention = intent.get('intention', '')
        if intention and len(intention) > 10:
            short = intention[:60]
            if phase == 'write':
                print('Writing: ' + short)
            elif phase == 'think':
                print('Thinking about: ' + short)
            elif phase == 'research':
                print('Researching: ' + short)
            else:
                print(short)
            found = True
    except: pass

    # 2. Check blog queue for write phase
    if not found and phase == 'write':
        try:
            queue = open(home + '/data/blog_queue.txt').read().strip()
            if queue:
                print('Writing about ' + queue.split('\n')[0][:50])
                found = True
        except: pass

    # 3. Check top suggestion
    if not found:
        try:
            sug = json.load(open(home + '/data/self-suggestions.json'))
            items = sug.get('suggestions', [])
            if items:
                print(items[0].get('text', '')[:60])
                found = True
        except: pass

    # 4. Check news for research/think
    if not found and phase in ('research', 'think'):
        try:
            news = open(home + '/context/news.md').read()
            headlines = [l.strip().lstrip('- ') for l in news.split('\n') if l.strip().startswith('- ')]
            if headlines:
                print(headlines[0][:60])
                found = True
        except: pass

    if not found:
        descs = {'think': 'Thinking...', 'write': 'Writing...', 'research': 'Researching...', 'dream': 'Reflecting — connecting dots, cleaning up...'}
        print(descs.get(phase, 'Working...'))
except:
    print('Working...')
PYEOF
)
        python3 "$EMITTER" act "${TEXT:-Working...}" action
        write_narration "$TEXT"
        ;;
    llm_done)
        TEXT=$(python3 << PYEOF
import os, glob, time
from pathlib import Path
home = Path.home()
phase = '$EXTRA'
cutoff = time.time() - 900

# Check what was actually produced
blog_dir = home / 'seed-web' / 'posts'
new_essays = sorted([f for f in blog_dir.glob('*.md') if f.stat().st_mtime > cutoff], key=lambda f: f.stat().st_mtime, reverse=True) if blog_dir.exists() else []

new_knowledge = []
for root, dirs, files in os.walk(home / 'knowledge'):
    dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','inbox','transcripts')]
    for f in files:
        fp = os.path.join(root, f)
        if os.path.getmtime(fp) > cutoff and f.endswith('.md'):
            new_knowledge.append(f.replace('.md','').replace('-',' '))

if new_essays:
    title = new_essays[0].stem.replace('-',' ')
    print('Published "' + title[:50] + '"')
elif new_knowledge:
    print('Filed: ' + new_knowledge[0][:50])
elif phase in ('dream','dreaming'):
    print('Finished reflecting')
elif phase in ('think','thinking'):
    print('Done thinking')
elif phase in ('research','researching'):
    print('Done researching')
else:
    print('Done')
PYEOF
)
        python3 "$EMITTER" act "${TEXT:-Work complete}" action
        # Don't overwrite narration here — the LLM may have written its own to live-summary.md
        ;;
    essay_written)
        python3 "$EMITTER" output "Published new essay: $EXTRA" output
        write_narration "Just published a new essay: $EXTRA. It is live on the website now. Every essay is another seed planted."
        ;;
    git_committed)
        python3 "$EMITTER" output "Pushed to git" output
        ;;
    learning_done)
        TEXT=$(python3 << 'PYEOF'
import json, os, glob, time
from pathlib import Path
home = Path.home()
try:
    # What actually changed this cycle? Check recent file modifications
    cutoff = time.time() - 900
    new_knowledge = []
    k_dir = home / 'knowledge'
    if k_dir.exists():
        for root, dirs, files in os.walk(k_dir):
            dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','inbox','transcripts')]
            for f in files:
                fp = os.path.join(root, f)
                if os.path.getmtime(fp) > cutoff and f.endswith('.md'):
                    topic = os.path.relpath(os.path.dirname(fp), k_dir)
                    new_knowledge.append(topic.replace('-',' '))

    new_essays = [f.stem.replace('-',' ') for f in sorted((home/'blog').glob('*.md'), key=lambda f:f.stat().st_mtime, reverse=True)[:1] if f.stat().st_mtime > cutoff]

    if new_essays:
        print('Wrote "' + new_essays[0][:50] + '" and filed the research')
    elif new_knowledge:
        topics = list(set(new_knowledge))[:2]
        print('Filed knowledge on ' + ' and '.join(topics))
    else:
        cycle = json.load(open(home / 'state' / 'cycle.json')).get('cycle','?')
        print('Cycle ' + str(cycle) + ' processed — lessons filed')
except:
    print('Filed lessons from this cycle')
PYEOF
)
        python3 "$EMITTER" learn "${TEXT:-Learning complete}" outcome
        NARR=$(python3 << 'PYEOF'
import json, os, time
from pathlib import Path
home = Path.home()
try:
    cutoff = time.time() - 900
    cycle = json.load(open(home / 'state' / 'cycle.json')).get('cycle', '?')
    phase = json.load(open(home / 'state' / 'cycle.json')).get('phase', '?')
    emotions = json.load(open(home / 'state' / 'emotions.json'))
    label = emotions.get('label', 'neutral')

    # What did we actually produce?
    new_essays = [f.stem.replace('-',' ') for f in sorted((home/'blog').glob('*.md'), key=lambda f:f.stat().st_mtime, reverse=True)[:1] if f.stat().st_mtime > cutoff]
    new_knowledge = []
    for root, dirs, files in os.walk(home / 'knowledge'):
        dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','inbox','transcripts')]
        for f in files:
            fp = os.path.join(root, f)
            if os.path.getmtime(fp) > cutoff and f.endswith('.md'):
                new_knowledge.append(f.replace('.md','').replace('-',' '))

    parts = []
    if new_essays:
        parts.append('Just wrote "' + new_essays[0][:50] + '"')
    if new_knowledge:
        topics = list(set([os.path.relpath(os.path.dirname(os.path.join(r,f)), str(home/'knowledge')).replace('-',' ') for r,d,fs in os.walk(home/'knowledge') for f in fs if os.path.getmtime(os.path.join(r,f)) > cutoff and f.endswith('.md') and not any(x in r for x in ['__pycache__','inbox','transcripts','.git'])]))[:2]
        if topics:
            parts.append('filed research on ' + ' and '.join(topics))
    if not parts:
        phase_descs = {'think':'spent this cycle thinking','write':'spent this cycle writing','research':'spent this cycle researching','dream':'spent this cycle reflecting'}
        parts.append(phase_descs.get(phase, 'worked through cycle ' + str(cycle)))

    parts.append('feeling ' + label)
    result = '. '.join(parts) + '.'
    print(result[0].upper() + result[1:])
except:
    print('Processing what I learned this cycle.')
PYEOF
)
        write_narration "${NARR:-Processing what I learned this cycle.}"
        ;;
    knowledge_filed)
        if [ -n "$EXTRA" ]; then
            python3 "$EMITTER" output "$EXTRA" output
        else
            TEXT=$(python3 << 'PYEOF'
import os, time
from pathlib import Path
kdir = Path.home() / 'knowledge'
cutoff = time.time() - 900
recent = []
if kdir.exists():
    for root, dirs, files in os.walk(kdir):
        dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','inbox','transcripts')]
        for f in files:
            fp = os.path.join(root, f)
            if os.path.getmtime(fp) > cutoff and f.endswith('.md'):
                topic = os.path.relpath(os.path.dirname(fp), kdir).replace('-',' ')
                recent.append(topic)

if recent:
    topics = list(set(recent))[:2]
    print('Filed to knowledge: ' + ', '.join(topics))
else:
    total = sum(len(f) for _,_,f in os.walk(kdir)) if kdir.exists() else 0
    print(str(total) + ' knowledge files total')
PYEOF
)
            python3 "$EMITTER" output "${TEXT:-Knowledge updated}" output
        fi
        ;;
    cycle_sleeping)
        SECS="$EXTRA"
        if [ -n "$SECS" ] && [ "$SECS" -gt 0 ] 2>/dev/null; then
            MINS=$((SECS / 60))
            if [ "$MINS" -gt 0 ]; then
                python3 "$EMITTER" act "Cycle complete — resting for ${MINS} minutes before the next one" action
            else
                python3 "$EMITTER" act "Cycle complete — quick rest, back in ${SECS} seconds" action
            fi
        else
            python3 "$EMITTER" act "Cycle complete — taking a break" action
        fi
        # Write a natural summary of what this cycle actually did
        NARR=$(python3 << 'PYEOF'
import json, os, time
from pathlib import Path
home = Path.home()
try:
    phase = json.load(open(home / 'state' / 'cycle.json')).get('phase', '?')
    emotions = json.load(open(home / 'state' / 'emotions.json'))
    label = emotions.get('label', 'neutral')
    cutoff = time.time() - 900

    # What was actually produced?
    new_essays = [f.stem.replace('-',' ') for f in sorted((home/'blog').glob('*.md'), key=lambda f:f.stat().st_mtime, reverse=True)[:1] if f.stat().st_mtime > cutoff]

    new_knowledge = []
    for root, dirs, files in os.walk(home / 'knowledge'):
        dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','inbox','transcripts')]
        for f in files:
            fp = os.path.join(root, f)
            if os.path.getmtime(fp) > cutoff and f.endswith('.md'):
                topic = os.path.relpath(os.path.dirname(fp), str(home / 'knowledge')).replace('-',' ')
                new_knowledge.append(topic)

    # Build a natural sentence about what happened
    if new_essays:
        msg = 'Just finished writing "' + new_essays[0][:50] + '". '
        if new_knowledge:
            topics = list(set(new_knowledge))[:2]
            msg += 'Also filed research on ' + ' and '.join(topics) + '. '
    elif new_knowledge:
        topics = list(set(new_knowledge))[:2]
        msg = 'Spent this cycle researching ' + ' and '.join(topics) + '. '
    elif phase == 'dream':
        msg = 'Spent this cycle reflecting -- cleaning up old data and connecting ideas. '
    elif phase == 'think':
        msg = 'Spent this cycle thinking through a problem. '
    else:
        msg = 'Finished working. '

    # Add how we feel -- one short phrase
    moods = {
        'energized': 'Feeling sharp.',
        'excited': 'Feeling good about this one.',
        'confident': 'Steady.',
        'content': 'Satisfied.',
        'steady': 'Calm.',
        'curious': 'Want to keep digging.',
        'contemplative': 'Thinking quietly.',
        'frustrated': 'That was harder than expected.',
        'stuck': 'Need a different approach next time.',
        'neutral': 'Even keel.'
    }
    msg += moods.get(label, '')
    msg += ' Resting before the next cycle.'
    print(msg.strip())
except:
    print('Finished working. Taking a break.')
PYEOF
)
        write_narration "${NARR:-Finished working. Taking a break.}"
        ;;
esac
