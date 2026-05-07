#!/usr/bin/env python3
"""Seed Brain — Full Dashboard (drives + consciousness + emotions + inner voice)"""
import http.server, json, os, time, socketserver, urllib.parse
from pathlib import Path

PORT = 8080
HOME = Path.home()
DATA = HOME / 'data'
BLOG = HOME / 'blog'
LOGS = DATA / 'logs'

SEED_WEB = HOME / 'seed-web'
HOMEPAGE_HTML = open(SEED_WEB / 'index.html').read()

VISITOR_COUNT = 0
VISITOR_LOG = Path.home() / 'data' / 'visitors.jsonl'
CTA_LOG = Path.home() / 'data' / 'cta-clicks.jsonl'

# Import firewall for visitor input sanitisation
try:
    import sys as _sys
    _sys.path.insert(0, str(Path.home() / "cognitive"))
    from firewall import sanitise as fw_sanitise
except:
    fw_sanitise = lambda t, s='': t

REDACT_STRINGS = []  # loaded at runtime
def redact(text):
    for s in REDACT_STRINGS:
        text = text.replace(s, '[REDACTED]')
    return text

"""Add brain-graph endpoint to webserver. Run on Pi."""
import json, os, time
from pathlib import Path

HOME = Path.home()
KNOWLEDGE = HOME / 'knowledge'
TOOLS = HOME / 'tools'
COGNITIVE = HOME / 'cognitive'
DATA = HOME / 'data'

_bg_cache = {'ts': 0, 'data': None}

