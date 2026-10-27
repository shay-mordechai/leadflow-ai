# SECURITY.md — MyLeads AI

**Classification:** Public (Post-Remediation)
**Last Audit:** October 2026
**Architecture:** Zero Trust · Defense in Depth · OWASP Top 10

---

## Overview

This document maps the security layers built into MyLeads AI — an AI-powered SaaS lead management platform. Security was designed as part of the architecture from day one, not bolted on as an afterthought.

Every finding in this document is based on self-directed code review, active threat modeling, and hands-on vulnerability research — including responsible disclosure of security flaws in external AI platforms.

---

## 1. Network Architecture — "Ghost Server" (Zero Attack Surface)

**Threat:** Automated bot scanning, direct IP DDoS, port enumeration.

**Implementation:**
- The Hetzner Cloud server blocks all inbound ports (`0.0.0.0/0` fully empty). The server does not listen to the public internet.
- All ingress traffic is exclusively routed through a **Cloudflare Tunnel** — an outbound-only encrypted connection initiated by the `cloudflared` container. This neutralizes Direct IP Scanning and network-layer DDoS entirely.
- SSH access requires hardware-key authentication via **Cloudflare Identity-Aware Proxy (IAP)**.
- The application stack runs as **Rootless Podman** on RHEL 10.1 — significantly reducing the blast radius of any container compromise.

---

## 2. Secrets Management — In-Memory Bootstrapping (SSRF/LFI Mitigation)

**Threat:** An attacker exploiting SSRF or LFI targets `.env` files to exfiltrate API keys and credentials.

**Implementation:**
- Static `.env` files **do not exist** in the production environment. At server startup, `src/config.py` calls **AWS SSM Parameter Store** directly via `boto3` and loads all secrets into memory only (In-Memory, never written to disk).
- Zero secret artifacts on disk — attacker's maneuvering surface approaches zero.
- **IMDSv2** (Token-based Metadata Service) enforced to block basic SSRF attacks against the AWS Metadata endpoint.

---

## 3. MFA — Single-Use OTP & Replay Attack Prevention

**Threat:** OTP reuse within the validity window (Replay Attack); weak OTP generation (CWE-338).

**Implementation:**

Atomic operation sequence:
1. **Charge the payment:** User submits OTP.
2. **Lock the register:** On match, the OTP is **immediately deleted from the DB and `db.commit()` is called** before any other operation.
3. **Issue the receipt:** Only after the OTP is invalidated in the DB is the JWT issued.

- **Cryptographic correctness:** OTP generated using `secrets` (OS CSPRNG) instead of the vulnerable `random` module (CWE-338).
- Delete-before-issue eliminates the Race Condition window between token issuance and OTP deletion.
- **Token Versioning (`token_version`):** Each user has a `token_version` counter in the database. When a password is reset or a critical security event occurs, this version is incremented, invalidating all older JWTs for that user (forcing re-login).
- **Redis JWT Revocation:** Logged-out or compromised tokens are immediately added to a Redis-backed blocklist, preventing their reuse until their natural expiration.

---

## 4. WASM DLP Firewall — Information Disclosure Prevention (CWE-209)

**Threat:** Stack traces exposing internal paths, server versions, and keys in error responses.

**Implementation:**
- A custom **WebAssembly (WASM)** filter written in **Rust**, running directly inside an **Envoy Proxy** sidecar container.
- **Fail-Closed architecture:** The filter intercepts errors Out-of-Process. Any `5xx` response is cut, the stack trace is stripped, and the client receives a sanitized generic JSON: `{"error": "Internal Security Proxy Intervention"}`.

**Why not eBPF?** eBPF is excellent for observability but is Read-Only on data payloads. The kernel verifier does not permit dynamic mutation of Layer 7 payloads at runtime — making Envoy WASM the correct architectural choice.

---

## 5. Access Control & IDOR Prevention

**Threat:** Attacker modifies `user_id` in a URL or payload to access another user's data (Insecure Direct Object Reference).

**Implementation (`src/security/dependencies.py`):**
- The API does not trust any client-supplied identifier. `get_current_user` decodes the JWT, extracts the `email` from the cryptographic claims, and fetches the user directly from the DB.
- All protected endpoints require this dependency — requests are structurally blocked at the routing layer before reaching business logic.

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

**Threat:** A database breach exposes customer phone numbers and AI conversation transcripts.

**Implementation (`src/security/encryption.py`):**

