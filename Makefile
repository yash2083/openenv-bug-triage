# ============================================================
# Bug/Issue Triage OpenEnv — Makefile
# ============================================================
# Usage:
#   make setup       — Create venv and install dependencies
#   make docker-build — Build the Docker image
#   make docker-run   — Run the Docker container
#   make validate     — Run openenv validate
#   make baseline     — Run baseline inference script
#   make test         — Run pytest test suite
#   make lint         — Run ruff linter
#   make clean        — Remove build artifacts
# ============================================================

SHELL := /bin/bash
PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
IMAGE_NAME := bugtriage-openenv
PORT := 8000

.PHONY: setup docker-build docker-run validate baseline test lint clean help

# ---- Default target ----
help:
	@echo ""
	@echo "  Bug/Issue Triage OpenEnv — Available targets:"
	@echo "  ──────────────────────────────────────────────"
	@echo "  make setup          Create venv & install deps"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run Docker container"
	@echo "  make validate       Run openenv validate"
	@echo "  make baseline       Run baseline inference"
	@echo "  make test           Run pytest suite"
	@echo "  make lint           Run ruff linter"
	@echo "  make clean          Remove build artifacts"
	@echo ""

# ---- Setup ----
setup:
	@echo "→ Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "→ Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "→ Installing dev dependencies..."
	$(PIP) install pytest ruff
	@echo "✓ Setup complete. Activate with: source $(VENV)/bin/activate"

# ---- Docker ----
docker-build:
	@echo "→ Building Docker image: $(IMAGE_NAME)..."
	docker build -t $(IMAGE_NAME) .
	@echo "✓ Docker image built: $(IMAGE_NAME)"

docker-run:
	@echo "→ Running Docker container on port $(PORT)..."
	docker run --rm -p $(PORT):$(PORT) --env-file .env $(IMAGE_NAME)

# ---- Validation ----
validate:
	@echo "→ Running openenv validate..."
	openenv validate
	@echo "✓ Validation passed"

# ---- Baseline ----
baseline:
	@echo "→ Running baseline inference..."
	@test -n "$$HF_TOKEN" || (echo "ERROR: HF_TOKEN not set. Export it first." && exit 1)
	$(PYTHON) inference.py
	@echo "✓ Baseline complete"

# ---- Testing ----
test:
	@echo "→ Running tests..."
	$(PYTEST) tests/ -v --tb=short
	@echo "✓ Tests complete"

# ---- Linting ----
lint:
	@echo "→ Running linter..."
	$(VENV)/bin/ruff check .
	@echo "✓ Lint passed"

# ---- Cleanup ----
clean:
	@echo "→ Cleaning up..."
	rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Clean complete"
