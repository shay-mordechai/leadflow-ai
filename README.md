# MyLeads AI (LeadFlow) — Secure AI Platform Architecture

**Engineering case study covering:**
- Product engineering & workflow design
- Secure distributed systems & edge proxy filtering (Envoy + Rust/Wasm)
- Linux-based deployment (Rootless Podman & Systemd Quadlets)
- AI workflows & dynamic RAG
- Runtime isolation & ASGI DoS mitigation
- Empirical performance benchmarking & production reliability

*Last Engineering Review: November 2026*

---

---
## Part 1: Current Active Workflows (29 Total)

Here is the complete catalog of all 29 active workflows currently implemented in your codebase. Due to output length constraints (מגבלות אורך פלט), I have included the exact file paths and descriptions for all of them, along with the **core architectural code snippets** for the most critical ones.

### Group 1: Identity & Multi-Tenancy

**1. Registration Workflow**

* **Path:** `/src/routers/auth.py`
* **Description:** Creates a new tenant, hashes the password securely via threadpool, and enforces the default STARTER tier.

```python
@router.post("/register", status_code=201)
@limiter.limit("5/minute")
async def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email exists")
    secure_hash = await run_in_threadpool(get_hash, data.password)
    new_user = User(email=data.email.lower(), hashed_password=secure_hash, plan_tier=PlanTier.STARTER)
    db.add(new_user)
    db.commit()
    return {"status": "success"}

```

**2. Login & Token Issuance**

* **Path:** `/src/routers/auth.py`, `/src/security/rate_limiter.py`
* **Description:** Authenticates credentials under Redis Rate Limiting (הגבלת קצב) and issues a JWT containing `tenant_id` and RBAC roles.

**3. Dashboard Management**

* **Path:** `/src/routers/leads.py`, `/src/routers/settings.py`
* **Description:** Fetches leads and updates AI configurations (`system_instruction`) with strict `tenant_id` isolation.

---

### Group 2: External Webhooks & Lead Ingestion (קליטת לידים מ-Webhooks)

**4. Landing Page Lead Ingestion**

* **Path:** `/src/routers/webhooks/campaign.py`
* **Description:** Receives POST requests, validates the Tenant Key, checks for Idempotency (מניעת כפילויות) in Redis, and pushes a Celery task.

```python
@router.post("/webhooks/leads/inbound")
async def receive_campaign_lead(payload: InboundLeadPayload, bg_tasks: BackgroundTasks, _: None = Depends(verify_tenant_key)):
    is_new = await _reserve_lead_idempotency_key(payload.phone_number)
    if not is_new:
        return {"status": "accepted"} # Ignored duplicate
    background_task_capacity.add_reserved(bg_tasks, trigger_outbound_ai_agent, payload)
    return {"status": "accepted"}

```

**5. Partners & Facebook OAuth**

* **Path:** `/src/routers/facebook.py`, `/src/routers/partners.py`
* **Description:** Handles Facebook OAuth 2.0 flow, exposes conversion analytics (`/api/v1/partners/performance`), and ingests Meta Lead Ads directly.

**6. Meshulam & Grow Payments**

* **Path:** `/src/routers/webhooks/meshulam.py`
* **Description:** Verifies payment HMAC signatures, upgrades tenant to PRO, and increases the Redis token quota.

```python
def verify_meshulam_signature(data: dict, api_key: str) -> bool:
    received_sig = data.get("signature")
    data_str = f"{data.get('transactionId')}{data.get('sum')}{data.get('status')}"
    expected_sig = hmac.new(api_key.encode(), data_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)

```

---

### Group 3: Core AI & Messaging Engine

**7. Outbound Lead Follow-up**

* **Path:** `/src/tasks/followup_tasks.py`
* **Description:** A Celery worker fetches the lead, atomically checks token quota in Redis, and sends a Meta-approved template message via WhatsApp.

**8. Two-Way WhatsApp Chat**