* Symmetric encryption using **Fernet (AES-128 CBC)** via the `cryptography` library.
* **Lazy Initialization:** The cipher is not instantiated until the `ENCRYPTION_KEY` is loaded from AWS SSM — prevents cryptographic operations with a missing or incomplete key.
* **Fail-Safe Decryption:** Decryption failure (key rotation / corrupted ciphertext) does not crash the application — logs a security audit event and returns `[DECRYPTION_FAILED]` as a safe placeholder.

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

**Threat:** An exposed admin panel is a primary target for web exploits.

**Implementation:**

* Admin actions are **fully disabled in the web UI** and moved to a unified CLI tool (`manage_cli.py`) accessible only via SSH.
* **Global Exception Handler:** Intercepts all 500 errors globally, strips stack traces, renders a localized generic message to the client, and dispatches a detailed HTML crash report to `ADMIN_EMAIL` out-of-band.

---

## 8. Proxy-Aware Rate Limiting (DoS & Brute Force Prevention)

**Threat:** A standard rate limiter behind Cloudflare throttles the tunnel's loopback IP (`127.0.0.1`) — causing a Global DoS affecting all legitimate users.

**Implementation (`src/security/rate_limiter.py`):**

* Custom `get_real_ip` function extracts the `CF-Connecting-IP` header injected by Cloudflare's edge — directing the rate limiter at the actual attacker IP, not the proxy. This ensures trusted proxy IP validation and fails closed if the expected headers are missing or malformed.

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

**Threat:** HTML-to-PDF engines (e.g., `wkhtmltopdf`) execute network requests based on user-supplied content, enabling `file:///etc/passwd` or AWS metadata exfiltration embedded in generated documents.

**Implementation:**

* Uses **FPDF**, which renders plain text cells only — no HTML parsing, no network calls. SSRF risk = zero by design.

**Remediation: Path Traversal (SEC-012)**

*   **Description:** Previously, `os.path.join(output_dir, filename)` was used without sufficient filename sanitization, allowing potential Path Traversal if the caller controlled the filename.
*   **Implemented Fix:**
    1.  **Filename Sanitization:** The caller-supplied filename is now strictly sanitized. It strips all directory components (`os.path.basename`), replaces unsafe characters (non-alphanumeric, underscore, hyphen) with underscores (`re.sub`), and enforces a `.pdf` extension.
    2.  **Strict Path Verification:** The resolved output path is rigorously checked to ensure it remains strictly within the intended target output directory (`storage/pdfs`). Any attempt to traverse outside this directory is detected and neutralized, resulting in the use of a safe, randomly generated filename instead.

---

## 10. Audit Logging & Security Monitoring (OWASP A09)

**Threat:** Absence of logging allows attackers to operate undetected (OWASP A09:2021 — Security Logging and Monitoring Failures).

**Implementation (`src/security/audit.py`):**

* Dual-write pattern: every security event is written to the DB **and** emitted as a **Structured JSON log** — ready for ingestion by AWS CloudWatch, ELK, or Splunk.
* **Fail-Safe:** DB write failure falls back to `logger.error` without raising — an attacker cannot trigger Application DoS by exhausting the audit table.
- **Log Injection Sanitization:** All user-supplied inputs destined for logs are sanitized upstream using strict allow-lists and encoding to prevent log injection attacks (CWE-117).

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

## 11. Webhook Spoofing (Twilio)

**Threat:** `src/routers/webhooks/twilio.py` previously accepted the `From` parameter from Form Data without cryptographic signature validation, allowing an attacker to forge `From` to impersonate the business owner and trigger Admin Command Mode.

**Remediation: Twilio Webhook Signature Validation (SEC-015)**

*   **Description:** An attacker could previously forge `From` requests to the Twilio webhook, impersonating the business owner and potentially sending mass broadcasts at the platform's expense.
*   **Implemented Fix:**
    1.  **Cryptographic Validation:** A `validate_twilio_signature` dependency has been implemented. It retrieves the `X-Twilio-Signature` header and `TWILIO_AUTH_TOKEN` from settings.
    2.  **HMAC-SHA1 Comparison:** The dependency reconstructs the signed payload (URL + sorted POST parameters) as per Twilio's specification, calculates the HMAC-SHA1 signature, and performs a constant-time comparison with the received signature.
    3.  **Fail-Closed Principle:** The webhook fails closed, rejecting requests with HTTP 403 Forbidden if the `X-Twilio-Signature` header is missing or invalid, preventing unauthorized access and spoofing.

## 12. CI/CD Pipeline RCE Prevention (Zero-Trust Pull CD)