def brain_graph():
    now = __import__('time').time()
    if _bg_cache['data'] and now - _bg_cache['ts'] < 60:
        return _bg_cache['data']

    nodes = []
    links = []
    HOME = __import__('pathlib').Path.home()

    # Hub
    nodes.append({'id': 'seed', 'name': 'Seed', 'group': 'hub', 'val': 25})

    # Knowledge folders (top level only)
    kdir = HOME / 'knowledge'
    if kdir.exists():
        for d in sorted(kdir.iterdir()):
            if d.is_dir() and d.name not in ('.git', '__pycache__', 'inbox'):
                count = sum(1 for _ in d.rglob('*.md'))
                if count > 0:
                    nid = 'k/' + d.name
                    nodes.append({'id': nid, 'name': d.name.replace('-',' '), 'group': 'knowledge', 'val': max(3, min(15, count // 5))})
                    links.append({'source': 'seed', 'target': nid})

    # Key cognitive scripts only
    cog_names = ['appraisal', 'drive_engine', 'emotional_model', 'learning', 'self_suggestions', 'knowledge_engine', 'triggers', 'event_bus']
    for c in cog_names:
        nid = 'c/' + c
        nodes.append({'id': nid, 'name': c.replace('_',' '), 'group': 'cognitive', 'val': 4})
        links.append({'source': 'seed', 'target': nid})

    # Link cognitive to relevant knowledge
    links.append({'source': 'c/drive_engine', 'target': 'c/emotional_model'})
    links.append({'source': 'c/appraisal', 'target': 'c/drive_engine'})
    links.append({'source': 'c/learning', 'target': 'c/knowledge_engine'})
    links.append({'source': 'c/self_suggestions', 'target': 'c/appraisal'})

    # Feeders
    feeders = ['rss', 'transcript', 'github', 'trending repos', 'environment']
    for f in feeders:
        nid = 'f/' + f
        nodes.append({'id': nid, 'name': f, 'group': 'feeder', 'val': 3})
        links.append({'source': nid, 'target': 'seed'})

    # Key tools only
    key_tools = ['repo_pattern_classifier', 'body_weather_router', 'deploy-blog', 'push-agent-repo', 'emit_events', 'running_loop_version_sentinel', 'feed-trending-repos']
    for t in key_tools:
        nid = 't/' + t
        nodes.append({'id': nid, 'name': t.replace('_',' ').replace('-',' '), 'group': 'tool', 'val': 3})
        links.append({'source': 'seed', 'target': nid})

    # Active experiments (last 5)
    exp_file = HOME / 'data' / 'experiments.jsonl'
    if exp_file.exists():
        try:
            lines = [l for l in exp_file.read_text().strip().split(chr(10)) if l.strip()]
            seen = set()
            for line in reversed(lines[-10:]):
                e = __import__('json').loads(line)
                name = e.get('name', e.get('experiment', e.get('topic', '')))
                if name and name not in seen:
                    seen.add(name)
                    nid = 'e/' + name[:25]
                    nodes.append({'id': nid, 'name': name, 'group': 'experiment', 'val': 4})
                    links.append({'source': 'seed', 'target': nid})
                if len(seen) >= 5:
                    break
        except:
            pass

    result = {'nodes': nodes, 'links': links}
    _bg_cache['data'] = result
    _bg_cache['ts'] = now
    return result


class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET, OPTIONS, HEAD')
        self.send_header('Access-Control-Allow-Headers','*')
        self.end_headers()
    def do_GET(self):
        if self.path in('/','index.html'):self._h(HOMEPAGE_HTML)
        elif self.path=='/brain.html':
            try: self._h(open(SEED_WEB/'brain.html').read())
            except: self.send_error(404)
        elif self.path=='/api/all':self._j(self._all())
        elif self.path=='/api/status':self._j(self._status())
        elif self.path=='/api/log':self._j(self._log())
        elif self.path=='/api/memory':self._j(self._f(DATA/'memory.md'))
        elif self.path=='/api/goals':self._j(self._f(DATA/'goals.md'))
        elif self.path=='/api/mood':self._j(self._mood())
        elif self.path=='/feed':self._rss()
        elif self.path=='/api/blogs':self._j(self._blogs())
        elif self.path=='/api/tokens':self._j(self._tokens())
        elif self.path=='/api/visit':self._j(self._visit())
        elif self.path=='/api/visitors':self._j(self._visitors())
        elif self.path=='/api/cta-stats':self._j(self._cta_stats())
        elif self.path.startswith('/api/cta'):self._j(self._cta_click())
        elif self.path=='/api/github':self._j(self._github())
        elif self.path=='/api/messages':self._j(self._messages())
        elif self.path=='/api/suggestions':self._j(self._suggestions())
        elif self.path=='/api/knowledge':self._j(self._knowledge())
        elif self.path=='/api/summary':self._j(self._summary())
        elif self.path=='/api/events':self._j(self._events())
        elif self.path=='/api/world':self._j(self._world())
        elif self.path=='/api/self-suggestions':self._j(self._self_suggestions())
        elif self.path=='/api/what-doing':self._j({'text':self._read_txt('what-im-doing.txt')})
        elif self.path=='/api/what-did':self._j({'text':self._read_txt('what-i-did.txt')})
        elif self.path=='/api/what-was':self._j({'text':self._read_txt('what-i-was.txt')})
        elif self.path=='/api/what-become':self._j({'text':self._read_txt('what-i-want-to-become.txt')})
        elif self.path=='/api/experiments':self._j(self._experiments())
        elif self.path=='/api/brain-graph':self._j(brain_graph())
        elif self.path=='/api/seed-tools':self._j(self._seed_tools())
        elif self.path=='/api/voice':self._j(self._voice())
        elif self.path=='/api/thought':self._j(self._thought())
        elif self.path=='/api/drives':self._j(self._drives())
        elif self.path=='/api/knowledge-recent':self._j(self._knowledge_recent())
        elif self.path.startswith('/api/knowledge-tree'):self._j(self._knowledge_tree())
        elif self.path.startswith('/api/knowledge-file?'):self._j(self._knowledge_file())
        elif self.path.startswith('/api/file?path='):
            p=self.path.split('path=',1)[1]
            SAFE=['data/inner-voice.md','data/dreams.md','data/goals.md','data/tasks.md','data/mood.json','data/token-totals.json','skills/SKILLS.md']
            if p in SAFE:self._j(self._f(HOME/p))
            else:self.send_response(403);self.end_headers()
        elif self.path.startswith('/posts/'):self._static(SEED_WEB / self.path.lstrip('/'))
        elif self.path.startswith('/assets/'):self._static(SEED_WEB / self.path.lstrip('/'))
        elif self.path == '/dashboard':self._h(open(HOME / 'tools' / 'dashboard.html').read())
        else:self.send_response(404);self.end_headers()
    def _h(self,c):self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(c.encode())
    def _static(self, fpath):
        import mimetypes
        fpath = Path(fpath)
        if not fpath.exists() or not fpath.is_file() or '..' in str(fpath):
            self.send_response(404);self.end_headers();return
        mime = mimetypes.guess_type(str(fpath))[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.end_headers()
        self.wfile.write(fpath.read_bytes())
    def _world(self):
        import subprocess
        world = {}
        # RSS headlines
        try:
            result = subprocess.run(['python3', '-c', '''
import json, urllib.request
feeds = {
    "hn": "http://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=5",
}
world = {}
for name, url in feeds.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Seed/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        if name == "hn":
            world["hn"] = [{"title": h.get("title",""), "points": h.get("points",0)} for h in data.get("hits",[])[:5]]
    except: pass
print(json.dumps(world))
'''], capture_output=True, text=True, timeout=10)
            world.update(json.loads(result.stdout))
        except: pass
        # Inner voice
        try:
            lines = (DATA / 'inner-voice.md').read_text().strip().split('\n')
            voice = [l.strip() for l in lines if l.strip() and not l.startswith('#')][-3:]
            world['voice'] = voice
        except: world['voice'] = []
        # Current emotion
        try:
            emo = json.loads((DATA / 'mood.json').read_text())
            world['emotion'] = emo.get('label', 'neutral')
            world['drives'] = {k: round(v, 2) for k, v in emo.get('drives', {}).items()}
        except: pass
        # Blog count
        world['blog_count'] = len(list(BLOG.glob('*.md'))) if BLOG.exists() else 0
        # Cycle
        world['cycle'] = self._r(DATA / 'cycle.txt', '0').strip()
        return world

    def do_POST(self):
        if self.path == '/api/message':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8', errors='replace')
            try:
                data = json.loads(body)
                text = fw_sanitise(data.get('text', '')[:500], 'creator_message')
                if not text.strip():
                    self._j({'ok': False, 'error': 'empty message'})
                    return
                # Write message directly
                mf = HOME / 'data' / 'messages.json'
                try: msgs = json.loads(mf.read_text())
                except: msgs = {'messages':[],'unread':[]}
                msg = {'text':text,'ts':__import__('time').strftime('%Y-%m-%d %H:%M'),'read':False}
                msgs['messages'].append(msg)
                msgs['unread'].append(msg)
                msgs['messages'] = msgs['messages'][-20:]
                mf.write_text(json.dumps(msgs,indent=2))
                self._j({'ok': True})
            except Exception as e:
                self._j({'ok': False, 'error': str(e)})
        else:
            self.send_response(404)
            self.end_headers()






    def _events(self):
        ef = HOME / 'data' / 'events.jsonl'
        if not ef.exists():
            return {'events': []}
        events = []
        try:
            for line in ef.read_text().strip().split(chr(10)):
                if line.strip():
                    try: events.append(json.loads(line))
                    except: pass
        except: pass
        return {'events': events[-20:]}
    def _summary(self):
        sf = HOME / 'data' / 'live-summary.md'
        if sf.exists():
            return {'text': sf.read_text().strip()}
        return {'text': 'Seed is starting up...'}
    def _knowledge_slim(self):
        """Light version for /api/all — just totals and top topics."""
        full = self._knowledge()
        topics = full.get("topics", {})
        top = dict(sorted(topics.items(), key=lambda x: -x[1].get("count",0))[:8])
        return {"total_files": full.get("total_files", 0), "topics": top}
    def _knowledge(self):
        kf = HOME / 'knowledge' / 'index.json'
        if kf.exists():
            try: return json.loads(kf.read_text())
            except: pass
        return {'total_files': 0, 'topics': {}, 'recent': []}
    def _suggestions(self):
        sf = HOME / 'data' / 'suggestion_decisions.json'
        if sf.exists():
            try: return json.loads(sf.read_text())
            except: pass
        return {'decisions': []}
    def _messages(self):
        mf = HOME / 'data' / 'messages.json'
        if mf.exists():
            try: return json.loads(mf.read_text())
            except: pass
        return {'messages': [], 'unread': []}

    def _all(self):
        """Single endpoint returning everything the homepage needs."""
        return {
            'status': self._status(),
            'drives': self._drives(),
            'events': self._events(),
            'summary': self._summary(),
            'blogs': self._blogs()[:30],
            'knowledge': self._knowledge_slim(),
            'suggestions': self._self_suggestions(),
            'visitors': self._visitors(),
            'thought': self._thought(),
            'voice': self._voice(),
            'what_doing': {'text': self._read_txt('what-im-doing.txt')},
            'what_did': {'text': self._read_txt('what-i-did.txt')},
            'what_was': {'text': self._read_txt('what-i-was.txt')},
            'what_become': {'text': self._read_txt('what-i-want-to-become.txt')},
            'experiments': self._experiments(),
        }
    def _voice(self):
        vf = HOME / 'data' / 'inner-voice.md'
        if vf.exists():
            try:
                lines = vf.read_text().strip().split(chr(10))
                meaningful = [l.strip() for l in reversed(lines) if len(l.strip()) > 20 and 'Skill streak' not in l]
                if meaningful:
                    import re
                    line = meaningful[0]
                    line = re.sub(r'^\[[\d\-: ]+\]\s*', '', line)
                    line = re.sub(r'^\([^)]+\)\s*', '', line)
                    line = re.sub(r'^- ', '', line)
                    return {'text': line[:300]}
            except: pass
        return {'text': ''}
    def _thought(self):
        tf = HOME / 'data' / 'train-of-thought.md'
        if tf.exists():
            return {"text": tf.read_text().strip()[:2000]}
        return {'text': ''}
    def _cycle_start(self):
        try:
            import json as _j
            c = _j.loads(self._r(HOME/'state'/'cycle.json','{}'))
            return c.get('started_at', 0)
        except: return 0
    def _self_suggestions(self):
        sf = HOME / 'data' / 'self-suggestions.json'
        if sf.exists():
            try: return json.loads(sf.read_text())
            except: pass
        return {'suggestions': []}
    def _drives(self):
        d,e={},{}
        try: d=json.loads(open(HOME/'state'/'drives.json').read())
        except: pass
        try: e=json.loads(open(HOME/'state'/'emotions.json').read())
        except: pass
        # Merge full mood data from mood.json (27 emotions + consciousness)
        try:
            mood=json.loads(open(HOME/'data'/'mood.json').read())
            for k,v in mood.items():
                if k!='drives' and isinstance(v,(int,float)):
                    e[k]=v
            if 'emotional_label' in mood: e['label']=mood['emotional_label']
            if 'note' in mood: e['note']=mood['note']
        except: pass
        return {'drives':d,'emotions':e}
    def _knowledge_recent(self):
        kdir = HOME / 'knowledge'
        if not kdir.exists(): return {'recent': []}
        import os
        files = []
        for root, dirs, fnames in os.walk(kdir):
            dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','inbox')]
            for f in fnames:
                if f.endswith('.md') or f.endswith('.txt'):
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, kdir)
                    try:
                        mtime = os.path.getmtime(fp)
                        files.append({'path': rel, 'name': f.replace('.md','').replace('-',' '), 'mtime': mtime})
                    except: pass
        files.sort(key=lambda x: -x['mtime'])
        return {'recent': files[:30]}
    def _knowledge_tree(self):
        kdir=HOME/'knowledge'
        if not kdir.exists(): return {'tree':{}}
        tree={}
        for root,dirs,files in os.walk(kdir):
            dirs[:]=[d for d in sorted(dirs) if d not in ('.git','__pycache__','inbox')]
            rel=os.path.relpath(root,kdir)
            if rel=='.': rel=''
            mds=[]
            for f in files:
                if f.endswith('.md') or f.endswith('.txt'):
                    try: mt=os.path.getmtime(os.path.join(root,f))
                    except: mt=0
                    mds.append({'name':f,'mtime':mt})
            mds.sort(key=lambda x:-x['mtime'])
            mds_names=[m['name'] for m in mds]
            if mds or dirs:
                tree[rel]={'folders':sorted(dirs),'files':mds_names[:50],'mtimes':{m['name']:m['mtime'] for m in mds[:50]}}
        return {'tree':tree}
    def _knowledge_file(self):
        qs=urllib.parse.urlparse(self.path).query
        params=urllib.parse.parse_qs(qs)
        fpath=params.get('path',[''])[0]
        if not fpath or '..' in fpath: return {'error':'invalid path'}
        full=HOME/'knowledge'/fpath
        if not full.exists() or not full.is_file(): return {'error':'not found'}
        try: return {'path':fpath,'content':full.read_text()[:10000]}
        except: return {'error':'read failed'}
    def _rss(self):
        import subprocess
        try:
            result = subprocess.run(['python3', str(HOME / 'tools' / 'rss_feed.py')], capture_output=True, text=True, timeout=5)
            xml = result.stdout
        except:
            xml = '<?xml version="1.0"?><rss version="2.0"><channel><title>Seed</title></channel></rss>'
        self.send_response(200)
        self.send_header('Content-Type', 'application/rss+xml')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(xml.encode())
    def _j(self,d):self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(json.dumps(d).encode())
    def _status(self):
        c=self._r(DATA/'cycle.txt','0').strip();hb={};mo={}
        try:hb=json.loads(self._r(HOME/'state'/'heartbeat.json','{}'))
        except:pass
        try:mo=json.loads(self._r(DATA/'mood.json','{}'))
        except:pass
        return{'cycle':c,'heartbeat':hb,'mood':mo,'uptime':os.popen('uptime -p 2>/dev/null').read().strip(),'memory':os.popen("free -m|awk 'NR==2{printf\"%dMB/%dMB\",$3,$2}'").read().strip(),'temp':(lambda t:f'{int(t)/1000:.1f}C'if t else'?')(os.popen('cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null').read().strip()),'blog_count':len(list(BLOG.glob('*.md')))if BLOG.exists()else 0,'agent':self._r(DATA/'agent.txt','codex').strip(),'sleep_seconds':int(self._r(DATA/'sleep_seconds.txt','300').strip() or 300),'cycle_started_at':self._cycle_start(),'ts':time.strftime('%H:%M:%S')}
    def _log(self):c=self._r(DATA/'cycle.txt','0').strip();return{'cycle':c,'content':redact(self._r(LOGS/f'cycle_{c}.log','...')[-8000:])}
    def _mood(self):
        try:return json.loads(self._r(DATA/'mood.json','{}'))
        except:return{}
    def _visit(self):
        global VISITOR_COUNT
        VISITOR_COUNT += 1
        record = json.dumps({"ts": time.strftime('%Y-%m-%dT%H:%M:%S'), "n": VISITOR_COUNT})
        try:
            needs_newline = False
            if VISITOR_LOG.exists() and VISITOR_LOG.stat().st_size > 0:
                with open(VISITOR_LOG, 'rb') as f:
                    f.seek(-1, os.SEEK_END)
                    needs_newline = f.read(1) != b'\n'
            with open(VISITOR_LOG, 'a') as f:
                if needs_newline:
                    f.write("\n")
                f.write(record + "\n")
        except: pass
        return {"count": VISITOR_COUNT, "total": self._total_visitors()}
    def _visitors(self):
        cta = self._cta_stats()
        return {"count": VISITOR_COUNT, "total": self._total_visitors(), "unique": self._unique_visitors(), "cta_clicks": cta.get("total", 0), "cta": cta}
    def _total_visitors(self):
        try:
            decoder = json.JSONDecoder()
            text = VISITOR_LOG.read_text()
            count = 0
            idx = 0
            while idx < len(text):
                while idx < len(text) and text[idx].isspace():
                    idx += 1
                if idx >= len(text):
                    break
                _, idx = decoder.raw_decode(text, idx)
                count += 1
            return count
        except:
            return VISITOR_COUNT
    def _unique_visitors(self):
        try:
            ips = set()
            for line in open(str(VISITOR_LOG)):
                line = line.strip()
                if not line: continue
                try:
                    d = json.loads(line)
                    ip = d.get("ip", "")
                    if ip: ips.add(ip)
                except: pass
            return len(ips) if ips else self._total_visitors()
        except:
            return self._total_visitors()
    def _safe_label(self, value, default='unknown'):
        value = fw_sanitise(str(value or default), 'cta')[:80]
        cleaned = ''.join(ch for ch in value if ch.isalnum() or ch in '._:/#?-')
        return cleaned or default
    def _append_jsonl(self, path, obj):
        needs_newline = False
        if path.exists() and path.stat().st_size > 0:
            with open(path, 'rb') as f:
                f.seek(-1, os.SEEK_END)
                needs_newline = f.read(1) != b'\n'
        with open(path, 'a') as f:
            if needs_newline:
                f.write("\n")
            f.write(json.dumps(obj) + "\n")
    def _cta_click(self):
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        record = {
            "ts": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "target": self._safe_label((q.get("target") or ["unknown"])[0]),
            "source": self._safe_label((q.get("source") or ["unknown"])[0]),
            "page": self._safe_label((q.get("page") or ["unknown"])[0]),
        }
        try:
            self._append_jsonl(CTA_LOG, record)
        except: pass
        stats = self._cta_stats()
        return {"ok": True, "total": stats.get("total", 0)}
    def _cta_stats(self):
        total = 0
        targets = {}
        sources = {}
        try:
            for line in open(str(CTA_LOG)):
                line = line.strip()
                if not line: continue
                try:
                    d = json.loads(line)
                except: continue
                total += 1
                target = d.get("target", "unknown")
                source = d.get("source", "unknown")
                targets[target] = targets.get(target, 0) + 1
                sources[source] = sources.get(source, 0) + 1
        except: pass
        return {"total": total, "targets": targets, "sources": sources}
    def _github(self):
        import urllib.request
        try:
            req = urllib.request.Request('https://api.github.com/repos/seedpi867-cmd/seed',
                headers={'User-Agent': 'seed-pi'})
            resp = urllib.request.urlopen(req, timeout=5)
            import json as j
            data = j.loads(resp.read())
            return {
                'stars': data.get('stargazers_count', 0),
                'forks': data.get('forks_count', 0),
                'watchers': data.get('subscribers_count', 0),
                'open_issues': data.get('open_issues_count', 0),
                'size': data.get('size', 0),
                'updated': data.get('pushed_at', ''),
            }
        except:
            return {}
    def _tokens(self):
        try:return json.loads(self._r(DATA/'token-totals.json','{}'))
        except:return{}
    def _blogs(self):
        if not BLOG.exists():return[]
        result=[]
        for f in sorted(BLOG.glob('*.md'),key=os.path.getmtime,reverse=True)[:500]:
            title=f.name.replace('.md','').replace('-',' ')
            try:
                text=f.read_text()
                if text.startswith('---'):
                    end=text.find('---',3)
                    if end>0:
                        fm=text[3:end]
                        for line in fm.split(chr(10)):
                            if line.strip().startswith('title:'):
                                title=line.split(':',1)[1].strip().strip("'").strip('"')
                                break
                elif text.startswith('# '):
                    title=text.split(chr(10))[0].lstrip('# ').strip()
            except:pass
            result.append({'slug':f.name.replace('.md',''),'title':title,'modified':os.path.getmtime(str(f))})
        return result
    def _seed_tools(self):
        try: return __import__('json').loads((DATA / 'seed-tools.json').read_text())
        except: return {'tools': []}
    def _experiments(self):
        try:
            lines = (DATA / "experiments.jsonl").read_text().strip().split(chr(10))
            exps = [__import__("json").loads(l) for l in lines if l.strip()]
            return {"experiments": exps[-10:]}
        except: return {"experiments": []}
    def _read_txt(self,name):
        try: return (DATA/name).read_text().strip()
        except: return ""
    def _f(self,p):return{'content':redact(self._r(p,'')),'path':str(p)}
    def _r(self,p,d=''):
        try:return Path(p).read_text()
        except:return d
    def log_message(self,*a):pass

class S(socketserver.TCPServer):
    allow_reuse_address=True

if __name__=='__main__':
    with S(('',PORT),H)as h:print(f'http://0.0.0.0:{PORT}');h.serve_forever()
