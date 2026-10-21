---
name: check-runner
description: Deterministic test and static analysis runner.
allowed-tools: Bash, Read
---
Run `ruff check .`, `bandit -r src/`, and `pytest`. Report failures clearly without modifying business logic.