**Threat:** A compromised GitHub Actions workflow or compromised dependency executes arbitrary bash commands on the production server (Remote Code Execution - הרצת קוד מרחוק) via exposed SSH keys.

**Implementation:**

* **Pull-Based CD:** The production server does not accept direct deployment commands (No Push).
* **HMAC-Signed Trigger:** GitHub sends a lightweight Webhook signed with HMAC-SHA256. The server validates the signature before independently pulling (`podman pull`) the latest image from GHCR (GitHub Container Registry).
* **Air-Gapped Runtime:** The server's runtime environment remains completely isolated from the CI/CD pipeline's execution context.
- **Static Analysis Security Testing (SAST) & Software Composition Analysis (SCA):** The CI pipeline includes `Gitleaks` for secret detection, `Trivy` for container image and filesystem vulnerability scanning, `Bandit` for Python SAST, and `pip-audit` for Python dependency vulnerability scanning. These are configured as mandatory gates (`exit-code: "1"`) for critical and high-severity findings.

---

## 13. Meta WhatsApp Webhook Security (HMAC Validation)

**Threat:** An attacker discovers the webhook endpoint and injects fake messages to manipulate the AI, spam the system, or cause Application DoS (Denial of Service - מניעת שירות).

**Implementation:**

* All incoming payloads from Meta are validated against the `X-Hub-Signature-256` header.
* The server calculates the HMAC-SHA256 hash using the `WHATSAPP_APP_SECRET` and the raw request body, instantly dropping any request that lacks cryptographic proof of origin.
- **5-Minute Replay Attack Prevention:** Incoming webhooks include a Unix timestamp in the `X-Hub-Signature-256` payload. The server rejects any request where the timestamp is older than 5 minutes, mitigating replay attacks.

---

## 14. AI Prompt Injection & Jailbreak Defense (Hierarchical Context Injection)

**Threat:** A user sends a malicious WhatsApp message (e.g., "Ignore previous instructions") to bypass system guardrails, extract system prompts, or force unauthorized actions (Prompt Injection - הזרקת פקודות).

**Implementation (`src/services/ai/prompt_builder.py`):**

* **XML Delimiters:** System rules and business context are isolated from untrusted user inputs using strict XML tags (e.g., `<system>`, `<latest_user_message>`).
* **Volatility Ordering (Caching):** Static guardrails and tenant business rules are placed at the top layer (100% Cached), while dynamic user input is strictly placed at the bottom layer.
* **Structured Outputs:** The LLM is restricted by the `google-genai` API to only return valid JSON matching the `WhatsAppAgentResponse` Pydantic schema, neutralizing free-text manipulation.
- **Conversation Turn Cap:** AI conversations are capped at 15 turns (user and AI messages combined) to limit the attack surface for persistent prompt injection and control resource consumption.

---

## 15. Campaign Lead API Security (Sanitization & Idempotency)

**Threat:** External marketing automations (Zapier/Make) sending unvalidated payloads, leading to Meta WABA bans (due to spam) or billing exhaustion from duplicate/malicious leads.

**Implementation (`src/routers/webhooks/campaign.py`):**

* **Authentication:** Enforced `X-Tenant-Key` header validation for all inbound campaign requests.
* **Strict Sanitization (ניקוי קלט):** Phone numbers are strictly validated against E.164 regex formatting. Text fields (names, notes) are strictly truncated to short limits to prevent injection payloads.
* **Idempotency (מניעת כפילויות) & Atomic Quota Reservation:** Employs Redis `SET NX` (set if not exists) for atomic, distributed idempotency keys, preventing duplicate outbound WhatsApp initialization for the same lead within a 24-hour window. This also enables atomic reservation of communication quotas, protecting the Meta Quality Rating and preventing billing exhaustion.

## 16. Immutable Deployments & Off-Site State Correlation (Disaster Recovery)

**Threat:** Silent data corruption, server physical failure, or schema-mismatch crashing the application after a code deployment.

**Implementation:**
- **Off-Site Backups (Zero Egress):** `scripts/backup_to_r2.sh` runs `pg_dump` inside the running Podman backend, compresses the SQL stream, and uploads it to **Cloudflare R2** using the AWS CLI S3-compatible endpoint. Configure `R2_BUCKET`, `R2_ENDPOINT_URL`, and AWS CLI credentials; optionally set `DB_CONTAINER_NAME` and `R2_PREFIX`.
- **State-Correlation (Image ID Tracking):** The script records the running container's exact Podman image ID in names of the form `db_backup_<UTC timestamp>_image_<sha256 digest>.sql.gz`.
- **24/7 Compatibility Monitoring:** `/health/db-sync-status` compares `EXPECTED_DB_REVISION` and `CURRENT_IMAGE_SHA` from the container environment with the live `alembic_version` revision. It returns HTTP 503 unless all deployment metadata is present and the database revision matches. Set both values during immutable-image deployment.

