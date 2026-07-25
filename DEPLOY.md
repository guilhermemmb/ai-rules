# Agent Config Deployment

## Overview

Agent definitions in `agents/*.md` define tool/MCP access per agent. Script `build-agents.sh` parses definitions and generates JSON config for `.claude/settings.json`.

## Building Config

```bash
cd bridgetown
./build-agents.sh [output-file]
```

Output: JSON with per-agent tool/MCP restrictions.

Default output: `/tmp/agents-config.json`

## Generated Schema

```json
{
  "agents": {
    "agent-name": {
      "tools": ["Tool1", "Tool2"],
      "mcps": ["mcp1", "mcp2"]
    }
  }
}
```

## Deployment Options

### Option 1: Global (~/.claude/settings.json)

Add agents config to global settings:

```bash
jq '.agents = input.agents' ~/.claude/settings.json /tmp/agents-config.json > ~/.claude/settings.json.tmp
mv ~/.claude/settings.json.tmp ~/.claude/settings.json
```

### Option 2: Per-Repo (.claude/settings.json)

Create per-repo settings with agent restrictions:

```bash
mkdir -p .claude
./build-agents.sh .claude/agents-config.json
# Merge into .claude/settings.json
```

### Option 3: Verify Only (Dry Run)

```bash
./build-agents.sh
cat /tmp/agents-config.json | jq .
```

## Verification

After deployment:

1. Check JSON is valid: `jq . ~/.claude/settings.json`
2. Test main agent has no cortex/Notion/Linear/chrome-devtools-mcp access
3. Test cortex-agent can call cortex MCP
4. Test browser-agent can call chrome-devtools-mcp MCP
5. Test observability-and-troubleshoot can call sentry-mcp MCP

## Agent Files

All agent definitions in `agents/`:
- `main.md` — orchestrator (no browser/obs/cortex/knowledge access)
- `browser-agent.md` — mcp-server-browser, chrome-devtools-mcp
- `observability-and-troubleshoot.md` — sentry-mcp, datadog-mcp (read-only)
- `cortex-agent.md` — cortex MCP
- `knowledge-agent.md` — notion, linear

Frontmatter format:
```yaml
---
name: agent-name
description: ...
tools: [Tool1, Tool2]
mcps: [mcp1, mcp2]
---
```

## Notes

- `main.md` is NOT parsed (main agent tools/MCPs defined in agent definition itself)
- `routing.md` and `README.md` are documentation only (not parsed)
- Script generates `.tools` and `.mcps` lists; future phase will wire these to `.claude/settings.json` permissions layer
- MCPs with HTTP type (cortex) do NOT restrict access in settings.json; they rely on agent definition isolation
