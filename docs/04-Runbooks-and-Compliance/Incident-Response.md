
# Production Incident Response Playbook

## 1. Fast Triage Commands (`devops-box` -> Hetzner)

```bash
# Check pod & container health
ssh hetzner-tunnel 'podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

# Verify external ingress & DB migration sync
curl -sS [https://my-leads.app/health/db-sync-status](https://my-leads.app/health/db-sync-status)

# Tail backend webhook & AI errors
ssh hetzner-tunnel 'podman logs --since 15m leadflow-backend | grep -i -E "error|warn|whatsapp|aitracing"'

# Tail Envoy / Wasm DLP logs
ssh hetzner-tunnel 'podman logs --tail 30 leadflow-data-gate'

```

## 2. Common Incident Playbooks

### A. `503 Service Unavailable` on Frontend Routes (`/`, `/privacy`, `/terms`)

* **Cause:** Next.js bound to pod hostname (`leadflow-prod`) instead of `0.0.0.0`, or `leadflow-frontend` stopped.
* **Fix:** Verify `Exec=sh -c "HOSTNAME=0.0.0.0 exec node server.js"` is present in `/home/deployer/.config/containers/systemd/leadflow/leadflow-frontend.container` and restart:
```bash
ssh hetzner-tunnel 'systemctl --user daemon-reload && systemctl --user restart leadflow-frontend.service'

```



### B. Inbound WhatsApp Ignored (`Received message for unassigned number`)

* **Cause:** `phone_numbers.provider_id` or `number` is missing/inactive for the business phone.
* **Fix:** Verify row in `phone_numbers` (`is_active = true`, `provider_id = '<meta_phone_number_id>'`, `owner_id = '<tenant_uuid>'`).

### C. Gemini Latency Spike / Timeout (`> 7s` SLA)

* **Cause:** Standard conversational turns routed to heavy model (`gemini-flash-latest` ~5.9s) instead of fast-path model (`gemini-flash-lite-latest` ~1s).
* **Fix:** Confirm `llm_router.py` routes `complexity="std"` to `gemini-flash-lite-latest` and verify `WHATSAPP_LLM_TIMEOUT_SECONDS=7`.

### D. Emergency Unit Restart (Zero DB Downtime)

```bash
ssh hetzner-tunnel 'systemctl --user restart leadflow-backend.service leadflow-worker.service leadflow-beat.service'

```

