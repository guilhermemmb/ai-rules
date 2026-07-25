#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CUSTOM="$SCRIPT_DIR/custom-configs.claude.json"
TARGET="$HOME/.claude.json"

if [ ! -f "$CUSTOM" ]; then
  echo "ERROR: $CUSTOM not found" >&2
  exit 1
fi

if [ ! -f "$TARGET" ]; then
  echo "ERROR: $TARGET not found" >&2
  exit 1
fi

BEFORE=$(cat "$TARGET")

# Use jq's built-in * operator (recursive object merge, arrays overridden by right side).
# mcpServers entries are replaced wholesale via shallow + merge so that an http-typed
# server in custom doesn't inherit leftover stdio fields from the target.
jq -s '
  .[0] as $target |
  .[1] as $custom |
  ($target * $custom) |
  if ($custom | has("mcpServers")) then
    .mcpServers = (($target.mcpServers // {}) + $custom.mcpServers)
  else . end
' "$TARGET" "$CUSTOM" > /tmp/claude.json.tmp \
  && mv /tmp/claude.json.tmp "$TARGET"

echo "Merged custom-configs.claude.json → $TARGET"
echo ""

jq -rn \
  --argjson before "$BEFORE" \
  --slurpfile aft "$TARGET" \
  --slurpfile cst "$CUSTOM" '
  $aft[0] as $after |
  $cst[0] as $custom |

  def fmt(v): v | tojson;

  ($custom | keys_unsorted)[] |
  . as $k |
  if ($before | has($k) | not) then
    "[+] \($k)  added\n    → \(fmt($custom[$k]))\n"
  elif ($before[$k] == $after[$k]) then empty
  else
    "[~] \($k)  merged\n    before: \(fmt($before[$k]))\n    after:  \(fmt($after[$k]))\n"
  end
'