* **Path:** `/src/routers/webhooks/whatsapp.py`
* **Description:** Validates Meta's `X-Hub-Signature-256`, runs Guardrails (סינון הזרקות), pushes to Celery, and immediately returns `200 OK`.

**9. AI Response Caching**

* **Path:** `/src/services/ai/engine.py`
* **Description:** Checks Redis for identical questions under the same `system_instruction` in the last 24h to save LLM tokens.

**10. Quota Rollback**

* **Path:** `/src/services/ai/engine.py`
* **Description:** A compensation mechanism (מנגנון פיצוי) that refunds tokens to the tenant's Redis counter if the LLM crashes.

**11. Audio Transcription**

* **Path:** `/src/tasks/audio_tasks.py`, `/src/services/ai/whisper.py`
* **Description:** Async task that downloads WhatsApp `.ogg` files, runs them through Whisper, and passes the transcribed text to the AI agent.

**12. Virtual CMO Marketing Insights**

* **Path:** `/src/routers/insights.py`
* **Description:** The newly added workflow! Aggregates `summary_text` from the past 6 months to generate strategic marketing recommendations based on lead demands.

---

### Group 4: Telecom & File Storage

**13. Business Number Provisioning**

* **Path:** `/src/routers/provisioning.py`
* **Description:** Uses Least-Cost Routing (LCR) APIs (Twilio/Meta) to purchase `+972` numbers and link them to the `tenant_id`.

**14. KYC Document Upload**

* **Path:** `/src/routers/phones.py`, `/src/services/storage/s3_service.py`
* **Description:** Securely uploads encrypted ID documents (JPG/PDF) to an S3 `kyc/` bucket for telecom regulatory approval.

**15. Local Media Storage**

* **Path:** `/src/routers/storage.py`
* **Description:** Serves files while strictly preventing Path Traversal vulnerabilities (חולשת מעבר נתיבים).

```python
@router.get("/{file_path:path}")
async def get_local_file(file_path: str, current_user: User = Depends(get_current_user)):
    base_dir = getattr(settings, "STORAGE_BASE_PATH", "/app/storage")
    safe_path = os.path.normpath(os.path.join(base_dir, file_path))
    if not safe_path.startswith(base_dir) or str(current_user.id) not in safe_path:
        raise HTTPException(status_code=403, detail="Unauthorized Access")
    return FileResponse(safe_path)

```

---

### Group 5: Background Jobs (Celery Beat & Async Tasks)

**16. Scheduled Follow-ups**

* **Path:** `/src/worker.py`, `/src/tasks/followup_tasks.py`
* **Description:** Triggers automated follow-up messages for unresponsive leads (לידים שלא הגיבו).

**17. Trial & Subscription Enforcement**

* **Path:** `/src/tasks/billing_tasks.py`
* **Description:** Daily cron job that identifies expired 14-day trials and sets `bot_active = False`.

**18. GDPR Data Retention**

* **Path:** `/src/tasks/retention_tasks.py`
* **Description:** Clears old logs and media files after their TTL expires (e.g., 90 days), while shielding protected databases.

**19. Secure S3 Database Backup**

* **Path:** `/src/tasks/backup_tasks.py`
* **Description:** Creates safe snapshots of PostgreSQL in WAL mode and uploads them to S3.

**20. Dead Letter Queue / DLQ Replayer**

* **Path:** `/src/tasks/followup_tasks.py` (DLQ Logic)
* **Description:** Automatically retries failed webhook events up to 5 times.

---

### Group 6: Infrastructure & Middleware

**21. Database Sync Health**

* **Path:** `/src/routers/health.py`
* **Description:** Validates that the active Alembic migration matches `EXPECTED_DB_REVISION`.

```python
@router.get("/health/db-sync-status")
def database_sync_status(db: Session = Depends(get_db)):
    expected = os.getenv("EXPECTED_DB_REVISION")
    actual = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    return JSONResponse(status_code=200 if actual == expected else 503, content={"synced": actual == expected})

```

