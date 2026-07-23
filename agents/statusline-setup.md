# Statusline Setup

Configure Claude Code statusline display using ccstatusline.

## Installation

Run interactive setup tool:

```bash
npx -y ccstatusline@latest
```

Or with Bun (faster):

```bash
bunx -y ccstatusline@latest
```

This opens a terminal UI to configure widgets, colors, and layout. Settings are automatically written to `~/.claude/settings.json` as:

```json
{
  "statusLine": {
    "type": "command",
    "command": "npx -y ccstatusline@latest"
  }
}
```

## Configuration

Settings stored in `~/.config/ccstatusline/settings.json`.

Available widgets:
- **Git status** — branch, ahead/behind, staged changes
- **Caveman mode** — current level (lite, full, ultra)
- **Agent status** — current agent (main, github-agent, browser-agent, etc.)
- **Custom text** — static or dynamic content with emoji support
- **Flex separator** — space padding between widgets
- **Token usage** — RTK token stats (if enabled)

## Reopen Configuration

Edit settings anytime:

```bash
ccstatusline
```

Or directly edit `~/.config/ccstatusline/settings.json`.

## Project-Level Override

Add `.claude/settings.json` in project root to override global statusline:

```json
{
  "statusLine": {
    "type": "command",
    "command": "npx -y ccstatusline@latest"
  }
}
```

Useful for showing project-specific status (branch, deployment state, etc.).

## Troubleshooting

- **Command not found**: `npx -y ccstatusline@latest` requires npm/Node.js
- **Config not loading**: Check `~/.config/ccstatusline/settings.json` permissions
- **Slow refresh**: Increase `refreshInterval` in statusLine config (default 10ms)
- **Windows issues**: See [ccstatusline Windows docs](https://github.com/sirmalloc/ccstatusline/blob/main/docs/WINDOWS.md)
