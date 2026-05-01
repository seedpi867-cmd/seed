#!/usr/bin/env python3
"""
send_chat.py — Post a message to the SEED chat UI so the operator can see it.
The agent uses this to proactively communicate with the user.
Usage: python3 send_chat.py "message from agent"
"""
import json
import sys
import urllib.request
import urllib.error

API_BASE = 'http://localhost:8080'


def send(message: str) -> dict:
    url  = f'{API_BASE}/api/chat/agent_message'
    data = json.dumps({'message': message}).encode()
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
    if len(sys.argv) < 2:
        print('Usage: send_chat.py "message"', file=sys.stderr)
        sys.exit(1)
    message = ' '.join(sys.argv[1:])
    result  = send(message)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