**22. Request Limits Middleware**

* **Path:** `/src/middleware/request_limits.py`
* **Description:** Blocks DoS memory-exhaustion by limiting JSON payloads to 1 MiB and audio to 26 MiB.

**23. CI/CD Pipeline**

* **Path:** `/.github/workflows/production.yml`
* **Description:** Runs PyTest, security scanners (Trivy, Bandit), and deploys Podman containers with `NoNewPrivs=1`.

**24. Application Lifespan**

* **Path:** `/src/main.py`
* **Description:** Handles safe DB connection pooling (חיבוריות) on startup and graceful teardown on shutdown.

**25. Distributed Tracing**

* **Path:** `/src/main.py`
* **Description:** Injects an `X-Request-ID` into every incoming request for distributed logging across microservices.

**26. Structured JSON Logging**

* **Path:** `/src/main.py`
* **Description:** Overrides Uvicorn logs to output pure JSON, injecting the `tenant_id` and `X-Request-ID`.

**27. Global Security Headers**

* **Path:** `/src/main.py`
* **Description:** Middleware that injects `HSTS`, `X-Content-Type-Options`, and `CSP` into every HTTP response.

**28. Egress DLP Trigger**

* **Path:** `/src/main.py`, `/src/routers/benchmark.py`
* **Description:** Adds `X-Data-TTL: 1` headers to sensitive API routes to trigger the Envoy WebAssembly (Wasm) filter to redact PII (צנזור מידע אישי).

**29. Global Exception Handler & Alerts**

* **Path:** `/src/main.py`
* **Description:** Catches all unhandled crashes, prevents API hangs, and triggers Sentry & email alerts to the DevOps team.

---

---



## 1. Project Overview & Product Thesis

MyLeads AI is a production-oriented AI platform designed with a strict emphasis on secure architecture, reliability, and deterministic runtime behavior. However, the system did not begin as an exploration of LLMs or AI technology for its own sake. It originated from a concrete business problem.

**The Product Thesis:**
> A small business owner (such as a coach, trainer, or therapist) should not have to manually coordinate repetitive lead-management and administrative workflows that do not require their professional expertise. Furthermore, they should not need to become an automation engineer to run an efficient business.

The project development followed a distinct product-engineering loop:
**Customer observation → Pain point → Business requirement → Technical requirement → System design → Implementation → Testing → Production operation → Feedback → Iteration**

---

## 2. Customer Discovery & Workflow Analysis

Initial design phases involved hands-on discussions and workflow analysis with a real coach/business owner. The goal was to understand how the business currently operates, identify repetitive manual tasks, map points where information is lost, and translate those operational pain points into strict system requirements.

By analyzing the daily work, it became clear that the business owner was acting as a manual router for data. Automation was introduced to act as an operational layer between customer communication and the business workflow.

---

## 3. Concrete Workflow Case Studies

### 3.1 Case Study 1: Lead Handoff & Conversion Tracking 
*Status: Core Routing & Webhooks Active, Multi-day Follow-up State Machine in Roadmap*

This workflow represents the core lead-management flow. It is not simply "WhatsApp automation." It requires persistent lead state, routing logic, asynchronous waiting, and human escalation.

**The Operational Workflow:**
```text
Incoming WhatsApp / Facebook inquiry
   ↓
Collect name & city
   ↓
Identify appropriate coach/partner based on location
   ↓
Notify customer and coach
   ↓
Track handoff status
   ↓
Follow up after a defined period (e.g., 3 days)
   ↓
Collect customer feedback & collect coach feedback
   ↓
Compare both states
   ↓
Resolve: Closed successfully / Not closed / Contradictory reports → Manual investigation

```

**State Machine Thinking:**
To engineer this, the workflow was modeled as a persistent business process rather than a sequence of independent, stateless API calls. It naturally behaves as a state machine:
`New Lead` → `Details Collected` → `Coach Assigned` → `Waiting for Contact` → `Feedback Pending` → `Closed / Manual Review`.

