#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -d .venv ]; then
  . .venv/bin/activate
fi
alembic upgrade head

