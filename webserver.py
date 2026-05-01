#!/usr/bin/env python3
"""Seed Brain — Live Dashboard Webserver (light theme)"""
import http.server, json, os, time, socketserver
from pathlib import Path

PORT = 8080
HOME = Path.home()
DATA = HOME / 'data'
BLOG = HOME / 'blog'
CONTEXT = HOME / 'context'
LOGS = DATA / 'logs'

DASHBOARD_HTML = r'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Seed — Live Brain</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#f8f9fa;--surface:#fff;--border:#e5e7eb;--text:#1a1a2e;--dim:#6b7280;--faint:#9ca3af;--accent:#2d6a4f;--accent2:#52b788;--orange:#e8945a;--red:#d47e7e;--blue:#4f46e5;--purple:#7c3aed;--mono:'SF Mono','Fira Code',monospace;--sans:system-ui,-apple-system,sans-serif}
body{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh}
.header{padding:16px 24px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:20px;color:var(--accent);font-family:var(--mono);font-weight:700}
.header .status{font-size:12px;color:var(--dim)}
.dot{width:10px;height:10px;border-radius:50%;background:var(--accent2);display:inline-block;margin-right:8px;animation:pulse 2s infinite}
.dot.sleeping{background:var(--faint);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px;max-width:1400px;margin:0 auto}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.card h2{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;font-family:var(--mono);font-weight:600}
.card.full{grid-column:1/-1}
.stat{font-size:32px;font-weight:800;color:var(--accent);font-family:var(--mono)}
.stat-label{font-size:11px;color:var(--faint);margin-top:2px}
.stats-row{display:flex;gap:24px;flex-wrap:wrap}
.stats-row .stat-box{text-align:center;min-width:60px}
.log{font-family:var(--mono);font-size:12px;line-height:1.8;color:var(--text);white-space:pre-wrap;max-height:500px;overflow-y:auto;word-break:break-all;background:#f1f5f9;border-radius:8px;padding:14px;border:1px solid var(--border)}
.log .seed{color:var(--accent);font-weight:700}
.log .error{color:var(--red);font-weight:700}
.log .phase{color:var(--blue);font-weight:700}
.mood-bar{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.mood-bar .name{width:100px;font-size:13px;color:var(--dim);font-weight:500}
.mood-bar .bar{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.mood-bar .fill{height:100%;border-radius:4px;transition:width .5s}
.mood-bar .val{width:35px;font-size:12px;color:var(--dim);text-align:right;font-family:var(--mono)}
.memory{font-family:var(--mono);font-size:12px;line-height:1.8;color:var(--text);max-height:350px;overflow-y:auto;white-space:pre-wrap;background:#f1f5f9;border-radius:8px;padding:14px;border:1px solid var(--border)}
.blog-list{list-style:none}
.blog-list li{padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;color:var(--text)}
.blog-list li:last-child{border:none}
.blog-list .date{font-size:11px;color:var(--faint);font-family:var(--mono)}
.agent-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;font-family:var(--mono);text-transform:uppercase}
.agent-codex{background:#fff7ed;color:#ea580c;border:1px solid #fed7aa}
.agent-claude{background:#f5f3ff;color:#7c3aed;border:1px solid #ddd6fe}
.agent-gemini{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}
.refresh-bar{height:3px;background:var(--accent2);width:100%;transform-origin:left;animation:drain 5s linear infinite}
@keyframes drain{from{transform:scaleX(1)}to{transform:scaleX(0)}}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style>
</head><body>
<div class="refresh-bar"></div>
<div class="header">
  <h1><span class="dot" id="dot"></span>SEED BRAIN</h1>
  <div class="status" id="ts">connecting...</div>
</div>
<div class="grid">
  <div class="card">
    <h2>Status</h2>
    <div class="stats-row">
      <div class="stat-box"><div class="stat" id="s-cycle">—</div><div class="stat-label">Cycle</div></div>
      <div class="stat-box"><div id="s-agent"></div><div class="stat-label">Agent</div></div>
      <div class="stat-box"><div class="stat" id="s-temp" style="font-size:18px">—</div><div class="stat-label">Temp</div></div>
      <div class="stat-box"><div class="stat" id="s-mem" style="font-size:18px">—</div><div class="stat-label">RAM</div></div>
      <div class="stat-box"><div class="stat" id="s-disk" style="font-size:18px">—</div><div class="stat-label">Disk</div></div>
      <div class="stat-box"><div class="stat" id="s-blogs" style="font-size:18px">—</div><div class="stat-label">Blogs</div></div>
      <div class="stat-box"><div class="stat" id="s-uptime" style="font-size:14px">—</div><div class="stat-label">Uptime</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Health</h2>
    <div class="stats-row">
      <div class="stat-box"><div class="stat" id="h-status" style="font-size:18px">—</div><div class="stat-label">State</div></div>
      <div class="stat-box"><div class="stat" id="h-load" style="font-size:18px">—</div><div class="stat-label">Load</div></div>
      <div class="stat-box"><div class="stat" id="h-throttle" style="font-size:18px">—</div><div class="stat-label">Throttle</div></div>
    </div>
    <div class="memory" id="h-actions" style="max-height:110px;margin-top:12px">loading...</div>
  </div>
  <div class="card">
    <h2>Mood</h2>
    <div id="mood"></div>
  </div>
  <div class="card full">
    <h2>Live Log — Current Cycle <span id="log-cycle" style="color:var(--accent)"></span></h2>
    <div class="log" id="log">waiting for cycle...</div>
  </div>
  <div class="card">
    <h2>Memory</h2>
    <div class="memory" id="memory">loading...</div>
  </div>
  <div class="card">
    <h2>Goals</h2>
    <div class="memory" id="goals">loading...</div>
  </div>
  <div class="card full">
    <h2>Blog Posts</h2>
    <ul class="blog-list" id="blogs"></ul>
  </div>
</div>
<script>
const API = window.location.origin;
function hl(txt) {
  return txt
    .replace(/\[seed\]/g, '<span class="seed">[seed]</span>')
    .replace(/ERROR:/g, '<span class="error">ERROR:</span>')
    .replace(/PHASE \d+/g, '<span class="phase">$&</span>')
    .replace(/Codex|Claude|Gemini/g, '<span class="phase">$&</span>');
}
async function refresh() {
  try {
    const [status, log, memory, goals, blogs] = await Promise.all([
      fetch(API+'/api/status').then(r=>r.json()),
      fetch(API+'/api/log').then(r=>r.json()),
      fetch(API+'/api/memory').then(r=>r.json()),
      fetch(API+'/api/goals').then(r=>r.json()),
      fetch(API+'/api/blogs').then(r=>r.json()),
    ]);
    document.getElementById('ts').textContent = status.ts + ' · ' + status.uptime;
    document.getElementById('s-cycle').textContent = '#'+status.cycle;
    const a = status.agent || 'codex';
    document.getElementById('s-agent').innerHTML = '<span class="agent-badge agent-'+a+'">'+a+'</span>';
    document.getElementById('s-temp').textContent = status.temp;
    document.getElementById('s-mem').textContent = status.memory;
    document.getElementById('s-disk').textContent = status.health && status.health.disk_percent ? status.health.disk_percent.root + '%' : '—';
    document.getElementById('s-blogs').textContent = status.blog_count;
    document.getElementById('s-uptime').textContent = status.uptime;
    const h = status.health || {};
    document.getElementById('h-status').textContent = h.status || 'unknown';
    document.getElementById('h-load').textContent = h.load_average || '—';
    document.getElementById('h-throttle').textContent = h.throttled || '—';
    document.getElementById('h-actions').textContent = h.actions && h.actions.length ? h.actions.join('\n') : 'No health actions taken.';
    const sleeping = status.heartbeat && status.heartbeat.state === 'sleeping';
    document.getElementById('dot').className = sleeping ? 'dot sleeping' : 'dot';
    const m = status.mood || {};
    document.getElementById('mood').innerHTML = ['curiosity','motivation','satisfaction'].map(k => {
      const v = m[k] || 0;
      const colors = {curiosity:'#2d6a4f',motivation:'#ea580c',satisfaction:'#4f46e5'};
      return '<div class="mood-bar"><span class="name">'+k+'</span><div class="bar"><div class="fill" style="width:'+(v*100)+'%;background:'+colors[k]+'"></div></div><span class="val">'+v.toFixed(1)+'</span></div>';
    }).join('');
    document.getElementById('log-cycle').textContent = '#'+log.cycle;
    const el = document.getElementById('log');
    el.innerHTML = hl(log.content || 'No log yet');
    el.scrollTop = el.scrollHeight;
    const lines = (memory.content || '').split('\n');
    document.getElementById('memory').textContent = lines.slice(-50).join('\n');
    document.getElementById('goals').textContent = goals.content || 'No goals set';
    document.getElementById('blogs').innerHTML = (blogs || []).map(b =>
      '<li>'+b.slug+' <span class="date">'+new Date(b.modified*1000).toLocaleDateString()+'</span></li>'
    ).join('') || '<li style="color:var(--faint)">No posts yet — Seed hasn\'t written anything this session</li>';
  } catch(e) { document.getElementById('ts').textContent = 'offline — retrying...'; }
}
refresh(); setInterval(refresh, 5000);
</script>
</body></html>'''

class SeedHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif self.path == '/api/status':
            self.send_json(self.get_status())
        elif self.path == '/api/log':
            self.send_json(self.get_latest_log())
        elif self.path == '/api/memory':
            self.send_json(self.get_file(DATA / 'memory.md'))
        elif self.path == '/api/goals':
            self.send_json(self.get_file(DATA / 'goals.md'))
        elif self.path == '/api/mood':
            self.send_json(self.get_mood())
        elif self.path == '/api/health':
            self.send_json(self.get_health())
        elif self.path == '/api/blogs':
            self.send_json(self.get_blogs())
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_status(self):
        cycle = self.read(DATA / 'cycle.txt', '0').strip()
        heartbeat = {}
        try: heartbeat = json.loads(self.read(DATA / 'heartbeat.json', '{}'))
        except: pass
        mood = {}
        try: mood = json.loads(self.read(DATA / 'mood.json', '{}'))
        except: pass
        uptime = os.popen('uptime -p 2>/dev/null').read().strip()
        mem = os.popen("free -m | awk 'NR==2{printf \"%dMB/%dMB\", $3, $2}'").read().strip()
        temp = os.popen('cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null').read().strip()
        temp = f'{int(temp)/1000:.1f}C' if temp else '?'
        blog_count = len(list(BLOG.glob('*.md'))) if BLOG.exists() else 0
        health = self.get_health()
        return {
            'cycle': cycle, 'heartbeat': heartbeat, 'mood': mood,
            'uptime': uptime, 'memory': mem, 'temp': temp,
            'blog_count': blog_count, 'health': health,
            'agent': self.read(DATA / 'agent.txt', 'codex').strip(),
            'ts': time.strftime('%Y-%m-%d %H:%M:%S')
        }

    def get_latest_log(self):
        cycle = self.read(DATA / 'cycle.txt', '0').strip()
        logfile = LOGS / f'cycle_{cycle}.log'
        content = self.read(logfile, 'No log yet')
        return {'cycle': cycle, 'content': content[-8000:]}

    def get_mood(self):
        try: return json.loads(self.read(DATA / 'mood.json', '{}'))
        except: return {}

    def get_health(self):
        try: return json.loads(self.read(DATA / 'health.json', '{}'))
        except: return {}

    def get_blogs(self):
        if not BLOG.exists(): return []
        posts = []
        for f in sorted(BLOG.glob('*.md'), key=os.path.getmtime, reverse=True)[:20]:
            posts.append({'slug': f.name, 'preview': f.read_text()[:200], 'modified': os.path.getmtime(str(f))})
        return posts

    def get_file(self, path):
        return {'content': self.read(path, ''), 'path': str(path)}

    def read(self, path, default=''):
        try: return Path(path).read_text()
        except: return default

    def log_message(self, *a): pass

class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    with ReuseTCPServer(('', PORT), SeedHandler) as httpd:
        print(f'Seed dashboard on http://0.0.0.0:{PORT}')
        httpd.serve_forever()
