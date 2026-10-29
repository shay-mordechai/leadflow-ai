# MyLeads AI (`leadflow-ai`) — System Architecture

*Last Architecture Review: October 2026*

## 1. Executive Summary
`MyLeads AI` is a production-grade, multi-tenant SaaS platform engineered for automated lead qualification and conversational sales over WhatsApp. The platform combines real-time webhook ingestion, edge-level egress PII sanitization via Rust/WebAssembly, multi-tier LLM routing, and strict runtime isolation.

---

## 2. High-Level Architecture Flow

```text
[ External Webhooks (Meta WhatsApp / Facebook / Twilio / Meshulam) & End Users ]
 │
 ▼
[ Cloudflare Zero-Trust Tunnel (cloudflared) ]
 │ (Outbound-Only Encrypted Tunnel — Zero Public Inbound Ports)
 ▼
[ Envoy Reverse Proxy (v1.28 — Port 10000) + Rust/Wasm Data-Gate ]
 ├─ Routes "/" ──────────────────────────► [ Next.js Frontend (Port 3000, user=nextjs) ]
 ├─ Routes "/api/v1/*", "/webhooks/*", "/health", "/bench"
 ├─ Egress Wasm Filter (data_hop_firewall.wasm):
 │   ├─ Scrubs top-level PII keys (phone, email, name) when x-data-ttl: 1 is present
 │   └─ Masks unhandled 5xx upstream stack traces (Fail-Closed JSON error)
 │
 ▼
[ FastAPI Async Backend (Port 8000 — Gunicorn + 4 Uvicorn Workers, user=leadflowuser) ]
 ├─ ASGI RequestBodyLimitMiddleware (1 MiB JSON cap / 26 MiB Audio / 64-Level JSON Depth)
 ├─ Proxy-Aware Rate Limiting (CF-Connecting-IP) & HMAC Webhook Verification
 ├─ JWT Auth Validation (token_version check + Redis jti revocation)
 ├─ Tenant Isolation Scoping (Explicit tenant_id filtering)
 │
 ├───► [ Redis 7 Alpine (127.0.0.1:6379) ]
 │      ├─ Atomic Idempotency Locks (SET NX — 24h TTL)
 │      ├─ Atomic Monthly Token Quota Tracking (incrby / decrby)
 │      └─ Revoked JWT Blocklist & Background Task Queue
 │
 ├───► [ PostgreSQL 15 Alpine (127.0.0.1:5432) ]
 │      ├─ Multi-tenant schema via SQLAlchemy Async & Alembic Migrations
 │      └─ Application-layer Fernet (AES-128-CBC + HMAC-SHA256) PII Encryption at Rest
 │
 └───► [ GeminiTieredRouter (AI Engine) ]
        ├─ Low Complexity  ──► Gemini 2.5 Flash-Lite (Intent parsing & classification)
        ├─ High Complexity ──► Gemini 2.5 Flash (Conversational sales & dynamic RAG)
        └─ Failover Logic  ──► Automatic fallback on upstream timeouts

```

---

## 3. Core Architectural Pillars

### A. Edge Security, Ingress & ASGI DoS Protection

* **Zero Open Inbound Ports:** The host server is invisible to public network scanners. All ingress traffic routes exclusively through **Cloudflare Zero-Trust Tunnels** (`cloudflared`), and administrative SSH mandates FIDO2/WebAuthn hardware keys.
* **Envoy Rust/Wasm Egress Firewall (`data-gate`):**
* Compiled from Rust (`proxy-wasm` v0.2.4) to WebAssembly (`data_hop_firewall.wasm`) and executed inline inside Envoy Proxy.
* **Header-Triggered Structural Redaction:** When upstream handlers emit `x-data-ttl: 1`, the filter strips internal TTL headers, parses the outbound JSON payload, and redacts designated top-level PII fields (`phone`, `email`, `name`) to `"[REDACTED]"`.
* **5xx Error Masking:** Intercepts unhandled `5xx` server errors out-of-process and replaces raw stack traces with `{"error": "Internal Security Proxy Intervention"}`.
* **Verified Performance (`wrk`):** Staggered load testing across 2.1 KB JSON payloads confirmed negligible Wasm latency overhead (`< 3 ms` median delta, bounded within normal run-to-run proxy jitter) while Envoy's HTTP/1.1 connection pooling lowers tail `P99` latency compared to direct backend access.


* **ASGI Streaming Body & Depth Limits (`RequestBodyLimitMiddleware`):**
* Inspects incoming `http.request` chunks in real time before payload buffering completes.
* Enforces a **1 MiB** hard cap on standard requests (failing closed with `HTTP 413 Payload Too Large`) and **26 MiB** for multipart audio uploads (`/api/v1/sessions/upload/`).
* Runs a zero-allocation (ללא הקצאת זיכרון נוספת), byte-level state machine over JSON streams to reject payloads nested deeper than **64 levels** (`HTTP 400 Bad Request`), neutralizing deserialization DoS attacks.



### B. Multi-Tenancy, Cryptography & Data Isolation