### 3.2 Case Study 2: Post-Session Transcription

*Status: Upload & Session Endpoints Active / Native C++ Audio Pipeline In Development*

A secondary workflow was analyzed regarding post-session administrative work. The operational problem: The professional should spend time coaching rather than manually processing recordings, transcripts, summaries, and documents.

**The Operational Workflow:**

```text
Audio recording from phone
   ↓
Upload via streaming-limited endpoint (/api/v1/sessions/upload/)
   ↓
Trigger scheduled processing pipeline
   ↓
Transcription (Whisper)
   ↓
Structured LLM summarization
   ↓
PDF generation (fpdf2)
   ↓
Delivery to client/coach
   ↓
Archive original recording & prevent duplicate processing

```

This demonstrated another applied engineering chain: **Operational task → Automation requirement → Processing pipeline → Reliable delivery → Archival & Idempotency**.

---

## 4. Engineering From Business Requirements

The platform's technical architecture is directly derived from the operational requirements discovered during workflow analysis. Technology is applied to resolve mapped friction, not to search for a use case.

| Operational Requirement | Engineering Constraint | Architecture Decision |
| --- | --- | --- |
| **External webhook retries** | Protection against duplicate processing | **Idempotency keys** |
| **Processing can fail after ingestion** | Minimize lead loss under processing failures | **Dead Letter Queue (DLQ) + retry architecture** |
| **Workflow spans several days** | Long-lived business processes | **Persistent PostgreSQL state + scheduled workers** |
| **Conflicting reports / unhandled cases** | Human intervention may be required | **Explicit exception states & alerts** |
| **Sensitive customer data crosses services** | Strict egress privacy & payload bounds | **Envoy Rust/Wasm Filter + ASGI Streaming Limits** |
| **Business owner shouldn't manage infra** | Managed, reproducible deployment | **Linux + Rootless Podman Quadlets + CI/CD** |

---

## 5. High-Level System Architecture

```text
User / External Webhooks (Meta WhatsApp, Facebook, Twilio, Meshulam)
 |
Cloudflare Zero Trust (Network Boundary)
 |
Envoy Proxy v1.28 (Port 10000 — Rust/Wasm Egress Filter: data_hop_firewall)
 |
 +---> Next.js Frontend (Port 3000 — Tenant Dashboard & UI)
 |
 +---> FastAPI Backend (Port 8000 — Gunicorn + 4 Uvicorn Workers)
        |  [ASGI RequestBodyLimitMiddleware: 1MB JSON / 64-Depth Bound]
        |
        +---> Asynchronous Workers & Rate/State Cache (Redis 7 Alpine)
        |
        +---> Relational Database (PostgreSQL 15 Alpine — Alembic Managed)
        |
        +---> Future C++ Engine (High-Performance Audio/AI) [In Development]
 |
Linux Runtime (Rootless Podman / Systemd Quadlets / no-new-privileges)

```

---

## 6. Security & Runtime Architecture

Because customer conversations contain sensitive information, security boundaries are treated as a primary product requirement rather than an infrastructure afterthought.

* **Edge Egress Privacy (Envoy Rust/Wasm Filter):** A custom Rust-compiled WebAssembly filter (`data_hop_firewall` built on `proxy-wasm` v0.2.4) runs inline inside Envoy Proxy. When upstream services attach the internal response header `x-data-ttl: 1`, the filter intercepts the response stream, strips the `x-data-ttl` and `content-length` headers, parses the JSON payload, and redacts designated top-level PII keys (`phone`, `email`, `name`) to `"[REDACTED]"` before bytes leave the network edge.
* **ASGI Streaming Body & JSON Depth Protection (`RequestBodyLimitMiddleware`):** To protect the backend and Wasm heap from Out-Of-Memory (OOM) and deeply nested deserialization DoS attacks, custom ASGI middleware inspects incoming `http.request` chunks in real time:
* Enforces a strict **1 MB** limit on standard requests (failing closed with `HTTP 413 Payload Too Large`) and **26 MB** for authenticated multipart audio uploads (`/api/v1/sessions/upload/`).
* Executes a zero-allocation, byte-level state machine over JSON streams to track bracket depth, rejecting payloads exceeding **64 levels of nesting** with `HTTP 400 Bad Request` before `json.loads()` is ever invoked.


