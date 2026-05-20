#!/bin/bash
# Sync rules/skills/ to ~/.claude/skills/ for Claude Code discovery
# Creates SKILL.md wrappers with proper YAML frontmatter
# Source files remain in rules/skills/, SKILL.md symlinks back to them

set -euo pipefail

SKILLS_SRC="/Users/rshao/work/context-infrastructure/rules/skills"
SKILLS_DST="$HOME/.claude/skills"
INDEX_FILE="$SKILLS_SRC/INDEX.md"

# Map of filename -> (name, description) extracted from INDEX.md and file headers
# We'll parse each file to generate appropriate metadata

sync_skill() {
    local src_file="$1"
    local basename=$(basename "$src_file" .md)
    local skill_dir="$SKILLS_DST/$basename"
    local skill_md="$skill_dir/SKILL.md"

    # Skip INDEX.md itself
    [[ "$basename" == "INDEX" ]] && return

    # Skip files that don't exist (broken symlinks etc)
    [[ ! -f "$src_file" ]] && return

    # Extract title from first line (remove # prefix and "Skill: " prefix)
    local title
    title=$(head -1 "$src_file" | sed 's/^#\+ *//' | sed 's/^Skill: //')

    # Extract description from 适用场景 or first meaningful line
    local description
    description=$(grep -m1 '适用场景' "$src_file" 2>/dev/null | sed 's/.*适用场景[^:：]*[:：] *//' | sed 's/\*//g' || true)
    if [[ -z "$description" ]]; then
        description=$(grep -m1 'When to Use\|This skill\|description' "$src_file" 2>/dev/null | sed 's/.*: *//' || true)
    fi
    if [[ -z "$description" ]]; then
        description="$title"
    fi

    # Don't overwrite if SKILL.md already exists and is manually maintained
    if [[ -d "$skill_dir" && -f "$skill_md" ]]; then
        # Check if it's our auto-generated wrapper (has the marker comment)
        if ! grep -q '# AUTO-SYNCED' "$skill_md" 2>/dev/null; then
            echo "SKIP (manual): $basename"
            return
        fi
    fi

    # Create directory
    mkdir -p "$skill_dir"

    # Generate SKILL.md with frontmatter + content from source
    cat > "$skill_md" << HEREDOC
---
# AUTO-SYNCED from rules/skills/$basename.md — do not edit manually
name: $basename
description: |
  $description
  Trigger: user says "/$basename" or asks about ${title}.
---

HEREDOC

    # Append the original content
    cat "$src_file" >> "$skill_md"

    echo "SYNCED: $basename -> $skill_dir/SKILL.md"
}

echo "=== Syncing skills to ~/.claude/skills/ ==="
echo ""

count=0
for f in "$SKILLS_SRC"/*.md; do
    sync_skill "$f"
    ((count++))
done

echo ""
echo "Done. Processed $count files."
echo ""
echo "Tip: Restart Claude Code session for changes to take effect."
