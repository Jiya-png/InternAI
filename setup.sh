#!/usr/bin/env bash
# InternAI - one-time setup for macOS / Linux.  Needs Python 3.11 and Node 18+.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"
PY=${PYTHON:-python3.11}; command -v "$PY" >/dev/null || PY=python3
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# On Linux, install CPU-only torch first (much smaller than the CUDA build)
if [ "$(uname)" = "Linux" ]; then pip install torch --index-url https://download.pytorch.org/whl/cpu || true; fi
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m app.ml.build_courses
python -m app.ml.validate_catalog
python -m app.ml.generate_data
python -m app.ml.train
cd "$ROOT/frontend" && npm install
echo "Setup complete. Run ./start.sh"
