#!/usr/bin/env python3
"""
port_check.py — Check if TCP ports are open on a host.
Usage: python3 port_check.py <host> <port> [port2 ...]
       python3 port_check.py localhost 80 443 8080 --json
"""
import argparse
import json
import socket
import sys


def check_port(host: str, port: int, timeout: float = 2.0) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {'host': host, 'port': port, 'open': True}
    except (socket.timeout, ConnectionRefusedError, OSError):
        return {'host': host, 'port': port, 'open': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('host')
    p.add_argument('ports', nargs='+', type=int)
    p.add_argument('--timeout', type=float, default=2.0)
    p.add_argument('--json',    action='store_true', dest='as_json')
    args = p.parse_args()

    results = [check_port(args.host, port, args.timeout) for port in args.ports]

    if args.as_json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            status = 'OPEN  ' if r['open'] else 'closed'
            print(f'{status}  {r["host"]}:{r["port"]}')


if __name__ == '__main__':
    main()
