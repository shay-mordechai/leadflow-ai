# 🔒 MyLeads AI - Internal Architecture & Secrets

**CLASSIFICATION:** TOP SECRET / INTERNAL USE ONLY  
**LAST AUDIT:** March 9, 2026

This document maps the Production configuration requirements.

> ⚠️ **SECURITY NOTE:** NEVER hardcode real secret values in this document. All sensitive values are injected at runtime via AWS Systems Manager (SSM) or GitHub Secrets.

---

## 1. 🔑 Production Secrets (AWS SSM)
**Root Path:** `/leadflow/prod/`  
**Region:** `eu-north-1`

| Variable Name | Value Location / Reference | Description |
| :--- | :--- | :--- |
| **System Config** | | |
| `APP_NAME` | AI LeadFlow | Branding Name |
| `BASE_URL` | `https://my-leads.app/` | Public Domain |
| `DEBUG` | `False` | Production Mode |
| `DATABASE_URL` | `sqlite:////app/data/leads.db` | Main DB (SQLite) |
| `ENABLE_REAL_PHONE_PURCHASE` | `true` | Allow real billing via Providers |
| **Security & Crypto** | | |
| `SECRET_KEY` | `[STORED_IN_AWS_SSM]` | JWT Signing Key (SHA256) |
| `ALGORITHM` | `HS256` | JWT Algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `1440` | Session Duration (24 Hours) |
| `ENCRYPTION_KEY` | `[STORED_IN_AWS_SSM]` | Fernet Key for DB PII Encryption |
| **AI Engines** | | |
| `GOOGLE_API_KEY` | `[STORED_IN_AWS_SSM]` | Gemini 2.0 Flash (Main Agent & Tools) |
| **Telephony Providers** | | |
| `TWILIO_ACCOUNT_SID` | `[STORED_IN_AWS_SSM]` | Twilio Account ID |
| `TWILIO_AUTH_TOKEN` | `[STORED_IN_AWS_SSM]` | Twilio API Token |
| `VONAGE_API_KEY` | `[STORED_IN_AWS_SSM]` | Vonage API Key |
| `VONAGE_API_SECRET` | `[STORED_IN_AWS_SSM]` | Vonage API Secret |
| `VONAGE_APP_ID` | `[STORED_IN_AWS_SSM]` | Vonage Application ID |
| `VONAGE_PRIVATE_KEY_PATH` | `./private.key` | Path to Vonage Cert |
| `SIGNALWIRE_PROJECT_ID` | `[STORED_IN_AWS_SSM]` | SignalWire Project |
| `SIGNALWIRE_AUTH_TOKEN` | `[STORED_IN_AWS_SSM]` | SignalWire Token |
| `SIGNALWIRE_SPACE_URL` | `[STORED_IN_AWS_SSM]` | SignalWire Domain |
| **Infrastructure & Meta** | | |
| `CLOUDFLARE_TOKEN` | `[STORED_IN_AWS_SSM]` | Cloudflare Tunnel Token |
| `AWS_ACCOUNT_ID` | `[STORED_IN_GITHUB_SECRETS]`| Needed for ECR Image Pull/Push |
| `META_ACCESS_TOKEN` | `[STORED_IN_AWS_SSM]` | Facebook/WhatsApp Graph API Token |
| `WHATSAPP_PHONE_ID` | `[STORED_IN_AWS_SSM]` | Official WhatsApp Business Phone ID |
| `SENTRY_DSN` | `[STORED_IN_AWS_SSM]` | Real-time Error Tracking URL |
| `NEXT_PUBLIC_POSTHOG_KEY` | `[STORED_IN_FRONTEND_ENV]`| PostHog Analytics Client Key |

---

## 2. 🗄️ Database Schema & Management

The system uses SQLite in production (stored safely on the host at `~/leadflow-ai/data/leads.db` and mounted to the container).  
Database changes are strictly managed via Alembic Migrations configured with `render_as_batch=True` to safely support complex schema mutations (like `DROP CONSTRAINT`) in SQLite without data loss.

### Key Tables
* **`users`**: Stores Auth info, Hashed Passwords, and Plan Tier (STARTER/PRO).
* **`phone_numbers`**: Stores purchased numbers from Twilio/Vonage.
* **`business_profiles`**: Stores AI Persona context (Tone, Services).
* **`leads`**: Stores inbound leads. Includes `bot_active` and `requires_human` flags for human handoff. Protected by `idempotency_key` against Retry Storms.
* **`messages`**: Stores Conversational Memory (Chat history) between the AI and Leads to prevent the "Goldfish Problem".
* **`tags` & `lead_tag_association`**: Stores logical groupings for leads (e.g., 'Morning Class', 'Kiryat Netafim') to allow targeted AI voice broadcasts.
* **`sessions`**: Stores metadata for uploaded audio files transcribed via local Faster-Whisper.
* **`webhook_dlq`**: Dead Letter Queue. Stores failed incoming webhooks to ensure 0% data loss during API outages.
* **`audit_logs`**: Security tracking. Records "Who did what, and when" (e.g., AI prompt modifications) for compliance and debugging.

---

## 3. 🔄 Deployment & Updates

The system uses a Zero-Downtime update mechanism via **GitHub Actions -> SSH Tunnel -> AWS ECR -> Podman Systemd**.

### Manual Update Command (Server-Side)
If the GitHub Action fails, run this on the EC2 server:

