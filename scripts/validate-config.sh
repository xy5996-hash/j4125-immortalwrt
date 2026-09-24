#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
cd "$ROOT_DIR"

"$PYTHON_BIN" scripts/render-config.py --check
"$PYTHON_BIN" scripts/check_feeds_lock.py
"$PYTHON_BIN" scripts/check_components.py
bash scripts/verify-config.sh
"$PYTHON_BIN" scripts/check_manifest.py --self-test
"$PYTHON_BIN" scripts/check_secrets.py

echo "validate-config OK"