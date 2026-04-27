#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -d .venv ]; then
  . .venv/bin/activate
fi
export STAR_PULSE_RELOAD="${STAR_PULSE_RELOAD:-true}"
uvicorn app.main:app --host "${STAR_PULSE_API_HOST:-0.0.0.0}" --port "${STAR_PULSE_API_PORT:-8000}" --reload

