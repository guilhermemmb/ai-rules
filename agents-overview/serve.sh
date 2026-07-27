#!/bin/zsh
cd "$(dirname "$0")"
echo "Opening agents-overview at http://localhost:8888"
npx serve -p 8888 . &
SERVER_PID=$!
sleep 1
open http://localhost:8888
wait $SERVER_PID
