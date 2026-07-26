#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Deploying agents → ~/.claude/agents/ ==="
cp -f agents/*.md ~/.claude/agents/

echo "=== Deploying agents → ~/.config/opencode/agents/ ==="
mkdir -p ~/.config/opencode/agents/
cp -f agents/*.md ~/.config/opencode/agents/

echo "=== Deploying rules → ~/.claude/rules/ ==="
mkdir -p ~/.claude/rules/
cp -f rules/*.md ~/.claude/rules/

echo "=== Deploying skills → ~/.claude/skills/ ==="
mkdir -p ~/.claude/skills/
for skill in skills/*/; do
  name=$(basename "$skill")
  echo "  skills/$name"
  mkdir -p ~/.claude/skills/"$name"
  cp -f "$skill"/* ~/.claude/skills/"$name"/
done

echo "=== Deploying commands → ~/.claude/commands/ ==="
mkdir -p ~/.claude/commands/
cp -f commands/*.md ~/.claude/commands/

echo "=== Building AGENTS.md (global instructions) ==="
python3 -c "
import os
out = []
for f in sorted(os.listdir('rules')):
    if not f.endswith('.md'):
        continue
    with open(f'rules/{f}') as fh:
        content = fh.read()
    if content.startswith('---'):
        idx = content.find('---', 4)
        body = content[idx+4:].strip() if idx >= 0 else content.strip()
    else:
        body = content.strip()
    out.append(body)
    out.append('')
with open('/tmp/AGENTS-build.md', 'w') as fh:
    fh.write('\n'.join(out) + '\n')
print('  Generated /tmp/AGENTS-build.md')
"
cp -f /tmp/AGENTS-build.md ~/.config/opencode/AGENTS.md
echo "  → ~/.config/opencode/AGENTS.md"

echo "=== Deploying ~/.claude/settings.json ==="
cp -f claude/settings.json ~/.claude/settings.json

echo "=== Deploying opencode.jsonc ==="
cp -f opencode.jsonc ~/.config/opencode/opencode.jsonc

echo "=== Installing Datadog pup skills ==="
pup skills install claude 2>/dev/null || echo "  WARNING: pup not installed"

echo ""
echo "Done. Deployed to:"
echo "  ~/.claude/          (agents, rules, skills, commands, settings.json)"
echo "  ~/.config/opencode/ (agents, AGENTS.md, opencode.jsonc)"
