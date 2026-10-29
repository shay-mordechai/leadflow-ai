# SECURITY.md — MyLeads AI (LeadFlow)

**Classification:** Public (Post-Remediation)
**Last Audit:** October 2026
**Architecture:** Zero Trust · Defense in Depth · OWASP Top 10

---

## Overview

This document maps the security layers built into MyLeads AI — an AI-powered SaaS lead management platform. Security was designed as part of the architecture from day one, not bolted on as an afterthought.

Every finding in this document is based on self-directed code review, active threat modeling, container runtime inspection, and hands-on vulnerability research — including responsible disclosure of security flaws in external platforms.

---

## 1. Network Architecture & Container Hardening — "Ghost Server"

**Threat:** Automated bot scanning, direct IP DDoS, port enumeration, and container privilege escalation.

**Implementation:**
- **Zero Inbound Attack Surface:** The Hetzner Cloud server blocks all public inbound ports (`0.0.0.0/0` fully closed). The server does not listen directly to the public internet.
- **Cloudflare Zero Trust Tunnel:** All ingress traffic is routed exclusively through an outbound-only encrypted connection initiated by the `cloudflared` daemon, neutralizing direct IP scanning and network-layer DDoS.
- **Hardware-Key SSH:** Administrative SSH access requires FIDO2/WebAuthn hardware-key authentication via **Cloudflare Identity-Aware Proxy (IAP)**.
- **Rootless Podman & Systemd Quadlets:** The entire stack executes under **Rootless Podman** (`rootless=true`) managed via user-level Systemd Quadlets (`systemctl --user`), eliminating root daemon attack surfaces.
- **Container Runtime Hardening (Verified via `podman inspect`):**
  - **No New Privileges:** Every container (`leadflow-backend`, `leadflow-frontend`, `leadflow-data-gate`, `leadflow-db`, `leadflow-redis`) enforces `sec_opt=[no-new-privileges]`, blocking setuid/setgid privilege escalation inside the container namespace.
  - **Unprivileged UIDs:** Application workloads run as non-root users (`user=leadflowuser` in Backend, `user=nextjs` in Frontend) with `privileged=false`.
  - **Resource & Cgroup Bounds:** The backend enforces a hard kernel memory ceiling of `1.5 GiB` (`mem=1610612736`) to contain memory-leak or resource-exhaustion blast radii.
  - **Loopback & Bridge Isolation:** Internal services bind exclusively to `127.0.0.1` (`PostgreSQL` on `5432`, `Redis` on `6379`) and communicate over an isolated bridge network (`leadflow-network`) with `STRICT_DNS` and `V4_ONLY` resolution.

---

## 2. Secrets Management — In-Memory Bootstrapping (SSRF/LFI Mitigation)

**Threat:** An attacker exploiting SSRF or LFI targets `.env` files on disk to exfiltrate API keys and database credentials.

**Implementation:**
- Static `.env` files **do not exist** in the production deployment. At server startup, `src/config.py` queries **AWS SSM Parameter Store** directly via `boto3` and loads all secrets exclusively into process memory (never written to disk).
- Zero secret artifacts on the filesystem reduce post-exploitation credential harvesting to near zero.
- **IMDSv2** (Token-based Metadata Service) is enforced to block unauthenticated SSRF token theft against cloud metadata endpoints.

---

## 3. MFA — Single-Use OTP & Replay Attack Prevention

**Threat:** OTP reuse within the validity window (Replay Attack); weak PRNG OTP generation (CWE-338).

**Implementation:**

Atomic operation sequence:
1. **Charge the payment:** User submits the OTP.
2. **Lock the register:** On match, the OTP is **immediately deleted from the DB and `db.commit()` is called** before any subsequent logic.
3. **Issue the receipt:** Only after the OTP deletion transaction commits is the JWT generated and returned.

