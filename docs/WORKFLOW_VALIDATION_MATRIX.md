# LeadFlow AI — End-to-End Workflow Validation & Test Coverage Matrix

**Purpose:** Machine-readable architectural map of all **33 atomic workflows** (**26 Business/AI** + **7 Infrastructure/Runtime**, preserving all 29 baseline workflows plus Phases 1–5 agentic capabilities), their **upstream/downstream dependencies**, and their **mapped PyTest suites**.

---

## Part 1: Linked Workflow Dependency Chains (Integration Boundaries)

Before validating individual workflows, verify that state transitions across linked workflows are covered by end-to-end tests:

1. **Chain A — Tenant Onboarding & Session Lifecycle:**
   `WF-01 (Register)` -> `WF-02 (Login & MFA OTP)` -> `WF-03 (Dashboard & Settings)` -> `WF-29 (JWT Revocation / Logout)`
2. **Chain B — Inbound Lead Capture & Outbound Activation:**
   `WF-05 (Campaign Webhook)` OR `WF-06 (Facebook Lead Ads)` -> `WF-14 (Outbound Meta Template)` -> `WF-19 (Scheduled Follow-Up & DLQ)`
3. **Chain C — Live WhatsApp Agentic Loop (Core Revenue Path):**
   `WF-08 (WhatsApp Webhook)` -> `WF-09 (Pre/Post Guardrails)` -> `WF-10 (Rolling Memory)` + `WF-12 (Hybrid RAG)` -> `WF-13 (Turn-1 Cache & Quota Rollback)` -> `WF-11 (Tenant Tools & HITL Queue)` -> `WF-04 (Pilot KPIs & Feedback)`
4. **Chain D — Voice Note & Session Document Pipeline:**
   `WF-15 (WhatsApp Audio Webhook)` -> `WF-16 (Whisper SSRF-Safe Transcription)` -> `WF-08 (AgentHarness)` | Parallel: `WF-18 (Session Upload & PDF Export)` -> `WF-21 (90-Day GDPR Purge)`
5. **Chain E — Billing, Quotas & Subscription Enforcement:**
   `WF-07 (Meshulam/Grow Webhook)` -> `WF-13 (Redis Token Quota Expansion)` -> `WF-20 (14-Day Trial Expiration Cron)`
6. **Chain F — Edge-to-Database Zero-Trust & Runtime Shield:**
   `WF-25 (RequestBodyLimit ASGI)` -> `WF-27 (Request-ID & PII-Safe Logs)` -> `WF-28 (Security Headers & Egress Wasm DLP)` -> `WF-24 (Alembic DB Sync Health)` -> `WF-22 (R2 DB Backups)`

---

## Part 2: Business & Agentic AI Workflows (26 Total)

