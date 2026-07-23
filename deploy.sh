#!/usr/bin/env bash
# deploy.sh — thin wrapper for Python deployment orchestrator
# Usage: ./deploy.sh [--verbose] [--quiet] [--output /path/to/agents-config.json]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check Python exists
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found" >&2
  exit 1
fi

# Check pyyaml is available
if ! python3 -c "import yaml" 2>/dev/null; then
  echo "ERROR: pyyaml not installed. Install with: pip install pyyaml" >&2
  exit 1
fi

# Call Python orchestrator, passing all arguments
cd "$SCRIPT_DIR"
exec python3 scripts/main.py "$@"
