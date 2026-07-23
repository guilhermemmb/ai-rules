#!/usr/bin/env bash
# build-agents.sh — thin wrapper for Python agent config builder
# Usage: ./build-agents.sh [output-file] [--verbose]

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

# Handle positional arg (output file) for backwards compatibility
OUTPUT_FILE="${1:-/tmp/agents-config.json}"
shift || true

# Call Python builder
cd "$SCRIPT_DIR"
exec python3 scripts/build_agents.py --output "$OUTPUT_FILE" "$@"
