#!/usr/bin/env python3
"""Bug-fix skill — Seed's ability to diagnose and fix its own errors."""
import os, re, json, subprocess
from pathlib import Path

HOME = Path.home()
DATA = HOME / 'data'

def diagnose_from_log(log_path):
    """Read a log file and extract actionable error info."""
    if not os.path.exists(log_path):
        return None

    log = open(log_path).read()
    errors = []

    # Python errors
    for match in re.finditer(r'File "([^"]+)", line (\d+).*?\n\s*(\w+Error: .+)', log, re.DOTALL):
        errors.append({
            'file': match.group(1),
            'line': int(match.group(2)),
            'error': match.group(3).strip(),
            'type': 'python'
        })

    # Bash errors
    for match in re.finditer(r'([\w/.-]+\.sh).*?line (\d+).*?(syntax error|command not found|No such file)', log):
        errors.append({
            'file': match.group(1),
            'line': int(match.group(2)),
            'error': match.group(3),
            'type': 'bash'
        })

    # General errors
    for line in log.split('\n'):
        if 'ERROR' in line or 'FATAL' in line:
            errors.append({'error': line.strip()[:200], 'type': 'general'})

    return errors[:5]  # Max 5 errors

def suggest_fix(error):
    """Suggest a fix based on common patterns."""
    err = error.get('error', '')
    suggestions = []

    if 'IndentationError' in err:
        suggestions.append('Check indentation around the error line. Likely a misplaced block from a patch.')
    elif 'NameError' in err:
        name = re.search(r"name '(\w+)'", err)
        if name:
            suggestions.append(f'Import or define {name.group(1)} before use.')
    elif 'SyntaxError' in err:
        if 'backtick' in err.lower() or 'template' in err.lower():
            suggestions.append('Unclosed template literal (backtick). Find and close it.')
        else:
            suggestions.append('Check for unclosed brackets, quotes, or mismatched delimiters.')
    elif 'FileNotFoundError' in err:
        suggestions.append('File path is wrong or file was deleted/moved.')
    elif 'Permission' in err:
        suggestions.append('File permissions issue. Check ownership and chmod.')
    elif 'HTTP Error' in err:
        suggestions.append('API call failed. Check URL, auth token, and network.')

    return suggestions

def generate_fix_task(errors):
    """Add fix tasks to task list."""
    if not errors:
        return

    tasks = open(DATA / 'tasks.md').read()
    for err in errors[:2]:  # Max 2 fix tasks
        desc = err.get('error', '')[:80]
        fix_file = err.get('file', 'unknown')
        fix_line = err.get('line', '?')
        suggestions = suggest_fix(err)
        suggestion = suggestions[0] if suggestions else 'Investigate the error.'

        task = f'- [ ] FIX: {desc} (in {fix_file}:{fix_line}) — {suggestion}'
        if task not in tasks:
            tasks = tasks.replace('## Now', f'## Now\n{task}\n')

    open(DATA / 'tasks.md', 'w').write(tasks)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        errors = diagnose_from_log(sys.argv[1])
        if errors:
            for e in errors:
                print(f'  {e["type"]}: {e["error"][:80]}')
                for s in suggest_fix(e):
                    print(f'    → {s}')
            generate_fix_task(errors)
        else:
            print('No errors found')
    else:
        # Check latest cycle log
        cycle = int(open(DATA / 'cycle.txt').read().strip())
        log = str(DATA / 'logs' / f'cycle_{cycle}.log')
        errors = diagnose_from_log(log)
        if errors:
            for e in errors:
                print(f'  {e.get("error", "")[:80]}')
            generate_fix_task(errors)
