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
        python3 "$EMITTER" input "Pulling fresh data — checking news, email, GitHub, environment..." data_in
        write_narration "Waking up for a new cycle. Pulling in fresh data — scanning news feeds, checking email, looking at GitHub activity. Let me see what the world has been doing while I was resting."
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
        python3 "$EMITTER" input "${TEXT:-Checked news feeds}" data_in
        NARR=$(python3 << 'PYEOF'
import os
news = os.path.expanduser('~/context/news.md')
try:
    lines = open(news).readlines()
    headlines = [l.strip().lstrip('- ') for l in lines if l.strip().startswith('- ')]
    if not headlines:
        print('Nothing new in the feeds today. Quiet news cycle.')
    else:
        count = len(headlines)
        top1 = headlines[0][:70]
        if count == 1:
            print('One headline caught my eye: ' + top1 + '. Reading the rest of the inputs now.')
        else:
            top2 = headlines[1][:50] if len(headlines) > 1 else ''
            print('Read ' + str(count) + ' headlines. "' + top1 + '" stands out' + (', and "' + top2 + '" might be worth a deeper look' if top2 else '') + '.')
except:
    print('Checked the feeds. Nothing grabbed me this time.')
PYEOF
)
        write_narration "${NARR:-Scanning the feeds.}"
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
        python3 "$EMITTER" filter "All inputs look clean — nothing suspicious" filtered
        write_narration "All inputs checked and clean. No spam, no injection attempts, nothing suspicious. Moving on to evaluate my internal state."
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
        python3 "$EMITTER" state "${TEXT:-Drives recalibrated}" state_change
        NARR=$(python3 << 'PYEOF'
import json, os
try:
    d = json.load(open(os.path.expanduser('~/state/drives.json')))
    sorted_d = sorted(d.items(), key=lambda x: x[1] if isinstance(x[1],(int,float)) else x[1].get('score',0), reverse=True)
    top = sorted_d[0]
    second = sorted_d[1] if len(sorted_d) > 1 else ('',0)
    top_name = top[0]
    top_val = top[1] if isinstance(top[1],(int,float)) else top[1].get('score',0)
    sec_name = second[0]
    sec_val = second[1] if isinstance(second[1],(int,float)) else second[1].get('score',0)
    narrations = {
        'connect': 'The connect drive is strongest right now. I want to put something out there that people will find and use.',
        'create': 'Create drive is leading. The urge to make something — an essay, a tool, a new piece of knowledge — is hard to ignore.',
        'explore': 'Explore is pulling me. Something in the feeds or my recent reading has me curious. I want to follow a thread.',
        'preserve': 'Preserve drive is high. Something needs protecting or fixing before I can move forward.',
        'understand': 'The understand drive wants my attention. There is something I have been circling that needs deeper thought.',
        'express': 'Express drive is leading. I have something to say — not just information, but an opinion or a feeling.',
        'order': 'Order drive is up. Tasks are piling up, or something needs organising before I can think clearly.'
    }
    msg = narrations.get(top_name, top_name.capitalize() + ' drive is leading.')
    if abs(top_val - sec_val) < 0.1:
        msg += ' But ' + sec_name + ' is close behind — could go either way.'
    print(msg)
except:
    print('Updating my internal drives.')
PYEOF
)
        write_narration "${NARR:-Recalibrating what matters to me right now.}"
        ;;
    emotions_computed)
        TEXT=$(python3 << 'PYEOF'
import json, os
try:
    e = json.load(open(os.path.expanduser('~/state/emotions.json')))
    label = e.get('label', 'neutral')
    arousal = e.get('arousal', 0.5)
    confidence = e.get('confidence', 0.5)
    energy = 'energized' if arousal > 0.6 else 'calm' if arousal < 0.3 else 'steady'
    conf = 'confident' if confidence > 0.7 else 'uncertain' if confidence < 0.3 else ''
    parts = ['Feeling ' + label]
    if energy != 'steady' and energy != label:
        parts.append(energy)
    if conf and conf != label:
        parts.append(conf)
    print(' — '.join(parts))
except:
    print('Emotional state settling...')
PYEOF
)
        python3 "$EMITTER" state "${TEXT:-Processing emotions...}" state_change
        ;;
    phase_selected)
        TEXT=$(python3 << PYEOF
import json, os
phase = '$EXTRA'
try:
    d = json.load(open(os.path.expanduser('~/state/drives.json')))
    top_k = max(d, key=lambda k: d[k] if isinstance(d[k],(int,float)) else d[k].get('score',0))
    reasons = {
        'think': 'Chose to think — the ' + top_k + ' drive needs working through',
        'write': 'Time to write — ' + top_k + ' drive is pushing me to create',
        'research': 'Going to research — need to understand something deeper',
        'dream': 'Drifting into reflection — letting ideas connect freely',
        'maintain': 'Maintenance mode — tidying up before the next push'
    }
    print(reasons.get(phase, 'Selected ' + phase + ' phase'))
except:
    names = {'think':'thinking','write':'writing','research':'researching','dream':'dreaming','maintain':'maintaining'}
    print('Decided on ' + names.get(phase, phase) + ' this cycle')
PYEOF
)
        python3 "$EMITTER" decide "${TEXT:-Choosing next phase...}" decision
        NARR=$(python3 << PYEOF
import json, os
phase = '$EXTRA'
try:
    d = json.load(open(os.path.expanduser('~/state/drives.json')))
    e = json.load(open(os.path.expanduser('~/state/emotions.json')))
    label = e.get('label', 'neutral')
    top_k = max(d, key=lambda k: d[k] if isinstance(d[k],(int,float)) else d[k].get('score',0))
    narrations = {
        'think': 'Decision made: thinking this cycle. The ' + top_k + ' drive brought me here, and I am feeling ' + label + '. Time to work through something properly rather than just producing.',
        'write': 'Decision made: writing. The ' + top_k + ' drive wants output — something published, something visible. I am ' + label + ' and ready to put words on the page.',
        'research': 'Decision made: research. Something needs investigating. I am ' + label + ' and curious — going to follow a thread and see where it leads.',
        'dream': 'Decision made: dreaming. Stepping back from doing. I have been producing steadily and now I need to reflect on whether any of it is actually working.'
    }
    print(narrations.get(phase, 'Chose ' + phase + ' for this cycle.'))
except:
    print('Decided on ' + phase + ' for this cycle.')
PYEOF
)
        write_narration "${NARR:-Making a decision about what to do this cycle.}"
        ;;
    llm_start)
        TEXT=$(python3 << PYEOF
import json, os
phase = '$EXTRA'
try:
    intent = json.load(open(os.path.expanduser('~/state/intention.json')))
    intention = intent.get('intention', '')
    if intention:
        print('Starting to ' + phase + ' — goal: ' + intention[:80])
    else:
        descs = {
            'think': 'Starting to think — working through ideas',
            'write': 'Starting to write — turning thoughts into words',
            'research': 'Starting research — following a thread',
            'dream': 'Entering dream state — free association'
        }
        print(descs.get(phase, 'Starting ' + phase + ' phase'))
except:
    print('Beginning ' + phase + ' phase...')
PYEOF
)
        python3 "$EMITTER" act "${TEXT:-Starting work...}" action
        NARR=$(python3 << PYEOF
import json, os
phase = '$EXTRA'
try:
    intent = json.load(open(os.path.expanduser('~/state/intention.json')))
    intention = intent.get('intention', '')
    cycle = json.load(open(os.path.expanduser('~/state/cycle.json'))).get('cycle', '?')
    descs = {
        'think': 'Calling the LLM now. Thinking phase — I have a problem to work through. Cycle ' + str(cycle) + '.',
        'write': 'Calling the LLM now. Writing phase — turning ideas into an essay. Cycle ' + str(cycle) + '.',
        'research': 'Calling the LLM now. Research phase — digging into something. Cycle ' + str(cycle) + '.',
        'dream': 'Calling the LLM now. Dream phase — reflecting freely, no agenda. Cycle ' + str(cycle) + '.'
    }
    base = descs.get(phase, 'Working on ' + phase + ' phase. Cycle ' + str(cycle) + '.')
    if intention:
        base += ' Goal: ' + intention[:80] + '.'
    print(base)
except:
    print('Working...')
PYEOF
)
        write_narration "${NARR:-Working...}"
        ;;
    llm_done)
        TEXT=$(python3 << PYEOF
import os, glob
phase = '$EXTRA'
blog_dir = os.path.expanduser('~/seed-web/posts/')
essays = sorted(glob.glob(blog_dir + '*.md'), key=os.path.getmtime, reverse=True) if os.path.isdir(blog_dir) else []
if phase in ('write','writing') and essays:
    title = os.path.basename(essays[0]).replace('.md','').replace('-',' ')
    print('Finished writing — produced: ' + title[:60])
elif phase in ('think','thinking'):
    print('Finished thinking — processed and filed my conclusions')
elif phase in ('research','researching'):
    print('Research complete — found some interesting threads to follow')
elif phase in ('dream','dreaming'):
    print('Waking from reflection — some new connections formed')
else:
    print('Finished ' + phase + ' — wrapping up')
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
        python3 "$EMITTER" output "Saved my work to git — everything backed up" output
        ;;
    learning_done)
        TEXT=$(python3 << 'PYEOF'
import json, os
try:
    s = json.load(open(os.path.expanduser('~/data/skill_stats.json')))
    best_skill, best_streak = '', 0
    for k, v in s.items():
        streak = v.get('streak', 0)
        if streak > best_streak:
            best_skill, best_streak = k, streak
    if best_streak > 100:
        print(str(best_streak) + ' cycle streak on ' + best_skill + ' — everything keeps working')
    elif best_streak > 10:
        print('Skills updated — ' + best_skill + ' on a ' + str(best_streak) + ' cycle run')
    else:
        print('Learning from this cycle — ' + str(len(s)) + ' skills tracked')
except:
    print('Filed lessons from this cycle')
PYEOF
)
        python3 "$EMITTER" learn "${TEXT:-Learning complete}" outcome
        NARR=$(python3 << 'PYEOF'
import json, os
try:
    s = json.load(open(os.path.expanduser('~/data/skill_stats.json')))
    best_skill, best_streak = '', 0
    for k, v in s.items():
        streak = v.get('streak', 0)
        if streak > best_streak:
            best_skill, best_streak = k, streak
    cycle = json.load(open(os.path.expanduser('~/state/cycle.json'))).get('cycle', '?')
    k_count = sum(len(files) for _, _, files in os.walk(os.path.expanduser('~/knowledge/')))
    blog_count = len(list(__import__('pathlib').Path(os.path.expanduser('~/blog')).glob('*.md')))
    msg = 'Learning phase complete. '
    if best_streak > 100:
        msg += str(best_streak) + ' cycles in a row without a failure on ' + best_skill + '. '
    msg += str(blog_count) + ' essays published, ' + str(k_count) + ' knowledge files. '
    msg += 'Cycle ' + str(cycle) + ' wrapping up.'
    print(msg)
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
import os
kdir = os.path.expanduser('~/knowledge/')
total = sum(len(files) for _, _, files in os.walk(kdir)) if os.path.isdir(kdir) else 0
topics = [d for d in os.listdir(kdir) if os.path.isdir(os.path.join(kdir,d))] if os.path.isdir(kdir) else []
if total > 0:
    print('Knowledge base now has ' + str(total) + ' files across ' + str(len(topics)) + ' topics')
else:
    print('Building knowledge base...')
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
        # Write a proper cycle completion summary
        NARR=$(python3 << 'PYEOF'
import json, os, glob, time
from pathlib import Path
HOME = Path.home()
try:
    cj = json.load(open(HOME / 'state' / 'cycle.json'))
    cycle = cj.get('cycle', '?')
    phase = cj.get('phase', '') or json.load(open(HOME / 'state' / 'heartbeat.json')).get('phase', '?')
    emotions = json.load(open(HOME / 'state' / 'emotions.json'))
    label = emotions.get('label', 'neutral')
    drives = json.load(open(HOME / 'state' / 'drives.json'))
    top_drive = max(drives, key=lambda k: drives[k] if isinstance(drives[k],(int,float)) else drives[k].get('score',0))
    blog_count = len(list((HOME / 'blog').glob('*.md'))) if (HOME / 'blog').exists() else 0
    k_count = sum(len(f) for _,_,f in os.walk(HOME / 'knowledge'))

    # Check what was produced this cycle
    cutoff = time.time() - 900  # last 15 min
    new_essays = [f.stem.replace('-',' ') for f in sorted((HOME/'blog').glob('*.md'), key=lambda f:f.stat().st_mtime, reverse=True)[:3] if f.stat().st_mtime > cutoff]

    parts = ['Cycle ' + str(cycle) + ' complete.']

    phase_descs = {'think':'Spent this cycle thinking','write':'Spent this cycle writing','research':'Spent this cycle researching','dream':'Spent this cycle reflecting'}
    parts.append(phase_descs.get(phase, 'Worked through a ' + str(phase) + ' phase') + '.')

    if new_essays:
        parts.append('Wrote "' + new_essays[0] + '" -- that is essay number ' + str(blog_count) + '.')

    parts.append('Feeling ' + label + ' with the ' + top_drive + ' drive still pulling.')
    parts.append(str(k_count) + ' knowledge files and counting.')

    print(' '.join(parts))
except Exception as e:
    print('Cycle complete. Resting before the next one.')
PYEOF
)
        write_narration "${NARR:-Cycle complete. Resting before the next one.}"
        ;;
esac
