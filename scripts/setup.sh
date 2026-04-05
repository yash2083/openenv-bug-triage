#!/usr/bin/env bash
# ============================================================
# setup.sh — Create virtual environment and install dependencies
# ============================================================
set -euo pipefail

VENV_DIR=".venv"

echo "→ Creating virtual environment in ${VENV_DIR}..."
python3 -m venv "${VENV_DIR}"

echo "→ Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

echo "→ Upgrading pip..."
pip install --upgrade pip

echo "→ Installing project dependencies..."
pip install -r requirements.txt

echo "→ Installing dev dependencies (pytest, ruff)..."
pip install pytest ruff

echo "✓ Setup complete!"
echo "  Activate with:  source ${VENV_DIR}/bin/activate"
