# MyLeads AI (`leadflow-ai`) — Architecture & Autonomous Agent Guidelines

## 1. System Overview & Tech Stack
Multi-tenant SaaS platform for automated lead qualification and conversational sales over WhatsApp.

- **Backend:** Python 3.11/3.12, FastAPI, Gunicorn + Uvicorn Workers, SQLAlchemy (Async), Alembic, Pydantic v2.
- **Frontend:** Next.js (`leadflow-frontend`, port `3000`).
- **Data Stores:** PostgreSQL 15 Alpine (`127.0.0.1:5432`) and Redis 7 Alpine (`127.0.0.1:6379` — idempotency locks, JWT blocklist, atomic token quotas).
- **Edge Proxy & DLP:** Cloudflare Zero-Trust Tunnels (`cloudflared`) → Envoy Proxy (`v1.28`, port `10000`) running a custom Rust/WebAssembly egress filter (`data-gate/src/lib.rs` → `data_hop_firewall.wasm`, `proxy-wasm` v0.2.4).
- **AI Engine (`GeminiTieredRouter`):**
  - **Tier 1 (`gemini-flash-lite-latest`):** Low-latency intent classification and status parsing.
  - **Tier 2 (`gemini-flash-latest`):** Complex sales qualification, objection handling, and dynamic tenant RAG.
- **Runtime & Cloud Infrastructure:**
  - **Compute:** Linux running **Rootless Podman** orchestrated via **Systemd Quadlets** (`systemctl --user`) with `sec_opt=[no-new-privileges]` and `--ulimit core=0`.
  - **Cloud Services:** AWS SSM Parameter Store (in-memory secrets bootstrapping over IMDSv2), AWS S3 (audio/PDF lifecycle storage), and Cloudflare R2 (state-correlated `pg_dump` backups).

---

## 2. Strict Coding & Security Rules

1. **Multi-Tenancy & IDOR Prevention:**
   - Every database query on tenant-scoped models (`Lead`, `Session`, `Message`, `Profile`) **MUST** explicitly filter by `tenant_id`.
   - Never trust client-supplied `user_id` or `tenant_id` in payloads; always resolve identity via `get_current_user` (`src/security/dependencies.py`), which verifies JWT signature, `jti` Redis revocation, `token_version`, and `exp`.
2. **Zero Hardcoded Secrets & Disk Hygiene:**
   - Never read, print, log, or hardcode `.env` files, API keys, or cloud credentials.
   - All runtime secrets are loaded into memory via `src/config.py` (`pydantic-settings` + AWS SSM Parameter Store).
3. **Edge Wasm DLP & Egress Privacy (`data-gate`):**
   - Envoy (`proxy-wasm`) normalizes all HTTP headers to **lowercase**. Always inspect headers in lowercase (e.g., `x-data-ttl`, `content-length`) inside `data-gate/src/lib.rs`.
   - Any endpoint returning sensitive PII that requires edge scrubbing must set `response.headers["X-Data-TTL"] = "1"`.
   - Whenever routes or clusters are modified in `data-gate/envoy.yaml`, keep `envoy-filter.yaml` and `envoy-nofilter.yaml` synchronized, and maintain `dns_lookup_family: V4_ONLY` on `STRICT_DNS` clusters.
4. **ASGI Streaming & DoS Guardrails (`src/middleware/request_limits.py`):**
   - Never bypass `RequestBodyLimitMiddleware`. Standard requests are capped at **1 MiB** (`HTTP 413`), multipart audio uploads (`/api/v1/sessions/upload/`) at **26 MiB**, and JSON nesting depth at **64 levels** (`HTTP 400`).
5. **AI Prompt Injection & Denial-of-Wallet (DoW) Controls:**
   - Encapsulate all untrusted user inputs inside XML boundary tags (`<system>`, `<latest_user_message>`) in `src/services/ai/prompt_builder.py`.
   - Enforce structured Pydantic outputs (`WhatsAppAgentResponse`), a maximum of **15 conversation turns**, **512 output tokens**, a **7-second timeout**, and Redis atomic quota tracking (`incrby`/`decrby`).
6. **Webhook & File Security:**
   - All inbound webhooks must validate cryptographic signatures before processing (`X-Hub-Signature-256` with 5-minute replay window for Meta; constant-time `X-Twilio-Signature` HMAC-SHA1 for Twilio; `X-Tenant-Key` + Redis `SET NX` idempotency for Campaign leads).
   - PDF generation must use `fpdf2` plain-text primitives only (no HTML-to-PDF engines) with strict `os.path.basename` and regex filename sanitization inside `storage/pdfs`.
7. **Code Comments & Style:**
   - All code comments, docstrings, and commit messages **MUST** be written in clear, professional technical English.

---

## 3. Mandatory Pre-Commit & CI/CD Verification Gates

Before committing or pushing any changes, agents **MUST** ensure all CI gates pass with zero errors or formatting diffs:

```bash
# 1. Linting & Import Sorting (No duplicate or unsorted imports)
ruff check src tests

# 2. Strict Code Formatting Check
ruff format --check src tests

# 3. Supply-Chain Vulnerability Audit (Zero known CVEs allowed)
pip-audit -r requirements.txt

# 4. Database Migration Drift Check
alembic check

# 5. Automated Unit & Security Tests
pytest tests/test_main.py -v

```

### Building & Verifying the Rust/Wasm Filter (Immutable Host / Podman)

When modifying `data-gate/src/lib.rs` on an immutable Linux host (e.g., Fedora Kinoite):

```bash
cd data-gate
podman run --rm -v "$PWD:/work:Z" -w /work docker.io/library/rust:1.82-slim \
  sh -c "rustup target add wasm32-unknown-unknown && cargo build --target wasm32-unknown-unknown --release"
podman build -t ghcr.io/shay-mordechai/leadflow-data-gate:latest .
systemctl --user restart leadflow-data-gate.service

```

---

## 4. Restricted Paths (DO NOT MODIFY, PRINT, OR READ)

* `.env*` (blocked via `.claude/settings.json` hook with `Exit 2`)
* `*.pem`, `*.key`, `*.crt`
* `terraform/*.tfstate*`
* `storage/pdfs/*` (runtime customer artifacts)