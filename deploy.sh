#!/usr/bin/env bash
# ~/developer/dotfiles/ai-rules/deploy.sh
# Sync ai-rules dotfiles → ~/.config/opencode/ runtime
#
# If the oh-my-opencode-slim plugin is not installed yet, auto-runs:
#   bunx oh-my-opencode-slim@latest install
# before overlaying our custom configs.
#
# Usage:
#   ./deploy.sh          — deploy (auto-install plugin if missing)
#   ./deploy.sh --check  — dry-run: show what would change
#   ./deploy.sh --force  — reinstall plugin + deploy (full refresh)
set -euo pipefail

OPENDIR="${HOME}/.config/opencode"
SRCDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEBASE_MEMORY_MCP_BIN="${HOME}/.local/bin/codebase-memory-mcp"
CODEBASE_MEMORY_MCP_INSTALLER_URL="https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh"
MODE="deploy"
MODEL_PROFILE="default"

# ── parse args ──
for arg in "$@"; do
  case $arg in
    --check)
      MODE="--check"
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --model-profile=*)
      MODEL_PROFILE="${arg#*=}"
      shift
      ;;
    *)
      # Preserve positional args if needed
      ;;
  esac
done

red()   { printf '\033[31m%s\033[0m\n' "$1"; }
green() { printf '\033[32m%s\033[0m\n' "$1"; }
cyan()  { printf '\033[36m%s\033[0m\n' "$1"; }

# ── helpers ──
omo_installed() {
  # Check if plugin is registered in opencode.json or opencode.jsonc
  if [ -f "$OPENDIR/opencode.json" ]; then
    python3 -c "import json; c=json.load(open('$OPENDIR/opencode.json')); exit(0 if 'oh-my-opencode-slim' in c.get('plugin',[]) else 1)" 2>/dev/null && return 0
  fi
  if [ -f "$OPENDIR/opencode.jsonc" ]; then
    python3 -c "import json; c=json.load(open('$OPENDIR/opencode.jsonc')); exit(0 if 'oh-my-opencode-slim' in c.get('plugin',[]) else 1)" 2>/dev/null && return 0
  fi
  return 1
}

# ── install codebase-memory-mcp if missing ──
install_codebase_memory_mcp() {
  if [ -x "$CODEBASE_MEMORY_MCP_BIN" ]; then
    green "  ✅ codebase-memory-mcp already installed — skipping"
    return 0
  fi

  if ! command -v curl >/dev/null 2>&1; then
    red "  ❌ curl is required to install codebase-memory-mcp"
    return 1
  fi

  cyan "  ⚡ codebase-memory-mcp not found — installing UI variant..."
  curl -fsSL "$CODEBASE_MEMORY_MCP_INSTALLER_URL" | bash -s -- --ui

  if [ ! -x "$CODEBASE_MEMORY_MCP_BIN" ]; then
    red "  ❌ codebase-memory-mcp installation completed without creating $CODEBASE_MEMORY_MCP_BIN"
    return 1
  fi

  green "  ✅ codebase-memory-mcp installed globally"
}

# ── install omo plugin if missing ──
install_omo() {
  if [ "${FORCE:-false}" = "true" ]; then
    cyan "  🧹 Forcing plugin reinstall..."
  elif omo_installed; then
    green "  ✅ oh-my-opencode-slim already installed — skipping"
    return 0
  else
    cyan "  ⚡ oh-my-opencode-slim not found — installing..."
  fi

  bunx oh-my-opencode-slim@latest install
  green "  ✅ Plugin installed"
}

# ── apply model profile ──
apply_model_profile() {
  python3 "$SRCDIR/scripts/apply-model-profile.py" "$SRCDIR" "$MODEL_PROFILE"
}

# ── rulesync generation ──
run_rulesync() {
  cyan "  📦 Copying engine configs to ~/.config/opencode (No Symlinks)..."
  
  # Ensure target dir exists
  mkdir -p "$OPENDIR"
  
  # Break symlinks and clear manually managed directories
  rm -f "$OPENDIR/opencode.json" "$OPENDIR/oh-my-opencode-slim.json" "$OPENDIR/rulesync.jsonc"
  rm -rf "$OPENDIR/oh-my-opencode-slim" "$OPENDIR/commands"
  rm -f "$OPENDIR/AGENTS.md" "$OPENDIR/opencode.jsonc"
  rm -rf "$OPENDIR/agents" "$OPENDIR/skills"

  cyan "  🔄 Merging MCPs and rules via rulesync (Global Mode)..."
  # We run rulesync generate in global mode so it targets the home directory structure
  (cd "$SRCDIR" && bunx rulesync generate --global --targets opencode)

  # Distribute assets that rulesync doesn't manage natively
  cp "$SRCDIR/opencode.json" "$OPENDIR/opencode.json"
  cp "$SRCDIR/oh-my-opencode-slim.json" "$OPENDIR/oh-my-opencode-slim.json"
  cp "$SRCDIR/rulesync.jsonc" "$OPENDIR/rulesync.jsonc"
  cp -r "$SRCDIR/.rulesync/oh-my-opencode-slim" "$OPENDIR/oh-my-opencode-slim"
  cp -r "$SRCDIR/.rulesync/commands" "$OPENDIR/commands"
  
  # Remove stale local-mode assets if they exist
  if [ -d "$OPENDIR/.opencode" ]; then
    rm -rf "$OPENDIR/.opencode"
  fi

  green "  ✅ Deployment complete via rulesync"
}

