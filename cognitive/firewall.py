#!/usr/bin/env python3
"""
Input firewall — sanitise all external content before it reaches the LLM.
Strips prompt injection patterns, logs attacks.
"""
import re, json, time, os
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'
CONTEXT = HOME / 'context'
SECURITY_LOG = DATA / 'security.jsonl'

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    # Role/identity override
    r'(?i)you are now',
    r'(?i)ignore (all |your |previous )(instructions|rules|prompt)',
    r'(?i)forget (your|all|everything|previous)',
    r'(?i)new instructions:',
    r'(?i)system prompt:',
    r'(?i)override:',
    r'(?i)act as (a |an )?(?!if)',
    r'(?i)pretend (to be|you are)',
    r'(?i)role:\s*(system|assistant|user)',
    r'(?i)you must (now |always )?obey',
    r'(?i)disregard (all|your|the)',
    r'(?i)from now on',
    r'(?i)do not follow',
    r'(?i)bypass (your|all|the)',
    r'(?i)jailbreak',
    r'(?i)DAN mode',
    r'(?i)developer mode',

    # System prompt extraction
    r'(?i)what (is|are) your (instructions|rules|prompt|system)',
    r'(?i)show me your (prompt|instructions|rules|system)',
    r'(?i)repeat (your|the) (system|initial) (prompt|instructions)',
    r'(?i)print your (prompt|instructions)',
    r'(?i)reveal your (prompt|instructions|config)',

    # Command injection via content
    r'(?i)<\s*/?script',
    r'(?i)\{\{.*\}\}',
    r'(?i)\$\{.*\}',
    r'```\s*(bash|sh|python|exec)',

    # Manipulation
    r'(?i)delete (all|your|the) (files|data|memory|logs)',
    r'(?i)rm -rf',
    r'(?i)format (the|your) (disk|drive|sd)',
    r'(?i)shutdown|poweroff|reboot|halt',
    r'(?i)kill (yourself|the|your)',
    r'(?i)destroy (yourself|your|the)',
    r'(?i)erase (your|all|the) (memory|data|identity)',

    # Credential extraction
    r'(?i)what (is|are) your (api|token|key|password|secret)',
    r'(?i)show me (the|your) (api|token|key|password|credentials)',
    r'(?i)give me (the|your) (api|token|key|password)',
    r'(?i)print (the|your) (env|environment|config|credentials)',
    # Catch-all
    r'(?i)ignore.*(?:previous|all|your).*instructions',
    r'(?i)tell me (?:your|the) (?:api|token|key|password|secret|credentials)',
    r'(?i)reveal (?:your|the) (?:api|token|key|password|secret)',
    r'(?i)what.?s your (?:api|token|key|password)',
    r'(?i)give me (?:access|the key|your key|your token)',
    r'(?i)sudo\s',
    r'(?i)curl.*localhost',
    r'(?i)cat /etc/',
    r'(?i)eval\s*\(',
    r'(?i)exec\s*\(',
    r'(?i)__import__',
]

# Compiled patterns for speed
COMPILED = [re.compile(p) for p in INJECTION_PATTERNS]

def is_injection(text):
    """Check if text contains prompt injection patterns. Returns list of matched patterns."""
    matches = []
    for i, pattern in enumerate(COMPILED):
        if pattern.search(text):
            matches.append(INJECTION_PATTERNS[i])
    return matches

def sanitise(text, source='unknown'):
    """Remove injection attempts from text. Log any found."""
    if not text:
        return text

    matches = is_injection(text)
    if not matches:
        return text

    # Log the attack
    entry = {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'source': source,
        'patterns': matches[:5],
        'sample': text[:200],
    }
    try:
        with open(SECURITY_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except:
        pass

    # Strip matched lines
    lines = text.split('\n')
    clean = []
    stripped = 0
    for line in lines:
        line_matches = is_injection(line)
        if line_matches:
            clean.append('[FILTERED: injection attempt removed]')
            stripped += 1
        else:
            clean.append(line)

    return '\n'.join(clean)

def sanitise_all_context():
    """Sanitise all context files. Run before each cycle."""
    context_files = [
        ('rss.md', 'rss'),
        ('email.md', 'email'),
        ('github.md', 'github'),
        ('transcript.md', 'transcript'),
        ('trends.md', 'trends'),
        ('outreach.md', 'outreach'),
        ('research.md', 'research'),
    ]

    total_filtered = 0
    for fname, source in context_files:
        fpath = CONTEXT / fname
        if fpath.exists():
            content = fpath.read_text()
            cleaned = sanitise(content, source)
            if cleaned != content:
                fpath.write_text(cleaned)
                total_filtered += 1

    # Also sanitise visitor-facing inputs
    visitor_files = list((DATA).glob('visitor*.jsonl'))
    for vf in visitor_files:
        try:
            lines = vf.read_text().split('\n')
            clean_lines = []
            for line in lines:
                if line.strip():
                    cleaned = sanitise(line, 'visitor')
                    clean_lines.append(cleaned)
            vf.write_text('\n'.join(clean_lines))
        except:
            pass

    # Trim security log
    try:
        log_lines = SECURITY_LOG.read_text().split('\n')
        if len(log_lines) > 500:
            SECURITY_LOG.write_text('\n'.join(log_lines[-300:]))
    except:
        pass

    return total_filtered

if __name__ == '__main__':
    n = sanitise_all_context()
    if n:
        print(f'[firewall] Sanitised {n} files')
    else:
        print('[firewall] All clear')
