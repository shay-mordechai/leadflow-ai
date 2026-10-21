# MyLeads AI (leadflow-ai) - Architecture & Agent Guidelines

## System Overview
Multi-tenant SaaS platform for automated lead management and WhatsApp AI agents.
- **Backend:** Python 3.12, FastAPI, SQLAlchemy (Async), PostgreSQL.
- **Edge & Security:** Cloudflare Tunnels, Envoy Proxy with Rust/Wasm PII redaction filters.
- **AI Providers:** Google Gemini Flash (primary high-speed), Anthropic Claude (complex reasoning fallback).
- **Cloud & IaC:** AWS (VPC, ECS, RDS, S3, Secrets Manager) managed via Terraform.

## Strict Coding & Security Rules
1. **Multi-Tenancy Isolation:** Every database query MUST filter by `tenant_id`. Never expose cross-tenant records.
2. **Zero Hardcoded Secrets:** Never read, print, or hardcode `.env` files, API keys, or AWS credentials. Use AWS Secrets Manager / environment variables via `pydantic-settings`.
3. **PII Redaction:** All user prompts and WhatsApp payloads must pass through the PII sanitizer before reaching external LLM APIs or application logs.
4. **Testing Requirement:** Every new endpoint or agent workflow requires an async `pytest` unit test.

## Restricted Paths (DO NOT MODIFY OR READ)
- `.env*`
- `*.pem`, `*.key`
- `terraform/*.tfstate*`