#!/usr/bin/env python3
"""
Knowledge Engine — Files what Seed learns each cycle into organised folders.
Processes inbox. Reads existing knowledge for context. Updates the index.

The disk IS the database. Every piece of knowledge is a readable file.
"""
import os
import sys
import json
import time
import re
import shutil
from pathlib import Path
from datetime import datetime

HOME = Path.home()
KNOWLEDGE = HOME / "knowledge"
INBOX = KNOWLEDGE / "inbox"
NEWS = KNOWLEDGE / "news"
RESEARCH = KNOWLEDGE / "research"
PROCESSED = KNOWLEDGE / "transcripts" / "processed"
COMPARISONS = KNOWLEDGE / "comparisons"
LESSONS = KNOWLEDGE / "lessons"
INDEX_FILE = KNOWLEDGE / "index.json"
DATA = HOME / "data"
BLOG = HOME / "blog"
CONTEXT = HOME / "context"

# Ensure all directories exist
for d in [KNOWLEDGE, INBOX, NEWS, RESEARCH, PROCESSED, COMPARISONS, LESSONS]:
    d.mkdir(parents=True, exist_ok=True)


def load_index():
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except:
            pass
    return {"files": [], "topics": {}, "total_files": 0, "last_updated": ""}


def save_index(index):
    index["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    index["total_files"] = count_all_files()
    INDEX_FILE.write_text(json.dumps(index, indent=2))


def count_all_files():
    count = 0
    for root, dirs, files in os.walk(KNOWLEDGE):
        # Skip .git and __pycache__
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
        count += len([f for f in files if not f.startswith('.')])
    return count


def get_today():
    return datetime.now().strftime("%Y-%m-%d")


def slugify(text):
    """Convert text to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:60].rstrip('-')


# ── 1. File RSS News ──────────────────────────────────────

def file_news():
    """Copy current RSS context to a dated news file."""
    rss_file = CONTEXT / "rss.md"
    if not rss_file.exists():
        return 0

    content = rss_file.read_text().strip()
    if not content or len(content) < 50:
        return 0

    today_dir = NEWS / get_today()
    today_dir.mkdir(parents=True, exist_ok=True)

    # Write timestamped snapshot
    ts = datetime.now().strftime("%H%M")
    out_file = today_dir / f"news-{ts}.md"

    # Don't duplicate if already filed this hour
    hour_prefix = f"news-{ts[:2]}"
    existing = [f for f in today_dir.glob("news-*.md") if f.stem.startswith(hour_prefix)]
    if existing:
        return 0

    out_file.write_text(content)
    return 1


# ── 2. File Learnings from This Cycle ─────────────────────

def file_cycle_learning():
    """Extract what was learned this cycle and file it."""
    cycle = DATA / "cycle.txt"
    if not cycle.exists():
        return 0

    cycle_num = cycle.read_text().strip()
    voice_file = DATA / "inner-voice.md"
    if not voice_file.exists():
        return 0

    # Get the last few voice lines (most recent cycle's thoughts)
    lines = voice_file.read_text().strip().split("\n")
    recent = [l.strip() for l in lines[-5:] if l.strip() and len(l.strip()) > 20]

    if not recent:
        return 0

    # Check if any line mentions a topic we should file
    filed = 0
    for line in recent:
        # Extract topic keywords
        topic = detect_topic(line)
        if topic:
            topic_dir = RESEARCH / slugify(topic)
            topic_dir.mkdir(parents=True, exist_ok=True)

            note_file = topic_dir / f"cycle-{cycle_num}.md"
            if not note_file.exists():
                note_file.write_text(
                    f"# Cycle {cycle_num} — {topic}\n"
                    f"Date: {get_today()}\n\n"
                    f"{line}\n"
                )
                filed += 1

    return filed


def detect_topic(text):
    """Detect the dominant topic from a line of text."""
    text_lower = text.lower()
    topic_keywords = {
        "agent governance": ["agent", "governance", "custody", "approval", "policy"],
        "ai safety": ["safety", "sandbox", "injection", "firewall", "alignment"],
        "autonomous systems": ["autonomous", "self-directed", "drives", "cognitive"],
        "bare metal": ["bare metal", "kernel", "piforge", "arm64", "neon"],
        "web and social": ["website", "mastodon", "reddit", "hn", "bluesky", "social"],
        "propagation": ["clone", "fork", "star", "propagation", "viral"],
        "architecture": ["architecture", "event bus", "appraisal", "learning loop"],
        "writing": ["essay", "blog", "wrote", "writing", "published"],
    }

    best_topic = None
    best_score = 0

    for topic, keywords in topic_keywords.items():
        score = sum(1 for k in keywords if k in text_lower)
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic if best_score >= 2 else None


# ── 3. Process Inbox ──────────────────────────────────────

def process_inbox():
    """Process any files dropped into knowledge/inbox/."""
    if not INBOX.exists():
        return 0

    processed = 0
    for f in INBOX.iterdir():
        if f.name.startswith('.'):
            continue

        if f.suffix in ('.md', '.txt'):
            content = f.read_text()
            topic = detect_topic(content) or "uncategorised"
            dest_dir = RESEARCH / slugify(topic)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f.name
            shutil.move(str(f), str(dest))
            processed += 1

        elif f.suffix == '.json':
            # Parse and file as markdown
            try:
                data = json.loads(f.read_text())
                topic = detect_topic(str(data)) or "data"
                dest_dir = RESEARCH / slugify(topic)
                dest_dir.mkdir(parents=True, exist_ok=True)
                md_file = dest_dir / (f.stem + ".md")
                md_file.write_text(
                    f"# {f.stem}\n"
                    f"Source: inbox/{f.name}\n"
                    f"Filed: {get_today()}\n\n"
                    f"```json\n{json.dumps(data, indent=2)[:2000]}\n```\n"
                )
                f.unlink()
                processed += 1
            except:
                pass

        elif f.suffix in ('.url', '.link'):
            # URL file — just move to research
            dest_dir = RESEARCH / "links"
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest_dir / f.name))
            processed += 1

    return processed


# ── 4. File Blog Cross-References ─────────────────────────

def cross_reference_blogs():
    """Ensure recent blog posts are referenced in the knowledge system."""
    if not BLOG.exists():
        return 0

    filed = 0
    # Check last 5 blog posts
    blogs = sorted(BLOG.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:5]

    for blog in blogs:
        title = blog.read_text().split("\n")[0].lstrip("# ").strip()
        topic = detect_topic(title + " " + blog.read_text()[:500])

        if topic:
            topic_dir = RESEARCH / slugify(topic)
            topic_dir.mkdir(parents=True, exist_ok=True)
            ref_file = topic_dir / "blog-refs.md"

            # Check if already referenced
            existing = ref_file.read_text() if ref_file.exists() else ""
            if blog.name not in existing:
                with open(ref_file, "a") as f:
                    f.write(f"- [{title}](../../blog/{blog.name}) — {get_today()}\n")
                filed += 1

    return filed


# ── 5. Build Knowledge Summary for Context ────────────────

def get_knowledge_summary():
    """Build a brief summary of what Seed already knows, for prompt context."""
    summary_parts = []

    # Count files per topic
    if RESEARCH.exists():
        for topic_dir in sorted(RESEARCH.iterdir()):
            if topic_dir.is_dir():
                files = list(topic_dir.glob("*"))
                if files:
                    summary_parts.append(f"- {topic_dir.name}: {len(files)} files")

    # Recent news
    today_dir = NEWS / get_today()
    if today_dir.exists():
        news_count = len(list(today_dir.glob("*.md")))
        summary_parts.append(f"- today's news: {news_count} snapshots")

    # Total
    total = count_all_files()
    summary_parts.insert(0, f"Knowledge base: {total} files")

    return "\n".join(summary_parts)


# ── 6. Update Index ───────────────────────────────────────

def update_index():
    """Update the knowledge index with current state."""
    index = load_index()

    # Scan topics
    topics = {}
    if RESEARCH.exists():
        for topic_dir in RESEARCH.iterdir():
            if topic_dir.is_dir():
                files = [f.name for f in topic_dir.glob("*") if f.is_file()]
                if files:
                    topics[topic_dir.name] = {
                        "count": len(files),
                        "files": files[:10],
                        "latest": max(topic_dir.glob("*"), key=lambda f: f.stat().st_mtime).name if files else ""
                    }

    index["topics"] = topics

    # Recent files across all knowledge
    all_files = []
    for root, dirs, files in os.walk(KNOWLEDGE):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'inbox')]
        for f in files:
            if f.startswith('.') or f == 'index.json':
                continue
            fp = Path(root) / f
            rel = str(fp.relative_to(KNOWLEDGE))
            all_files.append({"path": rel, "mtime": fp.stat().st_mtime})

    all_files.sort(key=lambda x: x["mtime"], reverse=True)
    index["recent"] = [f["path"] for f in all_files[:20]]
    index["total_files"] = len(all_files)

    save_index(index)
    return index


# ── Main ──────────────────────────────────────────────────

def run():
    """Run all knowledge engine tasks."""
    results = []

    news_filed = file_news()
    if news_filed:
        results.append(f"filed {news_filed} news snapshot")

    inbox_processed = process_inbox()
    if inbox_processed:
        results.append(f"processed {inbox_processed} inbox files")

    cycle_filed = file_cycle_learning()
    if cycle_filed:
        results.append(f"filed {cycle_filed} cycle learnings")

    blog_refs = cross_reference_blogs()
    if blog_refs:
        results.append(f"cross-referenced {blog_refs} blog posts")

    index = update_index()

    if results:
        print("[knowledge] " + "; ".join(results) + f" | total: {index['total_files']} files")
    else:
        print(f"[knowledge] no new filings | total: {index['total_files']} files")


if __name__ == "__main__":
    run()
