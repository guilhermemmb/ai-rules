#!/usr/bin/env bash
# Build agent configuration from agent definitions
# Parses ai-rules/agents/*.md frontmatter and generates allowlist JSON

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR/agents"
OUTPUT_FILE="${1:-/tmp/agents-config.json}"

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
    # Split by comma, trim spaces, quote each item
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
  for agent_file in "$AGENTS_DIR"/*.md; do
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
} | tee "$OUTPUT_FILE"

# Validate
if ! jq . "$OUTPUT_FILE" > /dev/null 2>&1; then
  echo "ERROR: Invalid JSON" >&2
  exit 1
fi

echo "✓ Config: $OUTPUT_FILE" >&2
