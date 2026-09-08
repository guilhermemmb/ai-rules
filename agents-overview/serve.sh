#!/bin/zsh
cd "$(dirname "$0")"

# Update data.yaml from the active OMO configuration and opencode.json
echo "🔄 Updating data.yaml..."
python3 ../scripts/update-agents-overview-data.py

echo "Opening agents-overview at http://localhost:8888"
npx serve -p 8888 . &
SERVER_PID=$!
sleep 1
open http://localhost:8888
wait $SERVER_PID
