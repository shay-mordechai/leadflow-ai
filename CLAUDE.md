# LeadFlow AI (`leadflow-ai`) — Architecture & Autonomous Agent Guidelines

## 1. System Overview & Tech Stack
Multi-tenant SaaS platform for automated lead qualification and conversational sales over WhatsApp.

- **Backend:** Python 3.12/3.13, FastAPI, Gunicorn + Uvicorn Workers, SQLAlchemy (Async runtime + Sync Alembic migrations), Alembic, Pydantic v2.
- **Frontend:** Next.js (`frontend/`, port `3000`).
- **Data Stores:**
  - **PostgreSQL 15 Alpine (`127.0.0.1:5432`):** Enforces tenant isolation via `FORCE ROW LEVEL SECURITY` and least-privilege roles (`leadflow_migrator`, `leadflow_writer`, `leadflow_reader`). Local tests must target `leadflow_test` exclusively—never `leadflow_prod`.
  - **Redis 7 Alpine (`127.0.0.1:6379`):** Idempotency locks (`SET NX`), JWT `jti` revocation blocklist, and atomic token quotas.
- **Edge Proxy & DLP:** Cloudflare Zero-Trust Tunnels (`cloudflared`) → Envoy Proxy (`v1.28`, port `10000`) running a custom Rust/WebAssembly egress filter (`data-gate/src/lib.rs` → `data_hop_firewall.wasm`, `proxy-wasm` v0.2.4).
- **AI Engine (`GeminiTieredRouter`):**
  - **Tier 1 (`gemini-flash-lite-latest`):** Low-latency intent classification and status parsing.
  - **Tier 2 (`gemini-flash-latest`):** Complex sales qualification, objection handling, and dynamic tenant RAG.
- **Meta Dual-Bot Architecture:**
  - **Messaging Bot (`META_ACCESS_TOKEN`):** Customer-facing inbound/outbound WhatsApp messaging (`src/routers/webhooks/whatsapp.py`).
  - **Admin Bot (`META_ADMIN_ACCESS_TOKEN` via `settings.admin_access_token`):** WABA and phone asset management, inspection, and operator-gated provisioning (`src/routers/provisioning.py`).
- **Runtime & Cloud Infrastructure:**
  - **Compute:** Linux running **Rootless Podman** / Docker Compose orchestrated via **Systemd Quadlets** (`systemctl --user`) with `sec_opt=[no-new-privileges]` and `--ulimit core=0`.
  - **Cloud Services:** AWS SSM Parameter Store (in-memory secrets bootstrapping over IMDSv2 when `ENABLE_AWS_SSM=true`), AWS S3 (audio/PDF lifecycle storage), and Cloudflare R2 (state-correlated `pg_dump` backups).

---

## 2. Autonomous Execution Protocol (Plan-Act-Verify — Lite Mode)

Execute all phases directly in the active lightweight/fast model session. **DO NOT** spawn sub-agents or escalate to heavier/expensive models unless explicitly instructed by the user.

Whenever a task involves modifying code, database schemas, or infrastructure and verifying them with tests (`pytest` / `npm test`), follow this three-stage workflow:

1. **PLAN Phase (Read-Only Analysis):**
   - Inspect relevant files, logs, database states, and failure tracebacks before making any edits.
   - Write a concise, step-by-step execution plan naming exact target files, SQL/CLI commands, and root-cause fixes.
   - Identify affected security invariants (RLS, tenant context, webhook signatures, PII masking) upfront.
2. **ACT Phase (Targeted Execution):**
   - Execute the plan step-by-step without deviating from architectural constraints.
   - Run the relevant unit and security test suites (`pytest`) after applying changes to verify behavior.
   - **Test Integrity Rule:** NEVER modify, weaken, mock out, or skip existing test assertions in `tests/` to make a failing test pass—fix the underlying application, migration, or environment issue instead.
3. **Circuit Breaker (Stop & Report Rule):**
   - Track consecutive test failures during the ACT phase.
   - If the same test suite fails **2 times in a row** or hits a complex PostgreSQL RLS, role-permission, or async/sync driver issue, **stop editing immediately** and output a concise summary of the root cause and full traceback for user review instead of looping or spawning sub-agents.

---

## 3. Strict Coding & Security Rules