- **Cryptographic Correctness:** OTPs are generated using Python's `secrets` module (OS CSPRNG) rather than the predictable `random` module (CWE-338).
- **Race-Condition Elimination:** Delete-before-issue closes the TOCTOU (Time-of-Check to Time-of-Use) window between token issuance and OTP invalidation.
- **Token Versioning (`token_version`):** Each user record maintains an integer `token_version` counter. On password reset or security events, this counter increments, immediately invalidating all previously issued JWTs for that user.
- **Redis JWT Revocation:** Logged-out or revoked tokens (`jti`) are written to a Redis blocklist until their natural `exp` timestamp expires.

---

## 4. Envoy Rust/Wasm DLP Firewall — Egress PII Redaction & Error Masking (CWE-209 / CWE-359)

**Threat:** Accidental leakage of sensitive PII in API responses or stack traces exposing internal file paths, library versions, and logic in `5xx` error responses.

**Implementation (`data-gate/src/lib.rs`):**
- A custom **WebAssembly (Wasm)** filter (`data_hop_firewall.wasm`) written in **Rust** (`proxy-wasm` v0.2.4) runs inline inside the **Envoy Proxy** (`v1.28`) container on port `10000`.
- **Header-Triggered Structural PII Redaction:**
  - When upstream FastAPI handlers set the internal response header `X-Data-TTL: 1` (normalized to `x-data-ttl: 1` by Envoy), `on_http_response_headers` activates redaction mode for that stream and strips both `x-data-ttl` and `content-length` from the outbound headers.
  - In `on_http_response_body`, the filter parses the JSON response buffer and scrubs designated top-level PII keys (`phone`, `email`, `name`), replacing their values with `"[REDACTED]"` before bytes leave the network edge.
- **Fail-Closed Error Masking:** Unhandled `5xx` upstream responses are intercepted out-of-process; raw stack traces are stripped and replaced with a generic JSON payload: `{"error": "Internal Security Proxy Intervention"}`.
- **Empirical Latency Verification (`wrk`):** Staggered load testing (`tests/benchmarks/run_latency_bench.sh`) across 2.1 KB JSON payloads confirmed that the Rust/Wasm filter introduces negligible latency overhead (bounded within normal run-to-run proxy jitter of `< 3 ms` median delta) while Envoy's connection pooling reduces tail `P99` latency compared to direct backend access.
- **Current Scope & Defense-in-Depth Roadmap:** The current Wasm filter performs deterministic, schema-based top-level key redaction (`serde_json::Value` map lookup). To protect unstructured conversational strings (e.g., phone numbers written inside a free-text `note` field) and deeply nested sub-objects, recursive JSON AST traversal and non-backtracking regex scrubbing are tracked in the engineering roadmap.

**Why Envoy Wasm instead of eBPF?** eBPF is designed for kernel-level observability and packet filtering, but the eBPF verifier prohibits arbitrary dynamic mutation and length-changing re-serialization of Layer-7 HTTP payloads. Envoy + `proxy-wasm` provides memory-safe, sandboxed Layer-7 stream manipulation.

---

## 5. Access Control & IDOR Prevention

**Threat:** Attacker modifies `user_id` or `tenant_id` in a URL or JSON body to access another tenant's data (Insecure Direct Object Reference).

**Implementation (`src/security/dependencies.py`):**
- The API never trusts client-supplied identity parameters. `get_current_user` validates the JWT signature, verifies `jti` (revocation check), `token_version`, and `exp`, extracts the authenticated identity from the cryptographic claims, and loads the user record from PostgreSQL.
- Protected routers enforce this dependency at the FastAPI routing layer prior to executing business logic.

```python
# src/security/dependencies.py
async def get_current_user(token: str = Depends(get_token), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if (
            not isinstance(payload.get("jti"), str)
            or not payload["jti"]
            or not isinstance(payload.get("token_version"), int)
            or payload["token_version"] < 0
            or not isinstance(payload.get("exp"), int)
        ):
            raise credentials_exception
        await ensure_token_not_revoked(token)
        # Support both 'email' and 'sub' claims for flexibility
        email: str = payload.get("email") or payload.get("sub")
        if email is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None or payload["token_version"] != (user.token_version or 0):
        raise credentials_exception
    return user

```

