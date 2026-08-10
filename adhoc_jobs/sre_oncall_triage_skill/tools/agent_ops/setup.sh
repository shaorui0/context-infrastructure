#!/bin/bash
# setup.sh — Install agent hooks + skills on this machine
#
# What it does:
#   1. Symlinks hooks into ~/.claude/hooks/
#   2. Ensures ~/.claude/settings.json has all hook entries from hooks-manifest.json
#   3. Creates logs/ dir if missing
#   4. Symlinks skills into ~/.claude/skills/
#
# Source of truth:
#   - Hook scripts:      ./hooks/*.sh
#   - Hook registrations: ./hooks-manifest.json
#   - Skills:            ../../skills/*/SKILL.md
#   - settings.json is personal config — we only ADD missing hook entries, never overwrite
#
# Usage:
#   bash tools/agent_ops/setup.sh
#   bash tools/agent_ops/setup.sh --dry-run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_SRC="$SCRIPT_DIR/hooks"
HOOKS_DST="$HOME/.claude/hooks"
LOGS_DIR="$SCRIPT_DIR/logs"
SETTINGS="$HOME/.claude/settings.json"
MANIFEST="$SCRIPT_DIR/hooks-manifest.json"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

log() { echo "  $*"; }
run() {
  if $DRY_RUN; then echo "  [dry-run] $*"; else eval "$*"; fi
}

echo ""
echo "agent-ops setup"
echo "  repo:     $REPO_DIR"
echo "  hooks →   $HOOKS_DST"
echo "  manifest: $MANIFEST"
echo "  logs:     $LOGS_DIR"
$DRY_RUN && echo "  mode:     DRY RUN — no changes will be made"
echo ""

# ─── 1. Symlink hook scripts ──────────────────────────────────────────────────

if [[ ! -d "$HOOKS_DST" ]]; then
  log "Creating $HOOKS_DST"
  run "mkdir -p '$HOOKS_DST'"
fi

for hook in k8s-gate.sh audit-log.sh audit-pre.sh mcp-audit.sh plan-safety-review.sh plan-summary.sh; do
  src="$HOOKS_SRC/$hook"
  dst="$HOOKS_DST/$hook"
  if [[ ! -f "$src" ]]; then
    echo "  [WARN] hook not found: $src — skipping"
    continue
  fi
  if [[ -L "$dst" && "$(readlink "$dst")" == "$src" ]]; then
    log "already linked: $hook"
  else
    log "symlink: $dst → $src"
    run "ln -sf '$src' '$dst'"
  fi
  run "chmod +x '$src'"
done

# ─── 2. Ensure logs dir exists ────────────────────────────────────────────────

if [[ ! -d "$LOGS_DIR" ]]; then
  log "Creating logs dir: $LOGS_DIR"
  run "mkdir -p '$LOGS_DIR'"
fi

# ─── 3. Ensure settings.json has all hook entries from manifest ───────────────

if [[ ! -f "$MANIFEST" ]]; then
  echo "  [WARN] hooks-manifest.json not found — skipping settings.json sync"
elif [[ ! -f "$SETTINGS" ]]; then
  log "[WARN] $SETTINGS not found"
  log "Create it manually, then re-run setup.sh. Required hook entries:"
  python3 -m json.tool "$MANIFEST"
else
  log "Syncing hooks from manifest → settings.json"
  # Use Python to merge manifest entries into settings.json (idempotent)
  if $DRY_RUN; then
    log "[dry-run] would merge hooks-manifest.json into settings.json"
    python3 -c "
import json, sys

with open('$MANIFEST') as f:
    manifest = json.load(f)
with open('$SETTINGS') as f:
    settings = json.load(f)

hooks = settings.setdefault('hooks', {})
added = 0
for phase in ['PreToolUse', 'PostToolUse']:
    if phase not in manifest:
        continue
    existing = hooks.setdefault(phase, [])
    existing_matchers = {e.get('matcher') for e in existing}
    for entry in manifest[phase]:
        if entry['matcher'] not in existing_matchers:
            print(f'  [dry-run] would add {phase}: {entry[\"matcher\"]}')
            added += 1
