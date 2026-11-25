#!/usr/bin/env bash
set -euo pipefail

echo "=== [1/4] Ruff Format & Lint ==="
ruff format --check src tests alembic scripts
ruff check src tests alembic scripts

echo "=== [2/4] Alembic Migration DAG Check (Offline) ==="
if python3 -c "import alembic" >/dev/null 2>&1; then
  HEAD_COUNT=$(python3 -m alembic heads | wc -l)
  if [[ "$HEAD_COUNT" -ne 1 ]]; then
    echo "ERROR: Expected exactly 1 Alembic head, found ${HEAD_COUNT}:" >&2
    python3 -m alembic heads >&2
    exit 1
  fi
  python3 -m alembic branches
  echo "Alembic single-head DAG verified."
else
  echo "SKIP: alembic not installed in current host venv."
fi

echo "=== [3/4] Pipeline & Security Pytest ==="
pytest tests/test_whatsapp_pipeline.py tests/security/ -q --tb=short

echo "=== [4/4] Git Diff Whitespace Check ==="
git diff --check
echo "ALL VALIDATION GATES PASSED."
