# Agent Engineering Roadmap & Optimization Log

## Completed: Optimization Cycle #1 — Telemetry, Context Compaction & Tiered Routing
- **Baseline Challenge:** Multi-turn WhatsApp conversations risked inflating prompt token footprints and P95 latency, while uniform model routing increased inference cost on routine queries.
- **Engineering Changes:**
  1. **Execution Telemetry (`AgentRunMetrics`):** Instrumented `AgentHarness` (`src/services/ai/harness.py`) with per-turn tracking for `model_tier`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`, `tool_calls_count`, and `context_compacted`, strictly preserving PII redaction.
  2. **Golden Evaluation Suite (`tests/evals/`):** Built a 15-scenario Hebrew/English multi-tenant benchmark (`tests/evals/golden_dataset.json`) validating RAG groundedness, multi-step tool calling, history compaction, tiered routing, and adversarial prompt-injection/cross-tenant defenses.
  3. **Automated Benchmark Reporting:** Added automated regression gates in `tests/evals/test_agent_regression_evals.py` generating `docs/EVAL_BENCHMARK_REPORT.md`.
- **Measured Results (Golden Dataset — 15 Scenarios):**
  - **Overall Pass Rate:** 100.0% (Tool selection, structured schema validation, groundedness, and security guardrails)
  - **Harness Overhead Latency:** P50 `14.20 ms` / P95 `38.50 ms`
  - **Average Token Footprint:** `165.0` tokens/turn (`$0.000180` total benchmark run cost)
  - Full scenario breakdown available in [`docs/EVAL_BENCHMARK_REPORT.md`](./EVAL_BENCHMARK_REPORT.md).

---

## Upcoming Backlog (Next Sprints)
- [ ] **Production Monitoring & Alerting:** Configure real-time alerts (Telegram/Webhook) for LLM error rate spikes, Celery queue depth / worker heartbeat stalls, and DLQ growth, plus document a post-mortem case study.
- [ ] **Autonomous Dev/Ops Agentic Workflows:** Deploy background agentic workflows to triage CI failures or Semgrep/Trivy security findings and propose automated remediation PRs.
- [ ] **HITL State Machine Upgrade:** Extend `PendingApproval` into a full suspend/resume execution state machine across `worker-reader` and `worker-writer`.
- [ ] **Guardrails & Sandboxing Case Study:** Maintain architectural documentation highlighting `leadflow_reader` + `FORCE RLS` + Envoy/Wasm DLP egress filtering.
