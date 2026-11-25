# LeadFlow AI (`my-leads.app`) — Documentation Index

## Root Planning & Benchmarks
- [Product & Engineering Roadmap](../ROADMAP.md) — Live status, pre-pilot blockers, OpenTelemetry & MCP plans
- [AI Eval Benchmark Report](EVAL_BENCHMARK_REPORT.md) — Golden Dataset latency, token cost, and safety pass rates
- [Workflow Validation Matrix](WORKFLOW_VALIDATION_MATRIX.md) — End-to-end validation status across all 29 workflows

## 01 — System Architecture
- [System Topology](01-Architecture/System-Topology.md) — Rootless Podman Pod (`leadflow-prod.pod`), Systemd Quadlets, Cloudflare Tunnel, Envoy
- [Multi-Tenancy & Security](01-Architecture/Multi-Tenancy-Security.md) — PostgreSQL `FORCE RLS`, split DB roles, JWT revocation, SSRF/DoS controls
- [Database Schema](01-Architecture/Database-Schema.md) — Core tables (`users`, `phone_numbers`, `ai_agents`, `leads`, `messages`, `pending_approvals`), `pgvector`
- [Webhooks & Integration Contract](01-Architecture/Webhooks-Contract.md) — Inbound/outbound routes, HMAC validation, replay protection, idempotency

## 02 — Business Workflows
- [WhatsApp & Messaging](02-Business-Workflows/WhatsApp-and-Messaging.md) — Meta Graph API `v21.0`/`v27.0`, 24h window vs. `lead_welcome_he` templates, burst debounce
- [Lead Ingestion & Partners](02-Business-Workflows/Lead-Ingestion-Partners.md) — Landing pages, Facebook/Instagram Lead Ads, E.164 normalization, partner analytics
- [AI & Voice Engine](02-Business-Workflows/AI-and-Voice-Engine.md) — `AgentHarness`, tiered Gemini routing, Hybrid RAG, `ConversationMemoryService`, Whisper
- [Auth & Tenant Lifecycle](02-Business-Workflows/Auth-and-Tenant.md) — Registration, OTP verification, `HS256` JWTs, tenant onboarding
- [Billing & Trials](02-Business-Workflows/Billing-and-Trials.md) — Starter/Pro message quotas, atomic SQL credit reservation, trial lifecycle
- [Telecom & KYC](02-Business-Workflows/Telecom-and-KYC.md) — Meta WABA onboarding, Twilio `+972` regulatory bundles, S3 `SSE-KMS` KYC storage

## 03 — Infrastructure & Security Workflows
- [App Lifespan & Health](03-Infrastructure-Workflows/App-Lifespan-and-Health.md) — FastAPI startup/shutdown hooks, `/health/db-sync-status`, Celery queues
- [CI/CD & Backups](03-Infrastructure-Workflows/CI-CD-and-Backups.md) — GitHub Actions security gate, HMAC `deploy.sh` webhook, Cloudflare R2 `pg_dump -Fc`
- [Edge Security & Wasm DLP](03-Infrastructure-Workflows/Edge-Security-DLP.md) — Envoy L7 proxy + Rust/Wasm `data_hop_firewall` (`X-Data-TTL: 1`)
- [Observability & Logging](03-Infrastructure-Workflows/Observability-Logging.md) — PII-redacted structured logging, `ProductionWatchdog`, planned OpenTelemetry rollout

## 04 — Runbooks & Compliance
- [Meta & Twilio Onboarding](04-Runbooks-and-Compliance/Meta-Twilio-Onboarding.md) — Live Meta App config, `/privacy` & `/terms` crawler checks, template approval
- [Incident Response](04-Runbooks-and-Compliance/Incident-Response.md) — Live SSH/Podman diagnostics, DLQ recovery, AI latency/quota fallbacks
- [Production Post-Mortems](04-Runbooks-and-Compliance/Postmortems.md) — Root-cause analyses for Podman `HOSTNAME` `503`, `AsyncSession` txn conflict, Redis `px=3500`
- [Meshulam Webhook Setup](04-Runbooks-and-Compliance/Meshulam-Webhook-Setup.md) — Payment gateway callback verification and idempotent invoice sync
