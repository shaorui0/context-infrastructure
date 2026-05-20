#!/bin/bash
# Run reflector only if it hasn't successfully run in the last 6 days.
# Stamp file mtime is the source of truth.

STAMP=/tmp/reflector.stamp
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$STAMP" ] && [ -z "$(find "$STAMP" -mtime +6 2>/dev/null)" ]; then
    echo "[$(date)] reflector skipped (last run within 6 days)"
    exit 0
fi

echo "[$(date)] reflector due, triggering"
cd "$SCRIPT_DIR/src/v0"
/opt/homebrew/bin/python3 reflector.py "$@" && touch "$STAMP"