* **Container Hardening & Rootless Isolation:**
* All services run under **Rootless Podman** (`rootless=true`) managed via **Systemd Quadlet** user units (`systemctl --user`), eliminating root daemon attack surfaces.
* Every container enforces `sec_opt=[no-new-privileges]`.
* Application containers execute as unprivileged UIDs (`user=leadflowuser` on Backend, `user=nextjs` on Frontend), with explicit cgroup memory limits (`1.5 GB` hard cap on the backend).


* **Network & Transport Hardening:**
* **Cloudflare Zero Trust & Tunnels:** Eliminates direct public SSH exposure (closing inbound port 22) and mandates hardware security keys (FIDO2/WebAuthn) for administrative access.
* **Local Loopback Binding:** Internal data stores (`PostgreSQL` on `127.0.0.1:5432`, `Redis` on `127.0.0.1:6379`) bind strictly to host loopback / isolated bridge networks (`leadflow-network` with `STRICT_DNS` and `V4_ONLY` resolution).
* **Strict HTTP Security Headers:** Responses enforce `Strict-Transport-Security` (HSTS), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`.


* **Global Exception Handler & Audit Logging:** Intercepts unhandled `500 Internal Server Errors` to prevent stack trace leakage while recording sensitive mutations in database-backed audit logs.

---

## 7. Multi-Tenant Architecture & State Management

* **Dynamic RAG & Profile Loader:** An asynchronous profile loader injects tenant-specific business context, catalogs, and privacy guardrails into Gemini Flash, featuring a deterministic fallback mechanism for missing files.
* **Per-Tenant State Isolation:** Tenant sessions and caching keys are isolated via structured Redis namespacing alongside relational tenant scoping in PostgreSQL.
* **Database Migrations:** Managed via **Alembic**. `alembic check` is enforced during CI/CD gating to prevent production `CrashLoopBackOff` caused by schema drift.
* **Transaction Safety:** Application-level state handling mitigates SQLAlchemy async object-detachment issues by caching system prompts prior to transaction commits, ensuring reliable state transitions across webhook invocations.

---

## 8. Deployment, CI/CD & DevSecOps Gating

The platform evolved from an initial AWS deployment to a deterministic, cost-efficient bare-metal deployment model on Hetzner.

Current production deployment utilizes a **Zero-Trust Pull-Based CD** architecture: **GitHub Actions (CI & Security Audit) → GHCR → Secure Local Webhook (CD Pull) → Rootless Podman Systemd Quadlets**.

* **Automated CI/CD Quality & Vulnerability Gates:** Every push to `main` must pass strict automated gates before container images are published to GitHub Container Registry (`ghcr.io`):
1. **Static Analysis & Formatting:** `ruff check` and `ruff format --check` across `src/` and `tests/`.
2. **Supply-Chain CVE Auditing:** `pip-audit` scans `requirements.txt` against the Python Advisory Database, blocking builds on any known vulnerability (e.g., enforcing patched bounds on `aiohttp`, `certifi`, `filelock`, `fpdf2`).
3. **Container Vulnerability Scanning:** **Trivy** scans built container images for OS and library CVEs.


* **RCE Prevention & Pull-Based CD:** To eliminate Remote Code Execution (RCE) risks associated with self-hosted runners or inbound SSH keys in CI, the production server accepts no remote execution commands. Deployments are triggered via an HMAC-signed webhook that triggers a hardcoded local image pull and systemd unit restart.
* **Out-of-Band Management (`manage_cli.py`):** Administrative mutations are decoupled from the public web UI and executed through an isolated CLI entrypoint.
* **Graceful Shutdown:** Gunicorn and Uvicorn workers handle `SIGTERM` signals cleanly, allowing active database transactions and in-flight webhook requests to complete before container termination.

---

## 9. Edge Proxy Performance & Latency Benchmarking

To quantify the exact latency and throughput cost of running inline Rust/Wasm JSON redaction inside Envoy, the repository includes an automated, reproducible benchmark suite (`tests/benchmarks/run_latency_bench.sh`) driven by `wrk`.

### 9.1 Methodology

The benchmark runs 5 staggered, interleaved iterations (`30s` duration, `2` threads, `20` concurrent connections) across three distinct topologies on the local host:

1. **`direct` (`127.0.0.1:8000`):** `wrk` → FastAPI/Gunicorn backend directly.
2. **`nofilter` (`127.0.0.1:10001`):** `wrk` → Baseline Envoy Proxy (no Wasm filter) → FastAPI backend.
3. **`filter` (`127.0.0.1:10000`):** `wrk` → Production Envoy Proxy (`data_hop_firewall.wasm` active, redacting `x-data-ttl: 1` responses) → FastAPI backend.

Payloads are generated dynamically via Lua scripts across three sizes: `small` (117 B), `medium` (2,131 B — 20 lead records), and `large` (21,211 B — 200 lead records).

### 9.2 Empirical Results (`medium` Payload — 2.1 KB JSON)

| Configuration | Median P50 Latency (ms) | Median P99 Latency (ms) | Median Throughput (RPS) | Non-2xx Errors |
| --- | --- | --- | --- | --- |
| **`direct` (FastAPI only)** | 22.51 ms | 358.82 ms | 710.13 req/s | 0 |
| **`nofilter` (Bare Envoy)** | 28.34 ms | 320.50 ms | 659.21 req/s | 0 |
| **`filter` (Envoy + Rust/Wasm)** | 30.11 ms | 305.03 ms | 646.88 req/s | 0 |

### 9.3 Statistical Analysis & Architectural Findings

* **Wasm Overhead vs. Run-to-Run Jitter:** Evaluating the paired per-run P50 difference (`filter - nofilter`) across the 5 staggered runs yielded deltas of `[-2.91, +2.90, +0.22, +8.58, +3.28] ms` (median delta: `+2.90 ms`, throughput delta: `< 2%`). Because run-to-run variance on a shared host (`11.49 ms` spread) exceeds the median delta, the Wasm execution overhead is statistically bounded within normal proxy jitter.
* **Tail-Latency Smoothing (P99):** Routing traffic through Envoy (`nofilter` and `filter`) yielded lower P99 latency (`305–320 ms`) compared to hitting Gunicorn/Uvicorn directly (`358.82 ms`), demonstrating the benefit of Envoy's HTTP/1.1 connection pooling and request queuing under burst concurrency.
* **Current Redaction Scope & Trade-offs:** The current `data_hop_firewall` implementation performs **schema-based, top-level key matching** (`serde_json::Value` object lookup). While this guarantees deterministic, low-overhead redaction for structured API contracts, it does not currently traverse deeply nested sub-objects, arrays, or unstructured free-text fields (such as raw phone numbers embedded inside a conversational `note` string). Extending the Wasm filter with recursive AST traversal and compiled regular expressions is tracked in the Systems Roadmap below.

---

## 10. Systems Engineering Roadmap (Performance & Low-Level)

### 10.1 Deep Wasm DLP Inspection [Next Up]

* Upgrade `data_hop_firewall` (`data-gate/src/lib.rs`) from top-level key matching to **recursive JSON tree traversal** across nested objects and arrays.
* Integrate deterministic, non-backtracking regex matching (e.g., `regex-automata` / SIMD-accelerated scanning) to redact unstructured PII (Israeli phone numbers, emails) embedded inside free-text WhatsApp message bodies, followed by re-benchmarking against the 2.1 KB and 21 KB baselines.

### 10.2 High-Performance C++ Processing Engine [In Development]

For selected CPU- and memory-intensive media processing paths, a native C++ layer (`cpp-transcription-engine`) is being developed to offload tasks:

* Linux systems programming using primitives such as `mmap`, POSIX shared memory, IPC, and CPU affinity.
* Custom arena/pool memory-allocation strategies for sustained high-throughput workloads.
* Zero-copy audio streaming pipelines to eliminate buffer-copy overhead between the API gateway and transcription workers.

---

## 11. QA & Benchmarking Commands

```bash
# 1. Code Quality, Formatting & Supply-Chain Security Audit:
ruff check src tests
ruff format --check src tests
pip-audit -r requirements.txt