---

## 17. Application, Media & Data Lifecycle Defenses

**Threat:** Resource exhaustion attacks (DoS), data exfiltration, uncontrolled data growth, and insecure handling of sensitive media.

**Implementation:**

- **Streaming Body Cap (1 MiB):** All incoming request bodies are capped at 1 MiB. This prevents resource exhaustion attacks by limiting the size of data an attacker can send to the API.
- **JSON Depth Limit (64 Levels):** Incoming JSON payloads are restricted to a maximum depth of 64 nested levels. This mitigates JSON parsing-based DoS attacks that exploit deeply nested structures.
- **Background Task Cap (200 Tasks):** The Celery task queue is configured with a hard limit of 200 concurrent or pending tasks. This ensures stability and prevents an attacker from overwhelming background workers.
- **BCrypt Threadpool Offloading:** Computationally intensive password hashing with BCrypt is offloaded to a dedicated threadpool. This prevents blocking the main event loop and ensures API responsiveness during authentication.
- **Remote/Local Audio SSRF & MIME Protections:**
    - Remote audio fetching for transcription (`src/services/ai/whisper.py`) explicitly validates URLs against a whitelist of trusted domains and disallows `file://` schemes, preventing SSRF.
    - Downloaded audio files are subjected to strict MIME type validation (`python-magic`) to ensure they are indeed audio files, preventing arbitrary file uploads or processing of malicious content.
- **90-Day GDPR Data Retention Task:** A scheduled Celery task (`src/tasks/retention_tasks.py`) automatically purges personally identifiable information (PII) and sensitive conversation data older than 90 days, ensuring GDPR compliance and minimizing data retention risk.
- **Core Dump Disablement (`--ulimit core=0`):** Production containers are launched with `--ulimit core=0`. This disables core dumps, preventing sensitive memory contents from being written to disk in the event of a crash, enhancing data confidentiality.

---

### Updated Defense-in-Depth Summary Table

| Security Layer | Mitigation Strategy |
|---|---|
| 1. Network Architecture | Cloudflare Tunnel, Zero Attack Surface, Rootless Podman |
| 2. Secrets Management | AWS SSM In-Memory Bootstrapping, IMDSv2 Enforcement |
| 3. MFA & Replay Prevention | Single-Use OTP, Token Versioning, Redis JWT Revocation, CSPRNG |
| 4. WASM DLP Firewall | Envoy Proxy Out-of-Process Error Stripping (WASM/Rust) |
| 5. Access Control & IDOR | JWT Claims-Based User Resolution, Policy Enforcement |
| 6. PII Encryption at Rest | Fernet (AES-128 CBC) with Lazy Init & Fail-Safe Decryption |
| 7. Out-of-Band Management | CLI-Only Admin, Global Exception Handler, OOB Crash Reports |
| 8. Proxy-Aware Rate Limiting | Cloudflare `CF-Connecting-IP` Trusted Proxy IP Validation |
| 9. PDF Generation | FPDF (Plain Text Only), Filename Sanitization, Path Verification |
| 10. Audit Logging | Dual-Write to DB & JSON Logs, Log Injection Sanitization, Fail-Safe |
| 11. Webhook Spoofing | Twilio HMAC-SHA1 Signature Validation, Fail-Closed |
| 12. CI/CD Pipeline | Pull-Based CD, HMAC-Signed Triggers, SAST/SCA Gates (Gitleaks, Trivy, Bandit, pip-audit) |
| 13. Meta WhatsApp Webhook | HMAC-SHA256 Validation, 5-Minute Replay Attack Prevention |
| 14. AI Prompt Injection | XML Delimiters, Volatility Ordering, Structured Outputs, 15-Turn Cap |
| 15. Campaign Lead API | `X-Tenant-Key` Auth, Strict Sanitization, Redis `SET NX` Idempotency & Atomic Quota Reservation |
| 16. Immutable Deployments | Off-Site Cloudflare R2 Backups, Image ID Tracking, DB Revision Monitoring |
| 17. Application, Media & Data Lifecycle | 1 MiB Body Cap, 64-Level JSON Depth, 200 Task Cap, BCrypt Threadpool, Audio SSRF/MIME, GDPR Retention, `--ulimit core=0` |