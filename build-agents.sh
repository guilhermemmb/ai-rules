#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📝 Merging rules..."
"$REPO_ROOT/merge-rules.sh"

echo "🚀 Broadcasting to ~/.codex..."
cd "$REPO_ROOT"
rulesync generate --global 2>&1 | grep -v "non-root rulesync rules found"

echo "✅ Done!"
