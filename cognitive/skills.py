#!/usr/bin/env python3
"""Skill tracking — skills improve from practice, degrade from disuse"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import *

SKILLS_FILE = DATA / 'skill_stats.json'

def load_skills():
    return load_json(SKILLS_FILE, {})

def save_skills(skills):
    save_json(SKILLS_FILE, skills)

def record_skill_use(skill_name, success):
    """Record a skill being used. Success improves it, failure notes the issue."""
    skills = load_skills()
    if skill_name not in skills:
        skills[skill_name] = {'attempts': 0, 'successes': 0, 'streak': 0, 'best_streak': 0, 'last_used': 0}

    s = skills[skill_name]
    s['attempts'] += 1
    s['last_used'] = now()

    if success:
        s['successes'] += 1
        s['streak'] += 1
        if s['streak'] > s['best_streak']:
            s['best_streak'] = s['streak']
    else:
        s['streak'] = 0

    s['rate'] = round(s['successes'] / max(s['attempts'], 1), 2)
    skills[skill_name] = s
    save_skills(skills)
    return s

def get_skill_summary():
    """Get a summary of all skills for working memory"""
    skills = load_skills()
    if not skills:
        return ''
    lines = ['SKILLS:']
    for name, s in sorted(skills.items(), key=lambda x: -x[1].get('rate', 0)):
        rate_pct = int(s.get('rate', 0) * 100)
        lines.append(f"  {name}: {rate_pct}% ({s.get('attempts',0)} attempts, streak {s.get('streak',0)})")
    return '\n'.join(lines[:8])  # Top 8 skills

# Map actions to skills
ACTION_SKILL_MAP = {
    'wrote_essay': 'writing',
    'published_blog': 'publishing',
    'completed_research': 'research',
    'completed_task': 'task_completion',
    'git_committed': 'version_control',
    'dream_completed': 'reflection',
    'error_occurred': None,  # Not a skill
    'nothing_happened': None,
}

def update_skills_from_events(events):
    """Update skill stats from cycle events"""
    for event in events:
        action = event.get('action', '')
        skill = ACTION_SKILL_MAP.get(action)
        if skill:
            success = action != 'error_occurred'
            record_skill_use(skill, success)

if __name__ == '__main__':
    print(get_skill_summary())
