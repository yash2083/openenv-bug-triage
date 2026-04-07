#!/usr/bin/env bash
# ============================================================
# run_docker.sh — Build and run the environment in Docker
# ============================================================
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-antigravity-bugtriage}"
PORT="${PORT:-8000}"

echo "→ Building Docker image: ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .

echo "→ Running Docker container on port ${PORT}..."
docker run --rm -p "${PORT}:${PORT}" --env-file .env "${IMAGE_NAME}"
