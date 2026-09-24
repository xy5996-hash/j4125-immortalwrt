#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
exec "$PYTHON_BIN" "$ROOT_DIR/scripts/render-config.py" "$@"