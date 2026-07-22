# Symlink Validation for Rulesync

## Overview

The `validate-rulesync-symlinks.sh` script ensures that all Claude AI tool profiles (Claude Code, OpenCode, Codex, Gemini) have proper symlinks pointing to the **source of truth** in the rules repository.

This guarantees that:
- All tools access the same rules, agents, and commands
- Changes to the source are immediately visible everywhere
- No divergence between tool configurations

## Source of Truth Locations

| Resource | Location |
|----------|----------|
| **Rules** | `/Users/guilhermebomfim/developer/rules/.rulesync/rules/` |
| **Agents** | `/Users/guilhermebomfim/developer/rules/.agents/agents/` |
| **Commands** | `/Users/guilhermebomfim/developer/rules/.agents/commands/` |
| **Skills** | `/Users/guilhermebomfim/developer/rules/.agents/skills/` |

## Symlink Targets

For each tool profile (Claude Code, OpenCode, Codex, Gemini):

```
~/.claude/rules        → .../rules/.rulesync/rules
~/.claude/agents       → .../rules/.agents/agents
~/.claude/commands     → .../rules/.agents/commands
~/.claude/skills       → .../rules/.agents/skills

(same pattern for ~/.opencode/, ~/.codex/, ~/.gemini/)
```

## Usage

### Check symlink status

```bash
./validate-rulesync-symlinks.sh
```

**Output:**
- ✓ (green) — symlink is valid
- → (yellow) — symlink is missing (needs repair)
- ✗ (red) — symlink points to wrong target
- ⊘ (gray) — profile directory doesn't exist yet

**Exit codes:**
- `0` — all symlinks valid
- `1` — some symlinks needed repair (and were auto-repaired with `--repair`)
- `2` — errors found (e.g., broken symlink target)

### Repair symlinks

```bash
./validate-rulesync-symlinks.sh --repair
```

This will:
1. **Backup existing directories** — if a real directory exists instead of a symlink, it's backed up to `<path>.backup.<timestamp>`
2. **Create missing symlinks** — for any profile that doesn't have the symlink yet
3. **Fix broken symlinks** — replace incorrect targets

After repair, run without `--repair` to verify everything is valid.

## Examples

### First-time setup
```bash
$ ./validate-rulesync-symlinks.sh
✗ /Users/guilhermebomfim/.claude/rules (dir exists, not a symlink)
→ /Users/guilhermebomfim/.codex/rules (missing)

# Fix all issues
$ ./validate-rulesync-symlinks.sh --repair
✓ replaced (backed up to ...rules.backup.1784748073)
✓ created

# Verify all fixed
$ ./validate-rulesync-symlinks.sh
✓ All symlinks are valid
```

### After creating new profile
If you install OpenCode or Gemini later, the script will automatically create symlinks to the source of truth:

```bash
$ ./validate-rulesync-symlinks.sh --repair
✓ created  /Users/guilhermebomfim/.opencode/rules
✓ created  /Users/guilhermebomfim/.opencode/agents
...
```

## Backups

When replacing existing directories with symlinks, the original directory is backed up with a timestamp:

```
~/.claude/rules           → symlink (new)
~/.claude/rules.backup.1784748073  ← original directory preserved
```

You can safely delete the backup once you've verified everything works:

```bash
rm -rf ~/.claude/rules.backup.*
```

## Automation

Consider running this script as part of your setup/onboarding process or periodically to ensure symlinks stay in sync:

```bash
# Check and repair monthly
(crontab -l 2>/dev/null; echo "0 0 1 * * cd /Users/guilhermebomfim/developer/rules && ./validate-rulesync-symlinks.sh --repair") | crontab -
```

Or add to a shell initialization hook:

```bash
# ~/.zshrc or ~/.bashrc
if ! $(/Users/guilhermebomfim/developer/rules/validate-rulesync-symlinks.sh >/dev/null 2>&1); then
    echo "⚠ Rulesync symlinks need repair. Run: validate-rulesync-symlinks.sh --repair"
fi
```
