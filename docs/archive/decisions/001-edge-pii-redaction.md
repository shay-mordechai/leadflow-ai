# ADR 001: Edge PII Redaction via Envoy Wasm & Cloudflare Tunnels

## Status
Accepted

## Context
MyLeads AI processes sensitive customer conversations via WhatsApp webhooks and forwards context to external LLMs (Gemini/Anthropic). Exposing raw origin ports or sending unmasked PII violates GDPR and increases attack surface.

## Decision
1. Expose ingress exclusively through **Cloudflare Tunnels** (zero open inbound ports on host).
2. Inspect and mask sensitive patterns (Israeli IDs, credit cards, phone numbers) at the proxy layer using a **Rust/Wasm filter in Envoy** prior to FastAPI/LLM processing.

## Consequences
- **Positive:** Near-zero latency overhead, language-agnostic PII protection, complete DDoS/WAF shielding.
- **Negative:** Requires maintaining a separate Rust Wasm build step in CI/CD.