# 2. Internal Logic & Security Unit Tests:
pytest tests/test_main.py -v

# 3. E2E Macro & Micro Pipeline Validation:
python3 tests/qa_macro.py --prod
python3 tests/qa_micro.py --prod

# 4. AI Agent Function Calling (Direct Engine QA):
python3 tests/qa_agents.py --api-key="[INJECTED_AT_RUNTIME]"

# 5. Reproducible Envoy + Wasm Latency Benchmark (wrk):
./tests/benchmarks/run_latency_bench.sh

```

---

## 12. Engineering Mindset

The recurring design principle governing this repository is:
**Observe → Model → Specify → Build → Validate → Operate → Iterate**

Start with the operational problem, model the workflow, identify failure modes, derive technical requirements, and *then* select and measure the implementation.

---

## 13. Applied Engineering Perspective

This project demonstrates the ability to move fluidly between business context and low-level systems implementation:

* **Workflow analysis & Requirements translation:** Mapping human workflows to technical state machines.
* **System decomposition & Event-driven integration:** Connecting external webhooks (WhatsApp, Facebook, Twilio, Meshulam) to resilient internal backends.
* **Edge & Runtime Security:** Combining Envoy/Wasm egress filtering, ASGI streaming memory bounds, and rootless Podman isolation.
* **Empirical Verification:** Validating architectural claims through staggered load testing (`wrk`), container inspection, and adversarial payload testing (`HTTP 413` / `HTTP 400` boundary verification).

---

## 14. Current Status

### Implemented

* **FastAPI Backend & Routing:** Modular routers (`auth`, `leads`, `partners`, `phones`, `provisioning`, `sessions`, `storage`, `system`, `settings`, `benchmark`), billing (`checkout`, `invoices`), and multi-provider webhooks (`whatsapp`, `facebook`, `twilio`, `meshulam`, `campaign`, `marketing`).
* **Next.js Frontend Container:** Deployed and routed via Envoy (`leadflow-frontend`).
* **ASGI DoS & Memory Protection:** `RequestBodyLimitMiddleware` enforcing streaming byte limits (1 MB JSON / 26 MB multipart) and 64-level JSON depth bounds.
* **Envoy Proxy + Rust/Wasm Egress Filter:** `data_hop_firewall` (`proxy-wasm`) performing header-triggered (`x-data-ttl: 1`) top-level JSON PII redaction, verified by automated `wrk` latency benchmarks.
* **Hardened Rootless Infrastructure:** Rootless Podman Quadlet systemd services with `no-new-privileges`, non-root users, and Cloudflare Zero Trust FIDO2 SSH access.
* **CI/CD DevSecOps Pipeline:** Automated GitHub Actions enforcing `ruff`, `pip-audit`, Alembic checks, and Trivy scans.

### In Progress [In Development]

* Recursive JSON traversal and unstructured text regex scrubbing inside the Rust/Wasm Envoy filter.
* Native C++ high-performance audio processing engine (`cpp-transcription-engine`) utilizing shared memory and IPC.

### Designed / Roadmap

* Formal state-machine engine for automated multi-day lead follow-up and contradictory report resolution.
* Automated PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`) policies with non-owner application DB roles and cross-tenant isolation integration tests.
* Automated background workers for 24-hour privacy compliance data purging.
