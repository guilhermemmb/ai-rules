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

jq -s '.[0] * .[1]' "$TARGET" "$CUSTOM" > /tmp/claude.json.tmp \
  && mv /tmp/claude.json.tmp "$TARGET"

echo "Merged custom-configs.claude.json → $TARGET"
