# src/routers/webhooks/whatsapp.py
import logging
from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import PlainTextResponse

from src.config import settings

router = APIRouter(tags=["Webhooks - WhatsApp"])
logger = logging.getLogger("WhatsAppWebhook")

# ------------------------------------------------------------------
# 1. Verification Endpoint (GET)
# Required by Meta to verify ownership of the webhook URL.
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
        # Must return the challenge integer as plain text
        return PlainTextResponse(content=challenge)
    
    logger.warning("❌ WhatsApp Verification Failed: Invalid Token.")
    raise HTTPException(status_code=403, detail="Verification failed")


# ------------------------------------------------------------------
# 2. Event Listener (POST)
# Receives actual messages and status updates.
# ------------------------------------------------------------------
@router.post("/")
async def whatsapp_event_listener(request: Request):
    """
    Receives incoming WhatsApp messages/statuses.
    """
    try:
        data = await request.json()
        
        # Check if this is a valid object from WhatsApp
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        # A. Handle Messages
        if "messages" in value:
            message = value["messages"][0]
            sender_id = message["from"]
            msg_type = message["type"]
            
            logger.info(f"💬 WhatsApp Message from {sender_id} [Type: {msg_type}]")
            
            if msg_type == "text":
                text_body = message["text"]["body"]
                logger.info(f"   Content: {text_body}")
                # TODO: Trigger ConversationManager logic here
                # await conversation_manager.handle_message(sender_id, text_body)

            elif msg_type == "audio":
                audio_id = message["audio"]["id"]
                logger.info(f"   Audio ID: {audio_id}")
                # TODO: Download media using WhatsAppAdapter
        
        # B. Handle Status Updates (Sent, Delivered, Read)
        elif "statuses" in value:
            status = value["statuses"][0]
            # logger.debug(f"ℹ️ Message Status Update: {status['status']}")
            pass

        # Always return 200 OK, otherwise Meta will retry sending the webhook
        return {"status": "received"}

    except Exception as e:
        logger.error(f"🔥 WhatsApp Webhook Error: {e}")
        return {"status": "error"}