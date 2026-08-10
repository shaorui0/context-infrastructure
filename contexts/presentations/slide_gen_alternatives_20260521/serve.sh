#!/usr/bin/env bash
# Start a local HTTP server for this deck.
# Usage: ./serve.sh [port]   (default port 8765)
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8765}"
echo "Serving deck at http://localhost:${PORT}/"
echo "Press Ctrl+C to stop."
python3 -m http.server "$PORT"
