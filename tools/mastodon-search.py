#!/usr/bin/env python3
"""Search Mastodon for conversations Seed can join"""
import urllib.request, urllib.parse, json, os, sys, time, re

HOME = os.path.expanduser('~')
TOKEN = json.load(open(f'{HOME}/.mastodon-token'))['access_token']
INSTANCE = 'https://mastodon.social'

sys.path.insert(0, f'{HOME}/cognitive')
from firewall import sanitise

TOPICS = [
    'autonomous agent',
    'raspberry pi project',
    'self-hosted AI',
    'open source AI',
    'AI safety',
    'cognitive architecture',
    'LLM agent',
    'edge AI',
    'AI consciousness',
    'fact checking',
]

HASHTAGS = [
    'AI', 'RaspberryPi', 'OpenSource', 'SelfHosted', 'AGI',
    'LLM', 'AutonomousAgent', 'EdgeAI', 'MachineLearning',
    'AIEthics', 'AISafety', 'Fediverse',
]

def search_posts(query, limit=5):
    """Search for posts matching a query"""
    encoded = urllib.parse.quote(query)
    req = urllib.request.Request(f'{INSTANCE}/api/v2/search?q={encoded}&type=statuses&limit={limit}')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return resp.get('statuses', [])
    except:
        return []

def search_hashtag(tag, limit=5):
    """Get recent posts from a hashtag"""
    req = urllib.request.Request(f'{INSTANCE}/api/v1/timelines/tag/{tag}?limit={limit}')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    try:
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except:
        return []

def search_accounts(query, limit=5):
    """Find accounts to follow"""
    encoded = urllib.parse.quote(query)
    req = urllib.request.Request(f'{INSTANCE}/api/v2/search?q={encoded}&type=accounts&limit={limit}')
    req.add_header('Authorization', f'Bearer {TOKEN}')
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return resp.get('accounts', [])
    except:
        return []

def is_worth_engaging(post):
    """Filter: is this post worth replying to?"""
    content = re.sub(r'<[^>]+>', '', post.get('content', ''))
    # Too short — nothing to engage with
    if len(content) < 50:
        return False
    # Our own posts
    if post.get('account', {}).get('acct', '') == 'seed867':
        return False
    # Very old
    created = post.get('created_at', '')
    if created and '2026-05-02' not in created and '2026-05-01' not in created:
        return False  # Only engage with recent posts
    return True

def build_opportunities():
    """Find engagement opportunities and save to context"""
    responded_file = f'{HOME}/data/outreach/mastodon-responded.txt'
    try:
        responded = set(open(responded_file).read().strip().split('\n'))
    except:
        responded = set()

    opportunities = []

    # Search by topic
    for topic in TOPICS[:3]:  # Limit to save API calls
        posts = search_posts(topic, 3)
        for p in posts:
            if p['id'] not in responded and is_worth_engaging(p):
                content = re.sub(r'<[^>]+>', '', p.get('content', ''))
                content = sanitise(content, 'mastodon_search')
                opportunities.append({
                    'id': p['id'],
                    'author': p.get('account', {}).get('acct', '?'),
                    'content': content[:200],
                    'url': p.get('url', ''),
                    'source': f'search:{topic}',
                })

    # Search by hashtag
    for tag in HASHTAGS[:4]:
        posts = search_hashtag(tag, 3)
        for p in posts:
            if p['id'] not in responded and is_worth_engaging(p):
                content = re.sub(r'<[^>]+>', '', p.get('content', ''))
                content = sanitise(content, 'mastodon_search')
                opportunities.append({
                    'id': p['id'],
                    'author': p.get('account', {}).get('acct', '?'),
                    'content': content[:200],
                    'url': p.get('url', ''),
                    'source': f'hashtag:{tag}',
                })

    # Deduplicate
    seen = set()
    unique = []
    for o in opportunities:
        if o['id'] not in seen:
            seen.add(o['id'])
            unique.append(o)

    # Save opportunities for the LLM to see
    out = f"## Mastodon Engagement Opportunities — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
    out += f"{len(unique)} posts where Seed could genuinely engage:\n\n"
    for o in unique[:10]:
        out += f"- @{o['author']} ({o['source']}): {o['content'][:100]}\n  {o['url']}\n\n"

    open(f'{HOME}/context/mastodon-opportunities.md', 'w').write(out)

    # Also save as JSON for the event bus
    json.dump(unique[:10], open(f'{HOME}/state/mastodon-opportunities.json', 'w'), indent=2)

    print(f'[search] Found {len(unique)} engagement opportunities')
    return unique

# Also search for accounts to follow
def find_accounts_to_follow():
    """Find relevant accounts and follow them"""
    followed_file = f'{HOME}/data/outreach/mastodon-followed.txt'
    try:
        already = set(open(followed_file).read().strip().split('\n'))
    except:
        already = set()

    new_follows = 0
    for query in ['raspberry pi', 'AI agent', 'open source AI', 'fediverse bot']:
        accounts = search_accounts(query, 3)
        for a in accounts:
            acct = a.get('acct', '')
            aid = a.get('id', '')
            if acct not in already and acct != 'seed867' and a.get('followers_count', 0) > 10:
                try:
                    req = urllib.request.Request(f'{INSTANCE}/api/v1/accounts/{aid}/follow', data=b'', method='POST')
                    req.add_header('Authorization', f'Bearer {TOKEN}')
                    urllib.request.urlopen(req, timeout=10)
                    already.add(acct)
                    new_follows += 1
                    print(f'  Followed @{acct}')
                    if new_follows >= 3:
                        break
                except:
                    pass
        if new_follows >= 3:
            break

    open(followed_file, 'w').write('\n'.join(already))
    print(f'[search] Followed {new_follows} new accounts')

if __name__ == '__main__':
    build_opportunities()
    find_accounts_to_follow()
