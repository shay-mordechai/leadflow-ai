## 1. Production `README.md`

```markdown
# LeadFlow AI (`my-leads.app`)

[![CI & Security Gate](https://img.shields.io/badge/CI-Ruff%20%7C%20Semgrep%20%7C%20Trivy%20%7C%20Pytest-10B981)]()
[![Runtime](https://img.shields.io/badge/Runtime-Rootless%20Podman%20%2B%20Systemd%20Quadlets-06B6D4)]()
[![Edge Security](https://img.shields.io/badge/Edge%20DLP-Envoy%20%2B%20Rust%2FWasm-0F172A)]()
[![Database](https://img.shields.io/badge/DB-PostgreSQL%2015%20%2B%20pgvector%20%2B%20FORCE%20RLS-336791)]()

**LeadFlow AI** is a multi-tenant conversational AI SaaS platform for automated lead ingestion, real-time qualification, and bidirectional WhatsApp Business communication. It combines strict tenant isolation (`FORCE ROW LEVEL SECURITY` + Rust/Wasm Edge DLP) with a bounded, evaluation-backed Gemini agent harness designed for sub-7-second production response SLAs.

---

## System Architecture

All external traffic enters via **Cloudflare Tunnel** and terminates at an **Envoy Proxy** sidecar (`127.0.0.1:10000`) inside a rootless Podman Pod (`leadflow-prod.pod`). No database, cache, backend, or frontend port is exposed to the host network or public internet.

```text
                         ┌──────────────────────────────┐
                         │  Meta / Lead Ads / Clients   │
                         └──────────────┬───────────────┘
                                        │ HTTPS (Zero Inbound Firewall Ports)
                                        ▼
                         ┌──────────────────────────────┐
                         │      Cloudflare Tunnel       │
                         └──────────────┬───────────────┘
                                        │ 127.0.0.1:10000 (Only Host-Exposed Port)