---

## 6. PII Encryption at Rest

**Threat:** A database snapshot compromise exposes customer phone numbers and AI conversation transcripts.

**Implementation (`src/security/encryption.py`):**

* Application-layer symmetric encryption using **Fernet (AES-128-CBC + HMAC-SHA256)** via the `cryptography` library.
* **Lazy Initialization:** The cipher is instantiated only after `ENCRYPTION_KEY` is fetched into memory, preventing cryptographic operations with uninitialized keys.
* **Fail-Safe Decryption:** Decryption errors (e.g., during key rotation or corrupted ciphertext) log a structured security event and return `"[DECRYPTION_FAILED]"` rather than crashing the worker process.

```python
def decrypt(self, ciphertext: str) -> Optional[str]:
    try:
        return self._get_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Decryption failed. Key might be rotated or invalid: {e}")
        return "[DECRYPTION_FAILED]"

```

---

## 7. Out-of-Band Management & CLI-Only Administration

**Threat:** Exposed web administrative panels serve as high-value targets for privilege escalation and credential stuffing.

**Implementation:**

* Administrative mutations are **disabled in the public web UI** and restricted to an isolated CLI tool (`manage_cli.py`) executable only via hardware-authenticated SSH.
* **Global Exception Handler:** Intercepts unhandled `500 Internal Server Errors`, returns a sanitized response to the client, and dispatches detailed crash diagnostics out-of-band to `ADMIN_EMAIL`.

---

## 8. Proxy-Aware Rate Limiting (DoS & Brute Force Prevention)

**Threat:** Standard rate limiters behind a reverse proxy or tunnel throttle the proxy's loopback IP (`127.0.0.1`), causing a self-inflicted Global DoS for all legitimate users.

**Implementation (`src/security/rate_limiter.py`):**

* Custom `get_real_ip` resolver extracts the `CF-Connecting-IP` header injected by Cloudflare's authenticated edge, ensuring rate limits track the actual client IP rather than the Envoy or `cloudflared` loopback interface.

```python
def get_real_ip(request: Request):
    """
    Extracts the authenticated client IP provided by Cloudflare.
    Prevents Global DoS by ensuring the limiter tracks the actual attacker,
    not the reverse proxy's loopback address.
    """
    return request.headers.get("CF-Connecting-IP", get_remote_address(request))

```

---

## 9. PDF Generation — SSRF & Path Traversal Mitigation

**Threat:** HTML-to-PDF engines (e.g., `wkhtmltopdf`) parse `<script>`, `<iframe>`, or `<img>` tags and execute server-side network requests, enabling `file:///etc/passwd` LFI or cloud metadata SSRF.

**Implementation:**

* Uses **`fpdf2`** (`>=2.8.8`), which constructs PDF primitives directly from plain text strings without an HTML/DOM parser or network client. SSRF via PDF rendering is eliminated by design.

**Remediation: Path Traversal (SEC-012)**

* **Description:** Previously, `os.path.join(output_dir, filename)` was called without strict filename canonicalization.
* **Implemented Fix:**
1. **Filename Sanitization:** Strips directory components via `os.path.basename`, replaces non-alphanumeric characters (except `_` and `-`) with underscores via `re.sub`, and enforces a `.pdf` suffix.
2. **Canonical Path Verification:** Resolves the absolute target path and verifies it resides strictly inside `storage/pdfs`. Any traversal attempt falls back to a cryptographically random UUID filename.



---

## 10. Audit Logging & Security Monitoring (OWASP A09)

**Threat:** Absence of tamper-evident logging allows attackers to probe or pivot undetected (OWASP A09:2021).

**Implementation (`src/security/audit.py`):**

