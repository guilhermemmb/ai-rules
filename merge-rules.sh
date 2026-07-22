#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_FILE="$REPO_ROOT/AGENTS.source.md"
OUTPUT_FILE="$REPO_ROOT/AGENTS.md"
RULES_DIR="$REPO_ROOT/.rulesync/rules"

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "❌ AGENTS.source.md not found"
  exit 1
fi

# Start with source
cp "$SOURCE_FILE" "$OUTPUT_FILE"

# Append all rule files
echo "" >> "$OUTPUT_FILE"
for rule_file in "$RULES_DIR"/*.md; do
  if [[ -f "$rule_file" ]]; then
    filename=$(basename "$rule_file")
    echo "# $filename" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"

    # Skip frontmatter
    tail -n +5 "$rule_file" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
  fi
done

echo "✅ Merged AGENTS.md from AGENTS.source.md + .rulesync/rules/"
