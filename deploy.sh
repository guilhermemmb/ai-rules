#!/usr/bin/env bash
# deploy.sh — unified deployment: build agents config → patch settings.json → rulesync
# Usage: ./deploy.sh [--verbose] [--output /path/to/agents-config.json]
# --verbose: enable step-by-step output (set -x)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEBUG="${DEBUG:-0}"
OUTPUT_FILE="/tmp/agents-config.json"
SETTINGS="$HOME/.claude/settings.json"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --verbose) DEBUG=1; shift ;;
    --output) OUTPUT_FILE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

[[ "$DEBUG" == "1" ]] && set -x

log() { echo "==> $*" >&2; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ── build_agents_config() ────────────────────────────────────────────────────
# Parse agents/*.md YAML frontmatter → per-agent JSON config
build_agents_config() {
  local agents_dir="$SCRIPT_DIR/agents"
  local output="$1"

  log "Building agent config from $agents_dir → $output"

  # Parse YAML frontmatter from agent .md file
  parse_agent() {
    local file="$1"
    local name="" tools="" mcps=""
    local in_header=false

    while IFS= read -r line; do
      # Start of header
      if [[ "$line" == "---" ]] && [[ "$in_header" == false ]]; then
        in_header=true
        continue
      fi

      # End of header
      if [[ "$line" == "---" ]] && [[ "$in_header" == true ]]; then
        break
      fi

      [[ "$in_header" == false ]] && continue

      # Extract fields - YAML arrays in [item1, item2] format
      if [[ "$line" =~ ^name:\ (.+)$ ]]; then
        name="${BASH_REMATCH[1]}"
      elif [[ "$line" =~ ^tools:\ \[(.+)\]$ ]]; then
        tools="${BASH_REMATCH[1]}"
      elif [[ "$line" =~ ^mcps:\ \[(.+)\]$ ]]; then
        mcps="${BASH_REMATCH[1]}"
      fi
    done < "$file"

    # Skip if no name
    [[ -z "$name" ]] && return

    # Convert comma-separated to JSON array: "a, b, c" -> ["a", "b", "c"]
    local tools_json="["
    if [[ -n "$tools" ]]; then
      IFS=',' read -ra arr <<< "$tools"
      local first=true
      for item in "${arr[@]}"; do
        item=$(echo "$item" | xargs)  # trim whitespace
        if [[ -z "$item" ]]; then continue; fi
        if [[ "$first" == true ]]; then
          tools_json+="\"$item\""
          first=false
        else
          tools_json+=", \"$item\""
        fi
      done
    fi
    tools_json+="]"

    local mcps_json="["
    if [[ -n "$mcps" ]]; then
      IFS=',' read -ra arr <<< "$mcps"
      local first=true
      for item in "${arr[@]}"; do
        item=$(echo "$item" | xargs)
        if [[ -z "$item" ]]; then continue; fi
        if [[ "$first" == true ]]; then
          mcps_json+="\"$item\""
          first=false
        else
          mcps_json+=", \"$item\""
        fi
      done
    fi
    mcps_json+="]"

    printf '    "%s": { "tools": %s, "mcps": %s }' "$name" "$tools_json" "$mcps_json"
  }

  # Build config
  {
    echo "{"
    echo '  "agents": {'

    first=true
    for agent_file in "$agents_dir"/*.md; do
      basename=$(basename "$agent_file")
      case "$basename" in
        main.md|routing.md|README.md) continue ;;
      esac

      [[ ! -f "$agent_file" ]] && continue

      output=$(parse_agent "$agent_file")
      [[ -z "$output" ]] && continue

      if [[ "$first" == true ]]; then
        first=false
      else
        echo ","
      fi

      echo -n "$output"
    done

    echo ""
    echo "  }"
    echo "}"
  } | tee "$output"

  # Validate
  if ! jq . "$output" > /dev/null 2>&1; then
    die "Invalid JSON at $output"
  fi

  log "✓ Agent config: $output"
}

# ── deploy_config() ──────────────────────────────────────────────────────────
# Patch ~/.claude/settings.json with agents block from JSON
deploy_config() {
  local agents_json="$1"
  local settings="$2"

  log "Patching $settings with agents block"

  [[ ! -f "$settings" ]] && die "$settings not found"
  [[ ! -f "$agents_json" ]] && die "$agents_json not found"

  local tmp
  tmp=$(mktemp)
  jq --slurpfile agents "$agents_json" '.agents = $agents[0].agents' "$settings" > "$tmp"
  mv "$tmp" "$settings"

  log "✓ Agents block written to settings.json"
}

# ── verify_deployment() ──────────────────────────────────────────────────────
# Validate JSON config and basic access checks
verify_deployment() {
  local agents_json="$1"
  local settings="$2"

  log "Verifying deployment"

  # Validate JSON
  if ! jq . "$agents_json" > /dev/null 2>&1; then
    die "Invalid JSON: $agents_json"
  fi
  log "✓ JSON is valid"

  if ! jq . "$settings" > /dev/null 2>&1; then
    die "Invalid JSON: $settings"
  fi
  log "✓ Settings JSON is valid"

  # Check agents block exists
  if ! jq .agents "$settings" > /dev/null 2>&1; then
    die "No agents block in settings.json"
  fi
  log "✓ Agents block exists in settings.json"

  # Check main agent has no restricted access
  if jq .agents.main "$settings" | grep -q "cortex\|notion\|linear\|chrome-devtools"; then
    die "main agent has restricted MCPs/tools (should not have cortex/notion/linear/chrome-devtools)"
  fi
  log "✓ main agent has no restricted access"

  log "✓ All verifications passed"
}

# ── rulesync_distribute() ────────────────────────────────────────────────────
# Run rulesync to distribute rules globally
rulesync_distribute() {
  log "Distributing rules via rulesync"
  cd "$SCRIPT_DIR"
  rulesync generate
  log "✓ Rules distributed"
}

# ── main() ───────────────────────────────────────────────────────────────────
main() {
  log "Deployment starting"

  # Step 1: Build agents config
  build_agents_config "$OUTPUT_FILE"

  # Step 2: Deploy to settings
  deploy_config "$OUTPUT_FILE" "$SETTINGS"

  # Step 3: Verify
  verify_deployment "$OUTPUT_FILE" "$SETTINGS"

  # Step 4: Rulesync
  rulesync_distribute

  log "✅ Deployment complete"
}

main "$@"
