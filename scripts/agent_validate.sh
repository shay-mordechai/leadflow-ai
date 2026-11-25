#!/usr/bin/env bash
set -euo pipefail

echo "=== [1/4] Ruff Format & Lint ==="
ruff format --check src tests alembic scripts
ruff check src tests alembic scripts

echo "=== [2/4] Alembic Migration Sync (Isolated SQLite) ==="
TMP_DB=$(mktemp /tmp/leadflow_alembic_XXXXXX.db)
trap 'rm -f "$TMP_DB"' EXIT
DATABASE_URL="sqlite:///${TMP_DB}" alembic upgrade head >/dev/null
DATABASE_URL="sqlite:///${TMP_DB}" alembic check

echo "=== [3/4] Pipeline & Security Pytest ==="
pytest tests/test_whatsapp_pipeline.py tests/security/ -q --tb=short

echo "=== [4/4] Git Diff Whitespace Check ==="
git diff --check
echo "ALL VALIDATION GATES PASSED."
