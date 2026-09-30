# MyLeads AI — Secure AI Platform Architecture

**Engineering case study covering:**
- Product engineering & workflow design
- Secure distributed systems
- Linux-based deployment
- AI workflows
- Runtime isolation
- Production reliability

*Last Engineering Review: September 2026*

---

## 1. Project Overview & Product Thesis

MyLeads AI is a production-oriented AI platform designed with a strict emphasis on secure architecture, reliability, and runtime behavior. However, the system did not begin as an exploration of LLMs or AI technology for its own sake. It originated from a concrete business problem.

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
*Status: Partially Implemented / Core Routing Active, Follow-up logic in Roadmap*

This workflow represents the core lead-management flow. It is not simply "WhatsApp automation." It requires persistent lead state, routing logic, asynchronous waiting, and human escalation.

**The Operational Workflow:**
```text
Incoming WhatsApp inquiry
   ↓
Collect name & city
   ↓
Identify appropriate coach based on location
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

*Status: Designed / Historical Prototype*

A secondary workflow was analyzed regarding post-session administrative work. The operational problem: The professional should spend time coaching rather than manually processing recordings, transcripts, summaries, and documents.

**The Operational Workflow:**

```text
Audio recording from phone
   ↓
Upload to cloud storage
   ↓
Trigger scheduled processing pipeline
   ↓
Transcription (Whisper)
   ↓
Structured LLM summarization
   ↓
PDF generation
   ↓
Delivery to client/coach
   ↓
Archive original recording
   ↓
Prevent duplicate processing

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
| **Sensitive customer data crosses services** | Strict access controls | **Security boundaries / Envoy DLP / Secrets Management** |
| **Business owner shouldn't manage infra** | Managed, predictable deployment | **Linux + Rootless Podman + CI/CD** |

---

## 5. High-Level System Architecture

```text
User / WhatsApp Client (Meta API)
 |
Cloudflare Zero Trust (Network Boundary)
 |
Envoy Proxy (Rust/WASM DLP Filter)
 |
FastAPI Backend (API Gateway & Core Logic)
 |
+-----------------------------------+
| Asynchronous Workers (Redis/DLQ)  |
+-----------------------------------+
 |
Database (PostgreSQL / SQLite) & JSON Profiles
 |
Future C++ Engine (High-Performance Audio/AI) [In Development]
 |
Linux Runtime (Rootless Podman / Hetzner Bare Metal)

```

---

## 6. Security & Runtime Architecture

Because customer conversations contain sensitive information, security boundaries are treated as a primary product requirement rather than an infrastructure afterthought.

* **Cloudflare Zero Trust & Tunnels:** Eliminates direct public SSH exposure (closing inbound port 22 on bare metal) and mandates hardware security keys (FIDO2/WebAuthn) for administrative SSH access.
* **WASM DLP Filter:** A custom Rust-compiled WebAssembly filter runs directly inside the Envoy proxy to execute high-performance, inline data loss prevention (redacting credentials) without rewriting core application code.
* **Local Network Binding:** Redis and internal services bind exclusively to local interfaces (`127.0.0.1:6379`) to resolve external vulnerability scans.
* **Global Exception Handler:** Intercepts `500 Internal Server Errors`, preventing Stack Trace leakage and dispatching HTML crash reports out-of-band.
* **Audit Logging:** Database-backed tracking providing traceability and accountability for sensitive actions.

---

## 7. Multi-Tenant Architecture & State Management

* **Dynamic RAG & Profile Loader:** An asynchronous profile loader injects tenant-specific business context, catalogs, and privacy guardrails into Gemini Flash. It features a silent fallback mechanism for missing files.
* **Database Migrations:** Managed via **Alembic**. `alembic check` is enforced in CI/CD gating to prevent production `CrashLoopBackOff` due to schema mismatches.
* **Transaction Safety:** Application-level state handling mitigates SQLAlchemy object-detachment issues by caching system prompts before transaction commits, ensuring stable state transitions for webhooks.

---

## 8. Deployment, CI/CD & Reliability

