#!/bin/bash
# Convenience wrapper — delegates to the real setup script.
exec bash "$(dirname "$0")/tools/agent_ops/setup.sh" "$@"
