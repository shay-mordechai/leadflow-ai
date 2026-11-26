# LeadFlow AI — Security Architecture & Remediated Vulnerabilities

This document catalogs the security architecture of **LeadFlow AI**, explicitly distinguishing **original architectural threat-modeling designs** from **application-level vulnerability remediations** and **zero-trust infrastructure baselines**.

---

## 1. Original Architectural Threat Modeling & Custom Defenses

These four architectural mechanisms were designed specifically to address structural trust-boundary, exfiltration, privilege-escalation, and distributed-concurrency risks in multi-tenant AI messaging systems:

### 1.1 Zero-Trust Outbound DLP Proxy (`Envoy + Rust/Wasm`)
* **Threat Vector (Egress Exfiltration):** Indirect prompt injection or LLM hallucination can trick an AI agent into leaking sensitive customer PII, internal prompts, or API credentials in outbound responses—bypassing traditional ingress-only WAFs.
* **Architectural Solution:** Deployed a custom `proxy-wasm` filter written in Rust (`data-gate/src/lib.rs`) inside Envoy to inspect outbound HTTP response bodies before they leave the cluster, redacting **41 PII and secret patterns** while enforcing a strict **10 MiB** Wasm buffer inspection ceiling (`MAX_WASM_BUFFER_SIZE`) to prevent edge OOM DoS.
* **Performance Profile:** ~15 ms P50 latency overhead (~11% throughput impact).
* **Verification:** `data-gate/` Wasm build & Envoy integration verification pipeline.

### 1.2 Dual Meta Bot Blast-Radius & Credential Isolation
* **Threat Vector (Cross-Channel Compromise & Policy Blast Radius):** Running customer-facing conversational flows and internal/marketing outreach bots under a single Meta App/Phone token couples their attack surfaces; token exposure, webhook abuse, or Meta rate-limit/policy throttling on one flow would disrupt the entire platform.
* **Architectural Solution:** Segregated the external customer-support bot and internal/marketing advisor bot into isolated webhook endpoints, credentials, and routing lifecycles so each channel operates within a strict blast radius.
* **Verification:** `src/routers/webhooks/whatsapp.py`, `tests/test_whatsapp_pipeline.py`.

### 1.3 Least-Privilege Celery Worker Split (`Read-Only` vs. `Transactional`)
* **Threat Vector (Background Privilege Escalation):** Granting analytical or marketing background workers full read/write database credentials allows a compromised task or poisoned RAG context to mutate tenant records, alter billing tiers, or bypass tenant boundaries.
* **Architectural Solution:** Split background workloads between a restricted PostgreSQL **read-only** database role (used by analytical/marketing digest workers) and transactional write workers, ensuring background intelligence tasks cannot modify production state.
* **Verification:** `tests/security/test_marketing_advisor_worker.py` (`test_marketing_advisor_least_privilege_reader_isolation`), `tests/security/test_postgres_rls_and_worker_split.py` (`test_least_privilege_reader_permissions`).

### 1.4 Decoupled Async DB Persistence via Atomic Redis State & Idempotency
* **Threat Vector (Distributed TOCTOU Race Conditions & DB Lock Contention):** Concurrent webhook retries and parallel async workers checking and decrementing message quotas directly in PostgreSQL create Time-of-Check to Time-of-Use (TOCTOU) race conditions, quota bypasses, and row-lock contention.
* **Architectural Solution:** Decoupled real-time concurrency gating from asynchronous PostgreSQL persistence using atomic Redis primitives (`incrby` / `decrby` quota reservations with compensating rollbacks on inference failure, plus `SET NX` webhook deduplication locks).
* **Verification:** `src/services/llm_router.py`, `tests/security/test_database_concurrency.py`, `tests/security/test_webhook_idempotency.py`.

---

## 2. Remediated Application & Protocol Vulnerabilities

In addition to the core architectural designs above, the following concrete vulnerabilities were identified and mitigated across the codebase:

| Vulnerability / Exploit Class | Root Cause Mitigated | Remediation & Code Location | Verification Suite |
| :--- | :--- | :--- | :--- |
| **Cross-Tenant RLS Context Leak / IDOR** | Missing `WHERE` clause or pooled async DB connections retaining a prior tenant's `app.current_tenant_id` session variable | Enforced `FORCE ROW LEVEL SECURITY` across all tenant tables (`alembic/versions/20261122_*`), scoped `pgvector` similarity queries, and guaranteed `app.current_tenant_id` cleanup in `try...finally` blocks (`src/database/session.py`) | `tests/security/test_postgres_rls_and_worker_split.py` |
| **Asymmetric Streaming JSON Recursion DoS** | Deeply nested JSON payloads or oversized chunked bodies exhausting ASGI worker memory or parser stack frames | Implemented `RequestBodyLimitMiddleware` (`src/middleware/request_limits.py`) enforcing 1 MiB / 26 MiB payload caps and real-time >64-level JSON nesting depth rejection (HTTP 400) | `tests/security/test_application_defenses.py` |
| **LLM Prompt Injection & RAG Poisoning** | Untrusted customer messages or retrieved knowledge chunks overriding system instructions | Escaped untrusted inputs (`_xml_safe`) and isolated instructions, retrieved context, and user messages inside strict XML tags (`<system>`, `<retrieved_knowledge>`, `<latest_user_message>`) in `src/services/ai/prompt_builder.py` | `tests/security/test_ai_llm_security.py` |
| **LLM Loop Exhaustion & Denial of Wallet (DoW)** | Unbounded conversational loops or oversized completions driving runaway API spend | Capped agent execution at 15 turns, 512 max output tokens, and a 7-second request timeout with atomic quota rollback (`src/services/ai/workflow_graph.py`, `src/services/llm_router.py`) | `tests/security/test_ai_llm_security.py` |
| **Webhook Signature Forgery & Replay** | Spoofed inbound Meta/Twilio/payment callbacks or replayed webhook payloads | Enforced constant-time HMAC-SHA256 validation (`X-Hub-Signature-256`), 5-minute timestamp replay windows, and Redis `SET NX` idempotency keys (`src/routers/webhooks/whatsapp.py`, `src/security/dependencies.py`) | `tests/security/test_webhook_hardening_audit.py`, `tests/security/test_sec_015_twilio_signature_validation.py` |
| **PDF Report Path Traversal (`CWE-22`)** | Unsanitized business/session names writing files outside the intended export directory | Normalized filenames via `os.path.basename` + strict character allowlisting confined to `storage/pdfs` (`src/services/media/pdf_maker.py`, `src/routers/sessions.py`) | `tests/security/test_sec_012_pdf_path_traversal.py` |

---

## 3. Infrastructure, Identity & DevSecOps Baseline

* **Zero-Trust Network Ingress:** All origin ports on the Hetzner VPS are closed to public traffic; ingress is routed exclusively through authenticated **Cloudflare Tunnel** connectors, and CD webhooks require HMAC-SHA256 + timestamp signatures.
* **Container Hardening:** Backend, worker, proxy, and database workloads execute as **rootless Podman** systemd Quadlets with read-only mounts where applicable.
* **Session & Token Revocation:** JWT authentication (`src/security/dependencies.py`) enforces signature verification, Redis `jti` blocklists, and per-user `token_version` invalidation.
* **Structured Log PII Redaction:** Phone numbers, emails, and message contents are masked via `src/security/pii.py` prior to structured log and AI trace emission.
* **Automated CI/CD Security Gates:** Releases are gated by Ruff static analysis, Alembic single-head migration verification, `pip-audit` dependency scanning, Gitleaks secret detection, Trivy container scanning, and 163 automated tests (`.github/workflows/production.yml`).