if added == 0:
    print('  All hook entries already present.')
"
  else
    python3 -c "
import json

with open('$MANIFEST') as f:
    manifest = json.load(f)
with open('$SETTINGS') as f:
    settings = json.load(f)

hooks = settings.setdefault('hooks', {})
added = 0
for phase in ['PreToolUse', 'PostToolUse']:
    if phase not in manifest:
        continue
    existing = hooks.setdefault(phase, [])
    existing_matchers = {e.get('matcher') for e in existing}
    for entry in manifest[phase]:
        if entry['matcher'] not in existing_matchers:
            existing.append(entry)
            print(f'  Added {phase}: {entry[\"matcher\"]}')
            added += 1

if added == 0:
    print('  All hook entries already present.')
else:
    with open('$SETTINGS', 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(f'  Wrote {added} new entries to settings.json')
"
  fi
fi

# ─── 4. Path normalization (legacy cleanup) ──────────────────────────────────

if [[ -f "$SETTINGS" ]] && grep -q "tools/agent_ops/hooks" "$SETTINGS" 2>/dev/null; then
  log "Patching absolute repo paths → ~/.claude/hooks/ in settings.json"
  if ! $DRY_RUN; then
    sed -i '' \
      's|bash [^ ]*/tools/agent_ops/hooks/k8s-gate.sh|bash ~/.claude/hooks/k8s-gate.sh|g;
       s|bash [^ ]*/tools/agent_ops/hooks/audit-pre.sh|bash ~/.claude/hooks/audit-pre.sh|g;
       s|bash [^ ]*/tools/agent_ops/hooks/audit-log.sh|bash ~/.claude/hooks/audit-log.sh|g;
       s|bash [^ ]*/tools/agent_ops/hooks/mcp-audit.sh|bash ~/.claude/hooks/mcp-audit.sh|g;
       s|python3 [^ ]*/tools/agent_ops/hooks/scope-gate.py|python3 ~/.claude/hooks/scope-gate.py|g' \
      "$SETTINGS"
  else
    log "[dry-run] would normalize absolute paths to ~/.claude/hooks/"
  fi
fi

# ─── 5. Register agent ───────────────────────────────────────────────────────

AGENTS_DST="$HOME/.claude/agents"
AGENT_DEF="$REPO_DIR/CLAUDE.md"
AGENT_LINK="$AGENTS_DST/sre-oncall-triage.md"

[[ -d "$AGENTS_DST" ]] || run "mkdir -p '$AGENTS_DST'"

if [[ -L "$AGENT_LINK" && "$(readlink "$AGENT_LINK")" == "$AGENT_DEF" ]]; then
  log "agent already linked: sre-oncall-triage.md"
else
  log "symlink: $AGENT_LINK → $AGENT_DEF"
  run "ln -sf '$AGENT_DEF' '$AGENT_LINK'"
fi

# ─── 6. Symlink skills ───────────────────────────────────────────────────────

SKILLS_SRC="$REPO_DIR/skills"
SKILLS_DST="$HOME/.claude/skills"

if [[ -d "$SKILLS_SRC" ]]; then
  [[ -d "$SKILLS_DST" ]] || run "mkdir -p '$SKILLS_DST'"
  for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name="$(basename "$skill_dir")"
    src="$skill_dir"
    dst="$SKILLS_DST/$skill_name"
    if [[ -L "$dst" && "$(readlink "$dst")" == "$src" ]]; then
      log "already linked: $skill_name"
    else
      log "symlink: $dst → $src"
      run "ln -sf '$src' '$dst'"
    fi
  done
else
  log "[WARN] skills/ dir not found at $SKILLS_SRC — skipping skill registration"
fi

echo ""
echo "Done. Verify with:"
echo "  ls -la ~/.claude/hooks/"
echo "  ls -la ~/.claude/skills/ | grep sre-oncall"
echo "  cat ~/.claude/settings.json | python3 -m json.tool | grep -A2 matcher"
echo ""