| ID | Workflow Name | Primary Code Path(s) | Linked Workflows | Mapped Test File(s) | Coverage Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WF-01** | Tenant Registration | `src/routers/auth.py` | `WF-02`, `WF-20` | `tests/security/test_identity_data_security.py` | `COVERED` |
| **WF-02** | Login & Atomic MFA OTP | `src/routers/auth.py`, `src/security/encryption.py` | `WF-01`, `WF-03`, `WF-29` | `tests/security/test_infrastructure_regression.py` | `COVERED` |
| **WF-03** | Tenant Dashboard & Lead CRUD | `src/routers/leads.py`, `src/routers/settings.py` | `WF-02`, `WF-11`, `WF-28` | `tests/security/test_grace_period_and_webhook.py` | `COVERED` |
| **WF-04** | Live AI Simulator | `src/routers/settings.py` (`/simulate`) | `WF-09`, `WF-12`, `WF-13` | `tests/test_ai_harness.py` | `COVERED` |
| **WF-05** | Campaign Lead Ingestion | `src/routers/webhooks/campaign.py` | `WF-14`, `WF-19`, `WF-25` | `tests/security/test_webhook_security.py` | `COVERED` |
| **WF-06** | Facebook OAuth & Lead Ads | `src/routers/facebook.py` | `WF-05`, `WF-14` | `tests/security/test_webhook_hardening_audit.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-07** | Partner Analytics Endpoint | `src/routers/partners.py` (`/performance`) | `WF-02`, `WF-06` | `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-08** | Payment Webhooks (Meshulam/Grow) | `src/routers/webhooks/meshulam.py` | `WF-13`, `WF-20` | `tests/security/test_webhook_security.py` | `COVERED` |
| **WF-09** | Two-Way WhatsApp Pipeline | `src/routers/webhooks/whatsapp.py`, `src/services/communication/whatsapp_pipeline.py` | `WF-10`, `WF-11`, `WF-12`, `WF-13`, `WF-14` | `tests/security/test_database_concurrency.py`, `tests/security/test_webhook_security.py` | `COVERED` |
| **WF-10** | Pre/Post-LLM Security Guardrails | `src/security/ai_guardrails.py`, `src/services/ai/output_sanitizer.py` | `WF-09`, `WF-12` | `tests/security/test_ai_llm_security.py`, `tests/test_ai_harness.py` | `COVERED` |
| **WF-11** | Rolling Conversation Memory | `src/services/ai/memory.py` | `WF-09`, `WF-12` | `tests/test_ai_harness.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-12** | Tenant-Scoped Closure Tools | `src/services/ai/tools/registry.py`, `crm_tools.py`, `calendar_tools.py` | `WF-09`, `WF-13` | `tests/test_tenant_tools_and_hitl.py`, `tests/security/test_ai_llm_security.py` | `COVERED` |
| **WF-13** | HITL Approval Gate (`PendingApproval`) | `src/routers/leads.py` (`/approvals`), `src/database/models.py` | `WF-12`, `WF-14`, `WF-17` | `tests/test_tenant_tools_and_hitl.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-14** | Multi-Tenant Hybrid RAG (`pgvector`) | `src/services/rag/chunker.py`, `ingestor.py`, `retriever.py`, `src/routers/knowledge.py` | `WF-09`, `WF-15` | `tests/test_hybrid_rag.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-15** | Turn-1 Cache & Quota Rollback | `src/services/ai/harness.py`, `src/services/llm_router.py` | `WF-08`, `WF-09`, `WF-14` | `tests/security/test_llm_router.py`, `tests/security/test_database_concurrency.py` | `COVERED` |
| **WF-16** | Outbound Lead Follow-Up (Meta Templates) | `src/tasks/followup_tasks.py` | `WF-05`, `WF-09`, `WF-21` | `tests/security/test_webhook_security.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-17** | Pilot KPIs & AI Feedback Loop | `src/routers/insights.py` (`/pilot-kpis`), `src/routers/leads.py` (`/feedback`) | `WF-03`, `WF-13`, `WF-14` | `tests/test_pilot_kpis.py`, `tests/evals/test_agent_regression_evals.py` | `COVERED` |
| **WF-18** | Virtual CMO Marketing Insights | `src/routers/insights.py` (`/marketing-report`) | `WF-11`, `WF-17` | `tests/test_pilot_kpis.py` | `COVERED` |
| **WF-19** | Async Audio Transcription (Whisper) | `src/tasks/audio_tasks.py`, `src/services/ai/whisper.py` | `WF-09`, `WF-25` | `tests/security/test_application_defenses.py` | `COVERED` |
| **WF-20** | Session Upload & PDF Summary Export | `src/routers/sessions.py`, `src/services/media/pdf_maker.py` | `WF-22`, `WF-23`, `WF-25` | `tests/security/test_sec_012_pdf_path_traversal.py`, `tests/security/test_application_defenses.py` | `COVERED` |
| **WF-21** | Twilio/Meta Number Provisioning | `src/routers/provisioning.py` | `WF-09`, `WF-22` | `tests/security/test_sec_015_twilio_signature_validation.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-22** | KYC Document Upload (S3) | `src/routers/phones.py`, `src/services/storage/s3_service.py` | `WF-21`, `WF-23` | `tests/security/test_application_defenses.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-23** | Local Tenant Media Containment | `src/routers/storage.py` | `WF-20`, `WF-24` | `tests/security/test_application_defenses.py` | `COVERED` |
| **WF-24** | Scheduled Follow-Ups & DLQ Replayer | `src/worker.py`, `src/tasks/followup_tasks.py` | `WF-05`, `WF-16` | `tests/security/test_webhook_security.py`, `tests/test_workflow_matrix_coverage.py` | `COVERED` |
| **WF-25** | Trial & Subscription Expiration Cron | `src/tasks/billing_tasks.py` | `WF-01`, `WF-08` | `tests/security/test_grace_period_and_webhook.py` | `COVERED` |
| **WF-26** | Hebrew Golden Set Regression Evals | `tests/evals/test_agent_regression_evals.py`, `tests/evals/golden_set_hebrew.jsonl` | `WF-09`, `WF-10`, `WF-14`, `WF-17` | `tests/evals/test_agent_regression_evals.py` | `COVERED` |

---

## Part 3: Infrastructure, Security & Runtime Workflows (7 Total)

| ID | Workflow Name | Primary Code Path(s) | Linked Workflows | Mapped Test File(s) | Coverage Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WF-27** | GDPR 90-Day Retention Purge | `src/tasks/retention_tasks.py` | `WF-20`, `WF-22`, `WF-23` | `tests/security/test_infrastructure_regression.py` | `COVERED` |
| **WF-28** | Automated PostgreSQL R2 Backups | `src/tasks/backup_tasks.py`, `scripts/backup_to_r2.sh` | `WF-27`, `WF-29` | `tests/security/test_infrastructure_regression.py` | `COVERED` |
| **WF-29** | Alembic DB Sync Health Gate | `src/routers/health.py` (`/health/db-sync-status`) | `WF-28`, `WF-30` | `tests/security/test_infrastructure_regression.py` | `COVERED` |
| **WF-30** | Raw ASGI Body & 64-Depth JSON Limits | `src/middleware/request_limits.py` | `WF-05`, `WF-09`, `WF-20` | `tests/security/test_application_defenses.py` | `COVERED` |
| **WF-31** | JWT Blocklist & Rate Limiter Resilience | `src/security/dependencies.py`, `token_revocation.py`, `rate_limiter.py` | `WF-01`, `WF-02`, `WF-03` | `tests/security/test_identity_data_security.py`, `tests/security/test_rate_limiter_resilience.py` | `COVERED` |
| **WF-32** | Request-ID Tracing, JSON Logs & Exception Alerts | `src/main.py`, `src/logging_config.py`, `src/services/ai/tracing.py` | `All WF-01..WF-33` | `tests/evals/test_agent_regression_evals.py`, `tests/test_main.py` | `COVERED` |
| **WF-33** | Security Headers & Envoy Wasm Egress DLP | `src/main.py` (`dlp_trigger_middleware`), `data-gate/src/lib.rs` | `WF-03`, `WF-09`, `WF-13` | `tests/security/test_grace_period_and_webhook.py`, `tests/benchmarks/run_scientific_bench.sh` | `COVERED` |