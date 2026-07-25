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

jq -s '
  def deepmerge(a; b):
    if (a | type) == "object" and (b | type) == "object" then
      ((a | keys) + (b | keys) | unique) | reduce .[] as $k (
        {};
        if (a | has($k)) and (b | has($k)) then
          .[$k] = deepmerge(a[$k]; b[$k])
        elif (a | has($k)) then
          .[$k] = a[$k]
        else
          .[$k] = b[$k]
        end
      )
    elif (a | type) == "array" and (b | type) == "array" then
      a + b
    else
      b
    end;
  deepmerge(.[0]; .[1])
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

  (($before | keys) + ($custom | keys) | unique)[] |
  . as $k |
  if ($custom | has($k) | not) then empty
  elif ($before | has($k) | not) then
    "[+] \($k)  added\n    → \(fmt($custom[$k]))\n"
  elif ($before[$k] == $after[$k]) then empty
  else
    "[~] \($k)  merged\n    before: \(fmt($before[$k]))\n    after:  \(fmt($after[$k]))\n"
  end
'
