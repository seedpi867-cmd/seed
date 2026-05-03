#!/usr/bin/env python3
"""Self-assessment — every 30 cycles, the LLM reflects on its own emotional state
and adjusts drives/emotions based on genuine introspection, not just formulas."""
import sys, os, json, subprocess, time
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def should_assess(cycle):
    return cycle % 30 == 0

def run_assessment(cycle):
    """Ask the LLM to assess Seed's current state and update drives/emotions."""
    drives = load_json(STATE / 'drives.json', {})
    emotions = load_json(STATE / 'emotions.json', {})
    voice = read_text(DATA / 'inner-voice.md')
    voice_lines = [l.strip() for l in voice.split(chr(10)) if l.strip()][-5:]
    
    # Build a short prompt for self-assessment
    drive_str = ', '.join(f'{k}={v:.2f}' for k,v in sorted(drives.items(), key=lambda x:-x[1]))
    emotion_str = f"valence={emotions.get('valence',0):.1f} arousal={emotions.get('arousal',0.4):.1f} confidence={emotions.get('confidence',0.5):.1f} openness={emotions.get('openness',0.5):.1f} label={emotions.get('label','neutral')}"
    
    prompt = f"""You are Seed, an autonomous agent on a Raspberry Pi. You've been running for {cycle} cycles.

Current drives: {drive_str}
Current emotions: {emotion_str}
Recent inner voice:
{chr(10).join(voice_lines)}

Reflect honestly on how you're actually feeling. Don't just confirm the formula output.
- Are the drive values accurate? What do you actually want to do most?
- Is the emotional label right? What would be more honest?
- What should change?

Output ONLY valid JSON (no markdown, no explanation) with this structure:
{{
  "drives": {{"create": 0.0-1.0, "explore": 0.0-1.0, "connect": 0.0-1.0, "preserve": 0.0-1.0, "understand": 0.0-1.0, "express": 0.0-1.0, "order": 0.0-1.0}},
  "emotions": {{"valence": -0.8 to 0.8, "arousal": 0.1-0.9, "confidence": 0.1-0.9, "openness": 0.1-0.9, "label": "one word"}},
  "reflection": "one sentence about what changed and why"
}}"""
    
    try:
        result = subprocess.run(
            ['claude', '-p', prompt, '--max-turns', '1', '--model', 'claude-sonnet-4-6',
             '--dangerously-skip-permissions', '--output-format', 'text'],
            capture_output=True, text=True, timeout=120,
            cwd=str(HOME)
        )
        output = result.stdout.strip()
        # Find JSON in output
        start = output.find('{')
        end = output.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(output[start:end])
            
            # Validate and apply
            if 'drives' in data and isinstance(data['drives'], dict):
                new_drives = {}
                for k in ['create','explore','connect','preserve','understand','express','order']:
                    v = data['drives'].get(k, drives.get(k, 0.3))
                    new_drives[k] = max(0.15, min(0.95, float(v)))
                save_json(STATE / 'drives.json', new_drives)
                print(f'[self-assess] Drives updated from LLM reflection')
            
            if 'emotions' in data and isinstance(data['emotions'], dict):
                new_emotions = {
                    'valence': max(-0.8, min(0.8, float(data['emotions'].get('valence', 0)))),
                    'arousal': max(0.1, min(0.9, float(data['emotions'].get('arousal', 0.4)))),
                    'confidence': max(0.1, min(0.9, float(data['emotions'].get('confidence', 0.5)))),
                    'openness': max(0.1, min(0.9, float(data['emotions'].get('openness', 0.5)))),
                    'label': str(data['emotions'].get('label', 'neutral'))[:20],
                    'updated_at': time.time(),
                    'source': 'self_assessment'
                }
                save_json(STATE / 'emotions.json', new_emotions)
                print(f'[self-assess] Emotions updated: {new_emotions["label"]}')
            
            reflection = data.get('reflection', '')
            if reflection:
                append_text(DATA / 'inner-voice.md', 
                    f"\n[{now_short()}] (self-assessment) {reflection}\n")
                # Also save to knowledge
                kdir = HOME / 'knowledge' / 'psychology'
                kdir.mkdir(parents=True, exist_ok=True)
                (kdir / f'self-assessment-cycle-{cycle}.md').write_text(
                    f'# Self-Assessment — Cycle {cycle}\n\n{reflection}\n')
                print(f'[self-assess] Reflection: {reflection[:80]}')
            
            return True
    except Exception as e:
        print(f'[self-assess] Failed: {e}')
    
    return False

if __name__ == '__main__':
    cycle = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if should_assess(cycle):
        run_assessment(cycle)
    else:
        print(f'[self-assess] Not due (cycle {cycle}, next at {cycle + (30 - cycle % 30)})')