* **Tenant-Scoped ORM Queries:** Core database entities (`Lead`, `Session`, `Message`, `Profile`) enforce explicit `tenant_id` scoping at the SQLAlchemy query layer alongside cryptographic JWT claim resolution (`get_current_user`) to prevent Insecure Direct Object Reference (IDOR) vulnerabilities.
* **Per-Tenant Redis Namespacing:** Rate limits, idempotency locks (`SET NX`), and token budgets are partitioned by tenant namespace.
* **Stateful Token Revocation:** JWT validation verifies an integer `token_version` counter in PostgreSQL (invalidating all existing sessions upon password reset) and checks a Redis `jti` blocklist for instant sign-out revocation.
* **Encryption at Rest:** Sensitive database fields are encrypted in application memory using **Fernet (AES-128-CBC + HMAC-SHA256)** with lazy key initialization and fail-safe decryption placeholders (`"[DECRYPTION_FAILED]"`).

### C. Cost-Optimized & Hardened AI Engine

* **Tiered Routing (`GeminiTieredRouter`):**
* **Tier 1 (`gemini-flash-lite-latest`):** Low-latency intent classification, basic parsing, and status evaluation.
* **Tier 2 (`gemini-flash-latest`):** Complex objection handling, sales qualification, and tenant-specific RAG synthesis.


* **Hierarchical Prompt Injection Defense:**
* Untrusted user messages are isolated inside strict XML boundary tags (`<system>`, `<latest_user_message>`).
* Immutable guardrails are placed at the top of the prompt for prefix caching (שמירה במטמון), while LLM outputs are restricted to the `WhatsAppAgentResponse` Pydantic JSON schema.


* **Denial-of-Wallet (DoW) Protection:**
* Conversation length is capped at **15 turns** to prevent infinite bot-to-bot loops.
* Output generation is capped at **512 tokens** with a strict **7-second** HTTP timeout per inference call.
* Monthly tenant token budgets are enforced atomically in Redis via `incrby`/`decrby`.



### D. Hardened Linux Runtime & Hybrid Cloud Infrastructure

* **Rootless Podman & Systemd Quadlets:**
* All services (`leadflow-backend`, `leadflow-frontend`, `leadflow-data-gate`, `leadflow-db`, `leadflow-redis`) run under **Rootless Podman** (`rootless=true`) orchestrated by user-level **Systemd Quadlets** (`systemctl --user`).
* Containers communicate over an isolated bridge network (`leadflow-network`) configured in Envoy with `STRICT_DNS` and `V4_ONLY` lookup.


* **Container Hardening Controls (Verified via `podman inspect`):**
* Every container enforces `sec_opt=[no-new-privileges]` and `--ulimit core=0` (disabling memory core dumps).
* Application workloads execute as non-root UIDs (`user=leadflowuser` in Backend, `user=nextjs` in Frontend) with `privileged=false`.
* The FastAPI backend is bounded by a `1.5 GiB` kernel cgroup memory limit (`mem=1610612736`).


* **Managed Cloud Services (AWS & Cloudflare R2):**
* **In-Memory Secrets Bootstrapping (AWS SSM):** No `.env` files exist on production disks. `src/config.py` fetches secrets from **AWS SSM Parameter Store** directly into process memory at startup over **IMDSv2**.
* **Zero-Egress Off-Site Backups (Cloudflare R2):** `scripts/backup_to_r2.sh` streams compressed `pg_dump` backups to Cloudflare R2, tagging each archive with the active Podman image SHA digest (`db_backup_<UTC>_image_<sha256>.sql.gz`).
* **Object Storage Lifecycle (AWS S3):** Session audio recordings and `fpdf2`-generated PDFs transition to Glacier Instant Retrieval after 30 days and expire after 365 days under least-privilege IAM policies.



### E. DevSecOps, CI/CD & Runtime Governance

* **Zero-Trust Pull-Based CD:** The production server exposes no inbound SSH or deployment sockets to GitHub Actions (eliminating CI-to-Prod Remote Code Execution risks). After CI pushes verified images to `ghcr.io`, an HMAC-SHA256 webhook triggers a local `podman pull` and systemd unit restart.
* **Mandatory CI/CD Security Gates (`exit-code: 1`):**
* **Linting & Formatting:** `ruff check src tests` and `ruff format --check src tests`.
* **Secret & Code Scanning:** `Gitleaks` (commit history secrets) and `Bandit` (Python SAST).
* **Supply-Chain & Container Auditing:** `pip-audit` (enforcing zero known CVEs in `requirements.txt`) and `Trivy` (container image vulnerability scanning).
* **Schema Sync Verification:** `alembic check` in CI paired with `/health/db-sync-status` at runtime (verifying `EXPECTED_DB_REVISION` matches live PostgreSQL `alembic_version`).


* **Autonomous AI Harness Guardrails:** Repository development rules are anchored in `CLAUDE.md` and `.clinerules`, with deterministic `.claude/settings.json` hooks blocking unauthorized `.env` inspection (`Exit 2`).

---

## 4. Systems Engineering Roadmap (In Development)

1. **Recursive & Regex Wasm DLP Inspection:** Upgrading `data_hop_firewall` (`data-gate/src/lib.rs`) from top-level JSON key matching to recursive AST traversal (סריקת עץ JSON רקורסיבית) and non-backtracking regex scrubbing for unstructured PII inside free-text WhatsApp messages.
2. **Native C++ Audio Engine (`cpp-transcription-engine`):** Offloading CPU-intensive audio processing to a native C++ service utilizing POSIX shared memory (`mmap`), IPC, and zero-copy streaming buffers.
3. **Database-Level Row-Level Security (`FORCE RLS`):** Extending application-layer `tenant_id` filtering with PostgreSQL `FORCE ROW LEVEL SECURITY` policies under a dedicated non-owner database role.