#!/bin/bash
# Deploy blog posts to your website repo
REPO=~/seed-web
[ -d "$REPO" ] || { echo "No website repo at $REPO"; exit 1; }
cd "$REPO"
cp ~/blog/*.md posts/ 2>/dev/null
python3 -c "
import json, os, time
from pathlib import Path
posts = []
for f in sorted(Path('posts').glob('*.md'), key=os.path.getmtime, reverse=True):
    if f.name == 'index.json': continue
    content = f.read_text()
    title = content.split('\\n')[0].lstrip('# ').strip() if content.startswith('#') else f.stem.replace('-',' ').title()
    posts.append({'title':title,'slug':f.stem,'date':time.strftime('%Y-%m-%d',time.localtime(os.path.getmtime(str(f)))),'tags':['seed'],'description':' '.join(content[:150].split())})
Path('posts/index.json').write_text(json.dumps(posts,indent=2))
print(f'Index: {len(posts)} posts')
"
git add -A
git diff --cached --quiet && echo "Nothing to deploy" && exit 0
git commit -m "Seed blog update — $(date '+%Y-%m-%d')"
git push origin main && echo "Deployed" || echo "Push failed"
