# MyLeads AI — Secure AI Platform Architecture

**Engineering case study covering:**
- Secure distributed systems
- Linux-based deployment
- AI workflows
- Runtime isolation
- Production reliability

*Last Engineering Review: March 13, 2026*

---

## 1. System Engineering Overview

MyLeads AI was designed as a production-grade AI platform, with an emphasis on secure architecture, reliability, and runtime behavior. 

The system combines:
- Backend API services
- AI inference workflows
- Event-driven processing
- Linux container runtime
- Secure networking boundaries
- Automated deployment pipelines

The architecture follows a **bottom-up engineering approach**: from operating system resources, memory, and processes, up through application services, to cloud infrastructure.

---

## 2. High-Level Architecture

```text
User / Web Client
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
Database (PostgreSQL / SQLite)
 |
Future C++ Engine (High-Performance Audio/AI)
 |
Linux Runtime (Rootless Podman / Cgroups)

```

### 2.1 Project Repository Structure

The repository is structured as a distributed micro-ecosystem rather than a single monolith:

```text
MyLeads-AI/
├── backend/                     # FastAPI core, API routing, Business logic
├── frontend/                    # Next.js UI, SSR, React
├── infrastructure/              # CI/CD, Container definitions, Cloudflare routing
├── security/
│   └── envoy-wasm-rust/         # Real-time DLP Proxy written in Rust
└── systems/
    └── cpp-transcription-engine/# (In-Progress) C++ High-Performance node
        ├── shared-memory/
        ├── ipc/
        ├── benchmarks/
        └── profiling/

```

---

## 3. Production Configuration

Secrets and environment variables are strictly decoupled from source control.
Credentials are managed using:

* **AWS Systems Manager (SSM) Parameter Store**
* **AWS KMS** encryption for runtime decryption
* **GitHub Actions Secrets** (for CI/CD pipelines)

*No credentials, internal IPs, or environment structures are stored in public repositories. (For full variable mapping, authorized personnel refer to `docs/internal/production-config.md`).*

---

## 4. Security & Runtime Architecture

* **WASM DLP Firewall:** A custom Rust-compiled WebAssembly filter runs directly inside the Envoy proxy to redact sensitive credentials in real-time.
* **Global Exception Handler (The "Airbag"):** Intercepts `500 Internal Server Errors`, prevents Stack Trace leakage to the client, and instantly fires a detailed HTML crash report out-of-band to the `ADMIN_EMAIL`.
* **Rate Limiting & Anti-Spam:** Cloudflare-aware Rate Limiting (`CF-Connecting-IP`) deployed on Auth endpoints to prevent Global DoS loops on the reverse proxy.
* **Audit Logging:** Database-backed tracking of sensitive user actions via `audit_service` for non-repudiation.

---

## 5. Systems Engineering Roadmap (Performance & Low-Level)

Future optimization layers target system-level bottlenecks. As AI workloads (like Whisper audio transcription) become heavier, high-level Python processes face memory and CPU limitations.

### High-Performance Processing Engine (In Development)

A planned **C++ processing layer** designed to take over compute-intensive workloads:

* **Linux System Programming:** Direct interaction with kernel primitives.
* **`mmap` Based Shared Memory:** Preventing redundant memory copies between API gateways and workers.
* **IPC Communication:** Fast message passing between distributed system components.
* **Worker Pool Architecture:** Multithreading with Thread Affinity / CPU Pinning.
* **Memory Optimization:** Custom memory allocators to prevent OS heap fragmentation.
* **Zero-Copy Data Pipelines:** For real-time audio streaming.

*The goal is to move compute-intensive workloads out of high-level Python services into optimized native components.*

---

## 6. Database Schema & State Management

Database changes are strictly managed via **Alembic Migrations**. In the CI/CD pipeline, `alembic check` is executed as a strict gating mechanism to prevent `CrashLoopBackOff` in production caused by unsynced database schemas.

**Key Architectural State Tables:**

* **`leads`:** Inbound targets. Protected by `idempotency_key` to silently absorb duplicate requests and prevent Retry Storms.
* **`webhook_dlq` (Dead Letter Queue):** Stores failed incoming webhooks to ensure 0% data loss during internal API outages or transient network failures.
* **`sessions`:** Stores metadata for uploaded audio files transcribed via local models.

---

## 7. Deployment, CI/CD & Reliability

The system uses a Zero-Downtime update mechanism via **GitHub Actions -> SSH Tunnel -> AWS ECR -> Podman Systemd**.

### Out-of-Band Management (Unified CLI)

For maximum security, administrative mutations (e.g., approving agency partners) are strictly disabled in the web UI. They are executed via a unified CLI script (`manage_cli.py`) inside the isolated Linux container runtime.

```bash
# View system stats and memory usage
podman exec -it leadflow-backend python manage_cli.py stats

# Agency / Platform Management
podman exec -it leadflow-backend python manage_cli.py assign-client --client "coach@gym.com"

```

### Graceful Shutdown

The application lifecycle binds to `SIGTERM` signals, ensuring active database transactions and AI inferences finish cleanly before the Linux container scheduler drops the process.

---

## 8. QA Testing Architecture

The testing suite has been modularized for faster execution and better CI/CD integration, ensuring resilience before deployment.

```bash
# 1. Internal Logic & Security Tests: 
pytest tests/test_main.py -v

# 2. Macro Flow (Core Pipeline Validation): 
python3 tests/qa_macro.py --prod

# 3. Micro Flow (Advanced Feature Validation): 
python3 tests/qa_micro.py --prod

# 4. AI Agent Function Calling (Direct Engine QA): 
python3 tests/qa_agents.py --api-key="[INJECTED_AT_RUNTIME]"
