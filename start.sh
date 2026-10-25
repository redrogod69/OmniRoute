#!/usr/bin/env bash
# Starts OmniRoute gateway (4000) and web console (8000) on macOS / Linux:  bash start.sh
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run setup.sh first."; exit 1; }
[ -f .env ] || { echo "Create .env from .env.example first."; exit 1; }
set -a; . ./.env; set +a
.venv/bin/litellm --config config.yaml --host 127.0.0.1 --port 4000 > gateway.log 2>&1 &
GW=$!
echo "Waiting for gateway..."
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:4000/health/liveliness && break; sleep 2; done
.venv/bin/python app/ui_server.py &
UI=$!
sleep 2
(open http://127.0.0.1:8000 2>/dev/null || xdg-open http://127.0.0.1:8000 2>/dev/null) &
echo "OmniRoute console: http://127.0.0.1:8000  (Ctrl+C to stop)"
trap "kill $GW $UI" INT TERM
wait
