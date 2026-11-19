# WhatsApp and Messaging

## Workflow Name & ID: WF-05: Outbound WhatsApp Messaging
* **Code Path:** `(/src/routers/...)`
* **Trigger (גורם מפעיל):** HTTP Endpoint / Webhook / Celery Beat Schedule
* **Sequence Flow:** Input $\rightarrow$ Validation $\rightarrow$ DB/Redis State Change $\rightarrow$ Output
* **Failure Modes & Rollback (מצבי כשל והתאוששות):** 
* **External Dependencies & Bureaucracy:** 

---

## Workflow Name & ID: WF-06: 2-Way Chat & Inbound Handling
### 1. Code Path
* `/src/routers/webhooks/whatsapp.py`
* `/src/services/communication/whatsapp_pipeline.py`
* `/src/services/ai/engine.py`
* `/src/security/ai_guardrails.py`
* `/src/services/ai/prompt_builder.py`

### 2. Trigger
An incoming HTTP POST webhook from Meta (WhatsApp Cloud API) carrying customer messages or status updates, received through the Cloudflare Zero-Trust Tunnel and Envoy Proxy.

### 3. Sequence Flow
1. **Webhook Ingestion & Signature Verification:** FastAPI receives the POST request at `/webhooks/whatsapp`. `verify_whatsapp_signature()` validates the `X-Hub-Signature-256` HMAC-SHA256 signature against `WHATSAPP_APP_SECRET`.
2. **Replay & Timestamp Protection:** The system checks that the event timestamp is within a strict 5-minute window (`_has_fresh_meta_timestamps`).
3. **Queue Offloading:** The webhook validates the payload, pushes processing to a background task (`process_whatsapp_message`), and immediately returns `200 OK` to Meta to prevent timeout retries.
4. **Tenant Resolution:** The background worker resolves the recipient business/tenant in PostgreSQL (`User` and `PhoneNumber` models) using `phone_number_id` or display phone.
5. **Rate Limiting & Quota Reservation:** Atomically increments and checks the tenant's monthly token quota in PostgreSQL/Redis (`_reserve_ai_message_credit`).
6. **Guardrails & Prompt Building:** Untrusted customer inputs are sanitized and wrapped in strict XML boundary tags (`<system>`, `<latest_user_message>`) via `PromptBuilder`.
7. **Gemini Tiered Routing:** The request is sent to Google Gemini with strict output schemas (`WhatsAppAgentResponse`), a 7-second timeout, and bounded output tokens (`max_output_tokens=512`).
8. **Egress DLP Sanitization:** The AI response is scrubbed by Envoy Wasm (`data_hop_firewall.wasm`) with `X-Data-TTL: 1` before being dispatched back to Meta and saved in PostgreSQL.

## 4. Key Code Implementation
```python
async def process_whatsapp_message(payload: dict[str, Any]) -> None:
    """
    Asynchronous WhatsApp pipeline processing inbound messages,
    enforcing quota limits, invoking Gemini LLM, and dispatching responses.
    """
    async with AsyncSessionLocal() as db:
        # 1. Resolve tenant and validate quota
        owner, phone_record = await _resolve_tenant(db, metadata)
        max_limit = STARTER_MESSAGE_LIMIT if owner.plan_tier == PlanTier.STARTER else PRO_MESSAGE_LIMIT
        
        reserved = await _reserve_ai_message_credit(db, owner.id, max_limit)
        if reserved is None:
            logger.warning("Tenant monthly AI message quota exceeded.")
            return

        try:
            # 2. Invoke Gemini AI Engine with strict JSON schema
            ai_client = _create_gemini_client()
            response = ai_client.models.generate_content(
                model=settings.GEMINI_DEFAULT_MODEL,
                contents=final_prompt,
                config=_build_generation_config(system_instruction),
            )
            ai_data = json.loads(response.text)
            reply_text = ai_data.get("reply_text")

            # 3. Send message via WhatsApp Cloud API
            await whatsapp_adapter.send_message(to_phone=sender_phone, text=reply_text)
            await db.commit()
        except Exception as error:
            # 4. Trigger Quota Rollback on failure
            await _release_ai_message_credit(db, owner.id)
            logger.error("WhatsApp pipeline processing failed: %s", error)
            raise
```

## 5. Failure Modes & Rollback
* **LLM Timeout / Upstream Error:** If Gemini times out (>7s) or fails, the exception triggers `_release_ai_message_credit()` to atomically rollback the reserved quota in the database so the tenant is not charged for failed turns.
* **Invalid Signature:** Inbound webhooks with invalid or missing `X-Hub-Signature-256` are immediately rejected with `HTTP 403 Forbidden`.
* **Dead Letter Queue (DLQ):** Unhandled webhook processing failures are captured and persisted into the `WebhookDLQ` table for asynchronous replaying by Celery Beat.

## 6. External Dependencies & Bureaucracy
* **Meta WhatsApp Cloud API (v21.0):** Requires a verified Meta Business Account, WhatsApp Business Phone Number ID, and a Permanent Access Token.
* **Google GenAI SDK (`google-genai`):** Requires `GOOGLE_API_KEY` configured in AWS SSM / environment.
* **Redis 7 Alpine:** Used for idempotency locks and distributed rate limiting.

---

## Workflow Name & ID: WF-19: Messaging Dead Letter Queue (DLQ) Processing
* **Code Path:** `(/src/routers/...)`
* **Trigger (גורם מפעיל):** HTTP Endpoint / Webhook / Celery Beat Schedule
* **Sequence Flow:** Input $\rightarrow$ Validation $\rightarrow$ DB/Redis State Change $\rightarrow$ Output
* **Failure Modes & Rollback (מצבי כשל והתאוששות):** 
* **External Dependencies & Bureaucracy:** 
