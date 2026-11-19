# MyLeads AI (`leadflow-ai`) - Operational Runbook

This guide covers daily maintenance, deployment procedures, and emergency troubleshooting (נוהל תפעול ותקלות) for system operators and on-call engineers.

---

## 1. Local Development & Testing

### Starting the Local Stack
```bash
# Start PostgreSQL, Redis, and Envoy with Rust WASM
docker compose up -d postgres redis envoy

# Run database migrations
alembic upgrade head

# Run local FastAPI server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
Executing Security & Unit Test Suites
Bash
# Run unit and LLM security regression tests
pytest tests/ -v

# Run SAST code audit
bandit -r src/ -ll -ii

# Verify dependency vulnerabilities
pip-audit
2. Production Deployment & Migrations
Running Migrations in Production
Bash
# SSH into the Hetzner server via Tailscale / secure jump host
alembic upgrade head
Updating Infrastructure (Terraform)
Bash
cd terraform/

# Format and validate configuration
terraform fmt -check
terraform validate

# Review deployment changes
terraform plan -var="environment=prod"

# Apply configuration changes
terraform apply -var="environment=prod"
3. Incident Response & Troubleshooting (טיפול בתקלות ייצור)
Incident 1: Tenant Token Quota Exceeded (TenantBudgetExceededError)
Symptom: AI responses stop for a specific tenant; logs show Tenant <tenant_id> exceeded monthly token quota.

Action:

Inspect the tenant's current token usage in Redis:

Bash
redis-cli GET tenant:<tenant_id>:monthly_tokens
If the customer upgraded their tier, adjust or reset the counter:

Bash
# Reset quota for current billing cycle
redis-cli SET tenant:<tenant_id>:monthly_tokens 0
Incident 2: Upstream Gemini API Outage / Rate Limiting
Symptom: Warnings in logs: Primary model gemini-flash-latest failed... Failing over to gemini-flash-lite-latest.

Diagnosis: The GeminiTieredRouter automatically falls back to Lite. If both fail:

Check the Google AI Studio status page.

Check current API key validity and quota in Google Cloud Console.

Verify outgoing DNS and network connectivity inside the container:

Bash
curl -I [https://generativelanguage.googleapis.com](https://generativelanguage.googleapis.com)
Incident 3: Cloudflare Tunnel Degradation (Zero Inbound Traffic)
Symptom: Incoming WhatsApp webhooks return 502/504 errors in Meta Developer Console.

Diagnosis:

Check tunnel service status on the host:

Bash
systemctl status cloudflared
Inspect tunnel logs for connection drops:

Bash
journalctl -u cloudflared -n 100 --no-pager
Restart the tunnel daemon if disconnected:

Bash
sudo systemctl restart cloudflared
Incident 4: Database Disaster Recovery (שחזור מאסון)
Automated Backups: Nightly dumps are executed via scripts/backup_to_r2.sh and pushed off-site.

Restoration Procedure:

Bash
# 1. Download latest dump
aws s3 cp s3://leadflow-backups/db-latest.sql.gz /tmp/db-latest.sql.gz

# 2. Decompress and restore into PostgreSQL container
gunzip < /tmp/db-latest.sql.gz | docker exec -i leadflow_postgres psql -U postgres -d leads_db
