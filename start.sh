#!/usr/bin/env bash
# Starts backend (8000) + frontend (5173). Ctrl+C stops both.
ROOT="$(cd "$(dirname "$0")" && pwd)"
(cd "$ROOT/backend" && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT
cd "$ROOT/frontend" && npm run dev