* **Dual-Write Pattern:** Every sensitive event is persisted to the `AuditLog` database table **and** emitted via `python-json-logger` (`JsonFormatter`) as a structured JSON log line with `request_id` correlation.
* **Fail-Safe Execution:** Database write exceptions fall back to `logger.error` without raising, preventing attackers from causing an Application DoS via audit storage exhaustion.
* **Log Injection Sanitization (CWE-117):** User-supplied strings are sanitized and JSON-encoded to prevent newline/CRLF log forging.

```python
@staticmethod
def log(db: Session, user_id: str, action: str, details: dict = None):
    try:
        db.add(AuditLog(user_id=user_id, action=action, details=details))
        db.commit()
        logger.info(f"AUDIT_EVENT: {action}", extra={"user_id": user_id, "details": details})
    except Exception as e:
        logger.error(f"Failed to save Audit Log: {e}")
        # Do not re-raise — audit failure must never crash the API

```

---

## 11. Webhook Spoofing Prevention (Twilio HMAC-SHA1)

**Threat:** Unauthenticated form submissions to `src/routers/webhooks/twilio.py` forging the `From` parameter to impersonate the business owner.

**Remediation: Twilio Webhook Signature Validation (SEC-015)**

1. **Cryptographic Validation:** The `validate_twilio_signature` dependency extracts `X-Twilio-Signature` and validates it against `TWILIO_AUTH_TOKEN`.
2. **Constant-Time HMAC-SHA1:** Reconstructs the canonical payload (full URL + sorted POST parameters), computes the HMAC-SHA1 digest, and verifies it using `hmac.compare_digest` to prevent timing side-channel attacks.
3. **Fail-Closed Principle:** Requests with missing or invalid signatures are immediately rejected with `HTTP 403 Forbidden`.

---

## 12. CI/CD Pipeline RCE Prevention & Supply-Chain Security

**Threat:** A compromised GitHub Actions runner or malicious third-party package executes arbitrary commands on the production server (RCE) or introduces vulnerable dependencies into container images.

**Implementation:**

* **Pull-Based CD (Air-Gapped Runtime):** The production server does not expose SSH or deployment sockets to GitHub Actions. Instead, CI publishes verified images to `ghcr.io`, and a lightweight HMAC-SHA256 webhook triggers a hardcoded local pull and Systemd service restart (`podman pull && systemctl --user restart`).
* **Mandatory CI/CD Security & Quality Gates (`exit-code: 1`):**
* **Code Quality & Linting:** `ruff check src tests` and `ruff format --check src tests`.
* **Secret Scanning:** `Gitleaks` scans commit history for accidental credential commits.
* **Python SAST:** `Bandit` scans application source code for insecure patterns.
* **Supply-Chain SCA (`pip-audit`):** Audits `requirements.txt` against the Python Advisory Database on every build, enforcing patched versions across transitive dependencies (including `aiohttp`, `certifi>=2026.10.19`, `filelock>=4.2.1`, and `fpdf2>=2.8.8`).
* **Container Vulnerability Scanning:** `Trivy` scans built container images for OS and library CVEs before registry push.



---

## 13. Meta WhatsApp Webhook Security (HMAC-SHA256 & Replay Defense)

**Threat:** Forged webhook payloads or replayed legitimate captures used to manipulate AI state or exhaust LLM quotas.

**Implementation:**

* **HMAC-SHA256 Verification:** Validates the raw request body against `X-Hub-Signature-256` using `WHATSAPP_APP_SECRET` and constant-time digest comparison.
* **5-Minute Replay Window:** Extracts the event timestamp and drops any webhook payload older than 300 seconds, neutralizing capture-and-replay attacks.

---

## 14. AI Prompt Injection & Jailbreak Defense (Hierarchical Context Isolation)

**Threat:** Untrusted WhatsApp messages attempting "Ignore previous instructions" attacks to leak system prompts or bypass tenant business boundaries.

**Implementation (`src/services/ai/prompt_builder.py`):**

