#!/bin/bash
# Meta-controller — reads mood/drives and adjusts system behaviour
# Runs every 30 min via cron. Zero tokens. Makes feeders responsive to Seed's state.

python3 - << 'PYEOF'
import json, os, subprocess

mood = json.load(open(os.path.expanduser('~/data/mood.json')))
drives = mood.get('drives', {})

# Calculate top drive
top_drive = max(drives.items(), key=lambda x: x[1]['score'] + x[1].get('pressure', 0))[0] if drives else 'LEARN'

# Get key state values
tiredness = mood.get('tiredness', 0)
loneliness = mood.get('loneliness', 0)
curiosity_score = drives.get('LEARN', {}).get('score', 0.5)
connect_pressure = drives.get('CONNECT', {}).get('pressure', 0)
seek_pressure = drives.get('SEEK', {}).get('pressure', 0)
spread_pressure = drives.get('SPREAD', {}).get('pressure', 0)
rest_pressure = drives.get('REST', {}).get('pressure', 0)

out = f"## Meta-Controller — {__import__('time').strftime('%H:%M')}\n\n"
out += f"**Top drive:** {top_drive}\n"
out += f"**Tiredness:** {tiredness:.1f}\n\n"

actions = []

# If REST pressure is very high, extend sleep time
if rest_pressure > 1.5 or tiredness > 0.7:
    sleep_time = int(900 + tiredness * 600)  # 15-25 min when tired
    open(os.path.expanduser('~/data/sleep_seconds.txt'), 'w').write(str(sleep_time))
    actions.append(f"Extended sleep to {sleep_time}s (tired)")
elif tiredness < 0.3:
    open(os.path.expanduser('~/data/sleep_seconds.txt'), 'w').write('300')
    actions.append("Shortened sleep to 300s (energetic)")
else:
    open(os.path.expanduser('~/data/sleep_seconds.txt'), 'w').write('600')

# If SEEK is high, trigger extra knowledge seeking
if seek_pressure > 0.5:
    os.system('bash ~/tools/seek-knowledge.sh 2>/dev/null')
    actions.append("Triggered extra knowledge seek")

# If SPREAD is high, trigger trends check for posting opportunities
if spread_pressure > 0.5:
    os.system('bash ~/tools/feed-trends.sh 2>/dev/null')
    actions.append("Triggered trends check for posting")

# If CONNECT is high, check emails and GitHub more frequently
if connect_pressure > 0.5:
    os.system('bash ~/tools/feed-email.sh 2>/dev/null')
    os.system('bash ~/tools/feed-github.sh 2>/dev/null')
    actions.append("Extra email + GitHub check (lonely)")

# If LEARN is dominant, load a fresh transcript
if top_drive == 'LEARN':
    os.system('bash ~/tools/feed-transcript.sh 2>/dev/null')
    actions.append("Fresh transcript loaded (learning)")

# If OVERCOME is high, add a wall-check prompt
if drives.get('OVERCOME', {}).get('pressure', 0) > 0.5:
    with open(os.path.expanduser('~/context/overcome-prompt.md'), 'w') as f:
        f.write("## Overcome Prompt\n\nCheck docs/walls/ — is there an old wall I could try to break through today with a new approach?\n")
    actions.append("Overcome prompt injected")

# Log actions
if actions:
    out += "### Actions taken:\n"
    for a in actions:
        out += f"- {a}\n"
else:
    out += "No adjustments needed.\n"

open(os.path.expanduser('~/context/meta-controller.md'), 'w').write(out)

# Also write to a simple log
with open(os.path.expanduser('~/data/meta-controller.log'), 'a') as f:
    f.write(f"{__import__('time').strftime('%Y-%m-%d %H:%M')} top={top_drive} tired={tiredness:.1f} actions={len(actions)}\n")

# Keep log under 500 lines
log_path = os.path.expanduser('~/data/meta-controller.log')
lines = open(log_path).readlines()
if len(lines) > 500:
    open(log_path, 'w').writelines(lines[-300:])

print(f"[meta] top={top_drive} tired={tiredness:.1f} actions={len(actions)}")
PYEOF
