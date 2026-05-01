#!/usr/bin/env python3
"""
file_ops.py — Safe file operations for the SEED agent.
Restricts all paths to ~/seed/workspace/ to prevent accidents.
Usage: python3 file_ops.py read <path>
       python3 file_ops.py write <path> <content>
       python3 file_ops.py list [dir]
       python3 file_ops.py delete <path>
       python3 file_ops.py exists <path>
"""
import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path.home() / 'seed' / 'workspace'


def safe_path(p: str) -> Path:
    """Resolve path, ensure it's within WORKSPACE."""
    resolved = (WORKSPACE / p).resolve()
    if not str(resolved).startswith(str(WORKSPACE.resolve())):
        raise ValueError(f'Path outside workspace: {p}')
    return resolved


def cmd_read(args):
    path = safe_path(args.path)
    if not path.exists():
        print(json.dumps({'error': f'Not found: {args.path}'}))
        sys.exit(1)
    content = path.read_text(errors='replace')
    print(json.dumps({'path': str(path), 'content': content, 'size': len(content)}))


def cmd_write(args):
    path = safe_path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = args.content if args.content else sys.stdin.read()
    path.write_text(content)
    print(json.dumps({'path': str(path), 'bytes': len(content), 'success': True}))


def cmd_list(args):
    base = safe_path(args.dir) if args.dir else WORKSPACE
    if not base.exists():
        print(json.dumps([]))
        return
    entries = []
    for p in sorted(base.iterdir()):
        entries.append({
            'name': p.name,
            'type': 'dir' if p.is_dir() else 'file',
            'size': p.stat().st_size if p.is_file() else None,
        })
    print(json.dumps(entries, indent=2))


def cmd_delete(args):
    path = safe_path(args.path)
    if not path.exists():
        print(json.dumps({'error': 'Not found'}))
        sys.exit(1)
    path.unlink() if path.is_file() else path.rmdir()
    print(json.dumps({'deleted': str(path), 'success': True}))


def cmd_exists(args):
    try:
        path = safe_path(args.path)
        print(json.dumps({'exists': path.exists(), 'path': str(path)}))
    except ValueError as e:
        print(json.dumps({'error': str(e)}))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)

    r = sub.add_parser('read');   r.add_argument('path')
    w = sub.add_parser('write');  w.add_argument('path'); w.add_argument('content', nargs='?')
    l = sub.add_parser('list');   l.add_argument('dir', nargs='?', default='')
    d = sub.add_parser('delete'); d.add_argument('path')
    e = sub.add_parser('exists'); e.add_argument('path')

    args = p.parse_args()
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    try:
        {'read': cmd_read, 'write': cmd_write, 'list': cmd_list,
         'delete': cmd_delete, 'exists': cmd_exists}[args.cmd](args)
    except ValueError as exc:
        print(json.dumps({'error': str(exc)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
