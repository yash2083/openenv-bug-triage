#!/usr/bin/env bash
# ============================================================
# run_baseline.sh — Run baseline inference with HF Router
# ============================================================
set -euo pipefail

VENV_DIR=".venv"

if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${HF_TOKEN:-}" ]; then
    echo "ERROR: OPENAI_API_KEY (or HF_TOKEN fallback) environment variable is not set."
    echo "  Export it:  export OPENAI_API_KEY='your-token-here'"
    echo "  Or create a .env file and source it:  source .env"
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: Virtual environment not found. Run ./scripts/setup.sh first."
    exit 1
fi

source "${VENV_DIR}/bin/activate"

echo "→ Running baseline inference..."
echo "  Model: ${MODEL_NAME:-Qwen/Qwen2.5-32B-Instruct}"
echo "  API:   ${API_BASE_URL:-https://router.huggingface.co/v1}"
echo ""

python inference.py

echo ""
echo "✓ Baseline inference complete."
