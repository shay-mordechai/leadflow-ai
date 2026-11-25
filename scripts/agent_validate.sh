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
  echo "SKIP: alembic not installed in current environment."
fi

echo "=== [3/4] Pipeline & Security Pytest ==="
# Run full security suite when local PostgreSQL is reachable; skip DB integration files when offline
if python3 -c "import socket; s = socket.create_connection(('127.0.0.1', 5432), timeout=0.5); s.close()" 2>/dev/null; then
  pytest tests/test_whatsapp_pipeline.py tests/security/ -q --tb=short
else
  echo "INFO: Local PostgreSQL (127.0.0.1:5432) unreachable; running offline security and pipeline tests."
  pytest tests/test_whatsapp_pipeline.py tests/security/ \
    --ignore=tests/security/test_billing_coupons.py \
    --ignore=tests/security/test_marketing_advisor_worker.py \
    --ignore=tests/security/test_postgres_rls_and_worker_split.py \
    --ignore=tests/security/test_sec_015_twilio_signature_validation.py \
    --ignore=tests/security/test_webhook_idempotency.py \
    -q --tb=short
fi

echo "=== [4/4] Git Diff Whitespace Check ==="
git diff --check
echo "ALL VALIDATION GATES PASSED."
