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
MODE="${1:-deploy}"

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

# ── check ──
check_file() {
  local label="$1" src="$2" dst="$3"
  if [ ! -f "$src" ] && [ ! -d "$src" ]; then
    red "  MISSING source: $src"
    return 1
  fi
  if [ ! -e "$dst" ]; then
    red "  NEW      $label → $dst"
    return
  fi
  if diff -q "$src" "$dst" > /dev/null 2>&1; then
    green "  OK       $label"
  else
    red "  DIFF     $label"
  fi
}

check_dir() {
  local label="$1" src="$2" dst="$3"
  local diff_count=0 new=0

  if [ ! -d "$src" ]; then
    red "  MISSING source dir: $src"
    return 1
  fi

  while IFS= read -r -d '' srcf; do
    rel="${srcf#$src/}"
    dstf="$dst/$rel"
    if [ ! -e "$dstf" ]; then
      ((new++))
    elif ! diff -q "$srcf" "$dstf" > /dev/null 2>&1; then
      ((diff_count++))
    fi
  done < <(find "$src" -type f -print0)

  if [ "$new" -eq 0 ] && [ "$diff_count" -eq 0 ]; then
    green "  OK       $label"
  else
    local parts=()
    [ "$new" -gt 0 ] && parts+=("$new new")
    [ "$diff_count" -gt 0 ] && parts+=("$diff_count changed")
    local msg
    printf -v msg '%s' "${parts[*]}"
    msg=${msg// /, }
    red "  DIFF     $label ($msg)"
  fi
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

# ── deploy config overlay ──
deploy() {
  cp "$SRCDIR/opencode.json" "$OPENDIR/opencode.json"
  green "  ✅ opencode.json"

  cp "$SRCDIR/tui.json" "$OPENDIR/tui.json"
  green "  ✅ tui.json"

  cp "$SRCDIR/oh-my-opencode-slim.json" "$OPENDIR/oh-my-opencode-slim.json"
  green "  ✅ oh-my-opencode-slim.json"

  mkdir -p "$OPENDIR/oh-my-opencode-slim"
  rsync -a "$SRCDIR/oh-my-opencode-slim/" "$OPENDIR/oh-my-opencode-slim/"
  green "  ✅ oh-my-opencode-slim/ (10 append files)"

  mkdir -p "$OPENDIR/commands"
  rsync -a "$SRCDIR/commands/" "$OPENDIR/commands/"
  green "  ✅ commands/"

  mkdir -p "$OPENDIR/skills"
  rsync -a "$SRCDIR/skills/" "$OPENDIR/skills/"
  green "  ✅ skills/ (merged — plugin-managed skills preserved)"
}

# ── main ──
case "$MODE" in
  "--check")
    echo "🔍 deploy.sh --check (dry-run)"
    echo ""
  check_file "tui.json"                 "$SRCDIR/tui.json"                 "$OPENDIR/tui.json"
  check_file "opencode.json"            "$SRCDIR/opencode.json"            "$OPENDIR/opencode.json"
  check_file "oh-my-opencode-slim.json" "$SRCDIR/oh-my-opencode-slim.json" "$OPENDIR/oh-my-opencode-slim.json"
  check_dir  "oh-my-opencode-slim/"     "$SRCDIR/oh-my-opencode-slim"      "$OPENDIR/oh-my-opencode-slim"
  check_dir  "commands/"                "$SRCDIR/commands"                 "$OPENDIR/commands"
  check_dir  "skills/"                  "$SRCDIR/skills"                   "$OPENDIR/skills"
    echo ""
    echo "Run './deploy.sh' to apply."
    ;;
  "--force")
    FORCE=true
    echo "⚡ deploy.sh — ai-rules → ~/.config/opencode"
    echo "   (force mode: full reinstall)"
    echo ""
    install_omo
    echo ""
    deploy
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Deploy complete."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Validation:"
    echo "  1. Restart OpenCode"
    echo "  2. Run:  ping all agents"
    echo "  3. If any agent fails, check provider auth with: opencode auth login"
    ;;
  "deploy"|"")
    echo "⚡ deploy.sh — ai-rules → ~/.config/opencode"
    echo ""
    install_omo
    echo ""
    deploy
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Deploy complete."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Validation:"
    echo "  1. Restart OpenCode"
    echo "  2. Run:  ping all agents"
    echo "  3. If any agent fails, check provider auth with: opencode auth login"
    ;;
  *)
    echo "Usage: ./deploy.sh [--check | --force]"
    exit 1
    ;;
esac
