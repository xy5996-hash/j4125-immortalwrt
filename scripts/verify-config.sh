#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
cd "$ROOT_DIR"

CONFIG_FILE="${1:-config/generated/immortalwrt-25.12.2-x86_64.config}"
"$PYTHON_BIN" scripts/check_hardware_profile.py --config "$CONFIG_FILE"
"$PYTHON_BIN" scripts/check_forbidden_packages.py --config "$CONFIG_FILE"

echo "verify-config OK: $CONFIG_FILE"