* **XML Boundary Delimiters:** Untrusted user inputs are strictly encapsulated within XML tags (`<system>`, `<latest_user_message>`) with explicit system instructions treating tag contents as inert data.
* **Volatility Ordering:** Immutable security guardrails and tenant rules are positioned at the top of the context window, isolating dynamic user input at the bottom.
* **Schema-Constrained Output:** `google-genai` responses are strictly bound to the `WhatsAppAgentResponse` Pydantic schema, preventing free-text policy bypasses.
* **15-Turn Conversation Cap:** Sessions are bounded to a maximum of 15 turns to prevent multi-turn context manipulation and bound token consumption.

---

## 15. Campaign Lead API Security (Sanitization & Atomic Idempotency)

**Threat:** External marketing integrations (Zapier/Make) submitting malformed payloads or duplicate retry bursts that exhaust billing quotas or trigger Meta WABA spam flags.

**Implementation (`src/routers/webhooks/campaign.py`):**

* **Tenant Key Authentication:** Requires a valid `X-Tenant-Key` header.
* **Strict Input Sanitization:** Phone numbers are validated against E.164 regex patterns, and free-text fields (`name`, `note`) are length-capped.
* **Atomic Redis Idempotency (`SET NX`):** Uses distributed Redis locks with a 24-hour TTL to guarantee single-execution semantics per lead and atomically reserve outbound messaging quotas.

---

## 16. Immutable Deployments & Off-Site State Correlation (Disaster Recovery)

**Threat:** Silent data corruption, host hardware failure, or Alembic schema drift causing post-deployment crash loops.

**Implementation:**

* **Zero-Egress Off-Site Backups:** `scripts/backup_to_r2.sh` streams compressed `pg_dump` snapshots directly to **Cloudflare R2** via S3-compatible APIs.
* **Image-to-Database State Correlation:** Backup artifacts embed the active Podman image digest (`db_backup_<UTC timestamp>_image_<sha256>.sql.gz`), ensuring backups can always be restored alongside the exact container binary that produced them.
* **Live Schema Sync Verification:** `/health/db-sync-status` compares `EXPECTED_DB_REVISION` and `CURRENT_IMAGE_SHA` against the live PostgreSQL `alembic_version` table, returning `HTTP 503` if schema drift is detected.

---

## 17. ASGI Streaming Limits, HTTP Hardening & Data Lifecycle Defenses

**Threat:** Memory exhaustion (OOM) via oversized or chunked payloads, CPU exhaustion via deeply nested JSON deserialization, and long-term PII retention exposure.

**Implementation:**

* **ASGI Streaming Body & JSON Depth Middleware (`src/middleware/request_limits.py`):**
* **Dual-Tier Payload Caps:** Enforces a strict **1 MiB** (`1,048,576` bytes) cap on standard HTTP requests and a **26 MiB** cap exclusively for `multipart/form-data` audio uploads on `/api/v1/sessions/upload/`.
* **Pre-Flight & Streaming Enforcement (Verified `HTTP 413`):** Validates `Content-Length` headers immediately (returning `HTTP 400` on negative/malformed values and `HTTP 413` when exceeding the limit) and wraps the ASGI `receive()` channel to count streamed bytes chunk-by-chunk, aborting oversized chunked transfers in real time before memory allocation completes.
* **Zero-Allocation JSON Nesting State Machine (64 Levels):** For `application/json` streams, the middleware inspects raw bytes on the fly—tracking string literals (`0x22`), escape characters (`0x5C`), and opening/closing brackets (`0x7B`, `0x5B`, `0x7D`, `0x5D`). If nesting exceeds **64 levels**, the request is immediately rejected with `HTTP 400 ("JSON nesting depth exceeds limit")` prior to invoking `json.loads()`.


* **Strict HTTP Security Response Headers:** Every backend response enforces:
* `Strict-Transport-Security: max-age=31536000; includeSubDomains`
* `Content-Security-Policy: default-src 'none'; frame-ancestors 'none';`
* `X-Content-Type-Options: nosniff`
* `X-Frame-Options: DENY`
* `X-XSS-Protection: 1; mode=block`
* `X-Request-ID: <UUIDv4>` (end-to-end request tracing)


