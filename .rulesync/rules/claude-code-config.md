---
name: claude-code-config
description: Claude Code configuration — status line setup for caveman mode badge
metadata:
  type: rule
---

# Claude Code Configuration

## Status Line Setup

Enable the caveman mode status line badge in Claude Code settings:

```json
{
  "statusLine": {
    "type": "command",
    "command": "context-mode statusline"
  }
}
```

Add to `.claude/settings.json` in each project root, or to `~/.claude/settings.json` for global activation.

Displays active caveman mode level (`[CAVEMAN]`, `[CAVEMAN:LITE]`, `[CAVEMAN:ULTRA]`) in the editor's status bar.
