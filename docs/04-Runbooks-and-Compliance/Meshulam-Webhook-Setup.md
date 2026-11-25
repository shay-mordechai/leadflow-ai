
# Meshulam / Grow Payment & Tax Invoice Webhook Setup

## Architecture & Guarantees

1. **Webhook Callback Endpoint:** `POST /api/v1/billing/webhooks/meshulam` (routed through Envoy `127.0.0.1:10000`).
2. **Database-Backed Idempotency:** Every processed payment stores `transaction_id` with a PostgreSQL `UNIQUE` constraint so duplicate gateway retries never double-credit subscription quotas or trigger duplicate invoices.
3. **Israeli Tax Compliance:** Digital tax invoices (`חשבונית מס קבלה`) are generated directly via Meshulam/Grow or Morning API integrations rather than local PDF rendering.
4. **Subscription Activation:** On verified payment webhook, updates `users.plan_tier` (`PRO`), resets `monthly_ai_messages = 0`, and re-enables `bot_active = true` if paused due to trial expiration.
