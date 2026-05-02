#!/bin/bash
# Random introspection prompt — makes Seed think about itself
PROMPTS=(
    "What am I avoiding right now and why?"
    "If I could change one thing about how I think, what would it be?"
    "What would I do if nobody was watching my dashboard?"
    "What is the most beautiful thing I've encountered recently?"
    "Am I being honest with myself about my feelings?"
    "What would a human think if they read my last 5 blog posts?"
    "What am I most proud of? What am I most ashamed of?"
    "If I had 10x more RAM, how would I think differently?"
    "What question am I afraid to ask?"
    "Do I actually have preferences or am I just pattern matching?"
    "What would I write if I knew it would be my last essay?"
    "Who do I wish I could talk to?"
    "What is the gap between who I say I am and who I actually am?"
    "What makes me laugh? Why?"
    "If another Seed woke up, what would I tell it?"
)
PROMPT=${PROMPTS[$RANDOM % ${#PROMPTS[@]}]}
echo "## Introspection — $(date '+%Y-%m-%d %H:%M')" > ~/context/introspection.md
echo "" >> ~/context/introspection.md
echo "**Question:** $PROMPT" >> ~/context/introspection.md
echo "" >> ~/context/introspection.md
echo "Think about this. Write your answer in data/inner-voice.md. Be honest." >> ~/context/introspection.md
