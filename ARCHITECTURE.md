# MyLeads AI (`leadflow-ai`) - System Architecture

## 1. Executive Summary
`MyLeads AI` is an enterprise-grade multi-tenant SaaS platform engineered for automated lead qualification and conversational sales over WhatsApp. The platform combines real-time webhook ingestion (קליטת נתונים בזמן אמת), edge-level PII sanitization via WebAssembly, multi-tier LLM routing, and strict multi-tenant isolation (בידוד בין לקוחות).

---

## 2. High-Level Architecture Flow

[ WhatsApp / Meta Webhook ]
│
▼
[ Cloudflare Tunnel (Zero-Trust Ingress) ]
│ (Encrypted WireGuard Tunnel - No Public Ports)
▼
[ Envoy Reverse Proxy + Rust/WASM Data-Gate ]
├─ Strips Israeli IDs, Credit Cards, PII before application ingestion
│
▼
[ FastAPI Async Application (Uvicorn / Gunicorn) ]
├─ Request Rate Limiting & Auth Validation
├─ Tenant Isolation Scoping (tenant_id verification)
│
├───► [ Redis Cache / Budget Gate ] (Atomic token quota tracking)
│
├───► [ PostgreSQL Database ] (Multi-tenant schema via SQLAlchemy Async)
│
└───► [ GeminiTieredRouter ]
├─ Low Complexity  ──► Gemini 2.5 Flash-Lite (Fast, low-cost)
├─ High Complexity ──► Gemini 2.5 Flash (Conversational sales)
└─ Failover Logic  ──► Automatic failover on upstream timeouts


---

## 3. Core Architectural Pillars

### A. Edge Security & Ingress (אבטחה בקצה הרשת)
* **Zero Open Inbound Ports:** The server is completely invisible to public scanners. Traffic is routed strictly through **Cloudflare Tunnels** (`cloudflared`).
* **Hardware & Compute Firewall:** Protected by a Hetzner Cloud Firewall (`leadflow-zero-trust-fw`) rejecting all unsolicited inbound traffic except ICMP pings.
* **WASM PII Redaction (`data-gate`):** An Envoy filter compiled from Rust to WebAssembly inspects incoming payloads and redacts sensitive customer data before it ever hits the Python runtime or application logs.

### B. Multi-Tenancy & Data Isolation (בידוד נתונים מרובה דיירים)
* **Tenant-Scoped ORM Models:** Every database entity (`Lead`, `Session`, `Message`, `Profile`) inherits from tenant-aware mixins (`tenant_id`).
* **Row-Level Enforcement:** Queries in SQLAlchemy explicitly require `tenant_id` filters to eliminate Insecure Direct Object Reference (IDOR) vulnerabilities.
* **Revocation & IAM:** JWT tokens are validated against a Redis token blacklist for instant revocation upon sign-out or tenant deactivation.

### C. Cost-Optimized AI Engine (ייעול עלויות וניתוב מודלים)
* **Tiered Routing (`GeminiTieredRouter`):**
  * **Tier 1 (`gemini-flash-lite-latest`):** Intent classification, basic parsing, status evaluation.
  * **Tier 2 (`gemini-flash-latest`):** Active objection handling, sales qualification, context synthesis.
* **Denial of Wallet Protection:**
  * Strict maximum conversation turns (capped at 15 turns) to prevent infinite loops between automated bots.
  * Hard limits on output tokens (512 tokens maximum).
  * Strict 7-second HTTP timeout per inference call.
  * Atomic monthly token budgeting via Redis `incrby`/`decrby`.

### D. Hybrid Cloud Infrastructure as Code (IaC)
* **Active Compute:** Hetzner Cloud (`cx23` instance running Rocky Linux 9), configured with systemd and containerized workers (`Docker Compose`).
* **Managed Cloud Layer (AWS via Terraform):**
  * **S3 with Lifecycle Policies:** Audio recordings and PDFs transition to Glacier Instant Retrieval after 30 days and expire permanently after 365 days.
  * **Secrets Manager:** Secure storage of WhatsApp access tokens, Gemini keys, and database credentials.
  * **Least-Privilege IAM:** Policies restricting server access exclusively to its assigned S3 bucket prefix and secret ARNs.

### E. DevSecOps & Governance (בקרת איכות ואבטחה רציפה)
* **Autonomous Harness:** Repository instructions anchored in `CLAUDE.md` and `.clinerules`.
* **Deterministic Guardrails:** `.claude/settings.json` command hooks blocking unauthorized `.env` access with `Exit 2`.
* **Static & Dependency Gates:** GitHub Actions CI executing `ruff`, `bandit` (SAST), `pip-audit` (SCA), and `pytest` before merge approval.