1. **Multi-Tenancy, RLS & IDOR Prevention:**
   - Every database query on tenant-scoped models (`Lead`, `Session`, `Message`, `Profile`, `AIAgent`) **MUST** explicitly filter by `tenant_id` / `user_id` **AND** execute within an active PostgreSQL tenant context (`set_current_tenant_context` / `reset_current_tenant_context` in `try...finally` blocks).
   - Never grant `SUPERUSER` or `BYPASSRLS` to runtime application roles (`leadflow_writer`, `leadflow_reader`), and never introduce fail-open (`IS NULL`) RLS policy bypasses.
   - Never trust client-supplied `user_id` or `tenant_id` in payloads; always resolve identity via `get_current_user` (`src/security/dependencies.py`), which verifies JWT signature, `jti` Redis revocation, `token_version`, and `exp`.
2. **Database Migrations & Connection Drivers:**
   - Alembic (`alembic/env.py`) runs synchronously and normalizes `postgresql+asyncpg://` to `postgresql+psycopg2://`. Use `ALEMBIC_DATABASE_URL` with the `leadflow_migrator` (or DB owner) role when running schema migrations.
   - Local development and test runs must resolve PostgreSQL via `127.0.0.1:5432/leadflow_test` (use hostname `db` only inside Compose container networks).
3. **Zero Hardcoded Secrets & Disk Hygiene:**
   - Never read, print, log, or hardcode `.env*` files, API keys, or cloud credentials.
   - In `production`, `src/config.py` rejects on-disk `.env` / `.env.test` files; secrets must be supplied via environment variables or AWS SSM Parameter Store.
4. **PII Masking in Logs:**
   - Never log raw phone numbers, email addresses, tokens, or unmasked message bodies. Always wrap identifiers and payloads with `mask_phone` and `mask_body` (`src/security/pii.py`).
5. **Edge Wasm DLP & Egress Privacy (`data-gate`):**
   - Envoy (`proxy-wasm`) normalizes all HTTP headers to **lowercase**. Always inspect headers in lowercase (e.g., `x-data-ttl`, `content-length`) inside `data-gate/src/lib.rs`.
   - Any endpoint returning sensitive PII that requires edge scrubbing must set `response.headers["X-Data-TTL"] = "1"`.
   - Whenever routes or clusters are modified in `data-gate/envoy.yaml`, keep `envoy-filter.yaml` and `envoy-nofilter.yaml` synchronized, and maintain `dns_lookup_family: V4_ONLY` on `STRICT_DNS` clusters.
6. **ASGI Streaming & DoS Guardrails (`src/middleware/request_limits.py`):**
   - Never bypass `RequestBodyLimitMiddleware`. Standard requests are capped at **1 MiB** (`HTTP 413`), multipart audio uploads (`/api/v1/sessions/upload/`) at **26 MiB**, and JSON nesting depth at **64 levels** (`HTTP 400`).
7. **AI Prompt Injection & Denial-of-Wallet (DoW) Controls:**
   - Encapsulate all untrusted user inputs inside XML boundary tags (`<system>`, `<latest_user_message>`) in `src/services/ai/prompt_builder.py`.
   - Enforce structured Pydantic outputs (`WhatsAppAgentResponse`), a maximum of **15 conversation turns**, **512 output tokens**, a **7-second timeout**, and Redis atomic quota tracking (`incrby`/`decrby`).
8. **Webhook & File Security:**
   - All inbound webhooks must validate cryptographic signatures before processing (`X-Hub-Signature-256` with 5-minute replay window for Meta; constant-time `X-Twilio-Signature` HMAC-SHA1 for Twilio; `X-Tenant-Key` + Redis `SET NX` idempotency for Campaign leads).
   - PDF generation must use `fpdf2` plain-text primitives only (no HTML-to-PDF engines) with strict `os.path.basename` and regex filename sanitization inside `storage/pdfs`.
9. **Code Comments & Style:**
   - All code comments, docstrings, and commit messages **MUST** be written in clear, professional technical English.

---

## 4. Mandatory Pre-Commit & CI/CD Verification Gates

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
pytest tests/test_main.py tests/security/ -v

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

## 5. Restricted Paths (DO NOT MODIFY, PRINT, OR READ)

* `.env*` (blocked via `.claude/settings.json` hook with `Exit 2`)
* `*.pem`, `*.key`, `*.crt`
* `terraform/*.tfstate*`
* `storage/pdfs/*` (runtime customer artifacts)

### Automated Guardrails & Verification Gate
- **Post-Edit Python Hook (`.claude/hooks/post_edit_py_guard.sh`):** Automatically runs `py_compile` and `ruff check` on every edited `.py` file. Fix any reported syntax or lint issue immediately before proceeding.
- **Independent Verifier (`.claude/agents/verifier.md`):** Before declaring any multi-file or feature task complete, invoke the read-only `verifier` sub-agent (or run the full `./venv/bin/pytest -q` + `./venv/bin/ruff check` gate) to confirm zero regressions, zero temporary artifacts, and zero `XX%` placeholders.
