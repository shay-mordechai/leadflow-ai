#!/usr/bin/env bash
set -Eeuo pipefail

START_TIME=$(date +%s)
echo "=== Running AI-Native Development Harness Verification ==="

trap 'echo "============================================================"; echo "HARNESS FAIL"; echo "============================================================"' ERR

echo "[1/4] Running ruff format check..."
ruff format --check src tests alembic scripts

echo "[2/4] Running ruff lint check..."
ruff check src tests alembic scripts

echo "[3/4] Verifying Alembic migration heads..."
alembic heads

echo "[4/4] Running pytest unit & security tests..."
pytest tests/ -q

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "============================================================"
echo "HARNESS PASS (Duration: ${DURATION}s)"
echo "============================================================"
