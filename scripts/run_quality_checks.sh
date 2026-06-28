#!/usr/bin/env bash
set -euo pipefail

echo "=== Ruff check ==="
uv run ruff check .

echo "=== Ruff format check ==="
uv run ruff format --check .

echo "=== Mypy ==="
uv run mypy src

echo "=== Pytest ==="
uv run pytest

echo "=== Check no raw data commit ==="
uv run python scripts/check_no_raw_data_commit.py

echo "=== Check no sensitive patterns ==="
uv run python scripts/check_no_sensitive_patterns.py

echo "=== Validate agent docs ==="
uv run python scripts/validate_agent_docs.py

echo "=== All checks passed ==="
