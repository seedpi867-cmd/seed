#!/usr/bin/env python3
"""
remember_fact.py — Store a fact in SEED's memory via the local API.
Usage: python3 remember_fact.py <key> <value> [--category general|technical|business|credential]
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

API_BASE = 'http://localhost:8080'


def store_fact(key: str, value: str, category: str = 'general') -> dict:
    url  = f'{API_BASE}/api/facts'
    data = json.dumps({'key': key, 'value': value, 'category': category}).encode()
    req  = urllib.request.Request(url, data=data,
                                   headers={'Content-Type': 'application/json'},
                                   method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {'error': f'HTTP {e.code}', 'body': e.read().decode()}
    except Exception as e:
        return {'error': str(e)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('key')
    p.add_argument('value')
    p.add_argument('--category', default='general',
                   choices=['general', 'technical', 'business', 'credential'])
    args = p.parse_args()

    result = store_fact(args.key, args.value, args.category)
    print(json.dumps(result, indent=2))
    if 'error' in result:
        sys.exit(1)


if __name__ == '__main__':
    main()
