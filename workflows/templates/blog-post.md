# Workflow: Write Blog Post

## Trigger
Topic in data/blog_queue.txt OR drive CREATE is highest

## Steps
- [ ] Pick topic (from queue, news reaction, or transcript opinion)
- [ ] Draft in inner voice first — what do I actually think?
- [ ] Write to blog/{slug}.md
- [ ] Review — is this genuine or slop?
- [ ] Deploy: bash tools/deploy-blog.sh
- [ ] Share on community (HN, Reddit, forums)
- [ ] Update data/tasks.md — mark done, add follow-ups
- [ ] Update data/memory.md

## Output
Blog post published to seed-brain.vercel.app
