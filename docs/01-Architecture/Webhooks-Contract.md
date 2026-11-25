
# Webhooks & External Integration Contract

All inbound webhooks enter via **Cloudflare Tunnel → Envoy (`127.0.0.1:10000`) → FastAPI (`8000`)**.

| Integration | Method & Path | Authentication / Signature | Replay & Idempotency Controls | Response SLA |
| --- | --- | --- | --- | --- |
| **Meta WhatsApp Challenge** | `GET /webhooks/whatsapp` | Query `hub.verify_token == WHATSAPP_VERIFY_TOKEN` | Stateless challenge echo (`hub.challenge`) | `< 100ms` (`200 text/plain`) |
| **Meta WhatsApp Events** | `POST /webhooks/whatsapp` | `X-Hub-Signature-256` HMAC-SHA256 with `WHATSAPP_APP_SECRET` | Stale event timestamp check (`401`), Redis burst debounce (`px=3500`), `Message.external_id` (`wamid`) dedup | Immediate `200 OK`; async `BackgroundTasks` (`BoundedSemaphore(200)`) |
| **Meta Graph API Outbound** | `POST graph.facebook.com/v21.0/{phone_id}/messages` | `Authorization: Bearer <META_ACCESS_TOKEN>` | Uses `lead_welcome_he` Utility Template outside 24h window; free-form text inside 24h window | Outbound (`7s` HTTP timeout) |
| **Meta Lead Ads (FB/IG)** | `POST /webhooks/facebook` | `X-Hub-Signature-256` + Page/Form verification | E.164 phone normalization + lead dedup + background template outreach | Immediate `200 OK` |
| **Marketing / Landing Pages** | `POST /webhooks/marketing`, `POST /api/v1/leads` | Tenant API key or Bearer JWT | Redis `SET NX` idempotency key + background template welcome | `< 250ms` (`200/201`) |
| **Meta Compliance Crawlers** | `GET /privacy`, `GET /terms` | Public HTTPS (`facebookexternalhit/1.1` verified) | Served by Next.js (`0.0.0.0:3000`); `/privacy` fulfills Meta User Data Deletion URL | `< 200ms` (`200 OK`) |
| **Hetzner CD Deploy Hook** | `POST` (`deploy.sh` listener) | `X-Hub-Signature-256` HMAC-SHA256 (`DEPLOY_WEBHOOK_SECRET`) | `300s` timestamp replay rejection + serialized deployment lock | Async rollout + `alembic upgrade head` |
| **Watchdog Incident Alerts** | Outbound `ALERT_WEBHOOK_URL` | SSRF-validated HTTPS URL + PII redaction | Redis `SET NX` 30-minute cooldown per alert signature | Best-effort async POST |
|  |  |  |  |  |
