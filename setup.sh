#!/usr/bin/env bash
# One-time setup for macOS / Linux:  bash setup.sh
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "Install Python 3.11-3.13 first."; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "Created .env - paste your API keys into it."; }
echo "Setup complete. Next: put your keys in .env, then run: bash start.sh"
