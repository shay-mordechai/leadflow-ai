# src/routers/webhooks/whatsapp.py
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, Query, HTTPException, Depends, status
from fastapi.responses import PlainTextResponse

# Internal imports
from src.config import settings

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

async def verify_whatsapp_signature(request: Request):
    """
    Security Middleware: Validates the SHA256 signature from Meta.
    Ensures the request originated from Facebook/Meta servers.
    """
    # 1. Get the signature from the header
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning(f"❌ Missing X-Hub-Signature-256 from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature missing")

    # 2. Extract the actual hash (format is sha256=HASH_VALUE)
    if not signature.startswith("sha256="):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature format")
    
    received_hash = signature[7:] # Remove 'sha256=' prefix

    # 3. Calculate expected signature using App Secret
    # SECURITY: Meta signs the raw request body
    body = await request.body()
    expected_hash = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    # 4. Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(received_hash, expected_hash):
        logger.error(f"❌ SECURITY ALERT: Invalid WhatsApp signature from {request.client.host}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

# ------------------------------------------------------------------
# 1. Verification Endpoint (GET)
# ------------------------------------------------------------------
@router.get("/")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    """
    Meta (Facebook) Verification Handshake.
    """
    verify_token = settings.WHATSAPP_VERIFY_TOKEN

    if mode == "subscribe" and token == verify_token:
        logger.info("✅ WhatsApp Webhook Verified successfully.")
        return PlainTextResponse(content=challenge)
    
    logger.warning("❌ WhatsApp Verification Failed: Invalid Token.")
    raise HTTPException(status_code=403, detail="Verification failed")


# ------------------------------------------------------------------
# 2. Event Listener (POST)
# ------------------------------------------------------------------
@router.post("/")
async def whatsapp_event_listener(request: Request):
    """
    Receives incoming WhatsApp messages after verifying Meta signature.
    """
    # SECURITY CHECK: Verify the signature before processing ANY data
    await verify_whatsapp_signature(request)

    try:
        data = await request.json()
        
        # Check if entries exist to prevent IndexError
        if not data.get("entry"):
            return {"status": "no_entry"}

        entry = data["entry"][0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        # A. Handle Messages
        if "messages" in value:
            message = value["messages"][0]
            sender_id = message["from"]
            msg_type = message["type"]
            
            logger.info(f"💬 Authenticated WhatsApp Message from {sender_id}")
            
            if msg_type == "text":
                text_body = message["text"]["body"]
                # TODO: Trigger ConversationManager
            elif msg_type == "audio":
                audio_id = message["audio"]["id"]
                # TODO: Download media

        return {"status": "received"}

    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Processing Error: {e}")
        # Always return 200 to Meta to avoid retry loops, unless it's a critical auth fail
        return {"status": "error"}