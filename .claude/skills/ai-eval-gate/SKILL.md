---
name: ai-eval-gate
description: Checklist for modifying AI prompts, models, RAG retrieval, or tools in leadflow-ai. Use before merging AI changes.
---

# AI Evaluation & Guardrail Gate (`leadflow-ai`)

1. **RESPECT Prompt Structure:** Ensure system prompts follow Role, Examples, Structure, Pipeline, Constraints, and Task.
2. **Abstention Enforced:** Factual claims missing from RAG retrieved chunks must trigger `abstained=True` and `needs_human_escalation=True`.
3. **Latency & Timeout Budget:** All AI turns must respect `GEMINI_REQUEST_TIMEOUT_MS = 7_000` with automatic fallbacks and Quota Rollback (`decrby`).
4. **PII Redaction in Traces:** Ensure logs and Traces scrub phone numbers, emails, and sensitive user data via `src/security/pii.py`.
5. **Golden Set Regression:** Run `pytest tests/evals/test_agent_regression_evals.py` to ensure all evaluation cases pass.
