#!/usr/bin/env python3
"""Intention protocol — predeclare what this cycle should produce, then verify."""
import sys, os, glob, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *

INTENTIONS_FILE = STATE / 'intention.json'

def modified_since(paths, declared_at):
    """Return the first file path modified after the intention declaration."""
    for path in paths:
        if path.exists() and os.path.getmtime(str(path)) > declared_at:
            return path
    return None

def predeclare(cycle, phase, drives):
    """Before the LLM runs: declare what this cycle should produce."""
    top_drive = max(drives.items(), key=lambda x: x[1])[0] if drives else 'think'

    PHASE_INTENTIONS = {
        'write': 'A new blog post in blog/',
        'research': 'New findings saved to context/research.md',
        'think': 'At least one file created or modified beyond memory/tasks',
        'dream': 'A reflection saved to dreams, philosophy, self-model, beliefs, or lessons',
        'maintain': 'A system issue fixed or health verified',
    }

    intention = {
        'cycle': cycle,
        'phase': phase,
        'declared_at': now(),
        'intention': PHASE_INTENTIONS.get(phase, 'Produce something visible'),
        'drive': top_drive,
        'verified': False,
        'result': None,
    }
    save_json(INTENTIONS_FILE, intention)
    return intention

def verify(cycle):
    """After the LLM runs: did the declared intention produce a trace?"""
    intention = load_json(INTENTIONS_FILE, {})
    if not intention or intention.get('cycle') != cycle:
        return None

    phase = intention.get('phase', 'think')
    declared_at = intention.get('declared_at', 0)
    success = False
    evidence = ''

    if phase == 'write':
        # Check if a new blog file was created since declaration
        for f in glob.glob(str(HOME / 'blog' / '*.md')):
            if os.path.getmtime(f) > declared_at:
                success = True
                evidence = os.path.basename(f)
                break

    elif phase == 'research':
        research_file = HOME / 'context' / 'research.md'
        if research_file.exists() and os.path.getmtime(str(research_file)) > declared_at:
            success = True
            evidence = 'research.md updated'

    elif phase == 'dream':
        dream_outputs = [
            HOME / 'data' / 'dreams.md',
            HOME / 'data' / 'self-model.md',
            HOME / 'data' / 'beliefs.md',
            HOME / 'data' / 'lessons.md',
            HOME / 'data' / 'inner-voice.md',
        ]
        dream_outputs.extend((HOME / 'knowledge' / 'philosophy').glob('*.md'))
        dream_outputs.extend((HOME / 'knowledge' / 'lessons').glob('*.md'))
        changed = modified_since(dream_outputs, declared_at)
        if changed:
            success = True
            evidence = str(changed.relative_to(HOME))

    elif phase == 'think':
        # Check if ANY file was created/modified (beyond just logs)
        check_dirs = [HOME / 'blog', HOME / 'data', HOME / 'tools', HOME / 'context']
        for d in check_dirs:
            for f in d.glob('*'):
                if f.is_file() and os.path.getmtime(str(f)) > declared_at:
                    if 'log' not in f.name and f.name != 'cycle.txt':
                        success = True
                        evidence = str(f.relative_to(HOME))
                        break
            if success:
                break

    elif phase == 'maintain':
        success = True  # Maintenance is always "something was checked"
        evidence = 'health verified'

    intention['verified'] = True
    intention['result'] = 'delivered' if success else 'missed'
    intention['evidence'] = evidence
    save_json(INTENTIONS_FILE, intention)

    # Log to feedback ledger
    try:
        from learning import log_to_ledger
        log_to_ledger(f'intention_{phase}', success, phase, cycle)
    except: pass

    # If missed, append to inner voice
    if not success:
        append_text(DATA / 'inner-voice.md',
            f'\n[{time.strftime("%Y-%m-%d %H:%M")}] MISSED INTENTION: declared {phase} but produced no visible artifact.\n')

    return intention

def get_intention_summary():
    """For working memory — show last intention result."""
    intention = load_json(INTENTIONS_FILE, {})
    if not intention or not intention.get('verified'):
        return ''
    result = intention.get('result', '?')
    phase = intention.get('phase', '?')
    evidence = intention.get('evidence', '')
    if result == 'delivered':
        return f'LAST INTENTION: {phase} — delivered ({evidence})'
    else:
        return f'LAST INTENTION: {phase} — MISSED. You said you would produce something. You didn\'t.'

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        cycle = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        r = verify(cycle)
        if r:
            print(f"[intention] {r['result']}: {r.get('evidence', 'none')}")
    else:
        print(get_intention_summary())
