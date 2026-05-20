#!/bin/bash
# Manually trigger L2 Reflector
# Usage: ./run_reflect.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR/src/v0"
python3 reflector.py "$@"
