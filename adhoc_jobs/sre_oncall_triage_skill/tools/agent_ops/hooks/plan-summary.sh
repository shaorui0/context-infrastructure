#!/bin/bash
# PreToolUse hook on ExitPlanMode — plain-language summary of the plan via `claude -p`.
# Plans tend to drown intent in implementation detail; this surfaces the WHAT.
#
# --tools "" disables every tool in the nested call → no hooks fire → recursion-safe.
# --no-session-persistence keeps the call out of `claude --resume`.

INPUT=$(cat)
PLAN=$(echo "$INPUT" | jq -r '.tool_input.plan // empty')
[ -z "$PLAN" ] && exit 0

PROMPT=$(cat <<EOF
Summarize this plan in 5 bullets or fewer. Focus on INTENT and OUTCOMES, not
file paths or implementation steps. Plain Chinese, terse, one line per bullet.
Lead with the user-visible change.

The plan:

---
$PLAN
EOF
)

{
  echo
  echo "═══ 计划摘要 (claude -p haiku) ═══"
  perl -e 'alarm shift; exec @ARGV' 30 \
    claude -p --tools "" --no-session-persistence --model haiku "$PROMPT" 2>&1
  echo "═════════════════════════════════"
} >&2

exit 0
