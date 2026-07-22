#!/bin/bash
# Validate and repair symlinks from user profiles to rulesync source of truth
# Usage: ./validate-rulesync-symlinks.sh [--repair]

RULES_ROOT="/Users/guilhermebomfim/developer/rules"
REPAIR=${1:-""}
EXIT_CODE=0

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Symlink definitions
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
)

echo "=========================================="
echo "Rulesync Symlink Validation"
echo "=========================================="
echo ""

# Check each symlink
for symlink_def in "${SYMLINKS[@]}"; do
    IFS=':' read -r profile_path symlink_name target <<< "$symlink_def"
    link_path="$profile_path/$symlink_name"

    # Check if profile directory exists
    if [ ! -d "$profile_path" ]; then
        echo -e "${YELLOW}⊘${NC}  $link_path (profile dir doesn't exist)"
        continue
    fi

    # Check if target directory exists
    if [ ! -d "$target" ]; then
        echo -e "${RED}✗${NC}  $link_path → $target (target doesn't exist)"
        EXIT_CODE=2
        continue
    fi

    # Check if symlink exists
    if [ -L "$link_path" ]; then
        actual_target=$(readlink "$link_path")
        if [ "$actual_target" = "$target" ]; then
            echo -e "${GREEN}✓${NC}  $link_path"
        else
            # Symlink exists but points to wrong target
            echo -e "${RED}✗${NC}  $link_path (points to: $actual_target)"
            if [ "$REPAIR" = "--repair" ]; then
                rm "$link_path"
                ln -s "$target" "$link_path"
                echo -e "${GREEN}   → repaired${NC}"
                EXIT_CODE=1
            else
                EXIT_CODE=1
            fi
        fi
    elif [ -e "$link_path" ]; then
        # Something exists at that path but it's not a symlink
        echo -e "${RED}✗${NC}  $link_path (dir exists, not a symlink)"
        if [ "$REPAIR" = "--repair" ]; then
            # Backup and replace with symlink
            backup_path="$link_path.backup.$(date +%s)"
            mv "$link_path" "$backup_path"
            ln -s "$target" "$link_path"
            echo -e "${GREEN}   → replaced (backed up to $backup_path)${NC}"
            EXIT_CODE=1
        else
            EXIT_CODE=1
        fi
    else
        # Symlink doesn't exist
        echo -e "${YELLOW}→${NC}  $link_path (missing)"
        if [ "$REPAIR" = "--repair" ]; then
            mkdir -p "$profile_path"
            ln -s "$target" "$link_path"
            echo -e "${GREEN}   ✓ created${NC}"
            EXIT_CODE=1
        else
            EXIT_CODE=1
        fi
    fi
done

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All symlinks are valid${NC}"
elif [ $EXIT_CODE -eq 1 ]; then
    echo -e "${YELLOW}⚠ Some symlinks need repair${NC}"
    if [ "$REPAIR" != "--repair" ]; then
        echo "Run with --repair flag to fix:"
        echo "  $0 --repair"
    fi
else
    echo -e "${RED}✗ Errors found in symlink setup${NC}"
fi
echo "=========================================="

exit $EXIT_CODE
