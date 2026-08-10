#!/bin/bash
# PreToolUse hook on ExitPlanMode — SRE safety review of the plan via `claude -p`.
# Advisory only: never blocks. Output goes to stderr → visible alongside the
# plan-approval prompt.
#
# --tools "" disables every tool in the nested call → no Bash/Edit/Write/
# ExitPlanMode invocations → no hooks fire → recursion-safe.
# --no-session-persistence keeps the call out of `claude --resume`.

INPUT=$(cat)
PLAN=$(echo "$INPUT" | jq -r '.tool_input.plan // empty')
[ -z "$PLAN" ] && exit 0

PROMPT=$(cat <<EOF
You are an SRE reviewing a plan that will execute against Datavisor production
or shared cluster environments. The user is an SRE oncall.

Identify ONLY actions that could cause production harm:
- Destructive K8s ops (delete, drain, taint, scale-to-0, rollout restart on hot services)
- Schema migrations or DROP/ALTER on hot tables
- Irreversible AWS changes (terminate, delete, IAM mutations)
- Missing dry-run / canary / staged rollout
- Missing rollback path
- Reads from untrusted cluster output used as inputs to mutations

Output format:
- If safe: a single line "SAFE — <one-sentence reason>"
- If risky: bullet list, each line "[SEV] <concern> — <recommendation>"
  where SEV ∈ {CRITICAL, HIGH, MEDIUM, LOW}

Be terse. No preamble. The plan to review:

---
$PLAN
EOF
)

{
  echo
  echo "═══ SRE safety review (claude -p sonnet) ═══"
  perl -e 'alarm shift; exec @ARGV' 60 \
    claude -p --tools "" --no-session-persistence --model sonnet "$PROMPT" 2>&1
  echo "════════════════════════════════════════════"
} >&2

exit 0
