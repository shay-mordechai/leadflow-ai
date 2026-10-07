# SECURITY.md — MyLeads AI

**Classification:** Public (Post-Remediation)
**Last Audit:** June 2026
**Architecture:** Zero Trust · Defense in Depth · OWASP Top 10

---

## Overview

This document maps the security layers built into MyLeads AI — an AI-powered SaaS lead management platform. Security was designed as part of the architecture from day one, not bolted on as an afterthought.

Every finding in this document is based on self-directed code review, active threat modeling, and hands-on vulnerability research — including responsible disclosure of security flaws in external AI platforms.

---

## 1. Network Architecture — "Ghost Server" (Zero Attack Surface)

**Threat:** Automated bot scanning, direct IP DDoS, port enumeration.

**Implementation:**
- The AWS EC2 server blocks all inbound ports (`0.0.0.0/0` fully empty). The server does not listen to the public internet.
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
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    email: str = payload.get("email") or payload.get("sub")
    if email is None:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
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

* Custom `get_real_ip` function extracts the `CF-Connecting-IP` header injected by Cloudflare's edge — directing the rate limiter at the actual attacker IP, not the proxy.

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

**Open Finding:**

* `os.path.join(output_dir, filename)` used without filename sanitization — potential Path Traversal if the caller controls the filename. Planned remediation: `secure_filename` wrapper before `os.path.join` [Tracked in Ticket: SEC-012].

---

## 10. Audit Logging & Security Monitoring (OWASP A09)

**Threat:** Absence of logging allows attackers to operate undetected (OWASP A09:2021 — Security Logging and Monitoring Failures).

**Implementation (`src/security/audit.py`):**

* Dual-write pattern: every security event is written to the DB **and** emitted as a **Structured JSON log** — ready for ingestion by AWS CloudWatch, ELK, or Splunk.
* **Fail-Safe:** DB write failure falls back to `logger.error` without raising — an attacker cannot trigger Application DoS by exhausting the audit table.

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

## 11. Open Finding — Webhook Spoofing (Twilio)

**Threat:** `src/routers/webhooks/twilio.py` accepts the `From` parameter from Form Data without cryptographic signature validation. An attacker who knows the webhook URL can forge `From` to impersonate the business owner and trigger Admin Command Mode — sending mass broadcasts at the platform's expense.

**Status:** Identified via self-directed code review. Planned remediation: **Twilio Signature Validation Middleware** validating the `X-Twilio-Signature` header on every inbound webhook request [Tracked in Ticket: SEC-015].

**Why this is documented as an open finding:** Full transparency about the current security posture is part of the Secure-by-Design philosophy. Early identification is preferable to concealment.

## 12. CI/CD Pipeline RCE Prevention (Zero-Trust Pull CD)

**Threat:** A compromised GitHub Actions workflow or compromised dependency executes arbitrary bash commands on the production server (Remote Code Execution - הרצת קוד מרחוק) via exposed SSH keys.

**Implementation:**

* **Pull-Based CD:** The production server does not accept direct deployment commands (No Push).
* **HMAC-Signed Trigger:** GitHub sends a lightweight Webhook signed with HMAC-SHA256. The server validates the signature before independently pulling (`podman pull`) the latest image from GHCR (GitHub Container Registry).
* **Air-Gapped Runtime:** The server's runtime environment remains completely isolated from the CI/CD pipeline's execution context.

---

## 13. Meta WhatsApp Webhook Security (HMAC Validation)

**Threat:** An attacker discovers the webhook endpoint and injects fake messages to manipulate the AI, spam the system, or cause Application DoS (Denial of Service - מניעת שירות).

**Implementation:**

* All incoming payloads from Meta are validated against the `X-Hub-Signature-256` header.
* The server calculates the HMAC-SHA256 hash using the `WHATSAPP_APP_SECRET` and the raw request body, instantly dropping any request that lacks cryptographic proof of origin.

---

## 14. AI Prompt Injection & Jailbreak Defense (Hierarchical Context Injection)

**Threat:** A user sends a malicious WhatsApp message (e.g., "Ignore previous instructions") to bypass system guardrails, extract system prompts, or force unauthorized actions (Prompt Injection - הזרקת פקודות).

**Implementation (`src/services/ai/prompt_builder.py`):**

* **XML Delimiters:** System rules and business context are isolated from untrusted user inputs using strict XML tags (e.g., `<system>`, `<latest_user_message>`).
* **Volatility Ordering (Caching):** Static guardrails and tenant business rules are placed at the top layer (100% Cached), while dynamic user input is strictly placed at the bottom layer.
* **Structured Outputs:** The LLM is restricted by the `google-genai` API to only return valid JSON matching the `WhatsAppAgentResponse` Pydantic schema, neutralizing free-text manipulation.

---

## 15. Campaign Lead API Security (Sanitization & Idempotency)

**Threat:** External marketing automations (Zapier/Make) sending unvalidated payloads, leading to Meta WABA bans (due to spam) or billing exhaustion from duplicate/malicious leads.

**Implementation (`src/routers/webhooks/campaign.py`):**

* **Authentication:** Enforced `X-Tenant-Key` header validation for all inbound campaign requests.
* **Strict Sanitization (ניקוי קלט):** Phone numbers are strictly validated against E.164 regex formatting. Text fields (names, notes) are strictly truncated to short limits to prevent injection payloads.
* **Idempotency (מניעת כפילויות):** Prevents duplicate outbound WhatsApp initialization for the same lead within a 24-hour window, protecting the Meta Quality Rating.

## 16. Immutable Deployments & Off-Site State Correlation (Disaster Recovery)

**Threat:** Silent data corruption, server physical failure, or schema-mismatch crashing the application after a code deployment.

**Implementation:**
- **Off-Site Backups (Zero Egress):** `scripts/backup_to_r2.sh` runs `pg_dump` inside the running Podman backend, compresses the SQL stream, and uploads it to **Cloudflare R2** using the AWS CLI S3-compatible endpoint. Configure `R2_BUCKET`, `R2_ENDPOINT_URL`, and AWS CLI credentials; optionally set `DB_CONTAINER_NAME` and `R2_PREFIX`.
- **State-Correlation (Image ID Tracking):** The script records the running container's exact Podman image ID in names of the form `db_backup_<UTC timestamp>_image_<sha256 digest>.sql.gz`.
- **24/7 Compatibility Monitoring:** `/health/db-sync-status` compares `EXPECTED_DB_REVISION` and `CURRENT_IMAGE_SHA` from the container environment with the live `alembic_version` revision. It returns HTTP 503 unless all deployment metadata is present and the database revision matches. Set both values during immutable-image deployment.

---

### *Updated Defense-in-Depth Summary Table (Append to existing table):*

| Security Layer | Mitigation Strategy |
| --- | --- |
| CI/CD Pipeline | Pull-Based Deployments, HMAC-SHA256 Webhook triggers (Zero RCE) |
| WhatsApp Integration | Meta `X-Hub-Signature-256` Cryptographic Validation |
| AI / LLM Engine | Hierarchical Context Injection, XML Delimiters, Pydantic Structured Outputs |
| Inbound Campaigns | `X-Tenant-Key` Auth, Regex Sanitization, Idempotency Checks |