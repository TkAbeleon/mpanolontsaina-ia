#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "Virtual environment not found at $VENV_DIR" >&2
  exit 1
fi

# Activate the project venv before launching the server.
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8080}"
export APP_ENV="${APP_ENV:-production}"
export WORKERS="${WORKERS:-2}"

exec python -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS"