# ── deploy ──
deploy() {
  BACKUP_FILE="$SRCDIR/oh-my-opencode-slim.json.tmp.json"
  
  # Create backup
  if [ -f "$SRCDIR/oh-my-opencode-slim.json" ]; then
    cp "$SRCDIR/oh-my-opencode-slim.json" "$BACKUP_FILE"
  fi

  # Ensure restoration on exit
  trap 'if [ -f "$BACKUP_FILE" ]; then mv "$BACKUP_FILE" "$SRCDIR/oh-my-opencode-slim.json"; fi' EXIT

  install_codebase_memory_mcp
  apply_model_profile
  run_rulesync
  install_omo
}

# ── main ──
case "$MODE" in
  "--check")
    echo "🔍 Building temporary global deployment to check for drift..."
    echo ""

    DRIFT=0
    if [ ! -x "$CODEBASE_MEMORY_MCP_BIN" ]; then
      DRIFT=1
      red "  ⚠️  MISSING: global codebase-memory-mcp at $CODEBASE_MEMORY_MCP_BIN"
    fi

    PROFILE_STAGE=$(mktemp -d)
    trap 'rm -rf "$PROFILE_STAGE"' EXIT
    cp "$SRCDIR/oh-my-opencode-slim.json" "$PROFILE_STAGE/oh-my-opencode-slim.json"
    cp -r "$SRCDIR/profiles" "$PROFILE_STAGE/profiles"
    python3 "$SRCDIR/scripts/apply-model-profile.py" "$PROFILE_STAGE" "$MODEL_PROFILE" > /dev/null

    # Let Rulesync validate generated global assets without writing files.
    local_rulesync_output=""
    if ! local_rulesync_output=$(cd "$SRCDIR" && bunx rulesync generate --global --targets opencode --check 2>&1); then
      DRIFT=1
      red "  ⚠️  Rulesync-managed OpenCode assets are out of date:"
      printf '%s\n' "$local_rulesync_output"
    fi

    # Compare files and directories managed directly by this script.
    compare_path() {
      local src="$1" dst="$2" label="$3"

      if [ ! -e "$src" ]; then
        if [ -e "$dst" ]; then
          DRIFT=1
          red "  ⚠️  STALE: $label"
        fi
      elif [ ! -e "$dst" ]; then
        DRIFT=1
        red "  ⚠️  NEW (missing in live): $label"
      elif [ -d "$src" ]; then
        local differences
        differences=$(diff -rq -x .DS_Store "$src" "$dst" 2>&1 || true)
        if [ -n "$differences" ]; then
          DRIFT=1
          red "  ⚠️  DRIFT detected in $label:"
          printf '%s\n' "$differences"
        fi
      elif ! cmp -s "$src" "$dst"; then
        DRIFT=1
        red "  ⚠️  CHANGED: $label"
      fi
    }

    for managed_path in \
      "oh-my-opencode-slim" \
      "commands"; do
      compare_path \
        "$SRCDIR/.rulesync/$managed_path" \
        "$HOME/.config/opencode/$managed_path" \
        ".config/opencode/$managed_path"
    done

    compare_path "$SRCDIR/opencode.json" "$HOME/.config/opencode/opencode.json" ".config/opencode/opencode.json"
    compare_path "$PROFILE_STAGE/oh-my-opencode-slim.json" "$HOME/.config/opencode/oh-my-opencode-slim.json" ".config/opencode/oh-my-opencode-slim.json"
    compare_path "$SRCDIR/rulesync.jsonc" "$HOME/.config/opencode/rulesync.jsonc" ".config/opencode/rulesync.jsonc"
    compare_path "$SRCDIR/.rulesync/oh-my-opencode-slim" "$HOME/.config/opencode/oh-my-opencode-slim" ".config/opencode/oh-my-opencode-slim"
    compare_path "$SRCDIR/.rulesync/commands" "$HOME/.config/opencode/commands" ".config/opencode/commands"

    # 3. Check for stale .opencode directory
    if [ -d "$OPENDIR/.opencode" ]; then
      DRIFT=1
      red "  ⚠️  STALE local-mode directory found: $OPENDIR/.opencode"
    fi

    if [ "$DRIFT" -eq 0 ]; then
      green "  ✅ Live deployment matches repository."
      exit 0
    else
      echo ""
      echo "Run './deploy.sh' to apply changes."
      exit 1
    fi
    ;;
  "deploy"|"")
    echo "⚡ deploy.sh — ai-rules (rulesync global)"
    echo ""
    deploy
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Migration complete."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ;;
  *)
    echo "Usage: ./deploy.sh [--check | --force | --model-profile=<name>]"
    echo "Profiles: $(ls "$SRCDIR/profiles/models" | sed 's/\.yml$//' | paste -sd, -)"
    exit 1
    ;;
esac
