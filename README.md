# MyLeads AI (LeadFlow) — Secure AI Platform Architecture

**Engineering case study covering:**
- Product engineering & workflow design
- Secure distributed systems & edge proxy filtering (Envoy + Rust/Wasm)
- Linux-based deployment (Rootless Podman & Systemd Quadlets)
- AI workflows & dynamic RAG
- Runtime isolation & ASGI DoS mitigation
- Empirical performance benchmarking & production reliability

*Last Engineering Review: October 2026*

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