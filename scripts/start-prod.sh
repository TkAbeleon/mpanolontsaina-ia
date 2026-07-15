#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "Virtual environment not found at $ROOT_DIR/.venv" >&2
  exit 1
fi

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8080}"
export APP_ENV="${APP_ENV:-production}"
export WORKERS="${WORKERS:-2}"

exec "$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS"
