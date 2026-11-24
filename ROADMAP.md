# 🎯 LeadFlow AI (`my-leads.app`) — Product & Engineering Roadmap

**Architecture:** Multi-Tenant Conversational AI SaaS (FastAPI, PostgreSQL + `pgvector`, Redis, Celery, Next.js, Envoy Proxy + Rust/Wasm Edge DLP, Cloudflare Tunnel)  
**Current Stage:** **Pilot-Ready MVP (Phases 1–5 & Optimization Cycles #1–#2 Complete — 149 Tests Passing)** — Freezing new enterprise features to focus on live pilot calibration, Meta/Twilio onboarding, and HITL state machine hardening.

---

## ✅ Completed Foundation (Implemented & Verified in Codebase)

### Core Infrastructure, Security & Billing Integrity
- [x] **Tenant Isolation (PostgreSQL `FORCE ROW LEVEL SECURITY`):** Enforced via `20261122_enforce_rls_all` Alembic migration, least-privilege `leadflow_reader` / `leadflow_writer` DB roles, and SQLAlchemy tenant context listeners.
- [x] **Zero-Trust Edge & Network:** Cloudflare Tunnel ingress with Hetzner Terraform firewall permitting zero inbound TCP/UDP ports; non-root containers (`no-new-privileges`, `core=0`, loopback-only DB/Redis bindings).
- [x] **Rust/Wasm Edge DLP (`data_hop_firewall`):** Fail-closed Envoy L7 response filter redacting 41 PII/credential fields on `X-Data-TTL: 1` (`<2%` throughput overhead, `-0.30 ms` median P50 delta, `0%` non-2xx errors).
- [x] **ASGI DoS, SSRF & Auth Hardening:** Zero-allocation streaming `RequestBodyLimitMiddleware` (1 MiB / 26 MiB caps, byte-level 64-depth JSON nesting limit), `HS256`-pinned JWTs with Redis `jti` + `token_version` revocation, `CF-Connecting-IP` trusted proxy parsing, Admin auth guard on `GET /api/v1/partners/performance` (`test_wf07_partner_performance_authz`), and `WhisperService` HTTPS domain allowlist (`follow_redirects=False`).
- [x] **Concurrency & TOCTOU Protection:** Atomic Redis `SET NX` webhook idempotency, conditional SQL `UPDATE ... RETURNING` message quotas, Redis `INCRBY`/`DECRBY` monthly token budget with rollback, single-use atomic OTP consumption, and `BoundedSemaphore(200)` background task capacity.
- [x] **Schema Migrations & Retention:** Dual SQLite/PostgreSQL `Alembic` migrations enforced in CI (`alembic check`), automated 90-day GDPR retention purge (`Celery Beat`), and Cloudflare R2 `pg_dump` backups.

### Agentic AI Architecture (Phases 1–5 Complete)
- [x] **Phase 1 — Unified `AgentHarness` & RESPECT Prompts:** Central execution harness (`src/services/ai/harness.py`), tiered Gemini routing (`7s` hard timeout, `512` max output tokens, `15`-turn escalation cap), XML-escaped prompt boundaries, structured `WhatsAppAgentResponse` (`abstained`, `cited_chunk_ids`), `bleach` output sanitization, and `kb_version`-aware Turn-1 Redis caching.
- [x] **Phase 2 — Rolling Memory, Debouncing & Evals:** `ConversationMemoryService` (`conversation_summary` + `extracted_state`), 3.5s Redis WhatsApp burst debouncing, PII-safe JSON tracing, and Hebrew Golden Set regression suite (`tests/evals/golden_set_hebrew.jsonl`).
- [x] **Phase 3 — Tenant-Scoped Tools & HITL Gates:** Closure-bound CRM/Calendar tools (`qualify_lead`, `check_calendar_availability`, `propose_appointment_booking`) with SSRF URL rejection and Human-in-the-Loop `PendingApproval` workflow (`GET/POST /api/v1/leads/approvals`).
- [x] **Phase 4 — Multi-Tenant Hybrid RAG (`pgvector`):** `pgvector:pg15` setup, pricing-table-aware chunker, Vector + Hebrew Lexical RRF retriever with mandatory `user_id` pre-filtering, and `POST/GET/DELETE /api/v1/knowledge/documents`.
- [x] **Phase 5 — Pilot Observability & Agent Guardrails:** Tenant-isolated `GET /api/v1/insights/pilot-kpis`, AI `THUMBS_UP`/`THUMBS_DOWN` feedback loop, and operational `.claude/skills/` (`tenant-endpoint`, `safe-alembic-migration`, `ai-eval-gate`).

---

## 🚨 TIER 1: Immediate Pre-Pilot Priorities (P1 Blockers)

Focus: Preventing worker starvation, hardening CD image pinning, and calibrating Hebrew RAG on live Design Partner traffic.

1. **[P1 — DevSecOps] Harden Production CD & Image Pinning:** Upgrade static `X-Deploy-Token` in `.github/workflows/production.yml` to HMAC-SHA256 + timestamp replay validation, pin base/deploy images by immutable `@sha256` digest, and run `alembic upgrade head` before switching container traffic.
2. **[P1 — AI Calibration] Hebrew Hybrid RAG Tuning (Under 7s Budget):** Calibrate RRF weights and `min_score` thresholds on real Hebrew SMB price lists and FAQs so pricing queries do not false-negative while missing facts reliably trigger `abstained=True` without adding a heavy reranker.
3. **[P1 — Pilot Loop] HITL Draft Mode (`EDITED` -> Golden Set):** Onboard the first Design Partner in **HITL Draft Mode** (50–100 leads), monitor edit rate (`EDITED` vs `APPROVED`) and `thumbs_up` % via `/api/v1/insights/pilot-kpis`, and convert human-edited replies into new `golden_set_hebrew.jsonl` test cases before enabling autonomous booking.
4. **[P1 — Reliability] Dedicated Audio Celery Queue:** Route `WF #10` / `WF #17` voice-note downloads and Whisper transcriptions to a dedicated `-Q audio_queue` worker pool so concurrent 15MB WhatsApp audio files never starve `-Q realtime_chat` text replies.
5. **[P1 — Performance] Pre-Compute Virtual CMO Insights (`WF #23`):** Move multi-month lead summary aggregation out of synchronous `GET /api/v1/insights/marketing-report` into a scheduled weekly Celery Beat job stored in PostgreSQL.

---

## ⚠️ Production Challenges & Operational Friction Analysis (Across All 29 Workflows)

The primary risks at launch are **external regulatory bottlenecks** and **operational edge cases** rather than Python application logic.

### 1. Telecom, Meta & KYC Workflows (`WF #5, #6, #7, #11, #21`) — *HIGHEST RISK*
- **Twilio `+972` Regulatory Bundles (`WF #7, #21`):** Programmatic purchase of Israeli phone numbers requires uploading business registration (תעודת התאגדות / עוסק מורשה), Israeli ID, and proof of address per tenant (48–72h Twilio review per bundle).
- **Meta Tech Provider & Embedded Signup (`WF #7`):** Requires passing Meta App Review (`whatsapp_business_management`, `whatsapp_business_messaging`), Meta Business Verification, and implementing **Meta Embedded Signup** in Next.js for 3-click WABA onboarding.
- **S3 KYC Encryption (`WF #21`):** Enforce `SSE-KMS` encryption, block all public access on the `kyc/` bucket, and serve identity files strictly via short-lived Pre-Signed URLs.
- **The 24-Hour WhatsApp Service Window (`WF #5, #6`):** Meta blocks free-form text on outbound lead follow-ups (`WF #5`) until the lead replies first. Initial outreach for landing-page leads **must** dispatch an approved **Meta Utility/Marketing Template**; once the lead replies, the 24-hour window opens for `WF #6` AI chat.
- **Facebook Lead Ads Token Expiry (`WF #11`):** User OAuth tokens expire every 60 days (or immediately on password reset). Implement automated token-health checks and tenant disconnect alerts.

### 2. AI Engine, Voice & Unit Economics (`WF #10, #13, #14, #17, #23`)
- **Context-Safe Caching (`WF #13`):** Keep Turn-1 cache restricted strictly to stateless first-turn messages keyed by `hash(tenant_id + kb_version + system_instruction + normalized_prompt)` to prevent cross-lead context pollution.
- **Delivery Failure Compensation (`WF #14`):** When Gemini succeeds and consumes tokens/quota but Meta WhatsApp delivery fails, enqueue the already-generated reply into the DLQ for delivery retry rather than re-invoking the LLM, and refund quota if delivery permanently fails.
- **Worker Isolation (`WF #10, #17`):** Separate `-Q audio_queue` from `-Q realtime_chat` to prevent 2-minute voice notes from blocking live text conversations.

### 3. Billing, Celery Beat & Subscription Lifecycle (`WF #8, #9, #20`)
- **Payment Gateway Reliability & Tax Invoices (`WF #8`):** Back Meshulam/Grow `transactionId` idempotency with PostgreSQL `UNIQUE` constraints (not Redis TTL alone). Delegate Israeli tax-compliant digital invoices to Meshulam/Grow or Morning APIs rather than custom Python PDFs.
- **Single-Instance Celery Beat (`WF #9, #20`):** Strictly enforce `replicas: 1` for `leadflow-beat` in production so scheduled follow-ups and monthly quota resets never fire twice.
- **Graceful Trial Cut-Off (`WF #20`):** Trigger an automated WhatsApp/email alert 48 hours before the 14-day trial expires showing active open leads so tenants convert before `bot_active` switches to `False`.

### 4. Security & Infrastructure Depth (`P2 Hardening Roadmap`)
| Workflow | Production Risk | Engineering Mitigation |
| :--- | :--- | :--- |
| **WF #4 & #19: Lead Ingestion** | Duplicate leads due to phone format drift (`054-...` vs `+97254...`) | Normalize all inbound phone numbers to strict **E.164** (`+972...`) *before* checking Redis idempotency keys. |
| **WF #22 & #28: Wasm DLP** | Case-mismatch bypass or false-positive redaction on 9-digit numbers | Normalize JSON keys with `to_ascii_lowercase()`, add explicit Wasm VM buffer size cap, and validate regex boundaries against Israeli phone/price formats. |
| **WF #18: R2 DB Backups** | Silent backup corruption | Run an automated monthly `pg_dump -Fc` restore verification test against an isolated staging container. |

---

## 📋 Step-by-Step Go-Live Checklist (Pilot Launch)

### Stage A — Technical & Security Freeze (This Week)
- [x] Re-enable `get_current_user` + Admin check on `src/routers/partners.py` (`P0`).
- [ ] Split Celery workers into `-Q realtime_chat` and `-Q audio_queue`, and verify `leadflow-beat` runs as a single instance.
- [ ] Run `podman compose up -d --build` (or Systemd Quadlets) with `pgvector:pg15` + `alembic upgrade head` on Hetzner VPS and verify `/health/db-sync-status`.
- [ ] Run end-to-end backup restore check from Cloudflare R2 (`pg_dump -Fc`).

### Stage B — External Bureaucracy (Parallel Track)
- [ ] Submit Meta App Review (`whatsapp_business_management`, `whatsapp_business_messaging`) & Meta Business Verification.
- [ ] Register pre-approved Hebrew Meta Utility Templates for `WF #5` initial outbound lead outreach.
- [ ] Submit first Twilio `+972` Regulatory Bundle for the Design Partner tenant.
- [ ] Connect Morning / Meshulam automatic invoice webhook integration.

### Stage C — Design Partner Pilot (HITL Draft Mode)
- [ ] Upload Design Partner pricing sheet, policies, and FAQs via `POST /api/v1/knowledge/documents` and verify `INDEXED` status.
- [ ] Operate first 50–100 live WhatsApp leads in **HITL Draft Mode** (`PendingApproval`).
- [ ] Monitor `/api/v1/insights/pilot-kpis`: once human `EDITED` rate drops below `15%` and `thumbs_up` exceeds `85%`, enable autonomous appointment booking for the tenant.

---

## 🤖 Agent Engineering & Optimization Roadmap

### ✅ Completed: Optimization Cycle #1 — Agent Evals, Telemetry & Tiered Routing
- [x] **Telemetry & Observability:** Instrumented `AgentHarness` with `AgentRunMetrics` (`model_tier`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd`, `tool_calls_count`, and `context_compacted`) with strict PII redaction.
- [x] **Evals & Benchmarking:** Expanded `tests/evals/` into a 15-scenario Hebrew/English multi-tenant Golden Dataset (`tests/evals/golden_dataset.json`) covering RAG groundedness, multi-step tool calling, history compaction, and prompt-injection/cross-tenant defenses.
- [x] **Latency & Cost Optimization:** Benchmarked `14.20 ms` P50 / `38.50 ms` P95 harness latency and `165.0` avg tokens/turn (`$0.000012`/turn) via automated compaction and tiered routing.
- [x] **Documentation:** Generated `docs/EVAL_BENCHMARK_REPORT.md` and updated `README.md`.

### ✅ Completed: Optimization Cycle #2 — Production Monitoring & Autonomous CI Triage
- [x] **Production Anomaly Watchdog & Alerting:** Implemented `ProductionWatchdog` (`src/services/monitoring/watchdog.py`) and 5-minute Celery Beat task (`src/tasks/watchdog_tasks.py`) monitoring rolling 15-minute LLM error rates and Celery DLQ growth, backed by `AlertDispatcher` (Redis `SET NX` 30-minute cooldown deduplication, PII redaction, and SSRF-validated `ALERT_WEBHOOK_URL`) and verified via `tests/security/test_production_watchdog.py`.
- [x] **Autonomous CI / Security Triage Workflow:** Deployed `.github/workflows/ci-triage.yml` to automatically diagnose failed SAST (`Semgrep`/`Ruff`) and Production Deploy (`Trivy`/`Alembic`/`Pytest`) runs and post actionable remediation steps.

### 📌 Active Backlog (Next Sprints)
- [ ] **HITL State Machine Upgrade:** Extend `PendingApproval` into a full suspend/resume execution state machine across `worker-reader` and `worker-writer`.
- [ ] **Live Incident Post-Mortem:** Configure live `ALERT_WEBHOOK_URL` on Hetzner VPS and document the first production anomaly detected and resolved via the Watchdog.
- [ ] **Guardrails & Sandboxing Showcase:** Maintain architectural case-study documentation highlighting `leadflow_reader` + `FORCE RLS` + Envoy/Wasm DLP egress filtering.

---

## 🔮 TIER 2 & V2: Post-Pilot Scale & Enterprise Workflows (Deferred Until Pilot KPIs Met)

> **Rule:** Do not implement these workflows until the first Design Partner pilot validates unit economics and HITL accuracy.

### V2 AI & Agentic Enhancements
1. **Production Workflow Graph & Reflection (`src/services/ai/workflow_graph.py`):** Enable bounded single-pass self-reflection behind a feature flag for complex multi-turn objections without breaching the `7s` latency SLA.
2. **Interactive WhatsApp Rich Media (`WF #11`):** Upgrade plain-text replies to WhatsApp interactive buttons, list menus, and product catalogs.
3. **Dynamic Multi-Language Switching:** Auto-detect Hebrew, English, Russian, or Arabic on Turn 1 and adapt prompt localization seamlessly.
4. **Real-Time Sentiment & Escalation Alerts:** Push instant WhatsApp/Slack/SMS alerts to the business owner when frustration is detected (`needs_human_escalation=True`).
5. **Drip Re-Engagement Campaigns:** Automated 3-day and 7-day follow-up sequences for cold leads (using approved Meta templates).
6. **Prompt A/B Testing & Semantic Caching:** Split traffic across `system_instruction` variants and measure conversion impact via `/api/v1/insights/pilot-kpis`.

### V2 Integrations, UX & Enterprise Scale
7. **Two-Way Calendar & CRM Sync:** Push approved `PendingApproval` bookings directly to Google Calendar, HubSpot, or Salesforce.
8. **Multi-Channel Fallback:** Automatic SMS/Email fallback when WhatsApp delivery fails.
9. **Frontend Polish & Growth:** Optimistic chat UI, skeleton loaders, dark/light theme, PWA installability, and public SEO `sitemap.xml` / `robots.txt`.
10. **Enterprise Governance & Self-Service:** DSAR/GDPR encrypted ZIP export endpoint, tenant API key rotation with 24h grace period, multi-user team roles per tenant, and agency white-label branding.
11. **Voice & Multi-Agent Frontier:** Live Twilio Media Streams voice agent, autonomous cold-list outbound pacing, and specialized Sales-to-Support agent handoff.

---
MCP ו-OpenTelemetry