#!/bin/bash
# Remove all symlinks from user profiles pointing to rulesync source of truth
# Usage: ./remove-rulesync-symlinks.sh

RULES_ROOT="/Users/guilhermebomfim/developer/rules"
EXIT_CODE=0

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Symlink definitions (same as in validate-rulesync-symlinks.sh)
SYMLINKS=(
    # Claude Code
    "$HOME/.claude:rules:$RULES_ROOT/.rulesync/rules"
    "$HOME/.claude:agents:$RULES_ROOT/.agents/agents"
    "$HOME/.claude:commands:$RULES_ROOT/.agents/commands"
    "$HOME/.claude:skills:$RULES_ROOT/.agents/skills"
    # OpenCode
    "$HOME/.opencode:rules:$RULES_ROOT/.rulesync/rules"
    "$HOME/.opencode:agents:$RULES_ROOT/.agents/agents"
    "$HOME/.opencode:commands:$RULES_ROOT/.agents/commands"
    "$HOME/.opencode:skills:$RULES_ROOT/.agents/skills"
    # Codex
    "$HOME/.codex:rules:$RULES_ROOT/.rulesync/rules"
    "$HOME/.codex:agents:$RULES_ROOT/.agents/agents"
    "$HOME/.codex:commands:$RULES_ROOT/.agents/commands"
    "$HOME/.codex:skills:$RULES_ROOT/.agents/skills"
    # Gemini
    "$HOME/.gemini:rules:$RULES_ROOT/.rulesync/rules"
    "$HOME/.gemini:agents:$RULES_ROOT/.agents/agents"
    "$HOME/.gemini:commands:$RULES_ROOT/.agents/commands"
    "$HOME/.gemini:skills:$RULES_ROOT/.agents/skills"
    # .agents profile
    "$HOME/.agents:rules:$RULES_ROOT/.rulesync/rules"
    "$HOME/.agents:agents:$RULES_ROOT/.agents/agents"
    "$HOME/.agents:commands:$RULES_ROOT/.agents/commands"
    "$HOME/.agents:skills:$RULES_ROOT/.agents/skills"
)

echo "=========================================="
echo "Rulesync Symlink Removal"
echo "=========================================="
echo ""

# Remove each symlink
for symlink_def in "${SYMLINKS[@]}"; do
    IFS=':' read -r profile_path symlink_name target <<< "$symlink_def"
    link_path="$profile_path/$symlink_name"

    # Check if symlink exists
    if [ -L "$link_path" ]; then
        rm "$link_path"
        echo -e "${GREEN}✓${NC}  Removed $link_path"
    elif [ -e "$link_path" ]; then
        # Something exists but it's not a symlink
        echo -e "${YELLOW}⊘${NC}  $link_path exists but is not a symlink (skipped)"
    else
        # Symlink doesn't exist
        echo -e "${YELLOW}−${NC}  $link_path (not found)"
    fi
done

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Symlink removal complete${NC}"
echo "=========================================="

exit $EXIT_CODE