* **Worker & Event-Loop Protection:**
* **Background Task Cap:** Bounded to 200 concurrent/pending background tasks to prevent queue memory exhaustion.
* **BCrypt Threadpool Offloading:** CPU-bound password hashing runs in a dedicated threadpool so the main asyncio event loop cannot be blocked during authentication bursts.


* **Audio SSRF & MIME Validation (`src/services/ai/whisper.py`):** Remote media URLs are validated against an explicit domain allow-list (blocking `file://` and internal IPs), and downloaded payloads are verified via `python-magic` MIME inspection before transcription.
* **90-Day GDPR Retention & Core Dump Disablement:** Scheduled retention tasks (`src/tasks/retention_tasks.py`) purge expired PII after 90 days, and production containers run with `--ulimit core=0` to prevent memory dumps from writing sensitive runtime state to disk.

---

### Defense-in-Depth Summary Table

| Security Layer | Mitigation Strategy |
| --- | --- |
| **1. Network & Container Runtime** | Cloudflare Tunnel, Zero Inbound Ports, Rootless Podman Quadlets, `no-new-privileges`, `1.5 GiB` Backend Memory Cap |
| **2. Secrets Management** | AWS SSM In-Memory Bootstrapping, Zero `.env` on Disk, IMDSv2 Enforcement |
| **3. MFA & Replay Prevention** | Single-Use CSPRNG OTP (Delete-Before-Issue), `token_version` Counter, Redis `jti` Blocklist |
| **4. Envoy Rust/Wasm DLP Firewall** | Header-Triggered (`x-data-ttl: 1`) Egress JSON PII Redaction (`phone`, `email`, `name`) & `5xx` Error Masking |
| **5. Access Control & IDOR** | Cryptographic JWT Claim Resolution (`get_current_user`), Strict Version & Expiry Checks |
| **6. PII Encryption at Rest** | Fernet (AES-128-CBC + HMAC-SHA256) with Lazy Init & Fail-Safe Decryption |
| **7. Out-of-Band Management** | CLI-Only Admin (`manage_cli.py`), Global `500` Exception Masking, OOB Crash Alerts |
| **8. Proxy-Aware Rate Limiting** | Cloudflare `CF-Connecting-IP` Client Resolution |
| **9. PDF Generation** | `fpdf2` (`>=2.8.8`, Plain-Text Primitives Only), Regex Filename Sanitization, Canonical Path Verification |
| **10. Audit Logging** | Dual-Write (PostgreSQL + `JsonFormatter` Logs), CWE-117 Sanitization, Fail-Safe Execution |
| **11. Twilio Webhook Security** | Constant-Time HMAC-SHA1 `X-Twilio-Signature` Validation, Fail-Closed (`HTTP 403`) |
| **12. CI/CD & Supply-Chain Security** | Pull-Based CD, HMAC Triggers, Mandatory Gates (`Ruff`, `Gitleaks`, `Bandit`, `pip-audit`, `Trivy`) |
| **13. Meta WhatsApp Webhook** | HMAC-SHA256 `X-Hub-Signature-256` Validation, 5-Minute Replay Window |
| **14. AI Prompt Injection** | XML Delimiters, Volatility Ordering, Pydantic Structured Outputs, 15-Turn Cap |
| **15. Campaign Lead API** | `X-Tenant-Key` Auth, E.164 Regex Sanitization, Redis `SET NX` Idempotency & Atomic Quota Reservation |
| **16. Immutable Disaster Recovery** | Cloudflare R2 Encrypted Backups, Image SHA Correlation, `/health/db-sync-status` Alembic Gating |
| **17. ASGI Limits & HTTP Hardening** | Streaming `1 MiB`/`26 MiB` Body Cap (`HTTP 413`), 64-Level JSON Byte State Machine (`HTTP 400`), Strict CSP/HSTS Headers, `--ulimit core=0` |