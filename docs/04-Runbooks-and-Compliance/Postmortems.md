
# Production Post-Mortems & Lessons Learned

## PM-001: Podman Pod `HOSTNAME` Override Causing `503` on Next.js Frontend

* **Date:** 2026-11-25
* **Symptom:** `https://my-leads.app/`, `/privacy`, and `/terms` returned `HTTP 503 Service Unavailable` to users and Meta's `facebookexternalhit/1.1` crawler despite `leadflow-frontend` being `Up`.
* **Root Cause:** Podman pods inject `HOSTNAME=leadflow-prod` at runtime, overriding Dockerfile `ENV HOSTNAME="0.0.0.0"`. Next.js standalone `server.js` bound exclusively to the pod's `eth0` IP (`leadflow-prod:3000`) and refused Envoy connections on `127.0.0.1:3000`.
* **Resolution:** Updated `frontend/Dockerfile` `CMD` and `leadflow-frontend.container` `Exec=` to `sh -c "HOSTNAME=0.0.0.0 exec node server.js"`. Verified `HTTP 200` across all frontend routes.

## PM-002: SQLAlchemy `AsyncSession` Implicit Transaction Conflict in `WhatsAppPipeline`

* **Date:** 2026-11-25
* **Symptom:** Inbound WhatsApp message passed signature check, tenant lookup, and Gemini inference (`AI Turn Trace Recorded`), then failed before sending the reply with `sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session`.
* **Root Cause:** `ConversationMemoryService.get_lead_memory(db, ...)` executed a `SELECT` on the `AsyncSession`, implicitly starting a read transaction. Subsequent `async with db.begin():` at line 438 raised `InvalidRequestError`.
* **Resolution:** Explicitly closed any open read transaction (`if db.in_transaction(): await db.commit()`) after `get_lead_memory()` and added `if db.in_transaction(): await db.rollback()` inside `_release_ai_message_credit()`, guarded by unit tests in `tests/test_whatsapp_pipeline.py`.

## PM-003: Redis Burst Debounce Float Expiry Type Warning

* **Date:** 2026-11-25
* **Symptom:** Logs emitted `Debounce Redis check failed (proceeding): ex must be datetime.timedelta or int`.
* **Root Cause:** `r_client.set(debounce_key, "1", ex=3.5, nx=True)` passed a float `3.5` to Redis `EX` (which requires integer seconds).
* **Resolution:** Replaced `ex=3.5` with integer milliseconds `px=3500`.
