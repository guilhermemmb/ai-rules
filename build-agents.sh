#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📝 Merging rules..."
"$REPO_ROOT/merge-rules.sh"

echo "🚀 Broadcasting to ~/.codex..."
cd "$REPO_ROOT"
rulesync generate --global 2>&1 | grep -v "non-root rulesync rules found"

echo "🪨 Cleaning stale caveman hooks from settings.json..."
node -e "
  const fs = require('fs');
  const path = require('os').homedir() + '/.claude/settings.json';
  const s = JSON.parse(fs.readFileSync(path, 'utf8'));
  if (s.hooks && s.hooks.SessionStart) {
    const before = s.hooks.SessionStart.length;
    s.hooks.SessionStart = s.hooks.SessionStart.filter(e =>
      !e.hooks || !e.hooks.some(h => h.command && h.command.includes('caveman-session-guidance'))
    );
    const removed = before - s.hooks.SessionStart.length;
    if (removed > 0) {
      fs.writeFileSync(path, JSON.stringify(s, null, 2) + '\n');
      console.log('  Removed ' + removed + ' stale caveman-session-guidance entries.');
    } else {
      console.log('  No stale entries found.');
    }
  }
"

echo "✅ Done!"