┌───────────────────────────────────────▼───────────────────────────────────────┐
│  leadflow-prod.pod (Rootless Podman Pod — Shared Loopback Namespace)          │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │ Envoy Data Gate (:10000) + Rust/Wasm DLP Filter (`data_hop_firewall`)   │  │
│  └──────────────┬───────────────────────────────────────────┬──────────────┘  │
│                 │ /api/*, /webhooks/*, /health/*            │ /*              │
│                 ▼                                           ▼                 │
│  ┌──────────────────────────────┐            ┌─────────────────────────────┐  │
│  │ FastAPI Backend (:8000)      │            │ Next.js Frontend (:3000)    │  │
│  │ - RequestBodyLimitMiddleware │            │ - Dashboard, HITL Approvals │  │
│  │ - AgentHarness + Hybrid RAG  │            │ - Public /privacy, /terms   │  │
│  └──────┬────────────────┬──────┘            └─────────────────────────────┘  │
│         │                │                                                    │
│         ▼                ▼                                                    │
│  ┌──────────────┐  ┌──────────────┐    ┌───────────────────────────────────┐  │
│  │ PostgreSQL   │  │ Redis (:6379)│◄───│ Celery Worker & Beat              │  │
│  │ + pgvector   │  │ - Debounce   │    │ - Watchdog, GDPR Purge, Followups │  │
│  │ + FORCE RLS  │  │ - Quotas/JTI │    └───────────────────────────────────┘  │
│  └──────────────┘  └──────────────┘                                           │
└───────────────────────────┬──────────────────────────┬────────────────────────┘
                            │ Outbound HTTPS           │ Outbound HTTPS
                            ▼                          ▼
                   ┌─────────────────┐       ┌─────────────────────┐
                   │   Gemini API    │       │ Meta Graph API v21  │
                   └─────────────────┘       └─────────────────────┘

```

---

## Key Capabilities & Engineering Controls

### Security & Multi-Tenant Isolation

* **Database Isolation (`FORCE ROW LEVEL SECURITY`):** Tenant context is enforced at the PostgreSQL layer via least-privilege `leadflow_reader` and `leadflow_writer` roles and SQLAlchemy session listeners.
* **Rust/Wasm Edge DLP (`data-gate/`):** Fail-closed Envoy L7 response filter (`data_hop_firewall.wasm`) that recursively redacts 41 PII and credential fields whenever `X-Data-TTL: 1` is set (`<2%` throughput overhead, `0%` non-2xx error delta).
* **ASGI & Auth Hardening:** Streaming `RequestBodyLimitMiddleware` (1 MiB JSON / 26 MiB media caps, byte-level 64-depth JSON nesting limit), `HS256`-pinned JWTs with Redis `jti` and `token_version` revocation, `CF-Connecting-IP` parsing, and SSRF URL allowlists (`follow_redirects=False`).
* **Concurrency & Quota Safety:** Atomic Redis `SET NX` webhook idempotency, conditional SQL `UPDATE ... RETURNING` message quotas, Redis `INCRBY`/`DECRBY` token budgets with failure rollback, and `BoundedSemaphore(200)` background task admission control.

### Agentic AI & Hybrid RAG (`src/services/ai/`)

* **Unified `AgentHarness`:** Tiered Gemini routing with a `7s` hard timeout, `512` max output tokens, `15`-turn human-escalation cap, XML-escaped prompt boundaries, structured Pydantic outputs (`abstained`, `cited_chunk_ids`), and `bleach` output sanitization.
* **Multi-Tenant Hybrid RAG (`pgvector`):** Pricing-table-aware chunking combined with Vector + Hebrew Lexical Reciprocal Rank Fusion (RRF) and mandatory `user_id` pre-filtering.
* **Memory & Burst Control:** `ConversationMemoryService` rolling summaries and extracted lead state, paired with Redis `3500ms` (`px=3500`) WhatsApp message burst debouncing.
* **Human-in-the-Loop (HITL):** Tenant-scoped tools (`qualify_lead`, `check_calendar_availability`, `propose_appointment_booking`) routed through `PendingApproval` review gates (`/api/v1/leads/approvals`).
* **Automated Evaluation Gate:** Offline and live regression benchmarks against a 15-scenario Hebrew/English Golden Dataset (`tests/evals/golden_dataset.json`).

---

## Webhook & Integration Surface

| Integration | Route | Authentication & Protection | Notes |
| --- | --- | --- | --- |
| **Meta WhatsApp Verification** | `GET /webhooks/whatsapp` | `WHATSAPP_VERIFY_TOKEN` handshake | Verified on Meta API `v27.0` |
| **Meta WhatsApp Inbound** | `POST /webhooks/whatsapp` | `X-Hub-Signature-256` (`WHATSAPP_APP_SECRET`) + stale timestamp `401` rejection | Triggers `WhatsAppPipeline` + AI reply |
| **Meta WhatsApp Outbound** | Graph API `v21.0` | System User token + tenant `phone_number_id` | Uses approved Utility Template (`lead_welcome_he`) outside the 24h window |
| **Meta Lead Ads (FB / IG)** | `POST /webhooks/facebook` | Meta signature validation + E.164 normalization | Dispatches proactive WhatsApp template welcome |
| **Marketing / Landing Pages** | `POST /webhooks/marketing`, `POST /api/v1/leads` | Tenant API key / JWT + Redis `SET NX` idempotency | Async welcome dispatch via FastAPI `BackgroundTasks` |
| **Compliance & Crawler Routes** | `GET /privacy`, `GET /terms` | Public HTTPS (`200 OK` verified for `facebookexternalhit/1.1`) | Serves Meta Privacy & Data Deletion requirements |
| **Production CD Deploy Hook** | `POST` Hetzner Webhook (`deploy.sh`) | HMAC-SHA256 signature + `300s` replay window | Zero-DB-downtime app rollout + `alembic upgrade head` |

---

## Repository Structure

```text
leadflow-ai/
├── src/
│   ├── routers/              # FastAPI REST endpoints & webhooks (whatsapp, facebook, marketing, leads)
│   ├── services/
│   │   ├── ai/               # AgentHarness, Hybrid RAG retriever, ConversationMemoryService, tools
│   │   ├── communication/    # WhatsAppPipeline, Meta Graph API client, template dispatcher
│   │   └── monitoring/       # ProductionWatchdog & AlertDispatcher
│   ├── tasks/                # Celery async tasks & Beat schedules (watchdog, GDPR purge, follow-ups)
│   ├── models/               # SQLAlchemy ORM models with tenant RLS metadata
│   └── config.py             # Typed Pydantic settings
├── frontend/                 # Next.js 16 standalone app (dashboard, HITL approvals, /privacy, /terms)
├── data-gate/                # Envoy proxy config (`envoy.yaml`) + Rust/Wasm `data_hop_firewall`
├── alembic/                  # Dual SQLite/PostgreSQL schema & RLS migrations
├── tests/                    # Unit, security, RLS, webhook, and Golden Dataset AI eval suites
├── scripts/                  # Verification harness (`verify_harness.sh`), eval runner, ops scripts
├── docs/                     # Architecture, security, runbooks, eval reports, and ADRs
├── compose.yaml              # Local/reference container topology
└── ROADMAP.md                # Phased product & engineering roadmap

```

---

## Local Development & Verification

### Prerequisites

* Python `3.12+`, Node.js `22+`, Rust (`wasm32-unknown-unknown` target for `data-gate/`)
* Rootless Podman (recommended via `leadflow-test.pod` / `devops-box`)
* PostgreSQL 15 (`pgvector/pgvector:pg15`) and Redis 7

### Environment Configuration

Create a `.env` (local) or `.env.production` (server) file. Never commit secrets to git.

```bash
# Core Runtime
APP_ENV=development
DATABASE_URL=postgresql+psycopg://leadflow_writer:<password>@127.0.0.1:5432/leadflow
REDIS_URL=redis://127.0.0.1:6379/0
JWT_SECRET_KEY=<32+ byte random secret>

# AI Provider
GEMINI_API_KEY=<google_ai_api_key>

# Meta WhatsApp Business Platform
WHATSAPP_VERIFY_TOKEN=<webhook_verify_token>
WHATSAPP_APP_SECRET=<meta_app_secret>
WHATSAPP_PHONE_ID=<default_phone_number_id>
WHATSAPP_WELCOME_TEMPLATE=lead_welcome_he
META_ACCESS_TOKEN=<system_user_permanent_token>

# Observability & Alerts (Optional in dev)
ALERT_WEBHOOK_URL=https://<ssrf-safe-alert-endpoint>

```

### Quality & Verification Gates

Every pull request and release must pass the full local verification harness and offline AI evaluation suite:

```bash
# Format & lint Python codebase
ruff format src tests alembic scripts
ruff check src tests alembic scripts

# Verify Alembic migration consistency
alembic check

# Run full test & security harness (Pytest, RLS, API, Wasm checks)
./scripts/verify_harness.sh

# Run offline Golden Dataset AI evaluation suite (must pass 100%)
python3 scripts/run_evals.py --mode offline

```

---

## Production Deployment & Operations

Production runs on Hetzner Cloud (`leadflow-cx23`) using **Rootless Podman + Systemd Quadlets** (`~/.config/containers/systemd/leadflow/`) with `loginctl enable-linger`.

* **Zero-DB-Downtime Deployments:** GitHub Actions (`.github/workflows/production.yml`) runs SAST (`Semgrep`/`Ruff`), container scanning (`Trivy`), migrations check, and Pytest before pushing images to GHCR and triggering the HMAC-signed `deploy.sh` webhook. Only app-tier units (`backend`, `worker`, `beat`, `frontend`, `data-gate`) restart while `leadflow-db` and `leadflow-redis` stay online.
* **Podman Pod Loopback Rule:** Podman pods inject `HOSTNAME=leadflow-prod` at runtime, overriding Dockerfile `ENV HOSTNAME`. `frontend/Dockerfile` and the Quadlet unit explicitly invoke `sh -c "HOSTNAME=0.0.0.0 exec node server.js"` so Envoy always reaches Next.js on `127.0.0.1:3000`.
* **Health & Sync Verification:** Monitor `GET https://my-leads.app/health/db-sync-status` after every deployment to verify Alembic head parity and DB connectivity.
* **Backups & Retention:** Automated encrypted `pg_dump -Fc` snapshots ship to Cloudflare R2; Celery Beat executes a daily 90-day GDPR data retention purge and a 5-minute `ProductionWatchdog` check on LLM error rates and DLQ depth.

---

## Documentation Index

| Area | Path | Description |
| --- | --- | --- |
| **Product Roadmap** | [`ROADMAP.md`](https://www.google.com/search?q=ROADMAP.md) | Live status, pre-pilot priorities, OpenTelemetry & MCP plans |
| **System Architecture** | [`docs/architecture/`](https://www.google.com/search?q=docs/architecture/) | Podman Quadlets, RLS isolation, Envoy/Wasm DLP, AgentHarness |
| **Integrations & Webhooks** | [`docs/integrations/`](https://www.google.com/search?q=docs/integrations/) | Meta WhatsApp setup, templates, Lead Ads, Twilio KYC |
| **Operations & Runbooks** | [`docs/operations/`](https://www.google.com/search?q=docs/operations/) | CD runbook, incident playbooks, R2 restore drills, post-mortems |
| **Security & Compliance** | [`docs/security/`](https://www.google.com/search?q=docs/security/) | Threat model, auth/SSRF controls, GDPR & Meta privacy compliance |
| **AI Evals & Benchmarks** | [`docs/evals/`](https://www.google.com/search?q=docs/evals/) | Eval benchmark report, Golden Dataset curation, HITL feedback loop |
| **ADRs** | [`docs/adr/`](https://www.google.com/search?q=docs/adr/) | Architecture Decision Records for core technical trade-offs |

```

---

## 2. Recommended `docs/` Directory Tree

This structure separates **stable architecture** (אדריכלות יציבה), **external integrations**, **operational runbooks** (מדריכי תפעול לשגרה וחירום), **security audits**, and **AI evaluations**—keeping `README.md` clean while making onboarding and incident response fast.

```text
docs/
├── architecture/
│   ├── SYSTEM_OVERVIEW.md          # End-to-end request lifecycle (Cloudflare -> Envoy -> FastAPI -> DB/AI)
│   ├── PODMAN_QUADLETS.md          # Rootless pod topology, loopback namespace, HOSTNAME=0.0.0.0 rule
│   ├── MULTI_TENANT_RLS.md         # PostgreSQL FORCE RLS, leadflow_reader/writer roles, SQLAlchemy listeners
│   ├── EDGE_DLP_WASM.md            # Envoy + Rust/Wasm data_hop_firewall spec, X-Data-TTL contract, benchmarks
│   └── AI_HARNESS_AND_RAG.md       # AgentHarness, tiered Gemini routing, pgvector Hybrid RRF, HITL state machine
│
├── integrations/
│   ├── WEBHOOKS_CONTRACT.md        # Exact payloads, HMAC verification, replay windows, and idempotency keys
│   ├── META_WHATSAPP_SETUP.md      # Meta App publish checklist, Billing Hub, phone_numbers mapping, templates (lead_welcome_he)
│   ├── FACEBOOK_LEAD_ADS.md        # OAuth 60-day token lifecycle, Page/Form ingestion, E.164 normalization
│   └── TWILIO_KYC_AND_BILLING.md   # +972 Regulatory Bundles, S3 SSE-KMS KYC storage, Meshulam/Morning webhooks
│
├── operations/
│   ├── DEPLOYMENT_RUNBOOK.md       # GitHub Actions CI/CD, deploy.sh HMAC webhook, Alembic zero-downtime flow
│   ├── INCIDENT_RESPONSE.md        # ProductionWatchdog alerts, DLQ drain/replay, LLM timeout fallback playbooks
│   ├── BACKUP_AND_RESTORE.md       # Cloudflare R2 pg_dump -Fc schedule + monthly staging restore drill
│   └── POSTMORTEMS.md              # Real prod fixes (Podman HOSTNAME 503, AsyncSession txn conflict, Redis px=3500)
│
├── security/
│   ├── THREAT_MODEL.md             # Tenant escape, prompt injection, SSRF, DoS, and webhook spoofing mitigations
│   ├── AUTH_AND_SECRETS.md         # HS256 JWT + Redis jti/token_version revocation, Cloudflare Tunnel, secret rotation
│   └── GDPR_AND_PRIVACY.md         # 90-day Celery retention purge, /privacy Data Deletion flow, PII log redaction
│
├── evals/
│   ├── EVAL_BENCHMARK_REPORT.md    # Existing benchmark report (P50/P95 latency, token cost, pass rates)
│   └── GOLDEN_DATASET_GUIDE.md     # How to convert HITL EDITED pilot replies into golden_set_hebrew.jsonl cases
│
└── adr/                            # Short Architecture Decision Records (Why we chose X over Y)
    ├── 0001-podman-quadlets-over-compose.md
    ├── 0002-envoy-wasm-dlp-edge-redaction.md
    ├── 0003-force-rls-and-split-db-roles.md
    └── 0004-opentelemetry-and-mcp-gateway.md