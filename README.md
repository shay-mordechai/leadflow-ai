# 🔒 MyLeads AI - Internal Architecture & Secrets
**CLASSIFICATION: TOP SECRET / INTERNAL USE ONLY**
**LAST AUDIT:** Feb 19, 2026

This document maps the Production configuration requirements.
⚠️ **SECURITY NOTE:** NEVER hardcode real secret values in this document. All sensitive values are injected at runtime via AWS Systems Manager (SSM).

---

## 1. 🔑 Production Secrets (AWS SSM)

**Root Path:** `/leadflow/prod/`
**Region:** `eu-north-1`

| Variable Name | Value Location / Reference | Description |
| :--- | :--- | :--- |
| **System Config** | | |
| `APP_NAME` | `AI LeadFlow` | Branding Name |
| `BASE_URL` | `https://my-leads.app/` | Public Domain |
| `DEBUG` | `False` | Production Mode |
| `DATABASE_URL` | `sqlite:///./leads.db` | Main DB (SQLite) |
| `ENABLE_REAL_PHONE_PURCHASE` | `true` | Allow real billing via Providers |
| **Security & Crypto** | | |
| `SECRET_KEY` | `[STORED_IN_AWS_SSM]` | JWT Signing Key (SHA256) |
| `ALGORITHM` | `HS256` | JWT Algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Session Duration (24 Hours) |
| `ENCRYPTION_KEY` | `[STORED_IN_AWS_SSM]` | Fernet Key for DB PII Encryption |
| **AI Engines** | | |
| `GOOGLE_API_KEY` | `[STORED_IN_AWS_SSM]` | Gemini 1.5 Flash (Main Agent) |
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
| `GIT_TOKEN` | `[STORED_IN_GITHUB_SECRETS]`| GitHub Access for Updates |
| `META_ACCESS_TOKEN` | `[STORED_IN_AWS_SSM]` | Facebook/WhatsApp Graph API Token |
| `WHATSAPP_PHONE_ID` | `[STORED_IN_AWS_SSM]` | Official WhatsApp Business Phone ID |
| `SENTRY_DSN` | `[STORED_IN_AWS_SSM]` | Real-time Error Tracking URL |

---

## 2. 🗄️ Database Schema & Management

The system uses **SQLite** in production (stored at `/app/leads.db`).
Database changes are strictly managed via **Alembic Migrations** to ensure zero data loss.

### Key Tables
* **`users`**: Stores Auth info, Hashed Passwords, and Plan Tier (`STARTER`/`PRO`).
* **`phone_numbers`**: Stores purchased numbers from Twilio/Vonage.
* **`business_profiles`**: Stores AI Persona context (Tone, Services).
* **`leads`**: Stores incoming customer interactions. **Protected by `idempotency_key`** to prevent Zapier/Meta retry storms.

---

## 3. 🔄 Deployment & Updates

The system uses a **Zero-Downtime** update mechanism via GitHub Actions -> SSH Tunnel, supported by FastAPI Graceful Shutdown logic.

### Manual Update Command (Server-Side)
If the GitHub Action fails, run this on the server:
```bash
# 1. Pull latest image
podman pull ghcr.io/shay-mordechai/leadflow-backend:latest

# 2. Restart Service
systemctl --user restart leadflow-backend

```

### Database Migrations (Updating Schema)

**⚠️ DO NOT DELETE leads.db ANYMORE.**
When a new column is added to the Python models, run this inside the server container to apply the changes safely:

```bash
podman exec -it leadflow-backend alembic upgrade head

```

---

## 4. 🛡️ Implemented Core Capabilities (Tier 1 Resolved)

* **Security & Network:**
* Cloudflare-aware Rate Limiting (`slowapi`) deployed on Auth (`/login`, `/register`) to block brute-force attacks.
* HSTS, CSP, and XSS Protection Headers active via global middleware.


* **Reliability & Ops:**
* Sentry SDK integrated for instant crash reporting (with PII obfuscation setup).
* Webhook Idempotency active (`leads.idempotency_key`) to silently absorb duplicate requests.
* Graceful Shutdown implemented (waits for active DB transactions to finish before server stops).


* **Business Logic:**
* Background Task Scheduler (`APScheduler`) active. Runs at 00:00 UTC to downgrade expired Trials.
* Timezone safety enforced (UTC saved in DB -> Local Time interpreted in Browser).



---

## 5. 🧪 QA Testing

Use the `qa_interactive.py` script to validate the full flow.

**Standard QA Run:**

```bash
python3 qa_interactive.py --prod --email qa@test.com --password "SecurePass1!"

```

---

## 6. 🚨 Emergency Contacts

* **DevOps Lead:** Shay Mordechai
* **Cloud Provider:** AWS (eu-north-1)
* **Security Layer:** Cloudflare Zero Trust