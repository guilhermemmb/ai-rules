---
name: screenshot
description: >
  Generate beautiful screenshots of code, terminal output, shell commands, and
  inline snippets using charmbracelet/freeze. Four modes: code (file), snippet
  (inline text), command (execute & capture output), terminal (tmux pane capture).
metadata:
  version: "1.1.0"
  tags: screenshot,freeze,code,terminal,snippet,command,capture
  alwaysApply: "false"
---

# Screenshot (freeze)

Generate polished PNG screenshots using [`charmbracelet/freeze`](https://github.com/charmbracelet/freeze).

## Prerequisites

Before running any screenshot command, check that the required tools are available.

**Check freeze:**
```bash
which freeze
```
If not found, propose to the user:
```bash
brew install charmbracelet/tap/freeze
```

**Check librsvg** (optional but strongly recommended — speeds up PNG conversion from ~31s to ~1s):
```bash
which rsvg-convert
```
If not found, propose to the user:
```bash
brew install librsvg
```

> **Note:** Never auto-install. Always surface the missing tool and the install command, then wait for the user to confirm before running it.

---

## Four Modes

### 1. Code Screenshot — file input

Render a source file with syntax highlighting.

```bash
freeze <file> \
  -c full \
  --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 \
  --output <name>.png
```

**Example:**
```bash
freeze src/auth.ts -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output auth.png
```

Auto-detects language from file extension. Force with `--language <lang>` if needed.

---

### 2. Snippet Screenshot — inline code

Render a code snippet without a file. Pipe the content directly:

```bash
echo '<code here>' | freeze \
  --language <lang> \
  -c full \
  --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 \
  --output <name>.png
```

Or use a heredoc for multi-line:
```bash
freeze --language python -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output snippet.png << 'EOF'
def greet(name: str) -> str:
    return f"Hello, {name}!"
EOF
```

Use `--show-line-numbers` when the snippet benefits from line context.

---

### 3. Command Screenshot — execute & capture output

Run a shell command and freeze its colored terminal output.

```bash
freeze --execute "<shell command>" \
  -c full \
  --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 \
  --output <name>.png
```

**Examples:**
```bash
# Directory listing
freeze --execute "eza -lah --color always" -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output ls.png

# Git log
freeze --execute "git log --oneline --color=always -10" -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output git-log.png

# Test results
freeze --execute "pnpm test --run 2>&1" -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output tests.png

# Any CLI tool output
freeze --execute "curl -s https://api.example.com/status | jq ." -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output api.png
```

Default timeout is 10s. Override with `--execute.timeout 30s` for slow commands.

---

### 4. Terminal Screenshot — tmux pane capture

Capture the live state of a running terminal session (TUI, REPL, server output, etc.).

```bash
# Capture current pane (pane 0)
tmux capture-pane -pet 0 | freeze -c full --language ansi --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output terminal.png

# Capture a specific pane by index
tmux capture-pane -pet <pane-index> | freeze -c full --language ansi --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output terminal.png
```

Use this for: running servers, TUI apps, REPL sessions, htop/lazygit/etc.

---

## Input + Output Pair

When capturing both the code (input) and its execution result (output), run both modes and produce a named pair:

```bash
# Step 1: code input
freeze <file> -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output <name>-input.png

# Step 2: command output
freeze --execute "<run command>" -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output <name>-output.png
```

Example:
```bash
freeze src/solve.py -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output solve-input.png
freeze --execute "python src/solve.py" -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 --output solve-output.png
```

---

## Styling Defaults

The `full` config preset applies: macOS-style window controls, border radius, drop shadow, padding. Use it by default with compact size flags:

```
--font.size 10 --padding 4,8 --margin 4 --shadow.blur 2
```

Override individual options as needed:

| Option | Flag | Default |
|--------|------|---------|
| Theme | `--theme` | `--theme dracula` |
| Font family | `--font.family` | `--font.family "SF Mono"` |
| Font size | `--font.size` | `10` |
| Padding | `--padding` | `4,8` |
| Margin | `--margin` | `4` |
| Shadow blur | `--shadow.blur` | `2` |
| Line numbers | `--show-line-numbers` | |
| Line range | `--lines` | `--lines 10,25` or `--lines -5,-1` |
| Wrap at column | `--wrap` | `--wrap 80` |
| Background | `--background` | `--background "#1e1e2e"` |
| Border radius | `--border.radius` | `--border.radius 12` |

Popular themes: `charm` (default), `dracula`, `monokai`, `catppuccin-mocha`, `github-dark`, `nord`.

---

## Output Conventions

- Default output path: current working directory
- Naming: `<subject>-<mode>.png` e.g. `auth-code.png`, `deploy-output.png`
- PNG is the default; SVG is faster if the image won't be shared as a raster
- Use `--output /tmp/<name>.png` for throwaway screenshots

---

## Quick Reference

Compact flags alias: `--font.size 10 --padding 4,8 --margin 4 --shadow.blur 2` (always include these)

| Mode | Command |
|------|---------|
| Code file | `freeze <file> -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 -o <name>.png` |
| Snippet | `echo '<code>' \| freeze --language <lang> -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 -o <name>.png` |
| Command output | `freeze --execute "<cmd>" -c full --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 -o <name>.png` |
| Terminal pane | `tmux capture-pane -pet 0 \| freeze -c full --language ansi --font.size 10 --padding 4,8 --margin 4 --shadow.blur 2 -o <name>.png` |
| Input + output | Run code mode + command mode, suffix `-input.png` / `-output.png` |