The platform was initially developed and deployed on AWS before evolving toward a more cost-efficient bare-metal deployment model on Hetzner.

Current production-oriented deployment utilizes a **Zero-Trust Pull-Based CD** architecture: **GitHub Actions (CI/Build) → GHCR → Secure Local Webhook (CD Pull) → Podman Systemd** on a Hetzner bare-metal server.

* **RCE Prevention & Zero-Trust Deployments:** To completely eliminate Remote Code Execution (RCE) risks associated with Self-Hosted Runners or exposed SSH ports, the production server accepts no direct pipeline commands. Deployments are triggered via a lightweight, cryptographically signed webhook (HMAC). Upon validation, the server executes a strictly hardcoded local script (`podman compose pull && podman compose up -d`), effectively air-gapping the runtime from remote CI/CD vulnerabilities.
* **Out-of-Band Management (`manage_cli.py`):** Administrative mutations are restricted from the web UI and executed through an isolated container CLI script.
* **Graceful Shutdown:** Services handle `SIGTERM` signals to allow active database transactions and in-flight processing to complete safely before container termination.

---

## 9. Systems Engineering Roadmap (Performance & Low-Level)

### High-Performance Processing Engine [In Development]

For selected CPU- and memory-intensive processing paths, a native C++ layer is being investigated to offload tasks:

* Linux systems programming using primitives such as `mmap`, IPC, process/thread management, and CPU affinity.
* Memory-allocation strategies for sustained high-throughput workloads.
* Zero-copy audio streaming pipelines to eliminate memory copy overhead between the API gateway and workers.

---

## 10. QA Testing Architecture

```bash
# 1. Internal Logic & Security Tests: 
pytest tests/test_main.py -v

# 2. Macro Flow (Core Pipeline Validation): 
python3 tests/qa_macro.py --prod

# 3. Micro Flow (Advanced Feature Validation): 
python3 tests/qa_micro.py --prod

# 4. AI Agent Function Calling (Direct Engine QA): 
python3 tests/qa_agents.py --api-key="[INJECTED_AT_RUNTIME]"

```

* **E2E Webhook Integration:** Simulated inbound customer messages validate proper tenant-specific RAG replies, routing logic, and state transitions via Envoy.

---

## 11. Engineering Mindset

The recurring design principle governing this repository is:
**Observe → Model → Specify → Build → Validate → Operate → Iterate**

Start with the operational problem, model the workflow, identify failure modes, derive technical requirements, and *then* select the implementation.

---

## 12. Applied Engineering Perspective

This project demonstrates the ability to move fluidly between business context and technical implementation. Core engineering behaviors exhibited in this architecture include:

* **Workflow analysis & Requirements translation:** Mapping human workflows to technical state machines.
* **System decomposition & Event-driven integration:** Connecting external APIs (WhatsApp) to resilient internal backends.
* **Stateful business processes:** Handling exceptions, asynchronous delays, and human escalation paths.
* **Production & Reliability engineering:** Building for idempotency, utilizing DLQs, and ensuring graceful degradation.
* **Security engineering:** Designing robust data boundaries, encryption, and operational access controls.

---

## 13. Current Status

### Implemented

* FastAPI core backend, routing, structured database models, and Alembic migrations.
* Dynamic RAG profile loader and Gemini Flash WhatsApp webhook integration.
* Secure infrastructure deployment on Hetzner with rootless Podman and Envoy proxy.
* Cloudflare Zero Trust networking, Tunnels, and FIDO2-authenticated SSH access.
* Rust/WASM DLP filtering and global exception handling.
* Modularized QA testing suites.

### In Progress [In Development]

* Native C++ high-performance processing engine (`cpp-transcription-engine`), shared-memory structures, and IPC mechanisms.

### Designed / Roadmap

* Formal state-machine engine for automated multi-day lead follow-up and verification.
* Frontend tenant settings UI dashboard and chat simulator.
* Production Meta WhatsApp Business API token integration (currently utilizing mock/sandbox testing).
* Billing and subscription plan enforcement.
* Production audio transcription pipeline.
* Automated Celery background workers for 24-hour privacy compliance data deletion.
