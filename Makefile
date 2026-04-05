.PHONY: install install-dev lint format test clean hooks

# Default target
help:
	@echo "MultiCode - Makefile targets"
	@echo ""
	@echo "  install       Install package in development mode"
	@echo "  install-dev   Install with development dependencies"
	@echo "  lint          Run Ruff linter on all source files"
	@echo "  format        Auto-fix linting issues with Ruff"
	@echo "  test          Run test suite with pytest"
	@echo "  test-cov      Run tests with coverage report"
	@echo "  typecheck     Run MyPy type checker"
	@echo "  check-secrets Run pre-commit secret scanner"
	@echo "  hooks         Install git pre-commit hooks"
	@echo "  clean         Remove build artifacts and caches"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

# Code quality
lint:
	ruff check .

format:
	ruff check --fix .

typecheck:
	mypy .

# Testing
test:
	pytest

test-cov:
	pytest --cov=multicode --cov-report=html --cov-report=term-missing

# Security
check-secrets:
	@echo "Scanning for secrets..."
	@bash scripts/check-secrets.sh || echo "Install gitleaks or detect-secrets for better scanning"

hooks:
	@echo "Installing pre-commit hooks..."
	@mkdir -p .git/hooks
	@cp scripts/check-secrets.sh .git/hooks/pre-commit 2>/dev/null || \
		echo "Note: check-secrets.sh is a bash script. For Windows, use scripts/install-hooks.bat"
	@chmod +x .git/hooks/pre-commit 2>/dev/null || echo "Note: chmod not available on Windows"

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ .ruff_cache/ .mypy_cache/ htmlcov/ .pytest_cache/
	rm -rf .coverage coverage.xml
