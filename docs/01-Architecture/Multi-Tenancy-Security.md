
# Multi-Tenancy Isolation & Defense-in-Depth Security

## 1. PostgreSQL Row-Level Security (`FORCE RLS`)

* Enforced across all tenant-scoped tables via Alembic migration `20261122_enforce_rls_all`.
* **Split Database Roles:**
* `leadflow_writer`: Application read/write role subject to `FORCE ROW LEVEL SECURITY`.
* `leadflow_reader`: Least-privilege read-only role used for analytics and RAG retrieval.


* **Session Context Binding:** Every authenticated HTTP request and background webhook worker sets `SET LOCAL app.current_tenant_id = '<tenant_uuid>'` via SQLAlchemy event listeners and `set_current_tenant_context()`.
* **Pre-Tenant Lookup Exception:** Inbound WhatsApp webhooks resolve the destination business number (`phone_numbers.provider_id` / `number`) before setting `app.current_tenant_id` for the remainder of the pipeline.

## 2. Authentication & Token Revocation

* **JWT Pinning:** Strictly pinned to `HS256` (`algorithms=["HS256"]`) to prevent `alg=none` or RSA/HMAC confusion attacks.
* **Immediate Revocation:** Each token embeds a unique `jti` and user `token_version` validated against Redis on logout, password reset, or security lockdown.
* **Admin Authorization:** Sensitive cross-tenant endpoints (e.g., `GET /api/v1/partners/performance`) enforce `get_current_user` + `is_admin` checks.

## 3. ASGI DoS, SSRF & Injection Defenses

* **Streaming Body Limits (`RequestBodyLimitMiddleware`):** Enforces 1 MiB max body size for JSON endpoints, 26 MiB for media uploads, and byte-level 64-depth JSON nesting rejection before parsing.
* **SSRF Protection:** Outbound HTTP clients (`WhisperService`, `AlertDispatcher`, calendar tools) validate target URLs against private/loopback IP ranges (`127.0.0.0/8`, `10.0.0.0/8`, `169.254.169.254`, `::1`) and enforce `follow_redirects=False`.
* **Prompt Injection & XSS Guardrails:** User messages and retrieved RAG chunks are wrapped in XML boundary tags (`<lead_message>`, `<knowledge_context>`), and LLM responses are sanitized with `bleach` before persistence or delivery.
