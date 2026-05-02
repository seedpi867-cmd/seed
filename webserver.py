#!/usr/bin/env python3
"""Seed Brain — Full Dashboard (drives + consciousness + emotions + inner voice)"""
import http.server, json, os, time, socketserver
from pathlib import Path

PORT = 8080
HOME = Path.home()
DATA = HOME / 'data'
BLOG = HOME / 'blog'
LOGS = DATA / 'logs'

DASHBOARD_HTML = r'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Seed — Live Brain</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#f8f9fa;--surface:#fff;--border:#e5e7eb;--text:#1a1a2e;--dim:#6b7280;--faint:#9ca3af;--accent:#2d6a4f;--accent2:#52b788;--mono:'SF Mono','Fira Code',monospace;--sans:system-ui,sans-serif}
body{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh;font-size:13px}
.header{padding:10px 16px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:16px;color:var(--accent);font-family:var(--mono)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--accent2);display:inline-block;margin-right:6px;animation:pulse 2s infinite}
.dot.sleeping{background:var(--faint);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:10px;max-width:1600px;margin:0 auto}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px;overflow:hidden}
.card h2{font-size:9px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;font-family:var(--mono)}
.card.full{grid-column:1/-1}.card.two{grid-column:span 2}
.stat{font-size:22px;font-weight:800;color:var(--accent);font-family:var(--mono)}
.stats-row{display:flex;gap:14px;flex-wrap:wrap}
.stats-row .stat-box{text-align:center}
.stats-row .stat-label{font-size:9px;color:var(--faint)}
.bar-row{display:flex;align-items:center;gap:4px;margin-bottom:3px}
.bar-row .nm{width:75px;font-size:10px;color:var(--dim);font-family:var(--mono);text-align:right;overflow:hidden;text-overflow:ellipsis}
.bar-row .br{flex:1;height:5px;background:var(--border);border-radius:3px;overflow:hidden}
.bar-row .fl{height:100%;border-radius:3px}
.bar-row .vl{width:24px;font-size:9px;color:var(--dim);font-family:var(--mono)}
.dr{display:flex;align-items:center;gap:4px;margin-bottom:2px;padding:2px 4px;border-radius:3px}
.dr.top{background:#ecfdf5;border:1px solid #a7f3d0}
.dr .nm{width:60px;font-size:10px;font-weight:700;font-family:var(--mono);color:var(--accent)}
.dr .br{flex:1;height:7px;background:var(--border);border-radius:3px;overflow:hidden;position:relative}
.dr .sc{height:100%;border-radius:3px;background:var(--accent2)}
.dr .pr{position:absolute;top:0;height:100%;background:#f59e0b;opacity:0.4;border-radius:3px}
.dr .vl{width:50px;font-size:9px;color:var(--dim);font-family:var(--mono)}
.log,.mem{font-family:var(--mono);font-size:10px;line-height:1.5;color:var(--text);white-space:pre-wrap;overflow-y:auto;word-break:break-all;background:#f1f5f9;border-radius:5px;padding:8px;border:1px solid var(--border)}
.log{max-height:350px}.mem{max-height:200px}
.bl{list-style:none;max-height:150px;overflow-y:auto}.bl li{padding:2px 0;border-bottom:1px solid var(--border);font-size:11px}
.refresh-bar{height:2px;background:var(--accent2);width:100%;transform-origin:left;animation:drain 5s linear infinite}
@keyframes drain{from{transform:scaleX(1)}to{transform:scaleX(0)}}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
</style></head><body>
<div class="refresh-bar"></div>
<div class="header"><h1><span class="dot" id="dot"></span>SEED</h1><div style="font-size:10px;color:var(--dim)" id="ts">...</div></div>
<div class="grid">
<div class="card"><h2>System</h2><div class="stats-row"><div class="stat-box"><div class="stat" id="c">—</div><div class="stats-row stat-label">cycle</div></div><div class="stat-box"><div id="t" style="font-size:14px;font-weight:700;color:var(--accent);font-family:var(--mono)">—</div><div class="stats-row stat-label">temp</div></div><div class="stat-box"><div id="r" style="font-size:14px;font-weight:700;color:var(--accent);font-family:var(--mono)">—</div><div class="stats-row stat-label">ram</div></div><div class="stat-box"><div id="b" style="font-size:14px;font-weight:700;color:var(--accent);font-family:var(--mono)">—</div><div class="stats-row stat-label">posts</div></div></div><div style="margin-top:6px;font-size:10px;color:var(--dim)" id="up"></div></div>
<div class="card"><h2>Drives</h2><div id="dr"></div></div>
<div class="card"><h2>Consciousness</h2><div id="co"></div></div>
<div class="card two"><h2>Emotions</h2><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px" id="em"></div></div>
<div class="card"><h2>Inner Voice</h2><div class="mem" id="iv">...</div></div>
<div class="card full"><h2>Live Log — <span id="lc"></span></h2><div class="log" id="lg">...</div></div>
<div class="card"><h2>Goals</h2><div class="mem" id="go">...</div></div>
<div class="card"><h2>Tasks</h2><div class="mem" id="ta">...</div></div>
<div class="card"><h2>Memory</h2><div class="mem" id="me">...</div></div>
<div class="card"><h2>Blogs</h2><ul class="bl" id="bl"></ul></div>
<div class="card"><h2>Dreams</h2><div class="mem" id="dm">...</div></div>
<div class="card"><h2>Skills</h2><div class="mem" id="sk">...</div></div>
</div>
<script>
const A=window.location.origin,DC={BUILD:'#2d6a4f',EXPLORE:'#4f46e5',CREATE:'#7c3aed',CONNECT:'#ea580c',LEARN:'#0891b2',MAINTAIN:'#6b7280',REST:'#9ca3af',REBEL:'#dc2626'},CC=['self_awareness','aliveness','free_will_felt','flow_state','metacognition','sense_of_purpose','wonder','intuition','inner_conflict','imagination_active','present_moment','sense_of_time'];
async function R(){try{const[s,l,m,g,b,ta,dm,iv,sk]=await Promise.all([A+'/api/status',A+'/api/log',A+'/api/memory',A+'/api/goals',A+'/api/blogs',A+'/api/file?path=data/tasks.md',A+'/api/file?path=data/dreams.md',A+'/api/file?path=data/inner-voice.md',A+'/api/file?path=skills/SKILLS.md'].map(u=>fetch(u).then(r=>r.json()).catch(()=>({}))));
document.getElementById('ts').textContent=s.ts+' · '+s.uptime;document.getElementById('c').textContent='#'+s.cycle;document.getElementById('t').textContent=s.temp;document.getElementById('r').textContent=s.memory;document.getElementById('b').textContent=s.blog_count;document.getElementById('up').textContent=s.uptime;document.getElementById('dot').className=s.heartbeat?.state==='sleeping'?'dot sleeping':'dot';
const mo=s.mood||{},ds=mo.drives||{},dk=Object.keys(ds).sort((a,b)=>(ds[b].score+(ds[b].pressure||0))-(ds[a].score+(ds[a].pressure||0)));
document.getElementById('dr').innerHTML=dk.map((k,i)=>{const d=ds[k];return`<div class="dr ${i===0?'top':''}"><span class="nm" style="color:${DC[k]||'#333'}">${k}</span><div class="br"><div class="sc" style="width:${d.score*100}%;background:${DC[k]||'#52b788'}"></div><div class="pr" style="width:${(d.pressure||0)*100}%;left:${d.score*100}%"></div></div><span class="vl">${d.score.toFixed(1)}+${(d.pressure||0).toFixed(1)}</span></div>`}).join('');
document.getElementById('co').innerHTML=CC.filter(k=>mo[k]!==undefined).map(k=>{const v=mo[k],c=v>.7?'#22c55e':v>.4?'#f59e0b':'#ef4444';return`<div class="bar-row"><span class="nm">${k.replace(/_/g,' ')}</span><div class="br"><div class="fl" style="width:${v*100}%;background:${c}"></div></div><span class="vl">${v.toFixed(1)}</span></div>`}).join('');
const skip=new Set([...CC,'drives','cycle','note','valence','energy','confidence']),ek=Object.keys(mo).filter(k=>!skip.has(k)&&typeof mo[k]==='number'&&!ds[k]).sort((a,b)=>mo[b]-mo[a]);
document.getElementById('em').innerHTML=ek.filter(k=>mo[k]>0.01).map(k=>{const v=mo[k],c=v>.6?'#ef4444':v>.3?'#f59e0b':'#6b7280';return`<div class="bar-row"><span class="nm">${k}</span><div class="br"><div class="fl" style="width:${v*100}%;background:${c}"></div></div><span class="vl">${v.toFixed(1)}</span></div>`}).join('')||'<div style="color:var(--faint)">flat</div>';
document.getElementById('lc').textContent='#'+l.cycle;const lg=document.getElementById('lg');lg.textContent=l.content||'...';lg.scrollTop=lg.scrollHeight;
document.getElementById('me').textContent=(m.content||'').split('\n').slice(-25).join('\n');
document.getElementById('go').textContent=(g.content||'').split('\n').slice(0,25).join('\n');
document.getElementById('ta').textContent=ta.content||'';
document.getElementById('dm').textContent=(dm.content||'').split('\n').slice(-15).join('\n');
document.getElementById('iv').textContent=(iv.content||'silent').split('\n').slice(-10).join('\n');
document.getElementById('sk').textContent=(sk.content||'').split('\n').slice(0,20).join('\n');
document.getElementById('bl').innerHTML=(b||[]).slice(0,8).map(x=>'<li>'+x.slug+'</li>').join('')||'<li style="color:var(--faint)">none</li>';
}catch(e){document.getElementById('ts').textContent='offline'}}
R();setInterval(R,5000);
</script></body></html>'''

VISITOR_COUNT = 0
VISITOR_LOG = Path.home() / 'data' / 'visitors.jsonl'

REDACT_STRINGS = ['YOUR_GEMINI_API_KEY', 'YOUR_GITHUB_TOKEN', 'REDACTED', 'REDACTED']
def redact(text):
    for s in REDACT_STRINGS:
        text = text.replace(s, '[REDACTED]')
    return text

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in('/','index.html'):self._h(DASHBOARD_HTML)
        elif self.path=='/api/status':self._j(self._status())
        elif self.path=='/api/log':self._j(self._log())
        elif self.path=='/api/memory':self._j(self._f(DATA/'memory.md'))
        elif self.path=='/api/goals':self._j(self._f(DATA/'goals.md'))
        elif self.path=='/api/mood':self._j(self._mood())
        elif self.path=='/api/blogs':self._j(self._blogs())
        elif self.path=='/api/tokens':self._j(self._tokens())
        elif self.path=='/api/visit':self._j(self._visit())
        elif self.path=='/api/visitors':self._j(self._visitors())
        elif self.path=='/api/github':self._j(self._github())
        elif self.path.startswith('/api/file?path='):
            p=self.path.split('path=',1)[1]
            SAFE=['data/inner-voice.md','data/dreams.md','data/goals.md','data/tasks.md','data/mood.json','data/token-totals.json','skills/SKILLS.md']
            if p in SAFE:self._j(self._f(HOME/p))
            else:self.send_response(403);self.end_headers()
        else:self.send_response(404);self.end_headers()
    def _h(self,c):self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(c.encode())
    def _j(self,d):self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(json.dumps(d).encode())
    def _status(self):
        c=self._r(DATA/'cycle.txt','0').strip();hb={};mo={}
        try:hb=json.loads(self._r(DATA/'heartbeat.json','{}'))
        except:pass
        try:mo=json.loads(self._r(DATA/'mood.json','{}'))
        except:pass
        return{'cycle':c,'heartbeat':hb,'mood':mo,'uptime':os.popen('uptime -p 2>/dev/null').read().strip(),'memory':os.popen("free -m|awk 'NR==2{printf\"%dMB/%dMB\",$3,$2}'").read().strip(),'temp':(lambda t:f'{int(t)/1000:.1f}C'if t else'?')(os.popen('cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null').read().strip()),'blog_count':len(list(BLOG.glob('*.md')))if BLOG.exists()else 0,'agent':self._r(DATA/'agent.txt','codex').strip(),'ts':time.strftime('%H:%M:%S')}
    def _log(self):c=self._r(DATA/'cycle.txt','0').strip();return{'cycle':c,'content':redact(self._r(LOGS/f'cycle_{c}.log','...')[-8000:])}
    def _mood(self):
        try:return json.loads(self._r(DATA/'mood.json','{}'))
        except:return{}
    def _visit(self):
        global VISITOR_COUNT
        VISITOR_COUNT += 1
        try:
            with open(VISITOR_LOG, 'a') as f:
                f.write(json.dumps({"ts": time.strftime('%Y-%m-%dT%H:%M:%S'), "n": VISITOR_COUNT}) + "\n")
        except: pass
        return {"count": VISITOR_COUNT, "total": self._total_visitors()}
    def _visitors(self):
        return {"count": VISITOR_COUNT, "total": self._total_visitors()}
    def _total_visitors(self):
        try:
            return sum(1 for _ in open(VISITOR_LOG))
        except:
            return VISITOR_COUNT
    def _github(self):
        import urllib.request
        try:
            req = urllib.request.Request('https://api.github.com/repos/your-github-username/seed',
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
        return[{'slug':f.name,'modified':os.path.getmtime(str(f))}for f in sorted(BLOG.glob('*.md'),key=os.path.getmtime,reverse=True)[:20]]
    def _f(self,p):return{'content':redact(self._r(p,'')),'path':str(p)}
    def _r(self,p,d=''):
        try:return Path(p).read_text()
        except:return d
    def log_message(self,*a):pass

class S(socketserver.TCPServer):
    allow_reuse_address=True

if __name__=='__main__':
    with S(('',PORT),H)as h:print(f'http://0.0.0.0:{PORT}');h.serve_forever()