```bash
# 1. Login to AWS ECR
aws ecr get-login-password --region eu-north-1 | podman login --username AWS --password-stdin [YOUR_AWS_ACCOUNT_ID].dkr.ecr.eu-north-1.amazonaws.com

# 2. Pull latest image
podman pull [YOUR_AWS_ACCOUNT_ID][.dkr.ecr.eu-north-1.amazonaws.com/leadflow-backend:latest](https://.dkr.ecr.eu-north-1.amazonaws.com/leadflow-backend:latest)

# 3. Restart Service via Systemd
systemctl --user restart container-leadflow-backend

```

### Database Migrations (Updating Schema)

⚠️ **DO NOT DELETE `leads.db` ANYMORE.** When a new column is added to the Python models, run this inside the server container to apply the changes safely:

```bash
podman exec -it leadflow-backend alembic upgrade head

```

---

## 4. 🛡️ Implemented Core Capabilities (Tier 1 & Tier 2)

### Security & Network (Zero Trust Architecture)

* **WASM DLP Firewall:** A custom Rust-compiled WebAssembly filter runs directly inside the Envoy proxy. It uses a "Fail-Closed" architecture to inspect outbound JSON payloads and redact sensitive credentials (Passwords, Tokens) in real-time, preventing Information Disclosure (Data Bleed).
* **Rate Limiting:** Cloudflare-aware Rate Limiting (`slowapi`) deployed on Auth (`/login`, `/register`) to block brute-force attacks.
* **Hardened Headers:** HSTS, CSP, and XSS Protection Headers active via global middleware.
* **Audit Logging:** Database-backed tracking of sensitive user actions (e.g., updating AI persona prompts) via `audit_service`.

### Reliability & Ops

* **Dead Letter Queue (DLQ):** Webhooks are wrapped in robust transactional logic. If a webhook processing fails, it rolls back the DB and saves the raw payload into `webhook_dlq` for manual recovery.
* **Idempotency Shield:** Webhook Idempotency active (`leads.idempotency_key`) to silently absorb duplicate requests and prevent retry storms.
* **Crash Reporting & Logs:** Sentry SDK integrated for instant crash reporting. Configured `python-json-logger` for structured JSON logs, easily searchable in AWS CloudWatch.
* **Graceful Shutdown:** Implemented to wait for active DB transactions to finish before the server stops.

### Business & Billing

* **Automated PDF Invoices:** High-performance, on-the-fly generation of Tax Invoices/Receipts using `fpdf2`, streamed directly to the client without polluting the server disk.
* **Subscription Enforcer:** Background Task Scheduler (APScheduler) active. Runs at 00:00 UTC to downgrade expired Trials.

### UX, SEO & Analytics

* **Skeleton Loaders:** Implemented premium UI loading states across the dashboard (`loading.tsx`) for instant visual feedback during API calls.
* **Toast Notifications:** Upgraded all native browser `alert()` calls to elegant `react-hot-toast` popups, including click-to-copy utilities.
* **Product Analytics:** Integrated PostHog globally to track pageviews, user journeys, and conversion funnels.
* **Dogfooding Support Widget:** Embedded a floating WhatsApp widget routing users directly to the system's own AI agent.
* **Dynamic SEO:** Fully implemented `sitemap.xml`, `robots.txt`, and OpenGraph/Twitter Cards for social media sharing.
* **Typography:** Upgraded to 'Heebo' font globally for crisp, modern Hebrew (RTL) rendering.

### AI, CRM & Advanced Features

* **Agentic Function Calling:** Upgraded to Gemini 2.0 Flash with `enable_automatic_function_calling=True`. The AI autonomously decides when to trigger tools (e.g., `check_calendar_availability`, `qualify_lead`) based on conversation context.
* **Omnichannel Inbox & Human Handoff:** Protects the owner's personal WhatsApp. The AI detects when a human is needed (using `[HANDOFF]` keyword), mutes itself (`bot_active=False`), and flags the lead in the dashboard.
* **Voice-to-Action Broadcasts:** Local Whisper AI transcribes audio notes, parses intent, identifies target Tags, and executes broadcasts.
* **Conversational Memory:** AI dynamically remembers past interactions with specific leads.
* **AI Feedback Loop:** Dedicated endpoint to track user ratings (Thumbs Up/Down) on AI responses to continuously improve prompts.

---

## 5. 🧪 QA Testing Architecture

The testing suite has been modularized for faster execution and better CI/CD integration.

**1. Internal Logic & Security Tests (No Network Needed):** Validates auth flows, pydantic validations, and DB operations using an in-memory SQLite DB.

```bash
pytest tests/test_main.py -v

```

**2. Macro Flow (Core Pipeline Validation):** Tests Registration -> MFA -> Billing Upgrade -> Lead Injection Webhook.

```bash
python3 tests/qa_macro.py --prod

```

**3. Micro Flow (Advanced Feature Validation):** Tests Regional Number Filtering (Area Code '03') -> Twilio WhatsApp Webhook -> Local Whisper Audio Upload.

```bash
python3 tests/qa_micro.py --prod

```

**4. AI Agent Function Calling (Direct Engine QA):** Tests the Gemini Agent's ability to autonomously trigger tools and handle human escalation, bypassing the need for a running server.

```bash
python3 tests/qa_agents.py --api-key="AIzaSy..."

```

---

## 6. 🚨 Emergency Contacts

* **DevOps Lead:** Shay Mordechai
* **Cloud Provider:** AWS (`eu-north-1`)
* **Security Layer:** Cloudflare Zero Trust
* **Registry:** AWS Elastic Container Registry (ECR)