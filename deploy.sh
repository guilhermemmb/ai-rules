#!/usr/bin/env bash
# deploy.sh — single command to rebuild and distribute all AI rules
# Order: merge AGENTS.md → build agent JSON → patch settings.json → rulesync
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
AGENTS_JSON="/tmp/agents-config.json"

log() { echo "==> $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ── 1. Merge AGENTS.md ───────────────────────────────────────────────────────
log "merge AGENTS.md"
"$SCRIPT_DIR/merge-rules.sh"

# ── 2. Build per-agent tool/MCP config ───────────────────────────────────────
log "build agent config → $AGENTS_JSON"
"$SCRIPT_DIR/build-agents.sh" "$AGENTS_JSON"

# ── 3. Patch ~/.claude/settings.json with agents block ───────────────────────
log "patch $SETTINGS"
[[ -f "$SETTINGS" ]] || die "$SETTINGS not found"
[[ -f "$AGENTS_JSON" ]] || die "$AGENTS_JSON not found"

TMP=$(mktemp)
jq --slurpfile agents "$AGENTS_JSON" '.agents = $agents[0].agents' "$SETTINGS" > "$TMP"
mv "$TMP" "$SETTINGS"
log "agents block written to settings.json"

# ── 4. rulesync: distribute rules, subagents, skills, commands ───────────────
log "rulesync generate (global)"
cd "$SCRIPT_DIR"
rulesync generate

log "done."
