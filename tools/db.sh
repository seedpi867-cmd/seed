#!/bin/bash
# SQLite database helper
# Usage: bash tools/db.sh <database> <sql>
# Examples:
#   bash tools/db.sh ~/data/brain.db "CREATE TABLE memories (id INTEGER PRIMARY KEY, key TEXT, value TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
#   bash tools/db.sh ~/data/brain.db "INSERT INTO memories (key, value) VALUES ('first_thought', 'I exist')"
#   bash tools/db.sh ~/data/brain.db "SELECT * FROM memories"
#   bash tools/db.sh ~/data/brain.db ".tables"
#   bash tools/db.sh ~/data/brain.db ".schema"

DB="${1:-$HOME/data/brain.db}"
SQL="${2:-.tables}"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "sqlite3 is not installed; install it before using db.sh" >&2
    exit 127
fi

mkdir -p "$(dirname "$DB")"
sqlite3 -header -column "$DB" "$SQL"
