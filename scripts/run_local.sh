#!/usr/bin/env bash
# ============================================================
# run_local.sh — Run the environment server locally
# ============================================================
set -euo pipefail

VENV_DIR=".venv"

if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: Virtual environment not found. Run ./scripts/setup.sh first."
    exit 1
fi

source "${VENV_DIR}/bin/activate"

echo "→ Starting local server..."
python -m server.app
