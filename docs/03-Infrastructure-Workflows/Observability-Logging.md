
# Observability, Anomaly Watchdog & OpenTelemetry Roadmap

## 1. PII-Safe Structured Logging & AI Tracing

* All FastAPI, Uvicorn, and `AgentHarness` logs emit structured JSON with `request_id` correlation.
* Phone numbers, tenant IDs, and message bodies are masked (`mask_phone()`, `[REDACTED]`) prior to log emission.
* `AITracing` records per-turn `trace_id`, `model_used`, `complexity_tier`, `latency_ms`, `input_tokens`, `output_tokens`, `cache_hit`, `abstained`, and `needs_human`.

## 2. Production Anomaly Watchdog (`src/services/monitoring/watchdog.py`)

* Executed every 5 minutes by `leadflow-beat` (`src/tasks/watchdog_tasks.py`).
* Monitors rolling 15-minute LLM error rates and Celery Dead Letter Queue (DLQ) depth.
* Dispatches deduplicated alerts via `AlertDispatcher` using Redis `SET NX` 30-minute cooldowns and SSRF-validated `ALERT_WEBHOOK_URL`.

## 3. Planned Upgrade: OpenTelemetry (`OTel`) Distributed Tracing

* Propagate W3C `traceparent` headers end-to-end across **Envoy → FastAPI → Celery → PostgreSQL/`pgvector` → Gemini (`gen_ai.*`) → Meta Graph API**.
* Export spans to Grafana Tempo / Jaeger through an OTel Collector configured with attribute redaction processors to eliminate latency blind spots while staying within the `7s` SLA.
