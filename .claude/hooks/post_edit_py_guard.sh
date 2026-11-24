#!/usr/bin/env bash
set -euo pipefail

# Read Claude Code PostToolUse JSON payload from stdin
PAYLOAD="$(cat)"
FILE_PATH="$(python3 -c 'import json, sys; d=json.loads(sys.argv[1]); print(d.get("tool_input", {}).get("file_path", ""))' "$PAYLOAD" 2>/dev/null || true)"

# Only inspect Python files inside this repo
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.py || ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# 1. Instant AST / syntax check (catches broken indentation immediately)
./venv/bin/python -m py_compile "$FILE_PATH"

# 2. Fast targeted Ruff lint check on the modified file only
./venv/bin/ruff check "$FILE_PATH"
