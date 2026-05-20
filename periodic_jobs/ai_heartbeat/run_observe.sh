#!/bin/bash
# Manually trigger L1 Observer
# Usage: ./run_observe.sh [YYYY-MM-DD]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR/src/v0"
python3 observer.py "$@"
